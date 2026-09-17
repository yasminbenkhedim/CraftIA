import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer
from app.core.database import Base
from app.core.plans import DEFAULT_PLAN, monthly_credits


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # ------------------------------------------------------------------
    # Credits (see app/services/credits.py for every read and write of these)
    # ------------------------------------------------------------------
    # A new user lands on the free plan with its full allowance already granted, so the
    # very first job works without waiting for a period roll-over.
    plan = Column(String(32), nullable=False, default=DEFAULT_PLAN.value)
    credits_remaining = Column(Integer, nullable=False, default=lambda: monthly_credits(DEFAULT_PLAN))
    credits_total = Column(Integer, nullable=False, default=lambda: monthly_credits(DEFAULT_PLAN))

    # When the current allowance period ends. Nullable on purpose: rows that predate
    # credits have NULL here, and credits.ensure_period_current() treats NULL as "period
    # has lapsed", which grants the allowance and stamps a real date on first touch.
    # That backfills old accounts without a data migration.
    credits_reset_at = Column(DateTime, nullable=True)
