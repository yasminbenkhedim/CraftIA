"""
Authoritative Production Schemas for JobOrchestrator & WorkflowStateMachine (Upgrade 10).
Includes JobStatus (12 states), StageStatus (11 states), Job, Stage, StageAttempt, and StateTransitionEvent.
"""
import uuid
import time
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field


# ============================================================================
# STATES & ENUMS
# ============================================================================

class JobStatus(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    RETRYING = "RETRYING"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    ARCHIVED = "ARCHIVED"


class StageStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    LEASED = "LEASED"
    RUNNING = "RUNNING"
    CHECKPOINTING = "CHECKPOINTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"
    STALE = "STALE"


# ============================================================================
# STATE TRANSITION LOGGING
# ============================================================================

class StateTransitionEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:8]}")
    job_id: str
    stage_id: Optional[str] = None
    previous_state: str
    new_state: str
    reason: str = "state_transition"
    timestamp_epoch: float = Field(default_factory=time.time)
    actor: str = "orchestrator"
    attempt: int = 1
    version: str = "v1.0"
    trace_id: str = Field(default_factory=lambda: f"tr_{uuid.uuid4().hex[:8]}")


# ============================================================================
# WORKFLOW ENTITIES
# ============================================================================

class StageAttempt(BaseModel):
    attempt_id: str = Field(default_factory=lambda: f"att_{uuid.uuid4().hex[:8]}")
    attempt_number: int = 1
    worker_id: Optional[str] = None
    started_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None
    status: StageStatus = StageStatus.RUNNING
    error_summary: Optional[str] = None


class Stage(BaseModel):
    stage_id: str
    job_id: str
    stage_name: str                   # "planning", "rendering_gpu", "critic"
    stage_version: str = "v1.0"
    status: StageStatus = StageStatus.PENDING
    depends_on_stage_ids: List[str] = Field(default_factory=list)
    current_attempt: int = 0
    max_attempts: int = 3
    checkpoint_id: Optional[str] = None
    idempotency_key: str = ""
    attempts: List[StageAttempt] = Field(default_factory=list)


class Job(BaseModel):
    job_id: str = Field(default_factory=lambda: f"job_{uuid.uuid4().hex[:8]}")
    tenant_id: str = "tenant_default"
    project_title: str
    status: JobStatus = JobStatus.CREATED
    created_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None
    stages: Dict[str, Stage] = Field(default_factory=dict)
    transitions: List[StateTransitionEvent] = Field(default_factory=list)
    current_checkpoint_id: Optional[str] = None
    lock_version: int = 1
