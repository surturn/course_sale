"""Per-buyer PDF watermarking (spec section 7).

Every page gets
  - a visible footer + faint diagonal stamp with the buyer's identity (vector text, so search still works), and
  - an invisible forensic fingerprint (text render mode 3) `INVFP:<code>` that survives removal of the
    visible marks; `<code>` = u<user>-r<resource>-<hmac>, so a leaked copy traces back to its buyer.
The fingerprint is also written to the document metadata."""
import hashlib
import hmac
import math

from pypdf import PageObject, PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, FloatObject, NameObject

from app.core.config import settings

FORMAT_VERSION = 2  # bump when the overlay changes so cached copies regenerate


def fingerprint(user_id: int, resource_id: int) -> str:
    mac = hmac.new(settings.SECRET_KEY.encode(), f"{user_id}:{resource_id}".encode(), hashlib.sha256).hexdigest()[:12]
    return f"u{user_id}-r{resource_id}-{mac}"


def _pdf_string(text: str) -> bytes:
    raw = text.encode("latin-1", errors="replace")
    return b"(" + raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def _overlay(width: float, height: float, footer: str, stamp: str, code: str) -> PageObject:
    angle = math.atan2(height, width)
    cos, sin = math.cos(angle), math.sin(angle)
    size = 28
    half = len(stamp) * size * 0.27  # ~half the Helvetica run width, so the stamp is centred on the page
    x, y = width / 2 - half * cos, height / 2 - half * sin
    ops = b"\n".join([
        # Faint diagonal stamp across the page.
        f"q /InvGS gs 0.5 g BT /InvF {size} Tf".encode(),
        f"{cos:.4f} {sin:.4f} {-sin:.4f} {cos:.4f} {x:.1f} {y:.1f} Tm".encode(),
        _pdf_string(stamp) + b" Tj ET Q",
        # Visible footer.
        b"q 0.35 g BT /InvF 7 Tf 1 0 0 1 24 12 Tm " + _pdf_string(footer) + b" Tj ET Q",
        # Invisible fingerprint (render mode 3 = neither fill nor stroke).
        b"q BT 3 Tr /InvF 4 Tf 1 0 0 1 2 2 Tm " + _pdf_string(f"INVFP:{code}") + b" Tj ET Q",
    ])
    page = PageObject.create_blank_page(width=width, height=height)
    stream = DecodedStreamObject()
    stream.set_data(ops)
    page[NameObject("/Contents")] = stream
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/InvF"): DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        })}),
        NameObject("/ExtGState"): DictionaryObject({NameObject("/InvGS"): DictionaryObject({
            NameObject("/Type"): NameObject("/ExtGState"),
            NameObject("/ca"): FloatObject(0.12),
        })}),
    })
    return page


def watermark_pdf(src: str, dst: str, *, buyer_name: str, buyer_email: str, order_id: int,
                  purchased_on: str, user_id: int, resource_id: int) -> None:
    code = fingerprint(user_id, resource_id)
    footer = f"Licensed to {buyer_name} <{buyer_email}> - Order #{order_id} - {purchased_on} - Sharing is traceable"
    writer = PdfWriter(clone_from=PdfReader(src))
    overlays: dict[tuple[float, float], PageObject] = {}
    for page in writer.pages:
        box = page.mediabox
        size = (float(box.width), float(box.height))
        if size not in overlays:
            overlays[size] = _overlay(*size, footer=footer, stamp=buyer_email, code=code)
        # ponytail: rotated / offset mediaboxes get an unrotated overlay; fine for typical notes PDFs.
        page.merge_page(overlays[size])
    writer.add_metadata({"/InvonicsFingerprint": code, "/Producer": "Invonics"})
    with open(dst, "wb") as fh:
        writer.write(fh)
