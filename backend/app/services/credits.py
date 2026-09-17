"""
Credit accounting -- the only module that reads or writes a user's credit columns.

Two rules drive the design, and they pull in opposite directions:

  1. A credit is spent only when a job COMPLETES successfully. A render that crashes,
     or one the artifact validator rejects, must cost the user nothing. So the debit
     lives at the completion gate in the workflow, not at job creation.

  2. A user must not be able to run more jobs than they can pay for.

Debiting only on success means the balance alone does not reflect work already in
flight: a user with 1 credit could submit five jobs in the same second, all five would
see credits_remaining == 1 at creation, and all five would complete. So the admission
check spends against *available* credits -- the balance minus the jobs already queued
or running (see available()). Nothing is reserved and nothing needs refunding; a failed
job simply drops out of the in-flight count and the credit was never taken.

Monthly reset is lazy rather than scheduled. There is no cron in this deployment, and a
user whose period lapsed while they were away should get their credits the moment they
come back, not whenever a scheduler next fires. Every read path calls
ensure_period_current() first, so the refill happens on the next request either way.
"""
import logging
from calendar import monthrange
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.plans import CREDIT_COST_PER_JOB, Plan, monthly_credits, normalize
from app.models.job import Job, JobStatus
from app.models.user import User

logger = logging.getLogger("uvicorn")

# Statuses that represent work already accepted but not yet paid for. A job in one of
# these will, if it succeeds, take a credit -- so it must count against the balance now.
IN_FLIGHT_STATUSES = (JobStatus.QUEUED.value, JobStatus.RUNNING.value)

# Guards the catch-up loop in ensure_period_current(). A dormant account is refilled
# once and its period is advanced to the present; without a bound, a reset_at from the
# distant past (or a clock jump) would spin.
_MAX_PERIOD_CATCHUP = 240  # 20 years of monthly periods


def add_one_month(moment: datetime) -> datetime:
    """
    Same day next month, clamped to the last valid day.

    Written out rather than pulled from dateutil because it is six lines and adding a
    dependency for it is not worth it. The clamp is the whole point: a user who signs up
    on 31 January has a period ending 28 February, not a ValueError.
    """
    year = moment.year + (1 if moment.month == 12 else 0)
    month = 1 if moment.month == 12 else moment.month + 1
    day = min(moment.day, monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def ensure_period_current(db: Session, user: User, now: Optional[datetime] = None) -> bool:
    """
    Roll the user's allowance forward if their period has lapsed. Returns True if it did.

    Also repairs the two states an older row can be in: a NULL reset_at (the column
    predates that account) and a credits_total that no longer matches the plan. Commits
    only when something actually changed, so read endpoints stay read-only in the
    common case.
    """
    now = now or datetime.utcnow()
    changed = False

    plan = normalize(user.plan)
    allowance = monthly_credits(plan)

    # Normalize a row written before credits existed, or by a build with a different
    # allowance for this plan.
    if user.plan != plan.value:
        user.plan = plan.value
        changed = True
    if user.credits_total != allowance:
        user.credits_total = allowance
        changed = True

    if user.credits_reset_at is None:
        # First contact for a pre-credits account: grant the allowance and start a
        # period from now.
        user.credits_remaining = allowance
        user.credits_reset_at = add_one_month(now)
        logger.info(
            f"Credits: initialised account {user.id} on plan '{plan.value}' "
            f"-- {allowance} credits, period ends {user.credits_reset_at.isoformat()}Z"
        )
        db.commit()
        return True

    if now >= user.credits_reset_at:
        periods = 0
        reset_at = user.credits_reset_at
        while now >= reset_at and periods < _MAX_PERIOD_CATCHUP:
            reset_at = add_one_month(reset_at)
            periods += 1
        # Credits do not accumulate across skipped months -- an allowance is per period,
        # so a user returning after six months gets one month's worth, not six.
        user.credits_remaining = allowance
        user.credits_reset_at = reset_at
        logger.info(
            f"Credits: monthly reset for {user.id} ({plan.value}) -- refilled to "
            f"{allowance}, {periods} period(s) advanced, next reset "
            f"{reset_at.isoformat()}Z"
        )
        changed = True

    if changed:
        db.commit()
        db.refresh(user)
    return changed


def in_flight_count(db: Session, user: User) -> int:
    """Jobs already accepted for this user that have not yet succeeded or failed."""
    return (
        db.query(Job)
        .filter(Job.user_id == user.id, Job.status.in_(IN_FLIGHT_STATUSES))
        .count()
    )


def available(db: Session, user: User) -> int:
    """
    Credits this user can still commit to NEW work.

    Balance minus in-flight jobs. This is what admission checks against; the balance
    itself is what the UI shows, because a user should see the credits they still hold,
    not a number that dips while a render is running and pops back if it fails.
    """
    return max(0, int(user.credits_remaining or 0) - in_flight_count(db, user) * CREDIT_COST_PER_JOB)


def can_start_job(db: Session, user: User) -> bool:
    ensure_period_current(db, user)
    return available(db, user) >= CREDIT_COST_PER_JOB


def consume_for_completed_job(db: Session, user_id: str, job_id: str) -> bool:
    """
    Debit one credit for a job that has just succeeded. Returns True if a credit was taken.

    Called from the workflow's completion gate, inside the same transaction that marks
    the job COMPLETED -- so a job is never delivered without being charged, and never
    charged without being delivered.

    Best-effort by design: a user row that has gone missing must not turn a finished
    render into a failed job. The balance floors at zero rather than going negative;
    reaching this with a zero balance means admission was bypassed (an admin set the
    balance mid-render, say), and the user keeps the artifact they were already promised.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"Credits: job {job_id} completed for unknown user '{user_id}' -- not charged.")
        return False

    before = int(user.credits_remaining or 0)
    if before <= 0:
        logger.warning(
            f"Credits: job {job_id} completed for {user_id} with a {before}-credit balance. "
            f"Delivering it anyway and leaving the balance at 0 -- admission should have "
            f"blocked this, so check for a manual balance change during the render."
        )
        user.credits_remaining = 0
        return False

    user.credits_remaining = before - CREDIT_COST_PER_JOB
    logger.info(
        f"Credits: charged {CREDIT_COST_PER_JOB} to {user_id} for completed job {job_id} "
        f"-- {before} -> {user.credits_remaining} remaining."
    )
    return True


def set_plan(db: Session, user: User, plan: Plan, grant_full_allowance: bool = True) -> User:
    """
    Move a user to another plan. Used by the admin/debug endpoint today, and by whatever
    checkout flow eventually replaces it.
    """
    allowance = monthly_credits(plan)
    user.plan = plan.value
    user.credits_total = allowance
    if grant_full_allowance:
        user.credits_remaining = allowance
    else:
        # Never leave a balance above the new plan's ceiling after a downgrade.
        user.credits_remaining = min(int(user.credits_remaining or 0), allowance)
    if user.credits_reset_at is None:
        user.credits_reset_at = add_one_month(datetime.utcnow())
    db.commit()
    db.refresh(user)
    logger.info(
        f"Credits: {user.id} moved to plan '{plan.value}' "
        f"({user.credits_remaining}/{user.credits_total} credits)."
    )
    return user


def set_balance(db: Session, user: User, credits_remaining: int) -> User:
    """Force a balance. Test/admin only -- clamped to [0, credits_total]."""
    ensure_period_current(db, user)
    ceiling = int(user.credits_total or monthly_credits(user.plan))
    user.credits_remaining = max(0, min(int(credits_remaining), ceiling))
    db.commit()
    db.refresh(user)
    logger.info(f"Credits: balance for {user.id} manually set to {user.credits_remaining}/{ceiling}.")
    return user


def expire_period_now(db: Session, user: User) -> User:
    """
    Backdate the period end so the next read triggers a monthly reset.

    Test/admin only. It exists because the reset is the one rule that cannot otherwise
    be exercised without waiting a month or editing the database by hand.
    """
    user.credits_reset_at = datetime.utcnow().replace(microsecond=0)
    db.commit()
    db.refresh(user)
    logger.info(f"Credits: period for {user.id} backdated -- next read will refill.")
    return user


def snapshot(db: Session, user: User) -> Dict[str, object]:
    """The payload behind GET /api/me/credits. Rolls the period over first."""
    ensure_period_current(db, user)
    return {
        "plan": normalize(user.plan).value,
        "credits_remaining": int(user.credits_remaining or 0),
        "credits_total": int(user.credits_total or 0),
        "credits_reset_at": user.credits_reset_at,
        # Distinct from credits_remaining whenever a render is in flight. The UI needs
        # it to explain a Generate button that is disabled while the balance still
        # reads 1.
        "credits_available": available(db, user),
        "jobs_in_flight": in_flight_count(db, user),
    }
