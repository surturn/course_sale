import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import aggregator, auth, library, news, orders, resources
from app.core.config import settings

if settings.DARAJA_ENV != "mock" and (len(settings.SECRET_KEY) < 32 or settings.SECRET_KEY.startswith("change")):
    raise RuntimeError("Set a strong SECRET_KEY (32+ random chars) before taking real payments")
if settings.DARAJA_ENV != "mock" and len(settings.DARAJA_CALLBACK_SECRET) < 16:
    raise RuntimeError("Set DARAJA_CALLBACK_SECRET (16+ random chars) so payment callbacks can't be forged")

if settings.DARAJA_ENV == "production":
    _missing = [k for k in ("DARAJA_CONSUMER_KEY", "DARAJA_CONSUMER_SECRET", "DARAJA_SHORTCODE", "DARAJA_PASSKEY")
                if not getattr(settings, k)]
    if _missing:
        raise RuntimeError(f"DARAJA_ENV=production but these are empty: {', '.join(_missing)}")
    if not settings.DARAJA_CALLBACK_URL.startswith("https://") or "localhost" in settings.DARAJA_CALLBACK_URL:
        raise RuntimeError("DARAJA_CALLBACK_URL must be a public https:// address Safaricom can reach")
    if settings.DARAJA_TRANSACTION_TYPE not in ("CustomerPayBillOnline", "CustomerBuyGoodsOnline"):
        raise RuntimeError("DARAJA_TRANSACTION_TYPE must be CustomerPayBillOnline or CustomerBuyGoodsOnline")

@asynccontextmanager
async def lifespan(_: FastAPI):
    tasks = [asyncio.create_task(orders.reconcile_loop()), asyncio.create_task(news.news_loop())]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan, docs_url=None if settings.COOKIE_SECURE else "/docs", redoc_url=None)
app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(resources.router)
app.include_router(library.router)
app.include_router(news.router)
app.include_router(aggregator.router)


@app.get("/api/health")
async def health():
    return {"ok": True}
