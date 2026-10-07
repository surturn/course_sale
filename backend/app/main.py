from fastapi import FastAPI

from app.api import auth, library, orders, resources
from app.core.config import settings

if settings.DARAJA_ENV != "mock" and (len(settings.SECRET_KEY) < 32 or settings.SECRET_KEY.startswith("change")):
    raise RuntimeError("Set a strong SECRET_KEY (32+ random chars) before taking real payments")
if settings.DARAJA_ENV != "mock" and len(settings.DARAJA_CALLBACK_SECRET) < 16:
    raise RuntimeError("Set DARAJA_CALLBACK_SECRET (16+ random chars) so payment callbacks can't be forged")

app = FastAPI(title=settings.PROJECT_NAME, docs_url=None if settings.COOKIE_SECURE else "/docs", redoc_url=None)
app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(resources.router)
app.include_router(library.router)


@app.get("/api/health")
async def health():
    return {"ok": True}
