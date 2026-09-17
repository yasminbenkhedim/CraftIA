"""
Production Job Orchestrator for CraftAI (Upgrade 10).

Manages job lifecycle using PostgreSQL as the authoritative state store.

Existing components used:
- app.core.database.SessionLocal (DB session factory)
- backend.orchestrator.models (ProductionJob, ProductionStage, OutboxEvent)
- backend.orchestrator.state_machine.WorkflowStateMachine (transition validation)
"""
import uuid
import time
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("uvicorn")

# Pipeline stage definitions with dependency ordering
PIPELINE_STAGES = [
    {"name": "planning", "queue": "planning", "depends_on": []},
    {"name": "asset_retrieval", "queue": "asset_retrieval", "depends_on": ["planning"]},
    {"name": "scene_graph", "queue": "scene_graph", "depends_on": ["planning"]},
    {"name": "motion_graphics", "queue": "motion_graphics", "depends_on": ["scene_graph"]},
    {"name": "audio", "queue": "audio", "depends_on": ["planning"]},
    {"name": "rendering", "queue": "rendering_gpu", "depends_on": ["asset_retrieval", "scene_graph", "motion_graphics", "audio"]},
    {"name": "critic", "queue": "critic", "depends_on": ["rendering"]},
    {"name": "revision", "queue": "revision", "depends_on": ["critic"]},
    {"name": "export", "queue": "export", "depends_on": ["rendering", "revision"]},
    {"name": "cleanup", "queue": "cleanup", "depends_on": ["export"]},
]


class ProductionJobOrchestrator:
    """
    Production job orchestrator backed by PostgreSQL.

    Replaces the in-memory Dict[str, Job] from the original job_orchestrator.py.
    All state transitions are transactional with outbox event publication.
    """

    @staticmethod
    def create_job(
        tenant_id: str,
        user_id: str,
        prompt: str,
        priority: int = 5,
        trace_id: str = "",
        input_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new production job with all pipeline stages in PostgreSQL."""
        from backend.app.core.database import SessionLocal
        from backend.orchestrator.models import ProductionJob, ProductionStage, OutboxEvent

        session = SessionLocal()
        try:
            job_id = str(uuid.uuid4())
            trace_id = trace_id or str(uuid.uuid4())
            config_hash = hashlib.sha256(str(input_config or {}).encode()).hexdigest()[:16]

            # Create job
            job = ProductionJob(
                id=job_id,
                tenant_id=tenant_id,
                user_id=user_id,
                prompt=prompt,
                status="QUEUED",
                priority=priority,
                trace_id=trace_id,
                config_hash=config_hash,
                total_stages=len(PIPELINE_STAGES),
                completed_stages=0,
            )
            session.add(job)

            # Create all pipeline stages
            stage_id_map = {}
            for stage_def in PIPELINE_STAGES:
                stage_id = str(uuid.uuid4())
                stage_id_map[stage_def["name"]] = stage_id

                # Resolve dependency stage IDs
                depends_on_ids = [stage_id_map[dep] for dep in stage_def["depends_on"] if dep in stage_id_map]

                # Generate idempotency key
                idem_key = hashlib.sha256(
                    f"{job_id}:{stage_def['name']}:1".encode()
                ).hexdigest()

                stage = ProductionStage(
                    id=stage_id,
                    job_id=job_id,
                    stage_name=stage_def["name"],
                    status="PENDING",
                    queue_name=stage_def["queue"],
                    depends_on=depends_on_ids if depends_on_ids else None,
                    idempotency_key=idem_key,
                    trace_id=trace_id,
                )
                session.add(stage)

            # Record outbox event — dispatched to Celery by background poller
            outbox_event = OutboxEvent(
                id=str(uuid.uuid4()),
                job_id=job_id,
                event_type="JOB_CREATED",
                payload={
                    "job_id": job_id,
                    "tenant_id": tenant_id,
                    "priority": priority,
                    "stage_count": len(PIPELINE_STAGES),
                    "first_stages": [stage_id_map["planning"]],
                },
            )
            session.add(outbox_event)

            # Commit atomically: job + stages + outbox event
            session.commit()

            logger.info(
                f"ProductionJobOrchestrator: Created job {job_id} "
                f"with {len(PIPELINE_STAGES)} stages, trace={trace_id}"
            )

            return {
                "job_id": job_id,
                "status": "QUEUED",
                "trace_id": trace_id,
                "total_stages": len(PIPELINE_STAGES),
                "stage_ids": stage_id_map,
            }

        except Exception as e:
            session.rollback()
            logger.error(f"ProductionJobOrchestrator: Failed to create job: {e}")
            raise
        finally:
            session.close()

    @staticmethod
    def get_job(job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status from PostgreSQL."""
        from backend.app.core.database import SessionLocal
        from backend.orchestrator.models import ProductionJob, ProductionStage

        session = SessionLocal()
        try:
            job = session.query(ProductionJob).filter(ProductionJob.id == job_id).first()
            if not job:
                return None

            stages = session.query(ProductionStage).filter(
                ProductionStage.job_id == job_id
            ).all()

            return {
                "job_id": job.id,
                "tenant_id": job.tenant_id,
                "status": job.status,
                "priority": job.priority,
                "lock_version": job.lock_version,
                "trace_id": job.trace_id,
                "total_stages": job.total_stages,
                "completed_stages": job.completed_stages,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "stages": [
                    {
                        "stage_id": s.id,
                        "stage_name": s.stage_name,
                        "status": s.status,
                        "attempt_count": s.attempt_count,
                        "duration_seconds": s.duration_seconds,
                        "error_summary": s.error_summary,
                    }
                    for s in stages
                ],
            }
        finally:
            session.close()

    @staticmethod
    def transition_job_status(
        job_id: str,
        new_status: str,
        expected_lock_version: int,
        reason: str = "",
        actor: str = "system",
    ) -> bool:
        """
        Transition job status with optimistic locking.
        Returns True if transition succeeded, False if lock version conflict.
        """
        from backend.app.core.database import SessionLocal
        from backend.orchestrator.models import ProductionJob, OutboxEvent, AuditEvent

        session = SessionLocal()
        try:
            job = session.query(ProductionJob).filter(
                ProductionJob.id == job_id,
                ProductionJob.lock_version == expected_lock_version,
            ).with_for_update().first()

            if not job:
                logger.warning(
                    f"Optimistic lock conflict: job={job_id} "
                    f"expected_version={expected_lock_version}"
                )
                return False

            old_status = job.status
            job.status = new_status
            job.lock_version += 1
            job.updated_at = datetime.utcnow()

            if new_status in ("COMPLETED", "FAILED", "CANCELLED"):
                job.completed_at = datetime.utcnow()

            # Audit event
            audit = AuditEvent(
                id=str(uuid.uuid4()),
                event_type="JOB_TRANSITION",
                actor=actor,
                resource_type="ProductionJob",
                resource_id=job_id,
                action=f"{old_status}->{new_status}",
                result="SUCCESS",
                details={"reason": reason, "lock_version": job.lock_version},
                trace_id=job.trace_id,
                tenant_id=job.tenant_id,
            )
            session.add(audit)

            # Outbox event
            outbox = OutboxEvent(
                id=str(uuid.uuid4()),
                job_id=job_id,
                event_type="JOB_STATUS_CHANGED",
                payload={
                    "job_id": job_id,
                    "old_status": old_status,
                    "new_status": new_status,
                    "lock_version": job.lock_version,
                },
            )
            session.add(outbox)

            session.commit()
            logger.info(
                f"Job {job_id}: {old_status} -> {new_status} "
                f"(version={job.lock_version}, reason={reason})"
            )
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Job transition failed: {e}")
            return False
        finally:
            session.close()

    @staticmethod
    def cancel_job(job_id: str, actor: str = "user") -> bool:
        """Cancel a job and all its non-completed stages."""
        from backend.app.core.database import SessionLocal
        from backend.orchestrator.models import ProductionJob, ProductionStage

        session = SessionLocal()
        try:
            job = session.query(ProductionJob).filter(
                ProductionJob.id == job_id
            ).with_for_update().first()

            if not job or job.status in ("COMPLETED", "CANCELLED", "FAILED"):
                return False

            job.status = "CANCELLING"
            job.lock_version += 1
            job.updated_at = datetime.utcnow()

            # Cancel all pending/running stages
            pending_stages = session.query(ProductionStage).filter(
                ProductionStage.job_id == job_id,
                ProductionStage.status.in_(["PENDING", "QUEUED", "RUNNING"]),
            ).all()

            for stage in pending_stages:
                stage.status = "CANCELLED"
                stage.updated_at = datetime.utcnow()

            session.commit()
            logger.info(f"Job {job_id} cancelled by {actor}, {len(pending_stages)} stages cancelled")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Job cancellation failed: {e}")
            return False
        finally:
            session.close()

    @staticmethod
    def dispatch_ready_stages(job_id: str) -> List[str]:
        """
        Find stages whose dependencies are all SUCCEEDED and dispatch them.
        Returns list of dispatched stage IDs.
        """
        from backend.app.core.database import SessionLocal
        from backend.orchestrator.models import ProductionStage, OutboxEvent

        session = SessionLocal()
        dispatched = []
        try:
            stages = session.query(ProductionStage).filter(
                ProductionStage.job_id == job_id,
            ).all()

            stage_status_map = {s.id: s.status for s in stages}

            for stage in stages:
                if stage.status != "PENDING":
                    continue

                # Check if all dependencies are SUCCEEDED
                deps = stage.depends_on or []
                all_deps_met = all(
                    stage_status_map.get(dep_id) == "SUCCEEDED"
                    for dep_id in deps
                )

                if all_deps_met:
                    stage.status = "QUEUED"
                    stage.updated_at = datetime.utcnow()

                    # Create outbox event for Celery dispatch
                    outbox = OutboxEvent(
                        id=str(uuid.uuid4()),
                        job_id=job_id,
                        stage_id=stage.id,
                        event_type="STAGE_DISPATCH",
                        payload={
                            "job_id": job_id,
                            "stage_id": stage.id,
                            "stage_name": stage.stage_name,
                            "queue_name": stage.queue_name,
                            "priority": 5,
                        },
                    )
                    session.add(outbox)
                    dispatched.append(stage.id)

            if dispatched:
                session.commit()
                logger.info(f"Dispatched {len(dispatched)} stages for job {job_id}")

            return dispatched

        except Exception as e:
            session.rollback()
            logger.error(f"Stage dispatch failed: {e}")
            return []
        finally:
            session.close()
