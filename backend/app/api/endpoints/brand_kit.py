"""
Brand kit endpoints: the user's saved palette, typeface and logo.

The kit is read at job creation and snapshotted into the job's render settings, so these
endpoints never talk to the pipeline directly -- see the brand-kit branch in
app/api/endpoints/jobs.py.
"""
import logging
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.brand import (
    DEFAULT_ACCENT,
    DEFAULT_FONT,
    DEFAULT_PRIMARY,
    DEFAULT_SECONDARY,
    font_catalogue,
    is_hex_color,
    normalize_font,
    normalize_hex,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.brand_kit import BrandKit
from app.models.user import User

logger = logging.getLogger("uvicorn")

router = APIRouter()

# Raster formats the renderer can actually composite. SVG is deliberately absent: the
# watermark step draws with OpenCV/PIL, neither of which rasterises vectors, so accepting
# one would store a file that silently never appears in a video.
ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_LOGO_BYTES = 4 * 1024 * 1024  # 4 MB — a logo, not a photograph.


def _logo_dir() -> str:
    # Beside the artifacts rather than inside them: storage retention sweeps artifact
    # directories by age, and a brand logo must outlive the videos it was stamped on.
    root = os.path.dirname(os.path.abspath(str(settings.STORAGE_PATH)))
    path = os.path.join(root, "brand_kits")
    os.makedirs(path, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BrandKitResponse(BaseModel):
    # False when the user has never saved one. The create page's "Use my brand kit"
    # toggle keys off this, so it is stated rather than inferred from default colours.
    has_brand_kit: bool
    primary_color: str
    secondary_color: str
    accent_color: str
    font_choice: str
    has_logo: bool
    # Relative on purpose: the browser appends its own ?token=, exactly as it does for
    # artifact downloads. Putting the caller's JWT in a response body would leak it into
    # logs and caches.
    logo_url: Optional[str] = None
    updated_at: Optional[datetime] = None


class BrandKitUpdate(BaseModel):
    primary_color: str = Field(default=DEFAULT_PRIMARY)
    secondary_color: str = Field(default=DEFAULT_SECONDARY)
    accent_color: str = Field(default=DEFAULT_ACCENT)
    font_choice: str = Field(default=DEFAULT_FONT)

    @field_validator("primary_color", "secondary_color", "accent_color")
    @classmethod
    def _must_be_hex(cls, v: str) -> str:
        """
        Rejected rather than silently corrected.

        normalize_hex() exists for reading rows written by older code; on the way in, a
        colour the user cannot see the effect of is worse than an error message.
        """
        if not is_hex_color(v):
            raise ValueError(f"'{v}' is not a hex colour (expected #RGB or #RRGGBB).")
        return normalize_hex(v, DEFAULT_PRIMARY)


class FontOption(BaseModel):
    id: str
    label: str
    note: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(kit: Optional[BrandKit]) -> dict:
    """
    An unsaved kit still answers with the defaults.

    The brand-kit page needs something to render into its colour pickers before the user
    has saved anything, and those defaults are the palette the Director would produce on
    its own -- so an untouched kit changes nothing about a render.
    """
    if kit is None:
        return {
            "has_brand_kit": False,
            "primary_color": DEFAULT_PRIMARY,
            "secondary_color": DEFAULT_SECONDARY,
            "accent_color": DEFAULT_ACCENT,
            "font_choice": DEFAULT_FONT,
            "has_logo": False,
            "logo_url": None,
            "updated_at": None,
        }

    has_logo = bool(kit.logo_path) and os.path.exists(kit.logo_path)
    return {
        "has_brand_kit": True,
        "primary_color": normalize_hex(kit.primary_color, DEFAULT_PRIMARY),
        "secondary_color": normalize_hex(kit.secondary_color, DEFAULT_SECONDARY),
        "accent_color": normalize_hex(kit.accent_color, DEFAULT_ACCENT),
        "font_choice": normalize_font(kit.font_choice),
        "has_logo": has_logo,
        # Checked against the filesystem, not just the column: a logo removed from disk
        # must not leave the preview requesting an image that can only 404.
        "logo_url": "/api/me/brand-kit/logo" if has_logo else None,
        "updated_at": kit.updated_at,
    }


def get_kit_for_user(db: Session, user_id: str) -> Optional[BrandKit]:
    return db.query(BrandKit).filter(BrandKit.user_id == user_id).first()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/brand-kit", response_model=BrandKitResponse)
def get_brand_kit(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _serialize(get_kit_for_user(db, current_user.id))


@router.put("/brand-kit", response_model=BrandKitResponse)
def save_brand_kit(
    req: BrandKitUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update the signed-in user's kit. The logo is uploaded separately."""
    kit = get_kit_for_user(db, current_user.id)
    if kit is None:
        kit = BrandKit(user_id=current_user.id)
        db.add(kit)

    kit.primary_color = req.primary_color
    kit.secondary_color = req.secondary_color
    kit.accent_color = req.accent_color
    kit.font_choice = normalize_font(req.font_choice)
    kit.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(kit)
    logger.info(
        f"Brand kit saved for {current_user.email}: {kit.primary_color}/{kit.secondary_color}/"
        f"{kit.accent_color}, font={kit.font_choice}"
    )
    return _serialize(kit)


@router.get("/brand-kit/fonts", response_model=List[FontOption])
def list_fonts():
    """
    The typefaces the renderer can actually load.

    Served rather than hardcoded in the frontend so the picker can never offer a font that
    has no file on disk — see the inventory note in app/core/brand.py.
    """
    return font_catalogue()


@router.post("/brand-kit/logo", response_model=BrandKitResponse, status_code=status.HTTP_201_CREATED)
async def upload_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported logo format '{ext or file.filename}'. "
                   f"Allowed: {', '.join(sorted(ALLOWED_LOGO_EXTENSIONS))}. "
                   f"SVG is not accepted — the renderer composites raster images.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")
    if len(data) > MAX_LOGO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Logo is {len(data) / 1048576:.1f} MB; the limit is {MAX_LOGO_BYTES // 1048576} MB.",
        )

    # Verify it decodes before it is stored. A file that is not really an image would be
    # accepted here and then fail silently inside a render, which is far harder to trace
    # back to this upload.
    try:
        import io as _io
        from PIL import Image
        with Image.open(_io.BytesIO(data)) as probe:
            probe.verify()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That file could not be read as an image.",
        )

    # Named by user id, so re-uploading replaces rather than accumulating. The extension
    # can change between uploads, so any previous file is removed first.
    for old in ALLOWED_LOGO_EXTENSIONS:
        stale = os.path.join(_logo_dir(), f"{current_user.id}{old}")
        if os.path.exists(stale):
            try:
                os.remove(stale)
            except OSError as e:
                logger.warning(f"Brand kit: could not remove previous logo {stale} ({e}).")

    dest = os.path.join(_logo_dir(), f"{current_user.id}{ext}")
    with open(dest, "wb") as fh:
        fh.write(data)

    kit = get_kit_for_user(db, current_user.id)
    if kit is None:
        kit = BrandKit(user_id=current_user.id)
        db.add(kit)
    kit.logo_path = dest
    kit.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(kit)

    logger.info(f"Brand kit: logo saved for {current_user.email} -> {dest} ({len(data) / 1024:.0f} KB)")
    return _serialize(kit)


@router.delete("/brand-kit/logo", response_model=BrandKitResponse)
def delete_logo(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kit = get_kit_for_user(db, current_user.id)
    if kit is None or not kit.logo_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No logo to remove.")
    if os.path.exists(kit.logo_path):
        try:
            os.remove(kit.logo_path)
        except OSError as e:
            logger.warning(f"Brand kit: could not delete logo ({e}).")
    kit.logo_path = None
    kit.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(kit)
    return _serialize(kit)


@router.get("/brand-kit/logo")
def get_logo(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Serves the signed-in user's own logo, for the settings preview.

    Scoped to current_user rather than taking an id: there is no reason for one account to
    fetch another's logo, and not offering the parameter is simpler than guarding it.
    """
    kit = get_kit_for_user(db, current_user.id)
    if kit is None or not kit.logo_path or not os.path.exists(kit.logo_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No logo uploaded.")
    return FileResponse(kit.logo_path)
