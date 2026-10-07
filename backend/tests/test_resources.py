from tests.conftest import make_pdf


async def upload(client, title="Algorithms Notes", price=300, pages=3, content=None):
    return await client.post(
        "/api/v1/admin/resources",
        data={"title": title, "description": "Week 1-6", "type": "pdf", "price": str(price)},
        files={"file": ("notes.pdf", content or make_pdf(pages), "application/pdf")},
    )


async def test_admin_upload_records_metadata_and_stores_file(client, admin, temp_storage):
    r = await upload(client, pages=4)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["page_count"] == 4
    assert len(body["sha256"]) == 64
    assert body["published"] is False
    assert (temp_storage / "originals" / f"{body['id']}.pdf").exists()


async def test_non_admin_cannot_upload(client, logged_in):
    assert (await upload(client)).status_code == 403


async def test_upload_rejects_non_pdf(client, admin):
    r = await upload(client, content=b"MZ this is an exe")
    assert r.status_code == 422


async def test_catalog_lists_only_published(client, admin):
    hidden = (await upload(client, title="Draft")).json()
    shown = (await upload(client, title="Live")).json()
    r = await client.patch(f"/api/v1/admin/resources/{shown['id']}", json={"published": True})
    assert r.status_code == 200

    catalog = (await client.get("/api/v1/resources")).json()
    ids = {r["id"] for r in catalog}
    assert shown["id"] in ids and hidden["id"] not in ids
    assert "storage_key" not in catalog[0]
    assert (await client.get(f"/api/v1/resources/{hidden['id']}")).status_code == 404


async def test_admin_can_edit_price(client, admin):
    res = (await upload(client, price=300)).json()
    r = await client.patch(f"/api/v1/admin/resources/{res['id']}", json={"price": 250})
    assert r.json()["price"] == 250


async def test_admin_sales_list_shows_orders(client, admin, make_resource):
    await client.post("/api/v1/orders", json={"resource_ids": [await make_resource(price=99)]})
    sales = (await client.get("/api/v1/admin/orders")).json()
    assert sales[0]["total_amount"] == 99
    assert sales[0]["state"] == "processing"
    assert "@" in sales[0]["buyer_email"]
