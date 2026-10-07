import io

from pypdf import PdfReader

from app.core.database import AsyncSessionLocal
from app.models import Order, Purchase, Resource, ResourceType, User
from tests.conftest import make_pdf, new_user_payload

DEVICE = {"X-Device-Id": "a" * 64}


async def owned_resource(email, storage, pages=3):
    """Resource with a real file on disk, already purchased by `email`. Returns (resource_id, original bytes)."""
    from sqlalchemy import select
    original = make_pdf(pages)
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        res = Resource(title="Owned Notes", type=ResourceType.pdf, price=100, published=True, page_count=pages)
        db.add(res)
        await db.flush()
        (storage / "originals").mkdir(exist_ok=True)
        (storage / "originals" / f"{res.id}.pdf").write_bytes(original)
        res.storage_key = f"originals/{res.id}.pdf"
        order = Order(user_id=user.id, total_amount=100, items=[{"resource_id": res.id, "title": res.title, "price": 100}])
        db.add(order)
        await db.flush()
        db.add(Purchase(order_id=order.id, user_id=user.id, resource_id=res.id, price_paid=100))
        await db.commit()
        return res.id, original


async def test_library_lists_purchased_resources(client, logged_in, temp_storage):
    rid, _ = await owned_resource(logged_in["email"], temp_storage)
    library = (await client.get("/api/v1/library")).json()
    assert [item["resource"]["id"] for item in library] == [rid]


async def test_file_is_watermarked_with_buyer_identity(client, logged_in, temp_storage):
    rid, original = await owned_resource(logged_in["email"], temp_storage, pages=3)
    r = await client.get(f"/api/v1/resources/{rid}/file", headers=DEVICE)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "no-store" in r.headers["cache-control"]
    assert r.content != original

    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 3
    for page in reader.pages:
        text = page.extract_text()
        assert logged_in["email"] in text
        assert "INVFP:" in text  # invisible forensic fingerprint survives as extractable text


async def test_served_bytes_are_stable_and_support_range(client, logged_in, temp_storage):
    rid, _ = await owned_resource(logged_in["email"], temp_storage)
    full = (await client.get(f"/api/v1/resources/{rid}/file", headers=DEVICE)).content
    again = (await client.get(f"/api/v1/resources/{rid}/file", headers=DEVICE)).content
    assert full == again

    r = await client.get(f"/api/v1/resources/{rid}/file", headers={**DEVICE, "Range": "bytes=10-99"})
    assert r.status_code == 206
    assert r.content == full[10:100]


async def test_non_owner_gets_403(client, logged_in, temp_storage):
    rid, _ = await owned_resource(logged_in["email"], temp_storage)
    other = new_user_payload()
    await client.post("/api/v1/auth/register", json=other)
    await client.post("/api/v1/auth/login", json={"email": other["email"], "password": other["password"]})
    assert (await client.get(f"/api/v1/resources/{rid}/file", headers=DEVICE)).status_code == 403


async def test_device_header_required(client, logged_in, temp_storage):
    rid, _ = await owned_resource(logged_in["email"], temp_storage)
    assert (await client.get(f"/api/v1/resources/{rid}/file")).status_code == 400


async def test_new_device_quota_per_month(client, logged_in, temp_storage, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "REBIND_LIMIT_PER_MONTH", 3)
    rid, _ = await owned_resource(logged_in["email"], temp_storage)
    url = f"/api/v1/resources/{rid}/file"
    for d in "abc":
        assert (await client.get(url, headers={"X-Device-Id": d * 64})).status_code == 200
    r = await client.get(url, headers={"X-Device-Id": "d" * 64})
    assert r.status_code == 403
    assert "device" in r.json()["detail"].lower()
    assert (await client.get(url, headers={"X-Device-Id": "a" * 64})).status_code == 200  # known device still works
