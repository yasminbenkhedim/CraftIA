"""
Credit endpoints: the user's own balance, the public plan catalogue, and a
deliberately-gated admin surface for exercising the rules without waiting a month.
"""
import os
import logging
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.plans import Plan, all_definitions
from app.core.security import get_current_user
from app.models.user import User
from app.services import credits as credit_service

logger = logging.getLogger("uvicorn")

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class CreditsResponse(BaseModel):
    plan: str
    credits_remaining: int
    credits_total: int
    credits_reset_at: Optional[datetime] = None
    # Balance minus jobs already queued or running. The Generate button keys off this,
    # not off credits_remaining, because a credit is only debited on success and a
    # render already in flight will claim one when it lands.
    credits_available: int
    jobs_in_flight: int


class PlanCatalogueResponse(BaseModel):
    plans: Dict[str, int] = Field(description="plan id -> monthly credit allowance")
    default_plan: str


# ---------------------------------------------------------------------------
# GET /api/me/credits
# ---------------------------------------------------------------------------

@router.get("/credits", response_model=CreditsResponse)
def get_my_credits(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    The signed-in user's credit state.

    Not a pure read: it rolls the monthly period over first if it has lapsed. With no
    scheduler in this deployment, the user's own next request is what refills them.
    """
    return credit_service.snapshot(db, current_user)


# ---------------------------------------------------------------------------
# GET /api/me/plans  (catalogue -- no auth, nothing user-specific in it)
# ---------------------------------------------------------------------------

@router.get("/plans", response_model=PlanCatalogueResponse)
def get_plan_catalogue():
    """
    Monthly allowances per plan, so the pricing page has one source of truth rather
    than a second copy of the numbers. Prices are absent: no payment provider is wired
    up yet, and a price rendered next to a non-functional button is worse than none.
    """
    from app.core.plans import DEFAULT_PLAN
    return {"plans": all_definitions(), "default_plan": DEFAULT_PLAN.value}


# ---------------------------------------------------------------------------
# Admin / debug surface
#
# OFF unless CREDITS_ADMIN_TOKEN is set in the environment, and every call must present
# that token in X-Admin-Token. These endpoints can hand out credits and target other
# accounts by email, so they are opt-in rather than opt-out: an unset variable means a
# deployment that never enabled them cannot have them reached, even by mistake.
# ---------------------------------------------------------------------------

def _require_admin(x_admin_token: Optional[str] = Header(None)) -> None:
    expected = (os.getenv("CREDITS_ADMIN_TOKEN") or "").strip()
    if not expected:
        # 404, not 403: an endpoint that is switched off should be indistinguishable
        # from one that does not exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    if not x_admin_token or x_admin_token.strip() != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Admin-Token.",
        )


class AdminCreditsRequest(BaseModel):
    email: str = Field(description="Email of the account to modify.")
    credits_remaining: Optional[int] = Field(
        default=None, description="Force the balance. Clamped to [0, credits_total]."
    )
    plan: Optional[str] = Field(
        default=None, description="Move to 'free' | 'starter' | 'pro'."
    )
    grant_full_allowance: bool = Field(
        default=True,
        description="On a plan change, top the balance up to the new allowance.",
    )
    expire_period: bool = Field(
        default=False,
        description="Backdate credits_reset_at so the next read triggers the monthly refill.",
    )


class AdminCreditsResponse(CreditsResponse):
    email: str
    user_id: str


@router.post(
    "/admin/credits",
    response_model=AdminCreditsResponse,
    dependencies=[Depends(_require_admin)],
)
def admin_set_credits(req: AdminCreditsRequest, db: Session = Depends(get_db)):
    """
    Set a user's plan and/or balance, or expire their period, for testing.

    Order matters: the plan is applied first (it resets credits_total and may top the
    balance up), then any explicit balance, then the period expiry. That way
    {"plan": "pro", "credits_remaining": 1} means "put them on Pro, then leave them
    with 1 credit" rather than the plan change silently undoing the balance.
    """
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user with email '{req.email}'.",
        )

    credit_service.ensure_period_current(db, user)

    if req.plan is not None:
        try:
            plan = Plan(req.plan.strip().lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown plan '{req.plan}'. Valid: {[p.value for p in Plan]}",
            )
        credit_service.set_plan(db, user, plan, grant_full_allowance=req.grant_full_allowance)

    if req.credits_remaining is not None:
        credit_service.set_balance(db, user, req.credits_remaining)

    if req.expire_period:
        credit_service.expire_period_now(db, user)

    logger.info(f"Credits admin: applied {req.model_dump(exclude_none=True)} to {user.email}.")

    # Deliberately NOT snapshot(): that would roll the period over and instantly undo
    # an expire_period request before the caller ever saw it take effect.
    return {
        "email": user.email,
        "user_id": user.id,
        "plan": user.plan,
        "credits_remaining": int(user.credits_remaining or 0),
        "credits_total": int(user.credits_total or 0),
        "credits_reset_at": user.credits_reset_at,
        "credits_available": credit_service.available(db, user),
        "jobs_in_flight": credit_service.in_flight_count(db, user),
    }
