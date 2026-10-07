"""Thin Daraja (M-Pesa) client: OAuth token, STK push, STK query.
DARAJA_ENV=mock skips the network so the whole flow runs offline; the callback is then
posted by a test or scripts/e2e_payment.py."""
import base64
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings

BASE_URLS = {"sandbox": "https://sandbox.safaricom.co.ke", "production": "https://api.safaricom.co.ke"}
EAT = timezone(timedelta(hours=3))  # Daraja timestamps are Nairobi time
_token: tuple[str | None, float] = (None, 0.0)


class MpesaError(Exception):
    pass


def is_mock() -> bool:
    return settings.DARAJA_ENV == "mock"


def callback_url() -> str:
    return f"{settings.DARAJA_CALLBACK_URL.rstrip('/')}/api/v1/payments/callback/{settings.DARAJA_CALLBACK_SECRET}"


def _password() -> tuple[str, str]:
    timestamp = datetime.now(EAT).strftime("%Y%m%d%H%M%S")
    raw = f"{settings.DARAJA_SHORTCODE}{settings.DARAJA_PASSKEY}{timestamp}"
    return base64.b64encode(raw.encode()).decode(), timestamp


async def _post(path: str, body: dict) -> dict:
    global _token
    base = BASE_URLS[settings.DARAJA_ENV]
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        token, expires = _token
        if not token or time.monotonic() > expires:
            r = await client.get("/oauth/v1/generate", params={"grant_type": "client_credentials"},
                                 auth=(settings.DARAJA_CONSUMER_KEY, settings.DARAJA_CONSUMER_SECRET))
            if r.status_code != 200:
                raise MpesaError(f"Daraja auth failed ({r.status_code}): check DARAJA_CONSUMER_KEY/SECRET")
            data = r.json()
            token = data["access_token"]
            _token = (token, time.monotonic() + int(data.get("expires_in", 3599)) - 60)
        r = await client.post(path, json=body, headers={"Authorization": f"Bearer {token}"})
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != 200:
        raise MpesaError(data.get("errorMessage") or f"Daraja HTTP {r.status_code}")
    return data


async def stk_push(phone: str, amount: int, account_reference: str, description: str) -> dict:
    if is_mock():
        return {"CheckoutRequestID": f"ws_CO_MOCK_{uuid.uuid4().hex}", "MerchantRequestID": "mock", "ResponseCode": "0"}
    password, timestamp = _password()
    data = await _post("/mpesa/stkpush/v1/processrequest", {
        "BusinessShortCode": settings.DARAJA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone,
        "PartyB": settings.DARAJA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": callback_url(),
        "AccountReference": account_reference[:12],  # Daraja truncates STK refs at 12 chars
        "TransactionDesc": description[:13],
    })
    if data.get("ResponseCode") != "0":
        raise MpesaError(data.get("ResponseDescription", "STK push rejected"))
    return data


async def stk_query(checkout_request_id: str) -> dict | None:
    """Return Daraja's final result ({"ResultCode", "ResultDesc"}) or None while still pending."""
    if is_mock():
        return None
    password, timestamp = _password()
    try:
        data = await _post("/mpesa/stkpushquery/v1/query", {
            "BusinessShortCode": settings.DARAJA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        })
    except MpesaError:
        return None  # "transaction is being processed" comes back as an error
    return data if "ResultCode" in data else None
