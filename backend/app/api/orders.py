"""Checkout: create order -> STK push -> Daraja callback (or status query) settles it.

Every state change is a new orders_paid row (append-only). Settlement locks the order row
(SELECT ... FOR UPDATE) and the partial unique index allows one terminal row per order, so
concurrent or repeated callbacks settle an order exactly once."""
import hmac
import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import exists, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import mpesa
from app.api.auth import SIGNUP_LIMIT, SIGNUP_WINDOW, normalise_phone
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.models import LedgerState, Order, OrderPaid, Purchase, Resource, User
from app.security import check_throttle, current_user, record_failure, start_session

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["orders"])

TERMINAL = (LedgerState.confirmed, LedgerState.failed)
FAILURE_REASONS = {1: "insufficient_funds", 1032: "user_cancelled", 1037: "timeout", 2001: "wrong_pin"}
QUERY_AFTER = timedelta(seconds=45)  # give the callback a chance before polling Daraja
OPEN_PROMPT_WINDOW = timedelta(minutes=2)  # STK prompts expire after ~1 minute
_last_query: dict[int, float] = {}  # ponytail: per-process throttle; fine for one API container


class CheckoutIn(BaseModel):
    resource_ids: list[int] = Field(min_length=1, max_length=20)
    phone: str | None = None  # defaults to the account phone

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        return normalise_phone(v) if v else v


def account_reference(order_id: int) -> str:
    return f"INV-{order_id}"


async def latest_row(db: AsyncSession, order_id: int) -> OrderPaid | None:
    return await db.scalar(select(OrderPaid).where(OrderPaid.order_id == order_id).order_by(OrderPaid.id.desc()).limit(1))


def order_out(order: Order, row: OrderPaid) -> dict:
    return {
        "id": order.id,
        "state": row.state.value,
        "failure_reason": row.failure_reason,
        "total_amount": order.total_amount,
        "items": order.items,
        "account_reference": row.account_reference,
        "checkout_request_id": row.checkout_request_id,
        "created_at": order.created_at,
    }


def ledger_row(order: Order, prev: OrderPaid, state: LedgerState, **fields) -> OrderPaid:
    base = {"phone": prev.phone, "amount": order.total_amount, "account_reference": prev.account_reference,
            "checkout_request_id": prev.checkout_request_id}
    return OrderPaid(order_id=order.id, state=state, **{**base, **fields})


async def _published(db: AsyncSession, resource_ids: list[int]) -> list[Resource]:
    ids = list(dict.fromkeys(resource_ids))
    resources = (await db.scalars(select(Resource).where(Resource.id.in_(ids), Resource.published))).all()
    if len(resources) != len(ids):
        raise HTTPException(404, "One or more resources are not available")
    return list(resources)


async def _start_order(db: AsyncSession, user: User, resources: list[Resource], phone: str) -> dict:
    """Create the order from server-side prices, record it pending, fire the STK push."""
    ids = [r.id for r in resources]
    owned = await db.scalar(select(Purchase.resource_id).where(Purchase.user_id == user.id, Purchase.resource_id.in_(ids)).limit(1))
    if owned:
        raise HTTPException(409, "You already own one of these resources")
    # A double-tap on Pay must not fire two STK prompts for the same item (and risk two charges).
    since = datetime.now(timezone.utc) - OPEN_PROMPT_WINDOW
    for recent in (await db.scalars(select(Order).where(Order.user_id == user.id, Order.created_at > since))).all():
        if {i["resource_id"] for i in recent.items} & set(ids) and (await latest_row(db, recent.id)).state not in TERMINAL:
            raise HTTPException(409, "A payment for this is already in progress. Check your phone for the M-Pesa prompt.")

    order = Order(user_id=user.id, total_amount=sum(r.price for r in resources),
                  items=[{"resource_id": r.id, "title": r.title, "price": r.price} for r in resources])
    db.add(order)
    await db.flush()
    pending = OrderPaid(order_id=order.id, state=LedgerState.pending, phone=phone,
                        amount=order.total_amount, account_reference=account_reference(order.id))
    db.add(pending)
    await db.commit()

    try:
        push = await mpesa.stk_push(phone, order.total_amount, pending.account_reference, "Invonics")
        row = ledger_row(order, pending, LedgerState.processing, checkout_request_id=push["CheckoutRequestID"], payload=push)
    except Exception as e:  # MpesaError or network error: the order must not stay pending forever
        log.exception("STK push failed for order %s", order.id)
        row = ledger_row(order, pending, LedgerState.failed, failure_reason="stk_push_error", payload={"error": str(e)})
    db.add(row)
    await db.commit()
    if row.state == LedgerState.failed:
        raise HTTPException(502, "Could not reach M-Pesa. Please try again.")
    return order_out(order, row)


@router.post("/orders", status_code=201)
async def create_order(body: CheckoutIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    resources = await _published(db, body.resource_ids)
    return await _start_order(db, user, resources, body.phone or user.phone)


class GuestCheckoutIn(BaseModel):
    resource_ids: list[int] = Field(min_length=1, max_length=20)
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str

    _phone = field_validator("phone")(normalise_phone)


@router.post("/orders/guest", status_code=201)
async def create_guest_order(body: GuestCheckoutIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Buy without an account. We make a passwordless guest account from the details, log the browser in,
    and start the payment, so the reader, watermark and device rules work exactly as for any buyer.
    An email or phone that already has an account is refused: logging someone into an existing account
    from typed details alone would be an account takeover."""
    ip_key = f"signup:{request.client.host if request.client else 'unknown'}"
    check_throttle(ip_key, SIGNUP_LIMIT, SIGNUP_WINDOW)
    record_failure(ip_key)
    resources = await _published(db, body.resource_ids)
    email = body.email.lower()
    if await db.scalar(select(User.id).where(or_(User.email == email, User.phone == body.phone))):
        raise HTTPException(409, "That email or phone already has an account here. Log in to continue.")
    user = User(email=email, phone=body.phone, full_name=body.full_name, password_hash=None, is_guest=True)
    db.add(user)
    await db.commit()
    start_session(response, user.id)
    return await _start_order(db, user, resources, body.phone)


async def settle(db: AsyncSession, order_id: int, result_code: int, payload: dict,
                 amount: int | None = None, receipt: str | None = None, phone: str | None = None) -> None:
    """Write the single terminal ledger row for an order and grant purchases on success. Idempotent."""
    order = await db.get(Order, order_id, with_for_update=True)
    terminal = await db.scalar(select(OrderPaid.id).where(OrderPaid.order_id == order_id, OrderPaid.state.in_(TERMINAL)))
    if terminal:
        await db.rollback()
        return
    prev = await latest_row(db, order_id)
    extra = {"payload": payload, **({"phone": phone} if phone else {})}

    if result_code != 0:
        reason = FAILURE_REASONS.get(result_code, f"mpesa_{result_code}")
        db.add(ledger_row(order, prev, LedgerState.failed, failure_reason=reason, **extra))
    elif amount is not None and amount != order.total_amount:
        log.warning("Order %s amount mismatch: paid %s, expected %s", order_id, amount, order.total_amount)
        db.add(ledger_row(order, prev, LedgerState.failed, failure_reason="amount_mismatch", mpesa_receipt=receipt, **extra))
    else:
        db.add(ledger_row(order, prev, LedgerState.confirmed, mpesa_receipt=receipt, **extra))
        await db.execute(insert(Purchase).values([
            {"order_id": order.id, "user_id": order.user_id, "resource_id": i["resource_id"], "price_paid": i["price"]}
            for i in order.items
        ]).on_conflict_do_nothing())
    try:
        await db.commit()
    except IntegrityError:  # receipt already recorded against another order: never double-grant
        await db.rollback()
        log.error("Duplicate M-Pesa receipt %s for order %s", receipt, order_id)


@router.post("/payments/callback/{secret}")
async def mpesa_callback(secret: str, request: Request, db: AsyncSession = Depends(get_db)):
    if not settings.DARAJA_CALLBACK_SECRET or not hmac.compare_digest(secret, settings.DARAJA_CALLBACK_SECRET):
        raise HTTPException(404)
    try:
        payload = await request.json()
        cb = payload["Body"]["stkCallback"]
        int(cb.get("ResultCode", -1))
    except (ValueError, KeyError, TypeError, AttributeError):
        log.warning("Malformed Daraja callback ignored")
        return {"ResultCode": 0, "ResultDesc": "Accepted"}  # still ack: a retry will not fix a bad body
    cb = payload["Body"]["stkCallback"]
    checkout_id = cb.get("CheckoutRequestID")
    order_id = await db.scalar(select(OrderPaid.order_id).where(OrderPaid.checkout_request_id == checkout_id).limit(1))
    if order_id is None:
        log.warning("Callback for unknown CheckoutRequestID %s", checkout_id)
    else:
        meta = {i["Name"]: i.get("Value") for i in cb.get("CallbackMetadata", {}).get("Item", [])}
        await settle(db, order_id, int(cb.get("ResultCode", -1)), payload,
                     amount=int(meta["Amount"]) if "Amount" in meta else None,
                     receipt=meta.get("MpesaReceiptNumber"),
                     phone=str(meta["PhoneNumber"]) if meta.get("PhoneNumber") else None)
    return {"ResultCode": 0, "ResultDesc": "Accepted"}  # always ack, or Daraja keeps retrying


@router.get("/orders/{order_id}")
async def order_status(order_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    order = await db.get(Order, order_id)
    if not order or order.user_id != user.id:
        raise HTTPException(404, "Order not found")
    row = await latest_row(db, order_id)

    # Reconcile if the callback is late or never arrives (e.g. callback URL unreachable).
    stale = datetime.now(timezone.utc) - row.transitioned_at > QUERY_AFTER
    if row.state == LedgerState.processing and stale and time.monotonic() - _last_query.get(order_id, 0) > 15:
        _last_query[order_id] = time.monotonic()
        result = await mpesa.stk_query(row.checkout_request_id)
        if result is not None:
            await settle(db, order_id, int(result["ResultCode"]), {"stk_query": result})
            row = await latest_row(db, order_id)
    return order_out(order, row)


@router.get("/orders")
async def my_orders(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    orders = (await db.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.id.desc()).limit(50))).all()
    return [order_out(o, await latest_row(db, o.id)) for o in orders]


RECONCILE_EVERY = 60  # seconds between sweeps
RECONCILE_MAX_AGE = timedelta(hours=24)


async def reconcile_stuck_orders() -> int:
    """Ask Daraja about orders still 'processing' after QUERY_AFTER. Covers lost callbacks (callback URL down,
    DNS not ready yet) and guests who closed the tab, who would otherwise never poll the status endpoint.
    Settlement is idempotent, so running this alongside live callbacks is safe. Returns orders settled."""
    if mpesa.is_mock():
        return 0
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        # Best effort: skips the sweep if another worker is selecting right now. Settlement is idempotent either way.
        if not await db.scalar(text("SELECT pg_try_advisory_xact_lock(727001)")):
            return 0
        done = select(OrderPaid.id).where(OrderPaid.order_id == Order.id, OrderPaid.state.in_(TERMINAL))
        latest = (select(OrderPaid.order_id, OrderPaid.checkout_request_id, OrderPaid.transitioned_at)
                  .where(OrderPaid.state == LedgerState.processing, OrderPaid.transitioned_at < now - QUERY_AFTER,
                         OrderPaid.transitioned_at > now - RECONCILE_MAX_AGE).subquery())
        rows = (await db.execute(select(latest.c.order_id, latest.c.checkout_request_id).join(Order, Order.id == latest.c.order_id)
                                 .where(~exists(done)).limit(50))).all()
    settled = 0
    for order_id, checkout_id in rows:
        result = await mpesa.stk_query(checkout_id)
        if result is None:
            continue
        async with AsyncSessionLocal() as db:
            await settle(db, order_id, int(result["ResultCode"]), {"stk_query": result, "source": "reconciler"})
        settled += 1
    return settled


async def reconcile_loop() -> None:
    import asyncio
    while True:
        try:
            await reconcile_stuck_orders()
        except Exception:
            log.exception("Order reconcile sweep failed")
        await asyncio.sleep(RECONCILE_EVERY)
