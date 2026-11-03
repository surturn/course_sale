import io

from PIL import Image

from tests.test_resources import upload


def image_bytes(fmt="PNG", size=(900, 1200), mode="RGB", exif=False):
    img = Image.new(mode, size, (200, 30, 30) if mode == "RGB" else (200, 30, 30, 120))
    buf = io.BytesIO()
    kwargs = {}
    if exif:
        ex = Image.Exif()
        ex[0x010F] = "SecretCamera"  # Make
        ex[0x9286] = "user comment with private info"
        kwargs["exif"] = ex.tobytes()
    img.save(buf, fmt, **kwargs)
    return buf.getvalue()


async def make_resource(client, published=True):
    res = (await upload(client, title="Cover Test")).json()
    if published:
        await client.patch(f"/api/v1/admin/resources/{res['id']}", json={"published": True})
    return res


async def set_cover(client, rid, content, name="cover.png", mime="image/png"):
    return await client.post(f"/api/v1/admin/resources/{rid}/cover", files={"file": (name, content, mime)})


async def test_upload_reencodes_to_webp_3x4_and_serves_with_cache_headers(client, admin, temp_storage):
    res = await make_resource(client)
    r = await set_cover(client, res["id"], image_bytes(size=(1600, 900)))  # landscape gets centre-cropped
    assert r.status_code == 200, r.text
    url = r.json()["cover_url"]
    assert url.startswith(f"/api/v1/resources/{res['id']}/cover?v=")
    assert "cover_sha" not in r.json()

    stored = temp_storage / "covers" / f"{res['id']}.webp"
    with Image.open(stored) as img:
        assert img.format == "WEBP" and img.size == (600, 800)

    detail = (await client.get(f"/api/v1/resources/{res['id']}")).json()
    assert detail["cover_url"] == url
    catalog = (await client.get("/api/v1/resources")).json()
    assert any(c["cover_url"] == url for c in catalog)

    got = await client.get(url)
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/webp"
    assert "immutable" in got.headers["cache-control"]
    assert got.headers["x-content-type-options"] == "nosniff"


async def test_metadata_is_stripped(client, admin, temp_storage):
    res = await make_resource(client)
    r = await set_cover(client, res["id"], image_bytes("JPEG", exif=True), "c.jpg", "image/jpeg")
    assert r.status_code == 200
    raw = (temp_storage / "covers" / f"{res['id']}.webp").read_bytes()
    assert b"SecretCamera" not in raw and b"private info" not in raw
    with Image.open(io.BytesIO(raw)) as img:
        assert not img.getexif()


async def test_transparent_png_is_flattened(client, admin, temp_storage):
    res = await make_resource(client)
    r = await set_cover(client, res["id"], image_bytes(mode="RGBA"))
    assert r.status_code == 200
    with Image.open(temp_storage / "covers" / f"{res['id']}.webp") as img:
        assert img.mode == "RGB"


async def test_rejects_bad_files(client, admin, temp_storage):
    res = await make_resource(client)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    assert (await set_cover(client, res["id"], svg, "x.svg", "image/svg+xml")).status_code == 422
    assert (await set_cover(client, res["id"], b"just text", "x.png")).status_code == 422
    assert (await set_cover(client, res["id"], image_bytes("GIF"), "x.gif", "image/gif")).status_code == 422
    small = await set_cover(client, res["id"], image_bytes(size=(100, 120)))
    assert small.status_code == 422 and "too small" in small.json()["detail"]
    huge = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024 + 10)
    assert (await set_cover(client, res["id"], huge)).status_code == 413
    detail = (await client.get(f"/api/v1/resources/{res['id']}")).json()
    assert detail["cover_url"] is None
    assert not (temp_storage / "covers" / f"{res['id']}.webp").exists()


async def test_non_admin_cannot_set_or_remove(client, admin, temp_storage):
    res = await make_resource(client)
    await client.post("/api/v1/auth/logout")
    assert (await set_cover(client, res["id"], image_bytes())).status_code == 401
    assert (await client.delete(f"/api/v1/admin/resources/{res['id']}/cover")).status_code == 401


async def test_hidden_resource_cover_is_not_served(client, admin, temp_storage):
    res = await make_resource(client, published=False)
    url = (await set_cover(client, res["id"], image_bytes())).json()["cover_url"]
    assert (await client.get(url)).status_code == 404


async def test_replace_changes_version_and_remove_falls_back(client, admin, temp_storage):
    res = await make_resource(client)
    first = (await set_cover(client, res["id"], image_bytes())).json()["cover_url"]
    blue = io.BytesIO()
    Image.new("RGB", (900, 1200), (20, 40, 200)).save(blue, "PNG")
    third = (await set_cover(client, res["id"], blue.getvalue())).json()["cover_url"]
    assert first != third
    r = await client.delete(f"/api/v1/admin/resources/{res['id']}/cover")
    assert r.status_code == 200 and r.json()["cover_url"] is None
    assert not (temp_storage / "covers" / f"{res['id']}.webp").exists()
    assert (await client.get(third)).status_code == 404
