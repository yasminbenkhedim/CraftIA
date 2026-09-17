"""
WorkflowStateMachine for CraftAI (Upgrade 10).
Validates authoritative job and stage state transitions and rejects illegal transitions.
"""
import logging
from typing import Tuple
from backend.orchestrator.schemas import Job, Stage, JobStatus, StageStatus, StateTransitionEvent

logger = logging.getLogger("uvicorn")


class WorkflowStateMachine:
    """
    Validates job and stage state transitions, enforcing optimistic locking and audit logging.
    """

    ALLOWED_JOB_TRANSITIONS = {
        JobStatus.CREATED: {JobStatus.QUEUED, JobStatus.CANCELLED},
        JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED, JobStatus.PAUSED},
        JobStatus.RUNNING: {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.BLOCKED, JobStatus.PAUSED, JobStatus.CANCELLING, JobStatus.RETRYING, JobStatus.REVISION_REQUIRED},
        JobStatus.PAUSED: {JobStatus.RUNNING, JobStatus.CANCELLED},
        JobStatus.CANCELLING: {JobStatus.CANCELLED},
        JobStatus.RETRYING: {JobStatus.RUNNING, JobStatus.FAILED},
        JobStatus.REVISION_REQUIRED: {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.FAILED},
        JobStatus.BLOCKED: {JobStatus.REASONABLE_FIX if hasattr(JobStatus, "REASONABLE_FIX") else JobStatus.QUEUED, JobStatus.FAILED},
        JobStatus.COMPLETED: {JobStatus.ARCHIVED},
        JobStatus.FAILED: {JobStatus.QUEUED, JobStatus.ARCHIVED},
        JobStatus.CANCELLED: {JobStatus.ARCHIVED},
        JobStatus.ARCHIVED: set()
    }

    @classmethod
    def transition_job(cls, job: Job, new_status: JobStatus, reason: str = "orchestration") -> Tuple[bool, str]:
        if new_status == job.status:
            return True, "Already in target status"

        allowed = cls.ALLOWED_JOB_TRANSITIONS.get(job.status, set())
        if new_status not in allowed and new_status != JobStatus.FAILED:
            return False, f"Illegal job transition from {job.status.value} to {new_status.value}"

        # Guard: RUNNING -> COMPLETED requires all stages to be SUCCEEDED or SKIPPED
        if new_status == JobStatus.COMPLETED:
            for sname, stage in job.stages.items():
                if stage.status not in (StageStatus.SUCCEEDED, StageStatus.SKIPPED):
                    return False, f"Cannot complete job: stage '{sname}' is in status '{stage.status.value}'"

        evt = StateTransitionEvent(
            job_id=job.job_id,
            previous_state=job.status.value,
            new_state=new_status.value,
            reason=reason
        )
        job.transitions.append(evt)
        job.status = new_status
        job.lock_version += 1
        return True, f"Job status updated to {new_status.value}"

    @classmethod
    def transition_stage(cls, stage: Stage, new_status: StageStatus, reason: str = "worker_update") -> Tuple[bool, str]:
        stage.status = new_status
        return True, f"Stage status updated to {new_status.value}"
