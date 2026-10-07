"""Buyer library and protected file delivery (spec sections 5, 7, 8).

The original upload is never served: /file only ever returns the buyer's own watermarked copy,
generated on first open and cached on disk (deterministic bytes, so HTTP Range resumes work)."""
import hashlib
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.resources import ResourceOut, original_path
from app.core.config import settings
from app.core.database import get_db
from app.models import DeviceBind, Purchase, Resource, User
from app.security import current_user
from app.watermark import FORMAT_VERSION, watermark_pdf

router = APIRouter(prefix="/api/v1", tags=["library"])


@router.get("/library")
async def library(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(Purchase, Resource).join(Resource).where(Purchase.user_id == user.id).order_by(Purchase.id.desc())
    )).all()
    return [{"purchased_at": p.created_at, "order_id": p.order_id, "resource": ResourceOut.model_validate(r)} for p, r in rows]


async def check_device(db: AsyncSession, user: User, device_id: str, ip: str | None) -> None:
    device_hash = hashlib.sha256(device_id.encode()).hexdigest()
    bind = await db.scalar(select(DeviceBind).where(DeviceBind.user_id == user.id, DeviceBind.device_hash == device_hash))
    if bind:
        bind.last_ip, bind.last_seen_at = ip, func.now()
        await db.commit()
        return
    await db.get(User, user.id, with_for_update=True, populate_existing=True)  # serialise quota checks per user
    since = datetime.now(timezone.utc) - timedelta(days=30)
    recent = await db.scalar(select(func.count()).select_from(DeviceBind)
                             .where(DeviceBind.user_id == user.id, DeviceBind.bound_at > since))
    if recent >= settings.REBIND_LIMIT_PER_MONTH:
        await db.rollback()
        raise HTTPException(403, f"This account has been opened on {recent} new devices in the last 30 days, "
                                 "the maximum allowed. Use a device you've used before, or contact support.")
    db.add(DeviceBind(user_id=user.id, device_hash=device_hash, first_ip=ip, last_ip=ip))
    try:
        await db.commit()
    except IntegrityError:  # same device bound by a parallel request
        await db.rollback()


@router.get("/resources/{resource_id}/file")
async def resource_file(
    resource_id: int,
    request: Request,
    x_device_id: str | None = Header(None),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if not x_device_id or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", x_device_id):
        raise HTTPException(400, "Missing device id")
    row = (await db.execute(select(Purchase, Resource).join(Resource)
                            .where(Purchase.user_id == user.id, Purchase.resource_id == resource_id))).first()
    if not row:
        raise HTTPException(403, "You haven't bought this resource")
    purchase, resource = row
    if not resource.storage_key:
        raise HTTPException(404, "This resource has no file yet")

    await check_device(db, user, x_device_id, request.client.host if request.client else None)

    path = Path(settings.STORAGE_DIR) / "watermarked" / str(resource_id) / f"{user.id}-v{FORMAT_VERSION}.pdf"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.stem}.{uuid.uuid4().hex}.part")
        try:
            await run_in_threadpool(
                watermark_pdf, str(original_path(resource_id)), str(tmp),
                buyer_name=user.full_name, buyer_email=user.email, order_id=purchase.order_id,
                purchased_on=purchase.created_at.strftime("%Y-%m-%d"), user_id=user.id, resource_id=resource_id,
            )
            os.replace(tmp, path)  # atomic: a reader never sees a half-written file
        finally:
            tmp.unlink(missing_ok=True)

    return FileResponse(path, media_type="application/pdf", headers={
        "Cache-Control": "private, no-store",
        "Content-Disposition": "inline",
        "X-Content-Type-Options": "nosniff",
    })
