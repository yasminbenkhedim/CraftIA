import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from app.core.database import Base
from app.core.brand import DEFAULT_ACCENT, DEFAULT_FONT, DEFAULT_PRIMARY, DEFAULT_SECONDARY


class BrandKit(Base):
    """
    One saved brand per user: the palette, typeface and logo their videos should use
    instead of the AI Director inventing a look per video.

    One row per user rather than a collection. A Tunisian agency serving three clients
    would want three, but that is a Pro-tier feature with its own picker, and building the
    many-side now would mean a nullable "which one is active" on every job. One kit is the
    honest shape of what is shipped.
    """
    __tablename__ = "brand_kits"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Unique: the endpoints upsert on it, so a duplicate row would make "the user's brand
    # kit" ambiguous and let a save silently land on the copy nobody reads.
    user_id = Column(String(36), unique=True, index=True, nullable=False)

    # Absolute path on the server. Nullable because colours alone are a usable kit --
    # a logo is the part users add later, once they have one.
    logo_path = Column(String(512), nullable=True)

    primary_color = Column(String(9), nullable=False, default=DEFAULT_PRIMARY)
    secondary_color = Column(String(9), nullable=False, default=DEFAULT_SECONDARY)
    accent_color = Column(String(9), nullable=False, default=DEFAULT_ACCENT)
    # An id from app.core.brand.FONT_CHOICES, not a font name: the renderer needs a file
    # it can open, and a free-text family name would be a promise nothing can keep.
    font_choice = Column(String(64), nullable=False, default=DEFAULT_FONT)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
