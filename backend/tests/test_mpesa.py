"""Contract test for the real (non-mock) Daraja client: request shapes, auth, token caching."""
import base64
import json

import httpx
import pytest

from app import mpesa
from app.core.config import settings

RealAsyncClient = httpx.AsyncClient  # captured before any test patches it


@pytest.fixture
def daraja(monkeypatch):
    """Route the client to a fake Daraja and record every request."""
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/oauth/v1/generate":
            return httpx.Response(200, json={"access_token": "tok123", "expires_in": "3599"})
        if request.url.path == "/mpesa/stkpush/v1/processrequest":
            return httpx.Response(200, json={"MerchantRequestID": "m1", "CheckoutRequestID": "ws_CO_1",
                                             "ResponseCode": "0", "ResponseDescription": "Success"})
        if request.url.path == "/mpesa/stkpushquery/v1/query":
            return httpx.Response(200, json={"ResultCode": "1032", "ResultDesc": "Request cancelled by user"})
        return httpx.Response(404)

    monkeypatch.setattr(mpesa.httpx, "AsyncClient",
                        lambda **kw: RealAsyncClient(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(mpesa, "_token", (None, 0.0))
    for key, value in {"DARAJA_ENV": "sandbox", "DARAJA_CONSUMER_KEY": "ck", "DARAJA_CONSUMER_SECRET": "cs",
                       "DARAJA_SHORTCODE": "174379", "DARAJA_PASSKEY": "pk",
                       "DARAJA_CALLBACK_URL": "https://shop.example.com/", "DARAJA_CALLBACK_SECRET": "s3cret"}.items():
        monkeypatch.setattr(settings, key, value)
    return calls


async def test_stk_push_sends_daraja_contract(daraja):
    result = await mpesa.stk_push("254712345678", 150, "INV-42", "Invonics")
    assert result["CheckoutRequestID"] == "ws_CO_1"

    auth, push = daraja
    assert auth.url.host == "sandbox.safaricom.co.ke"
    assert auth.headers["authorization"] == "Basic " + base64.b64encode(b"ck:cs").decode()
    assert push.headers["authorization"] == "Bearer tok123"

    body = json.loads(push.content)
    assert body["BusinessShortCode"] == body["PartyB"] == "174379"
    assert body["TransactionType"] == "CustomerPayBillOnline"
    assert body["Amount"] == 150 and body["PartyA"] == body["PhoneNumber"] == "254712345678"
    assert body["AccountReference"] == "INV-42"
    assert body["CallBackURL"] == "https://shop.example.com/api/v1/payments/callback/s3cret"
    assert len(body["Timestamp"]) == 14
    assert base64.b64decode(body["Password"]).decode() == "174379" + "pk" + body["Timestamp"]


async def test_access_token_is_cached_between_calls(daraja):
    await mpesa.stk_push("254712345678", 1, "INV-1", "x")
    await mpesa.stk_push("254712345678", 1, "INV-2", "x")
    assert [c.url.path for c in daraja].count("/oauth/v1/generate") == 1


async def test_stk_query_returns_final_result(daraja):
    result = await mpesa.stk_query("ws_CO_1")
    assert result["ResultCode"] == "1032"


async def test_bad_credentials_raise_clear_error(daraja, monkeypatch):
    monkeypatch.setattr(mpesa.httpx, "AsyncClient", lambda **kw: RealAsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(400, json={"errorMessage": "Invalid credentials"})), **kw))
    with pytest.raises(mpesa.MpesaError, match="DARAJA_CONSUMER_KEY"):
        await mpesa.stk_push("254712345678", 1, "INV-1", "x")
