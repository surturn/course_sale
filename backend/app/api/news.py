"""Public tech news feed: pulls a fixed list of RSS/Atom feeds server-side, caches them,
and serves one merged list. Feed URLs are hardcoded (never taken from the client), so
there is no SSRF surface. A feed that fails is skipped; stale cache is served if every
feed fails."""
import asyncio
import html
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Literal

import httpx
from defusedxml import ElementTree as ET
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.aggregator import require_disclaimer

router = APIRouter(prefix="/api/v1", tags=["news"])

Niche = Literal["hardware", "software", "ai", "security", "africa"]

# (source name, feed url, niche)
FEEDS: list[tuple[str, str, Niche]] = [
    ("Ars Technica Gadgets", "https://feeds.arstechnica.com/arstechnica/gadgets", "hardware"),
    ("Tom's Hardware", "https://www.tomshardware.com/feeds/all", "hardware"),
    ("Hacker News", "https://hnrss.org/frontpage", "software"),
    ("InfoQ", "https://www.infoq.com/feed/", "software"),
    ("GitHub Blog", "https://github.blog/feed/", "software"),
    ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml", "ai"),
    ("MIT Technology Review AI", "https://www.technologyreview.com/topic/artificial-intelligence/feed", "ai"),
    ("BleepingComputer", "https://www.bleepingcomputer.com/feed/", "security"),
    ("Krebs on Security", "https://krebsonsecurity.com/feed/", "security"),
    ("TechCabal", "https://techcabal.com/feed/", "africa"),
]

CACHE_TTL = 30 * 60
MAX_FEED_BYTES = 2_000_000
PER_FEED_LIMIT = 10
MAX_AGE = timedelta(days=30)
MAX_ITEMS = 100


class NewsItem(BaseModel):
    title: str
    link: str
    source: str
    niche: Niche
    published: datetime
    summary: str


class NewsOut(BaseModel):
    updated: datetime | None
    items: list[NewsItem]


_cache: dict = {"at": float("-inf"), "items": [], "updated": None}
_lock = asyncio.Lock()
_TAG = re.compile(r"<[^>]+>")


def _clean(text: str | None, limit: int = 220) -> str:
    text = html.unescape(_TAG.sub(" ", text or ""))
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    try:
        d = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(el, name: str) -> str | None:
    for c in el:
        if _local(c.tag) == name:
            return c.text
    return None


def parse_feed(xml_bytes: bytes, source: str, niche: Niche) -> list[NewsItem]:
    """Parse RSS 2.0 or Atom. Unknown or broken input yields an empty list."""
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return []
    items: list[NewsItem] = []
    now = datetime.now(timezone.utc)
    for el in root.iter():
        kind = _local(el.tag)
        if kind not in ("item", "entry"):
            continue
        title = _clean(_child_text(el, "title"), 160)
        link = ""
        if kind == "item":
            link = (_child_text(el, "link") or "").strip()
        else:
            for c in el:
                if _local(c.tag) == "link" and c.get("rel", "alternate") == "alternate":
                    link = (c.get("href") or "").strip()
                    break
        when = _date(_child_text(el, "pubDate") or _child_text(el, "published") or _child_text(el, "updated"))
        summary = _clean(_child_text(el, "description") or _child_text(el, "summary") or _child_text(el, "content"))
        if not title or not link.lower().startswith(("http://", "https://")) or when is None:
            continue
        if now - when > MAX_AGE or when - now > timedelta(days=1):
            continue
        items.append(NewsItem(title=title, link=link, source=source, niche=niche, published=when, summary=summary))
        if len(items) >= PER_FEED_LIMIT:
            break
    return items


async def _fetch_one(client: httpx.AsyncClient, source: str, url: str, niche: Niche) -> list[NewsItem]:
    try:
        # Stream and stop at the limit, so an oversized or gzip-bomb response never sits fully in memory.
        async with client.stream("GET", url) as res:
            res.raise_for_status()
            body = bytearray()
            async for chunk in res.aiter_bytes():
                body += chunk
                if len(body) > MAX_FEED_BYTES:
                    return []
        return parse_feed(bytes(body), source, niche)
    except Exception:
        return []


async def refresh() -> None:
    headers = {"User-Agent": "InvonicsNewsFeed/1.0", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"}
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=headers) as client:
        results = await asyncio.gather(*(_fetch_one(client, s, u, n) for s, u, n in FEEDS))
    merged = sorted((i for r in results for i in r), key=lambda i: i.published, reverse=True)[:MAX_ITEMS]
    if merged:  # keep the last good copy if every feed failed
        _cache.update(items=merged, updated=datetime.now(timezone.utc))
    _cache["at"] = time.monotonic()


@router.get("/news", response_model=NewsOut, dependencies=[Depends(require_disclaimer)])
async def news(niche: Niche | None = None):
    if time.monotonic() - _cache["at"] > CACHE_TTL:
        async with _lock:
            if time.monotonic() - _cache["at"] > CACHE_TTL:
                await refresh()
    items = [i for i in _cache["items"] if niche is None or i.niche == niche]
    return NewsOut(updated=_cache["updated"], items=items)
