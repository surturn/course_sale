from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

from app.api import news

NOW = datetime.now(timezone.utc)


def rss(*items):
    body = "".join(
        f"<item><title>{t}</title><link>{l}</link><pubDate>{format_datetime(d)}</pubDate>"
        f"<description>&lt;p&gt;Hi &amp;amp; bye&lt;/p&gt;</description></item>"
        for t, l, d in items
    )
    return f"<?xml version='1.0'?><rss version='2.0'><channel>{body}</channel></rss>".encode()


def atom(title, href, when):
    return (
        f"<feed xmlns='http://www.w3.org/2005/Atom'><entry><title>{title}</title>"
        f"<link rel='alternate' href='{href}'/><updated>{when.isoformat()}</updated>"
        f"<summary>sum</summary></entry></feed>"
    ).encode()


def test_parses_rss_and_cleans_summary():
    out = news.parse_feed(rss(("A", "https://x.test/a", NOW)), "Src", "software")
    assert [i.title for i in out] == ["A"]
    assert out[0].summary == "Hi & bye"


def test_parses_atom():
    out = news.parse_feed(atom("B", "https://x.test/b", NOW), "Src", "ai")
    assert out[0].link == "https://x.test/b" and out[0].niche == "ai"


def test_drops_bad_links_old_items_and_garbage():
    old = NOW - timedelta(days=90)
    out = news.parse_feed(
        rss(("js", "javascript:alert(1)", NOW), ("old", "https://x.test/o", old), ("ok", "https://x.test/k", NOW)),
        "Src", "software",
    )
    assert [i.title for i in out] == ["ok"]
    assert news.parse_feed(b"not xml at all", "Src", "software") == []


def test_rejects_entity_bomb():
    bomb = b"<?xml version='1.0'?><!DOCTYPE l [<!ENTITY a 'aaaa'><!ENTITY b '&a;&a;&a;&a;'>]><rss><channel><item><title>&b;</title></item></channel></rss>"
    assert news.parse_feed(bomb, "Src", "software") == []


@pytest.fixture
def fake_feeds(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.COOKIE_SECURE", False)
    news._cache.update(at=float("-inf"), items=[], updated=None)
    calls = {"n": 0}

    async def fake_fetch(client, source, url, niche):
        calls["n"] += 1
        if source == "InfoQ":
            return []  # one feed down
        return news.parse_feed(rss((f"{source} story", f"https://x.test/{source}", NOW)), source, niche)

    monkeypatch.setattr(news, "_fetch_one", fake_fetch)
    return calls


async def test_endpoint_merges_filters_and_caches(client, fake_feeds):
    assert (await client.get("/api/v1/news")).status_code == 403  # gated until accepted
    await client.post("/api/v1/disclaimer/accept", json={"agreed": True})
    res = await client.get("/api/v1/news")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == len(news.FEEDS) - 1  # failed feed skipped
    first_calls = fake_feeds["n"]

    hw = (await client.get("/api/v1/news", params={"niche": "hardware"})).json()["items"]
    assert hw and all(i["niche"] == "hardware" for i in hw)
    assert fake_feeds["n"] == first_calls  # served from cache

    assert (await client.get("/api/v1/news", params={"niche": "bogus"})).status_code == 422


async def test_keeps_stale_copy_when_everything_fails(client, fake_feeds, monkeypatch):
    await client.post("/api/v1/disclaimer/accept", json={"agreed": True})
    await client.get("/api/v1/news")

    async def dead(*a, **k):
        return []

    monkeypatch.setattr(news, "_fetch_one", dead)
    news._cache["at"] = float("-inf")  # expire
    res = await client.get("/api/v1/news")
    assert len(res.json()["items"]) == len(news.FEEDS) - 1


def _client_for(handler):
    import httpx
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_one_parses_a_normal_feed():
    import httpx

    def handler(request):
        return httpx.Response(200, content=rss(("A story", "https://x.test/a", NOW)))

    async with _client_for(handler) as c:
        items = await news._fetch_one(c, "Src", "https://feed.test/rss", "software")
    assert [i.title for i in items] == ["A story"]


async def test_fetch_one_stops_reading_an_oversized_feed():
    import httpx
    sent = {"bytes": 0}

    async def endless():
        while True:  # a feed that never ends; reading it all would exhaust memory
            sent["bytes"] += 100_000
            yield b"x" * 100_000

    def handler(request):
        return httpx.Response(200, content=endless())

    async with _client_for(handler) as c:
        items = await news._fetch_one(c, "Src", "https://feed.test/rss", "software")
    assert items == []
    assert news.MAX_FEED_BYTES < sent["bytes"] <= news.MAX_FEED_BYTES + 1_000_000  # stopped just past the limit


async def test_fetch_one_skips_error_responses():
    import httpx

    async with _client_for(lambda r: httpx.Response(503)) as c:
        assert await news._fetch_one(c, "Src", "https://feed.test/rss", "software") == []


async def test_stale_copy_is_served_at_once_and_refreshed_in_the_background(client, fake_feeds, monkeypatch):
    import asyncio
    import time
    await client.post("/api/v1/disclaimer/accept", json={"agreed": True})
    await client.get("/api/v1/news")  # first call warms the cache
    warm_calls = fake_feeds["n"]
    news._cache["at"] = time.monotonic() - news.CACHE_TTL - 1  # now stale, but not "never loaded"

    release = asyncio.Event()
    real_fetch = news._fetch_one

    async def slow(client_, source, url, niche):
        await release.wait()  # a refresh that takes a long time
        return await real_fetch(client_, source, url, niche)

    monkeypatch.setattr(news, "_fetch_one", slow)
    started = time.monotonic()
    res = await client.get("/api/v1/news")
    assert time.monotonic() - started < 1.0  # did not wait for the refresh
    assert len(res.json()["items"]) == len(news.FEEDS) - 1  # served the old copy

    release.set()
    await news._bg  # the refresh finishes behind the scenes
    assert news._cache["at"] > time.monotonic() - 5


async def test_a_feed_that_never_answers_is_cut_off(fake_feeds, monkeypatch):
    import asyncio
    import time

    async def hang(*a, **k):
        await asyncio.sleep(30)

    monkeypatch.setattr(news, "_fetch_one", hang)
    monkeypatch.setattr(news, "FEED_DEADLINE", 0.05)
    started = time.monotonic()
    await news.refresh()
    assert time.monotonic() - started < 2.0
    assert news._cache["items"] == []
