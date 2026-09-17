"""
Production SQLAlchemy ORM Models for CraftAI Upgrade 10.

Integrates with the existing CraftAI database layer:
- Existing component: app.core.database.Base (SQLAlchemy declarative base)
- Existing component: app.core.database.SessionLocal (session factory)
- Existing component: app.core.database.engine (PostgreSQL with SQLite fallback)

These models extend the existing database schema (Job, User, AgentExecutionLog)
with production orchestration tables for distributed rendering.

All tables are created via Base.metadata.create_all() in app.core.database.init_db().
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, JSON, Index, UniqueConstraint
)
from app.core.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class ProductionJob(Base):
    """
    Authoritative job state in PostgreSQL.
    Replaces the in-memory Dict[str, Job] from backend/orchestrator/job_orchestrator.py.
    """
    __tablename__ = "production_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False)
    prompt = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="CREATED")
    priority = Column(Integer, default=5)
    lock_version = Column(Integer, default=0)
    trace_id = Column(String(64))
    config_hash = Column(String(64))
    total_stages = Column(Integer, default=0)
    completed_stages = Column(Integer, default=0)
    error_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class ProductionStage(Base):
    """
    Per-stage tracking with dependency graph, retry state, and artifact references.
    Replaces the in-memory stage tracking in orchestrator schemas.
    """
    __tablename__ = "production_stages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("production_jobs.id"), nullable=False, index=True)
    stage_name = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    queue_name = Column(String(64), nullable=False)
    depends_on = Column(JSON, nullable=True)
    attempt_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry_at = Column(DateTime, nullable=True)
    worker_id = Column(String(64), nullable=True)
    idempotency_key = Column(String(64), unique=True)
    input_artifact_ids = Column(JSON, nullable=True)
    output_artifact_ids = Column(JSON, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    error_summary = Column(Text, nullable=True)
    failure_class = Column(String(32), nullable=True)
    trace_id = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_production_stages_job_stage", "job_id", "stage_name"),
    )


class OutboxEvent(Base):
    """
    Transactional outbox for guaranteed at-least-once event delivery.
    Replaces the in-memory List[OutboxEvent] from backend/orchestrator/outbox.py.
    Events are inserted in the same DB transaction as state changes,
    then published to Celery by a background poller.
    """
    __tablename__ = "outbox_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), nullable=False, index=True)
    stage_id = Column(String(36), nullable=True)
    event_type = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    published = Column(Boolean, default=False, index=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class GPULease(Base):
    """
    GPU device lease tracking in PostgreSQL.
    Replaces the in-memory Dict[str, GPULease] from backend/scheduler/gpu_leases.py.
    Uses SELECT FOR UPDATE to prevent concurrent acquisition of the same device.
    """
    __tablename__ = "gpu_leases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    device_id = Column(String(128), nullable=False, index=True)
    worker_id = Column(String(64), nullable=False)
    job_id = Column(String(36), nullable=False)
    stage_id = Column(String(36), nullable=False)
    reserved_memory_mb = Column(Integer, default=4096)
    acquired_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    released = Column(Boolean, default=False)


class WorkerRegistration(Base):
    """
    Worker lifecycle tracking in PostgreSQL.
    Replaces the in-memory Dict[str, WorkerRecord] from backend/workers/base_worker.py.
    """
    __tablename__ = "worker_registrations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    worker_role = Column(String(64), nullable=False)
    hostname = Column(String(255))
    state = Column(String(32), default="STARTING")
    gpu_count = Column(Integer, default=0)
    last_heartbeat = Column(DateTime, default=datetime.utcnow, index=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    deregistered_at = Column(DateTime, nullable=True)


class CheckpointRecord(Base):
    """
    Scene-level checkpoint persistence for resumable rendering.
    Replaces the in-memory Dict from backend/checkpoints/checkpoint_manager.py.
    """
    __tablename__ = "checkpoint_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("production_jobs.id"), nullable=False, index=True)
    stage_id = Column(String(36), nullable=False)
    scene_id = Column(String(64), nullable=True)
    checkpoint_type = Column(String(32), nullable=False)
    artifact_hash = Column(String(64), nullable=False)
    status = Column(String(32), default="VALID")
    tenant_id = Column(String(64), nullable=False)
    code_version = Column(String(32))
    parent_checkpoint_id = Column(String(36), ForeignKey("checkpoint_records.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ArtifactRecord(Base):
    """
    Content-addressed artifact metadata in PostgreSQL.
    Replaces the in-memory Dict[str, bytes] from backend/artifacts/store.py.
    Actual binary content stored on filesystem; this table tracks metadata.
    """
    __tablename__ = "artifact_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    content_hash = Column(String(64), nullable=False, index=True, unique=True)
    storage_path = Column(String(512), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    content_type = Column(String(128))
    tenant_id = Column(String(64), nullable=False, index=True)
    produced_by_stage_id = Column(String(36), nullable=True)
    retention_class = Column(String(32), default="standard")
    expires_at = Column(DateTime, nullable=True)
    reference_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class ArtifactAlias(Base):
    """
    Mutable alias pointers to immutable content-addressed artifacts.
    """
    __tablename__ = "artifact_aliases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    alias_name = Column(String(255), nullable=False)
    tenant_id = Column(String(64), nullable=False)
    content_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("alias_name", "tenant_id", name="uq_artifact_alias_tenant"),
    )


class DeadLetterRecord(Base):
    """
    Dead letter queue entries persisted in PostgreSQL.
    Replaces the in-memory Dict from backend/scheduler/dead_letter.py.
    """
    __tablename__ = "dead_letter_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), nullable=False)
    stage_id = Column(String(36), nullable=False)
    failure_class = Column(String(32), nullable=False)
    error_summary = Column(Text)
    attempt_history = Column(JSON)
    recovery_guidance = Column(Text, nullable=True)
    replayed = Column(Boolean, default=False)
    replayed_at = Column(DateTime, nullable=True)
    replay_audit_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditEvent(Base):
    """
    Security and governance audit trail persisted in PostgreSQL.
    """
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_type = Column(String(64), nullable=False, index=True)
    actor = Column(String(128), nullable=False)
    resource_type = Column(String(64))
    resource_id = Column(String(128))
    action = Column(String(64))
    result = Column(String(32))
    details = Column(JSON, nullable=True)
    trace_id = Column(String(64))
    tenant_id = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class TenantQuota(Base):
    """
    Multi-tenant quota enforcement persisted in PostgreSQL.
    Replaces the in-memory dicts from backend/security/tenant_context.py.
    """
    __tablename__ = "tenant_quotas"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(64), nullable=False, unique=True, index=True)
    max_concurrent_jobs = Column(Integer, default=10)
    max_queued_jobs = Column(Integer, default=50)
    gpu_minutes_quota = Column(Integer, default=600)
    storage_quota_gb = Column(Float, default=100.0)
    daily_render_quota = Column(Integer, default=100)
    priority_class = Column(String(32), default="standard")
    used_concurrent_jobs = Column(Integer, default=0)
    used_gpu_minutes = Column(Float, default=0.0)
    weight = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
