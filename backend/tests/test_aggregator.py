import pytest


@pytest.fixture(autouse=True)
def plain_http_cookie(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.COOKIE_SECURE", False)


async def test_content_blocked_until_accepted(client):
    assert (await client.get("/api/v1/disclaimer")).json() == {"accepted": False}
    assert (await client.get("/api/v1/free-resources")).status_code == 403
    assert (await client.get("/api/v1/news")).status_code == 403


async def test_must_tick_the_box(client):
    assert (await client.post("/api/v1/disclaimer/accept", json={"agreed": False})).status_code == 422
    assert (await client.post("/api/v1/disclaimer/accept", json={})).status_code == 422
    assert (await client.get("/api/v1/free-resources")).status_code == 403


async def test_acceptance_unlocks_and_is_remembered(client):
    res = await client.post("/api/v1/disclaimer/accept", json={"agreed": True})
    assert res.status_code == 204
    cookie = res.headers["set-cookie"].lower()
    assert "httponly" in cookie and "max-age=31536000" in cookie and "samesite=lax" in cookie
    assert (await client.get("/api/v1/disclaimer")).json() == {"accepted": True}
    items = (await client.get("/api/v1/free-resources")).json()
    assert len(items) > 50 and {"title", "url", "kind", "niche", "desc"} <= set(items[0])


async def test_old_or_forged_cookie_value_is_rejected(client):
    client.cookies.set("aggregator_ok", "v0")
    assert (await client.get("/api/v1/free-resources")).status_code == 403
