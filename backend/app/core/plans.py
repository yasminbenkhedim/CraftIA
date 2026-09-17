"""
Subscription plans and their monthly credit allowances.

This is deliberately a plain config table rather than database rows: plans change by
deploying a new allowance, not by an admin editing records, and keeping them in code
means the values are reviewable in a diff. Prices are absent on purpose -- no payment
provider is integrated yet, and a price sitting in the code with nothing charging it
is the kind of thing that later gets mistaken for the real one. Add TND pricing here
when a provider is actually wired up.

Changing an allowance affects a user the next time their monthly period rolls over,
or immediately if an admin moves them to a different plan (see credits.set_plan).
"""
from enum import Enum
from typing import Dict, NamedTuple


class Plan(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"


class PlanDefinition(NamedTuple):
    plan: Plan
    label: str
    monthly_credits: int


PLANS: Dict[Plan, PlanDefinition] = {
    Plan.FREE: PlanDefinition(Plan.FREE, "Free", 3),
    Plan.STARTER: PlanDefinition(Plan.STARTER, "Starter", 30),
    Plan.PRO: PlanDefinition(Plan.PRO, "Pro", 100),
}

DEFAULT_PLAN = Plan.FREE

# One credit buys one successfully delivered artifact, whatever the agent. A video
# costs far more compute than a slide deck, so this will likely need to differ per
# agent later -- when it does, this is the constant to replace with a lookup.
CREDIT_COST_PER_JOB = 1


def normalize(value: object) -> Plan:
    """
    Coerce a stored or user-supplied plan name to a real Plan.

    Falls back to FREE rather than raising: a row written by an older build, or a typo
    in an admin call, must not make a user's account unloadable. The caller that cares
    about rejecting bad input (the admin endpoint) validates before calling.
    """
    if isinstance(value, Plan):
        return value
    try:
        return Plan(str(value).strip().lower())
    except (ValueError, AttributeError):
        return DEFAULT_PLAN


def definition(value: object) -> PlanDefinition:
    return PLANS[normalize(value)]


def monthly_credits(value: object) -> int:
    return definition(value).monthly_credits


def all_definitions() -> Dict[str, int]:
    """{'free': 3, 'starter': 30, 'pro': 100} -- for the pricing page and debug output."""
    return {p.value: d.monthly_credits for p, d in PLANS.items()}
