from fastapi import FastAPI

from app.api import auth
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(auth.router)


@app.get("/api/health")
async def health():
    return {"ok": True}
