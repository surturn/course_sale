"""End-to-end payment demo against a running API.

    python -m scripts.e2e_payment                      # DARAJA_ENV=mock: simulates Safaricom's callback
    python -m scripts.e2e_payment --phone 0712345678   # DARAJA_ENV=sandbox: real STK prompt, approve it on the phone

Flow: admin uploads + publishes a demo PDF -> buyer registers -> checkout (STK push) -> callback/query
settles the order -> resource appears in the library -> watermarked file downloads with the buyer's email.
"""
import argparse
import asyncio
import io
import sys
import time
import uuid

import httpx
from pypdf import PdfReader
from sqlalchemy import update

from app.api.auth import normalise_phone
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models import User


def demo_pdf(pages: int = 3) -> bytes:
    """A tiny real PDF with text on every page (no extra dependencies)."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for n in range(1, pages + 1):
        text = f"BT /F1 24 Tf 72 760 Td (Invonics demo notes - page {n}) Tj ET".encode()
        objects.append(f"<< /Length {len(text)} >>\nstream\n{text.decode()}\nendstream")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                       f"/Resources << /Font << /F1 3 0 R >> >> /Contents {len(objects)} 0 R >>")
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {pages} >>"
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n{body}\nendobj\n".encode())
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    out.write("".join(f"{o:010d} 00000 n \n" for o in offsets).encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def step(msg: str):
    print(f"  - {msg}", flush=True)


def check(response: httpx.Response, expected: int = 200) -> dict:
    if response.status_code != expected:
        sys.exit(f"FAILED {response.request.method} {response.request.url.path}: {response.status_code} {response.text}")
    return response.json() if response.content else {}


async def promote(email: str):
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.email == email).values(is_admin=True))
        await db.commit()
    await engine.dispose()


def account(client: httpx.Client, phone: str) -> dict:
    user = {"email": f"demo-{uuid.uuid4().hex[:8]}@example.com", "phone": phone,
            "full_name": "Demo Buyer", "password": uuid.uuid4().hex}
    check(client.post("/api/v1/auth/register", json=user), 201)
    check(client.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]}))
    return user


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--phone", default="254708374149", help="Safaricom number to receive the STK prompt")
    parser.add_argument("--price", type=int, default=1, help="KES; keep at 1 for sandbox")
    parser.add_argument("--timeout", type=int, default=180, help="seconds to wait for the payment to settle")
    args = parser.parse_args()
    phone = normalise_phone(args.phone)
    print(f"DARAJA_ENV={settings.DARAJA_ENV}  API={args.base}")

    with httpx.Client(base_url=args.base, timeout=60) as admin, httpx.Client(base_url=args.base, timeout=60) as buyer:
        check(admin.get("/api/health"))
        step("admin account")
        boss = account(admin, f"2541{uuid.uuid4().int % 10**8:08d}")
        asyncio.run(promote(boss["email"]))

        step("upload + publish demo PDF")
        res = check(admin.post("/api/v1/admin/resources",
                               data={"title": f"Demo notes {time.strftime('%H:%M:%S')}", "type": "pdf", "price": str(args.price)},
                               files={"file": ("demo.pdf", demo_pdf(), "application/pdf")}), 201)
        check(admin.patch(f"/api/v1/admin/resources/{res['id']}", json={"published": True}))

        step(f"buyer registers with {phone}")
        user = account(buyer, phone if settings.DARAJA_ENV != "mock" else f"2547{uuid.uuid4().int % 10**8:08d}")

        step("checkout: STK push")
        order = check(buyer.post("/api/v1/orders", json={"resource_ids": [res["id"]], "phone": phone}), 201)
        print(f"    order {order['id']} ref {order['account_reference']} checkout {order['checkout_request_id']}")

        if settings.DARAJA_ENV == "mock":
            step("simulating Safaricom callback")
            check(buyer.post(f"/api/v1/payments/callback/{settings.DARAJA_CALLBACK_SECRET}", json={"Body": {"stkCallback": {
                "MerchantRequestID": "mock", "CheckoutRequestID": order["checkout_request_id"], "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {"Item": [
                    {"Name": "Amount", "Value": args.price},
                    {"Name": "MpesaReceiptNumber", "Value": f"MOCK{uuid.uuid4().hex[:6].upper()}"},
                    {"Name": "PhoneNumber", "Value": int(phone)},
                ]}}}}))
        else:
            step(f"approve the M-Pesa prompt on {phone} (waiting up to {args.timeout}s)")

        deadline = time.monotonic() + args.timeout
        while True:
            status = check(buyer.get(f"/api/v1/orders/{order['id']}"))
            if status["state"] in ("confirmed", "failed") or time.monotonic() > deadline:
                break
            time.sleep(3)
        print(f"    order state: {status['state']} {status['failure_reason'] or ''}")
        if status["state"] != "confirmed":
            sys.exit("FAILED: payment did not confirm")

        step("library + watermarked file")
        library = check(buyer.get("/api/v1/library"))
        assert any(i["resource"]["id"] == res["id"] for i in library), "resource missing from library"
        pdf = buyer.get(f"/api/v1/resources/{res['id']}/file", headers={"X-Device-Id": uuid.uuid4().hex * 2})
        check_pdf = PdfReader(io.BytesIO(pdf.content))
        assert pdf.status_code == 200 and all(user["email"] in p.extract_text() for p in check_pdf.pages), "watermark missing"
        print(f"    {len(check_pdf.pages)} pages, every page stamped for {user['email']}")
    print("PASSED end-to-end")


if __name__ == "__main__":
    main()
