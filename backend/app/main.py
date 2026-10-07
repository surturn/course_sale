from fastapi import FastAPI

from app.api import auth, library, orders, resources
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(resources.router)
app.include_router(library.router)


@app.get("/api/health")
async def health():
    return {"ok": True}
