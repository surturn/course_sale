"""Aggregator disclaimer gate. The free-library list and the news feed are only served to
visitors who ticked the disclaimer, so skipping the page script gets nothing. Each acceptance
is stored in the database (version, time, IP, browser, account if logged in) and the visitor
keeps a random token in a one-year HttpOnly cookie. A logged-in account that accepted once is
recognised on any device."""
import json
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models import DisclaimerAcceptance, User
from app.security import check_throttle, current_user, record_failure

router = APIRouter(prefix="/api/v1", tags=["aggregator"])

COOKIE = "aggregator_ok"
VERSION = "v1"  # bump when the disclaimer wording changes to ask everyone again
ONE_YEAR = 365 * 24 * 3600
# Flood guard, not a gate: Safaricom and campus networks put many real visitors behind one IP, so this must be
# far above any honest burst. Over the limit, visitors get a 429 and can retry later.
ACCEPT_LIMIT, ACCEPT_WINDOW = 300, 3600  # per IP per hour, so the table cannot be flooded
RESOURCES = json.loads((Path(__file__).resolve().parents[1] / "data" / "free-resources.json").read_text(encoding="utf-8"))


async def _optional_user(request: Request, db: AsyncSession) -> User | None:
    try:
        return await current_user(request, db)
    except HTTPException:
        return None


async def has_accepted(request: Request, db: AsyncSession) -> bool:
    token = request.cookies.get(COOKIE)
    if token:
        row = await db.scalar(select(DisclaimerAcceptance.id).where(
            DisclaimerAcceptance.token == token, DisclaimerAcceptance.version == VERSION))
        if row:
            return True
    user = await _optional_user(request, db)
    if user:
        row = await db.scalar(select(DisclaimerAcceptance.id).where(
            DisclaimerAcceptance.user_id == user.id, DisclaimerAcceptance.version == VERSION).limit(1))
        return row is not None
    return False


async def require_disclaimer(request: Request, db: AsyncSession = Depends(get_db)) -> None:
    if not await has_accepted(request, db):
        raise HTTPException(403, "Please accept the disclaimer first.")


class Accept(BaseModel):
    agreed: bool


@router.get("/disclaimer")
async def disclaimer_status(request: Request, db: AsyncSession = Depends(get_db)):
    return {"accepted": await has_accepted(request, db)}


@router.post("/disclaimer/accept", status_code=204)
async def accept_disclaimer(body: Accept, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    if not body.agreed:
        raise HTTPException(422, "You need to tick the box to continue.")
    ip = request.client.host if request.client else None
    token = request.cookies.get(COOKIE)
    if not (token and await has_accepted(request, db)):
        key = f"disclaimer:{ip}"
        check_throttle(key, ACCEPT_LIMIT, ACCEPT_WINDOW)
        record_failure(key)
        user = await _optional_user(request, db)
        token = secrets.token_urlsafe(32)
        db.add(DisclaimerAcceptance(
            token=token, version=VERSION, user_id=user.id if user else None, ip=ip,
            user_agent=(request.headers.get("user-agent") or "")[:300] or None,
        ))
        await db.commit()
    response.set_cookie(COOKIE, token, max_age=ONE_YEAR, httponly=True,
                        secure=settings.COOKIE_SECURE, samesite="lax", path="/")


@router.get("/free-resources", dependencies=[Depends(require_disclaimer)])
async def free_resources():
    return RESOURCES
