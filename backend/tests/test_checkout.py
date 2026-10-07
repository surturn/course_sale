import uuid

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models import OrderPaid, Purchase
from tests.conftest import new_user_payload

CALLBACK = "/api/v1/payments/callback/test-secret"


def stk_callback(checkout_id, result_code=0, amount=150, receipt=None):
    """Shape of Daraja's STK push result callback."""
    body = {
        "MerchantRequestID": "29115-34620561-1",
        "CheckoutRequestID": checkout_id,
        "ResultCode": result_code,
        "ResultDesc": "The service request is processed successfully." if result_code == 0 else "Request cancelled by user",
    }
    if result_code == 0:
        body["CallbackMetadata"] = {"Item": [
            {"Name": "Amount", "Value": amount},
            {"Name": "MpesaReceiptNumber", "Value": receipt or uuid.uuid4().hex[:10].upper()},
            {"Name": "TransactionDate", "Value": 20261007120000},
            {"Name": "PhoneNumber", "Value": 254708374149},
        ]}
    return {"Body": {"stkCallback": body}}


async def checkout(client, resource_ids):
    r = await client.post("/api/v1/orders", json={"resource_ids": resource_ids})
    assert r.status_code == 201, r.text
    return r.json()


async def ledger_states(order_id):
    async with AsyncSessionLocal() as db:
        rows = await db.scalars(select(OrderPaid.state).where(OrderPaid.order_id == order_id).order_by(OrderPaid.id))
        return [s.value for s in rows]


async def purchase_count(order_id):
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(Purchase).where(Purchase.order_id == order_id))


async def test_checkout_sends_stk_push_and_marks_processing(client, logged_in, make_resource):
    order = await checkout(client, [await make_resource(price=150)])
    assert order["state"] == "processing"
    assert order["total_amount"] == 150
    assert order["account_reference"] == f"INV-{order['id']}"
    assert await ledger_states(order["id"]) == ["pending", "processing"]


async def test_checkout_requires_login(client, make_resource):
    r = await client.post("/api/v1/orders", json={"resource_ids": [await make_resource()]})
    assert r.status_code == 401


async def test_successful_callback_confirms_order_and_grants_purchase(client, logged_in, make_resource):
    order = await checkout(client, [await make_resource(price=150), await make_resource(price=50)])
    r = await client.post(CALLBACK, json=stk_callback(order["checkout_request_id"], amount=200))
    assert r.status_code == 200
    assert r.json()["ResultCode"] == 0

    status = (await client.get(f"/api/v1/orders/{order['id']}")).json()
    assert status["state"] == "confirmed"
    assert await purchase_count(order["id"]) == 2


async def test_duplicate_callback_is_a_no_op(client, logged_in, make_resource):
    order = await checkout(client, [await make_resource(price=150)])
    payload = stk_callback(order["checkout_request_id"], amount=150, receipt=uuid.uuid4().hex[:10].upper())
    await client.post(CALLBACK, json=payload)
    r = await client.post(CALLBACK, json=payload)
    assert r.status_code == 200
    assert await ledger_states(order["id"]) == ["pending", "processing", "confirmed"]


async def test_cancelled_payment_fails_order_without_purchase(client, logged_in, make_resource):
    order = await checkout(client, [await make_resource(price=150)])
    await client.post(CALLBACK, json=stk_callback(order["checkout_request_id"], result_code=1032))
    status = (await client.get(f"/api/v1/orders/{order['id']}")).json()
    assert status["state"] == "failed"
    assert status["failure_reason"] == "user_cancelled"
    assert await purchase_count(order["id"]) == 0


async def test_amount_mismatch_fails_order(client, logged_in, make_resource):
    order = await checkout(client, [await make_resource(price=150)])
    await client.post(CALLBACK, json=stk_callback(order["checkout_request_id"], amount=1))
    status = (await client.get(f"/api/v1/orders/{order['id']}")).json()
    assert status["state"] == "failed"
    assert status["failure_reason"] == "amount_mismatch"
    assert await purchase_count(order["id"]) == 0


async def test_callback_with_wrong_secret_is_404(client, logged_in, make_resource):
    order = await checkout(client, [await make_resource()])
    r = await client.post("/api/v1/payments/callback/guess", json=stk_callback(order["checkout_request_id"]))
    assert r.status_code == 404
    assert await ledger_states(order["id"]) == ["pending", "processing"]


async def test_callback_for_unknown_checkout_is_acknowledged_and_ignored(client):
    r = await client.post(CALLBACK, json=stk_callback("ws_CO_does_not_exist"))
    assert r.status_code == 200


async def test_cannot_buy_resource_already_owned(client, logged_in, make_resource):
    resource_id = await make_resource(price=150)
    order = await checkout(client, [resource_id])
    await client.post(CALLBACK, json=stk_callback(order["checkout_request_id"], amount=150))
    r = await client.post("/api/v1/orders", json={"resource_ids": [resource_id]})
    assert r.status_code == 409


async def test_unpublished_resource_cannot_be_bought(client, logged_in, make_resource):
    r = await client.post("/api/v1/orders", json={"resource_ids": [await make_resource(published=False)]})
    assert r.status_code == 404


async def test_order_status_hidden_from_other_users(client, logged_in, make_resource):
    order = await checkout(client, [await make_resource()])
    other = new_user_payload()
    await client.post("/api/v1/auth/register", json=other)
    await client.post("/api/v1/auth/login", json={"email": other["email"], "password": other["password"]})
    assert (await client.get(f"/api/v1/orders/{order['id']}")).status_code == 404


async def test_concurrent_duplicate_callbacks_settle_once(client, logged_in, make_resource):
    import asyncio
    order = await checkout(client, [await make_resource(price=150)])
    payload = stk_callback(order["checkout_request_id"], amount=150)
    await asyncio.gather(*(client.post(CALLBACK, json=payload) for _ in range(5)))
    assert await ledger_states(order["id"]) == ["pending", "processing", "confirmed"]
    assert await purchase_count(order["id"]) == 1
