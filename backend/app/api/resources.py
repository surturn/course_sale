import hashlib
import io
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool
from PIL import Image, ImageOps
from pydantic import BaseModel, Field, computed_field
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.orders import latest_row
from app.core.config import settings
from app.core.database import get_db
from app.models import Order, Resource, ResourceType, User
from app.security import current_user

router = APIRouter(prefix="/api/v1", tags=["resources"])


def original_path(resource_id: int) -> Path:
    return Path(settings.STORAGE_DIR) / "originals" / f"{resource_id}.pdf"


def cover_path(resource_id: int) -> Path:
    return Path(settings.STORAGE_DIR) / "covers" / f"{resource_id}.webp"


# Covers: JPEG, PNG or WebP up to 5 MB. Every upload is decoded and re-encoded (no metadata,
# no embedded scripts, no polyglots), centre-cropped to the 3:4 cover shape and stored as WebP.
COVER_MAX_BYTES = 5 * 1024 * 1024
COVER_SIZE = (600, 800)
COVER_MIN = (240, 320)
COVER_FORMATS = {"JPEG", "PNG", "WEBP"}
Image.MAX_IMAGE_PIXELS = 40_000_000  # refuse decompression bombs


def _process_cover(raw: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            fmt = probe.format
            probe.verify()
        if fmt not in COVER_FORMATS:
            raise ValueError
        with Image.open(io.BytesIO(raw)) as img:
            img = ImageOps.exif_transpose(img)
            if img.width < COVER_MIN[0] or img.height < COVER_MIN[1]:
                raise HTTPException(422, f"Cover is too small. Use at least {COVER_MIN[0]} x {COVER_MIN[1]} pixels.")
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                flat = Image.new("RGB", img.size, (255, 255, 255))
                flat.paste(img, mask=img.getchannel("A"))
                img = flat
            else:
                img = img.convert("RGB")
            img = ImageOps.fit(img, COVER_SIZE, Image.LANCZOS)
            out = io.BytesIO()
            img.save(out, "WEBP", quality=85, method=6)
            return out.getvalue()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "Use a JPEG, PNG or WebP image for the cover")


async def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Admins only")
    return user


class ResourceOut(BaseModel):
    id: int
    title: str
    description: str
    type: ResourceType
    price: int
    page_count: int | None
    published: bool
    cover_sha: str | None = Field(None, exclude=True)

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def cover_url(self) -> str | None:
        # The version in the query string changes with the image, so browsers can cache it forever.
        return f"/api/v1/resources/{self.id}/cover?v={self.cover_sha[:12]}" if self.cover_sha else None


class AdminResourceOut(ResourceOut):
    sha256: str | None


class ResourcePatch(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=200)
    description: str | None = None
    price: int | None = Field(None, ge=1, le=150_000)  # STK push single-transaction ceiling
    published: bool | None = None


@router.get("/resources", response_model=list[ResourceOut])
async def catalog(db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(Resource).where(Resource.published).order_by(Resource.id.desc()))).all()


@router.get("/resources/{resource_id}", response_model=ResourceOut)
async def resource_detail(resource_id: int, db: AsyncSession = Depends(get_db)):
    resource = await db.get(Resource, resource_id)
    if not resource or not resource.published:
        raise HTTPException(404, "Resource not found")
    return resource


@router.get("/resources/{resource_id}/cover")
async def resource_cover(resource_id: int, db: AsyncSession = Depends(get_db)):
    resource = await db.get(Resource, resource_id)
    path = cover_path(resource_id)
    if not resource or not resource.published or not resource.cover_sha or not path.exists():
        raise HTTPException(404, "No cover")
    return FileResponse(path, media_type="image/webp", headers={
        "Cache-Control": "public, max-age=31536000, immutable",
        "X-Content-Type-Options": "nosniff",
    })


@router.get("/admin/resources", response_model=list[AdminResourceOut])
async def admin_list(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(Resource).order_by(Resource.id.desc()))).all()


@router.post("/admin/resources", status_code=201, response_model=AdminResourceOut)
async def admin_upload(
    title: str = Form(min_length=2, max_length=200),
    description: str = Form(""),
    type: ResourceType = Form(ResourceType.pdf),
    price: int = Form(ge=1, le=150_000),
    file: UploadFile = File(),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    head = await file.read(5)
    if head != b"%PDF-":
        raise HTTPException(422, "Only PDF files are supported")
    await file.seek(0)

    resource = Resource(title=title, description=description, type=type, price=price, published=False)
    db.add(resource)
    await db.flush()
    path = original_path(resource.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    sha, size, limit = hashlib.sha256(), 0, settings.MAX_UPLOAD_MB * 1024 * 1024
    with tmp.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close()
                tmp.unlink()
                raise HTTPException(413, f"File larger than {settings.MAX_UPLOAD_MB} MB")
            sha.update(chunk)
            out.write(chunk)
    try:
        pages = await run_in_threadpool(lambda: len(PdfReader(tmp).pages))
    except Exception:
        tmp.unlink()
        raise HTTPException(422, "That PDF could not be read")
    os.replace(tmp, path)

    resource.storage_key = str(path.relative_to(settings.STORAGE_DIR))
    resource.sha256 = sha.hexdigest()
    resource.page_count = pages
    await db.commit()
    return resource


@router.patch("/admin/resources/{resource_id}", response_model=AdminResourceOut)
async def admin_update(resource_id: int, body: ResourcePatch, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    resource = await db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(404, "Resource not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(resource, field, value)
    if resource.published and not resource.storage_key:
        raise HTTPException(422, "Upload a file before publishing")
    await db.commit()
    return resource


@router.post("/admin/resources/{resource_id}/cover", response_model=AdminResourceOut)
async def admin_set_cover(resource_id: int, file: UploadFile = File(), _: User = Depends(require_admin),
                          db: AsyncSession = Depends(get_db)):
    resource = await db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(404, "Resource not found")
    raw = await file.read(COVER_MAX_BYTES + 1)
    if len(raw) > COVER_MAX_BYTES:
        raise HTTPException(413, "Cover larger than 5 MB")
    data = await run_in_threadpool(_process_cover, raw)
    path = cover_path(resource_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    resource.cover_sha = hashlib.sha256(data).hexdigest()
    await db.commit()
    return resource


@router.delete("/admin/resources/{resource_id}/cover", response_model=AdminResourceOut)
async def admin_remove_cover(resource_id: int, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    resource = await db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(404, "Resource not found")
    cover_path(resource_id).unlink(missing_ok=True)
    resource.cover_sha = None
    await db.commit()
    return resource


@router.get("/admin/orders")
async def admin_sales(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Payments dashboard: every app order with its latest ledger state (AccountReference INV-<id>)."""
    rows = (await db.execute(select(Order, User.email).join(User).order_by(Order.id.desc()).limit(200))).all()
    out = []
    for order, email in rows:
        row = await latest_row(db, order.id)
        if row is None:  # only possible for orders created outside checkout (e.g. manual grants)
            continue
        out.append({"id": order.id, "buyer_email": email, "total_amount": order.total_amount, "items": order.items,
                    "state": row.state.value, "failure_reason": row.failure_reason, "mpesa_receipt": row.mpesa_receipt,
                    "account_reference": row.account_reference, "created_at": order.created_at})
    return out
