import httpx
import pytest
from sqlalchemy import func, select

from app.api import aggregator
from app.core.database import AsyncSessionLocal
from app.main import app
from app.models import DisclaimerAcceptance
from app.security import _failures
from tests.conftest import new_user_payload


@pytest.fixture(autouse=True)
def plain_http_cookie(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.COOKIE_SECURE", False)
    _failures.clear()


def fresh_client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                             headers={"user-agent": "TestBrowser/1.0"})


async def rows_for(token: str):
    async with AsyncSessionLocal() as db:
        return (await db.scalars(select(DisclaimerAcceptance).where(DisclaimerAcceptance.token == token))).all()


async def test_content_blocked_until_accepted(client):
    assert (await client.get("/api/v1/disclaimer")).json() == {"accepted": False}
    assert (await client.get("/api/v1/free-resources")).status_code == 403
    assert (await client.get("/api/v1/news")).status_code == 403


async def test_must_tick_the_box(client):
    assert (await client.post("/api/v1/disclaimer/accept", json={"agreed": False})).status_code == 422
    assert (await client.post("/api/v1/disclaimer/accept", json={})).status_code == 422
    assert (await client.get("/api/v1/free-resources")).status_code == 403


async def test_acceptance_is_stored_and_unlocks(client):
    res = await client.post("/api/v1/disclaimer/accept", json={"agreed": True}, headers={"user-agent": "TestBrowser/1.0"})
    assert res.status_code == 204
    cookie = res.headers["set-cookie"].lower()
    assert "httponly" in cookie and "max-age=31536000" in cookie and "samesite=lax" in cookie
    token = client.cookies.get("aggregator_ok")
    (row,) = await rows_for(token)
    assert row.version == aggregator.VERSION and row.user_id is None
    assert row.user_agent == "TestBrowser/1.0" and row.ip and row.accepted_at
    assert (await client.get("/api/v1/disclaimer")).json() == {"accepted": True}
    items = (await client.get("/api/v1/free-resources")).json()
    assert len(items) > 50 and {"title", "url", "kind", "niche", "desc"} <= set(items[0])


async def test_accepting_again_does_not_add_rows(client):
    await client.post("/api/v1/disclaimer/accept", json={"agreed": True})
    token = client.cookies.get("aggregator_ok")
    await client.post("/api/v1/disclaimer/accept", json={"agreed": True})
    assert client.cookies.get("aggregator_ok") == token
    assert len(await rows_for(token)) == 1


async def test_forged_or_unknown_token_is_rejected(client):
    client.cookies.set("aggregator_ok", "v1")
    assert (await client.get("/api/v1/free-resources")).status_code == 403
    client.cookies.set("aggregator_ok", "not-a-real-token-1234567890")
    assert (await client.get("/api/v1/free-resources")).status_code == 403


async def test_old_version_must_accept_again(client, monkeypatch):
    await client.post("/api/v1/disclaimer/accept", json={"agreed": True})
    assert (await client.get("/api/v1/free-resources")).status_code == 200
    monkeypatch.setattr(aggregator, "VERSION", "v2")
    assert (await client.get("/api/v1/free-resources")).status_code == 403
    await client.post("/api/v1/disclaimer/accept", json={"agreed": True})
    assert (await client.get("/api/v1/free-resources")).status_code == 200
    (row,) = await rows_for(client.cookies.get("aggregator_ok"))
    assert row.version == "v2"


async def test_account_acceptance_follows_the_user_to_a_new_device():
    user = new_user_payload()
    async with fresh_client() as phone:
        assert (await phone.post("/api/v1/auth/register", json=user)).status_code == 201
        assert (await phone.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]})).status_code == 200
        await phone.post("/api/v1/disclaimer/accept", json={"agreed": True})
        (row,) = await rows_for(phone.cookies.get("aggregator_ok"))
        assert row.user_id is not None
    async with fresh_client() as laptop:  # no disclaimer cookie
        assert (await laptop.get("/api/v1/free-resources")).status_code == 403
        await laptop.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]})
        assert (await laptop.get("/api/v1/free-resources")).status_code == 200


async def test_accept_is_rate_limited_per_ip():
    async with fresh_client() as c:
        before = None
        async with AsyncSessionLocal() as db:
            before = await db.scalar(select(func.count()).select_from(DisclaimerAcceptance))
        codes = []
        for _ in range(aggregator.ACCEPT_LIMIT + 3):
            c.cookies.clear()  # a bot that never keeps the cookie
            codes.append((await c.post("/api/v1/disclaimer/accept", json={"agreed": True})).status_code)
        assert codes[: aggregator.ACCEPT_LIMIT] == [204] * aggregator.ACCEPT_LIMIT
        assert codes[aggregator.ACCEPT_LIMIT:] == [429] * 3
        async with AsyncSessionLocal() as db:
            after = await db.scalar(select(func.count()).select_from(DisclaimerAcceptance))
        assert after - before == aggregator.ACCEPT_LIMIT
