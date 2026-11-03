"""Aggregator disclaimer gate. The free-library list and the news feed are only served to
browsers that accepted the disclaimer, so skipping the page script gets nothing. Acceptance
is a long-lived HttpOnly cookie set by the server after an explicit POST."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/api/v1", tags=["aggregator"])

COOKIE = "aggregator_ok"
VERSION = "v1"  # bump when the disclaimer wording changes to ask everyone again
ONE_YEAR = 365 * 24 * 3600
RESOURCES = json.loads((Path(__file__).resolve().parents[1] / "data" / "free-resources.json").read_text(encoding="utf-8"))


def accepted(request: Request) -> bool:
    return request.cookies.get(COOKIE) == VERSION


def require_disclaimer(request: Request) -> None:
    if not accepted(request):
        raise HTTPException(403, "Please accept the disclaimer first.")


class Accept(BaseModel):
    agreed: bool


@router.get("/disclaimer")
async def disclaimer_status(request: Request):
    return {"accepted": accepted(request)}


@router.post("/disclaimer/accept", status_code=204)
async def accept_disclaimer(body: Accept, response: Response):
    if not body.agreed:
        raise HTTPException(422, "You need to tick the box to continue.")
    response.set_cookie(
        COOKIE, VERSION, max_age=ONE_YEAR,
        httponly=True, secure=settings.COOKIE_SECURE, samesite="lax", path="/",
    )


@router.get("/free-resources", dependencies=[Depends(require_disclaimer)])
async def free_resources():
    return RESOURCES
