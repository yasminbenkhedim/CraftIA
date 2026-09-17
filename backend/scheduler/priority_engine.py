"""
Global Job Priority Engine for CraftAI (Upgrade 11).

Supports 5 Enterprise Priority Tiers:
- CRITICAL (10): Immediate preemption & dedicated queue
- HIGH (8): Expedited SLA scheduling
- NORMAL (5): Standard production render pipeline
- LOW (2): Batch / off-peak processing
- BACKGROUND (1): Low-priority background asset indexing / cleanup

Features:
- Dynamic Aging Algorithm ($P_{effective} = P_{base} + \lfloor \frac{t_{wait}}{60} \rfloor$) preventing starvation
- Weighted fair scheduling per tenant
- SLA-aware scheduling calculating remaining time-to-SLA
- Hard deadline scheduling with automatic emergency priority escalation
"""
import math
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger("uvicorn")


class PriorityTier:
    CRITICAL = 10
    HIGH = 8
    NORMAL = 5
    LOW = 2
    BACKGROUND = 1

    TIER_MAP = {
        "critical": CRITICAL,
        "high": HIGH,
        "normal": NORMAL,
        "low": LOW,
        "background": BACKGROUND,
    }


class GlobalPriorityEngine:
    """Enterprise 5-Tier Priority Scheduler."""

    AGING_INTERVAL_SEC = 60      # Age by +1 priority every 60s waiting
    MAX_AGED_PRIORITY = 15       # Priority cap after aging escalation

    @staticmethod
    def calculate_effective_priority(
        base_priority: int,
        created_at: datetime,
        tenant_weight: float = 1.0,
        sla_deadline: Optional[datetime] = None,
        hard_deadline: Optional[datetime] = None
    ) -> float:
        """
        Calculate dynamic effective priority considering:
        - Base priority tier
        - Wait time aging
        - Tenant weight modifier
        - SLA time urgency
        - Hard completion deadline
        """
        now = datetime.utcnow()
        if created_at.tzinfo is not None:
            created_at = created_at.replace(tzinfo=None)

        if sla_deadline and sla_deadline.tzinfo is not None:
            sla_deadline = sla_deadline.replace(tzinfo=None)

        if hard_deadline and hard_deadline.tzinfo is not None:
            hard_deadline = hard_deadline.replace(tzinfo=None)

        # Wait time calculation
        wait_seconds = max((now - created_at).total_seconds(), 0)
        aging_boost = math.floor(wait_seconds / GlobalPriorityEngine.AGING_INTERVAL_SEC)

        # Base effective score
        effective = base_priority + aging_boost

        # Tenant weight scaling
        effective *= max(tenant_weight, 0.1)

        # SLA Urgency scaling (if remaining SLA < 15 mins, boost priority)
        if sla_deadline:
            remaining_sla = (sla_deadline - now).total_seconds()
            if remaining_sla < 900:  # 15 minutes
                urgency = (900 - max(remaining_sla, 0)) / 100
                effective += urgency

        # Hard Deadline Emergency Escalation
        if hard_deadline:
            remaining_deadline = (hard_deadline - now).total_seconds()
            if remaining_deadline <= 0:
                # Deadline missed — force maximum priority or emergency handling
                effective = float(GlobalPriorityEngine.MAX_AGED_PRIORITY * 2)
            elif remaining_deadline < 1800:  # 30 mins
                effective += 5.0

        return min(effective, float(GlobalPriorityEngine.MAX_AGED_PRIORITY * 2))

    @staticmethod
    def rank_and_select_jobs(jobs: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        """
        Rank a list of pending job dictionaries by effective priority and FIFO ordering.
        Returns top `limit` candidate jobs for worker assignment.
        """
        ranked = []
        for job in jobs:
            base_p = job.get("priority", PriorityTier.NORMAL)
            if isinstance(base_p, str):
                base_p = PriorityTier.TIER_MAP.get(base_p.lower(), PriorityTier.NORMAL)

            created_at = job.get("created_at")
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except Exception:
                    created_at = datetime.utcnow()
            elif not isinstance(created_at, datetime):
                created_at = datetime.utcnow()

            tenant_weight = job.get("tenant_weight", 1.0)
            sla = job.get("sla_deadline")
            deadline = job.get("hard_deadline")

            score = GlobalPriorityEngine.calculate_effective_priority(
                base_priority=base_p,
                created_at=created_at,
                tenant_weight=tenant_weight,
                sla_deadline=sla,
                hard_deadline=deadline
            )

            job_copy = dict(job)
            job_copy["effective_priority"] = score
            ranked.append(job_copy)

        # Sort by effective priority descending, created_at ascending (FIFO tie-breaking)
        ranked.sort(key=lambda j: (-j["effective_priority"], j.get("created_at", datetime.utcnow())))
        return ranked[:limit]

    @staticmethod
    def check_starvation_alerts(jobs: List[Dict[str, Any]], max_wait_sec: int = 600) -> List[str]:
        """Identify jobs that have exceeded maximum allowed waiting time without execution."""
        starving_ids = []
        now = datetime.utcnow()

        for job in jobs:
            created_at = job.get("created_at")
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except Exception:
                    continue
            if isinstance(created_at, datetime):
                if (now - created_at).total_seconds() > max_wait_sec:
                    job_id = job.get("id") or job.get("job_id")
                    if job_id:
                        starving_ids.append(job_id)
                        logger.warning(f"Starvation Alert: Job {job_id} waiting for >{max_wait_sec}s")

        return starving_ids
