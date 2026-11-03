"""Guest checkout: buy without an account, then keep the purchase by setting a password or recovering with the M-Pesa code."""
import uuid

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import User
from tests.conftest import new_user_payload
from tests.test_checkout import CALLBACK, purchase_count, stk_callback


def guest(**kw):
    p = new_user_payload()
    p.pop("password")
    p.update(kw)
    return p


async def guest_order(client, resource_ids, **kw):
    return await client.post("/api/v1/orders/guest", json={"resource_ids": resource_ids, **guest(**kw)})


async def test_guest_can_buy_and_is_logged_in(client, make_resource):
    r = await guest_order(client, [await make_resource(price=150)])
    assert r.status_code == 201, r.text
    assert r.json()["total_amount"] == 150 and r.json()["state"] == "processing"
    assert (await client.get("/api/v1/auth/me")).json()["is_guest"] is True


async def test_guest_payment_grants_purchase_and_library(client, make_resource):
    rid = await make_resource(price=150)
    order = (await guest_order(client, [rid])).json()
    await client.post(CALLBACK, json=stk_callback(order["checkout_request_id"], amount=150))
    assert (await client.get(f"/api/v1/orders/{order['id']}")).json()["state"] == "confirmed"
    assert await purchase_count(order["id"]) == 1
    assert [i["resource"]["id"] for i in (await client.get("/api/v1/library")).json()] == [rid]


async def test_guest_price_comes_from_server(client, make_resource):
    r = await client.post("/api/v1/orders/guest", json={"resource_ids": [await make_resource(price=150)], "amount": 1, **guest()})
    assert r.json()["total_amount"] == 150


async def test_existing_account_email_is_refused_not_logged_in(client, make_resource):
    owner = new_user_payload()
    assert (await client.post("/api/v1/auth/register", json=owner)).status_code == 201
    client.cookies.clear()
    r = await guest_order(client, [await make_resource()], email=owner["email"])
    assert r.status_code == 409
    assert (await client.get("/api/v1/auth/me")).status_code == 401  # no session was issued


async def test_existing_phone_is_refused(client, make_resource):
    owner = new_user_payload()
    await client.post("/api/v1/auth/register", json=owner)
    client.cookies.clear()
    assert (await guest_order(client, [await make_resource()], phone=owner["phone"])).status_code == 409


async def test_unpublished_resource_creates_no_guest_account(client, make_resource):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    assert (await guest_order(client, [await make_resource(published=False)], email=email)).status_code == 404
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(User.id).where(User.email == email)) is None


async def test_guest_cannot_log_in_with_any_password(client, make_resource):
    g = guest()
    await client.post("/api/v1/orders/guest", json={"resource_ids": [await make_resource()], **g})
    client.cookies.clear()
    for pw in ("", "password", "None"):
        r = await client.post("/api/v1/auth/login", json={"email": g["email"], "password": pw})
        assert r.status_code == 401


async def test_guest_sets_password_and_can_log_in_later(client, make_resource):
    g = guest()
    await client.post("/api/v1/orders/guest", json={"resource_ids": [await make_resource()], **g})
    r = await client.post("/api/v1/auth/set-password", json={"password": "a long new password"})
    assert r.status_code == 200 and r.json()["is_guest"] is False
    client.cookies.clear()
    assert (await client.post("/api/v1/auth/login", json={"email": g["email"], "password": "a long new password"})).status_code == 200


async def test_set_password_refused_for_normal_accounts(client, logged_in):
    assert (await client.post("/api/v1/auth/set-password", json={"password": "another long one"})).status_code == 400


async def test_claim_with_mpesa_receipt_recovers_guest_account(client, make_resource):
    g, receipt = guest(), uuid.uuid4().hex[:10].upper()
    order = (await client.post("/api/v1/orders/guest", json={"resource_ids": [await make_resource(price=50)], **g})).json()
    await client.post(CALLBACK, json=stk_callback(order["checkout_request_id"], amount=50, receipt=receipt))
    client.cookies.clear()  # session lost
    r = await client.post("/api/v1/auth/claim", json={"email": g["email"], "mpesa_receipt": receipt.lower(), "password": "fresh password 1"})
    assert r.status_code == 200 and r.json()["is_guest"] is False
    assert len((await client.get("/api/v1/library")).json()) == 1


async def test_claim_is_throttled_after_five_misses(client, make_resource):
    g, real = guest(), uuid.uuid4().hex[:10].upper()
    order = (await client.post("/api/v1/orders/guest", json={"resource_ids": [await make_resource(price=50)], **g})).json()
    await client.post(CALLBACK, json=stk_callback(order["checkout_request_id"], amount=50, receipt=real))
    client.cookies.clear()
    for _ in range(5):
        r = await client.post("/api/v1/auth/claim", json={"email": g["email"], "mpesa_receipt": "WRONG12345", "password": "fresh password 1"})
        assert r.status_code == 400
    r = await client.post("/api/v1/auth/claim", json={"email": g["email"], "mpesa_receipt": real, "password": "fresh password 1"})
    assert r.status_code == 429  # locked out after five misses, even with the right code


async def test_claim_does_not_work_on_normal_accounts(client, logged_in):
    r = await client.post("/api/v1/auth/claim", json={"email": logged_in["email"], "mpesa_receipt": "ABCDEFGH12", "password": "fresh password 1"})
    assert r.status_code == 400
