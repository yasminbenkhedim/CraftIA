"""
Transactional Outbox for CraftAI (Upgrade 10).

Replaces the in-memory List[OutboxEvent] with a PostgreSQL-backed
transactional outbox pattern.

Existing components used:
- app.core.database.SessionLocal (DB session factory)
- backend.orchestrator.models.OutboxEvent (SQLAlchemy model)
- backend.celery_app (Celery app for task dispatch)

The outbox guarantees at-least-once delivery:
1. Events are inserted in the same DB transaction as state changes
2. A background poller reads unpublished events
3. Events are dispatched to Celery
4. On success, events are marked as published
"""
import logging
import time
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger("uvicorn")


class TransactionalOutboxDispatcher:
    """
    Polls the outbox_events table for unpublished events and dispatches
    them to Celery task queues.

    This replaces the in-memory outbox.dispatch_all() that only flipped
    a boolean flag.
    """

    @staticmethod
    def poll_and_dispatch(batch_size: int = 50) -> int:
        """
        Poll for unpublished outbox events and dispatch to Celery.
        Returns the number of events dispatched.
        """
        from backend.app.core.database import SessionLocal
        from backend.orchestrator.models import OutboxEvent

        session = SessionLocal()
        dispatched_count = 0

        try:
            # Fetch unpublished events ordered by creation time
            events = session.query(OutboxEvent).filter(
                OutboxEvent.published == False
            ).order_by(OutboxEvent.created_at).limit(batch_size).all()

            for event in events:
                try:
                    success = TransactionalOutboxDispatcher._dispatch_event(event)
                    if success:
                        event.published = True
                        event.published_at = datetime.utcnow()
                        dispatched_count += 1
                except Exception as e:
                    logger.error(f"Outbox dispatch failed for event {event.id}: {e}")
                    continue

            if dispatched_count > 0:
                session.commit()
                logger.info(f"Outbox: Dispatched {dispatched_count}/{len(events)} events")

            return dispatched_count

        except Exception as e:
            session.rollback()
            logger.error(f"Outbox poll failed: {e}")
            return 0
        finally:
            session.close()

    @staticmethod
    def _dispatch_event(event) -> bool:
        """Dispatch a single outbox event to the appropriate Celery queue."""
        event_type = event.event_type
        payload = event.payload or {}

        if event_type == "STAGE_DISPATCH":
            return TransactionalOutboxDispatcher._dispatch_stage(payload)
        elif event_type == "JOB_CREATED":
            logger.info(f"Job created event: job_id={payload.get('job_id')}")
            # Dispatch the first stages (no dependencies)
            first_stages = payload.get("first_stages", [])
            for stage_id in first_stages:
                TransactionalOutboxDispatcher._dispatch_stage({
                    "job_id": payload.get("job_id"),
                    "stage_id": stage_id,
                    "stage_name": "planning",
                    "queue_name": "planning",
                    "priority": payload.get("priority", 5),
                })
            return True
        elif event_type == "JOB_STATUS_CHANGED":
            logger.info(
                f"Job status changed: job_id={payload.get('job_id')} "
                f"{payload.get('old_status')} -> {payload.get('new_status')}"
            )
            return True
        else:
            logger.warning(f"Unknown outbox event type: {event_type}")
            return True

    @staticmethod
    def _dispatch_stage(payload: Dict[str, Any]) -> bool:
        """Dispatch a stage execution task to Celery."""
        stage_name = payload.get("stage_name", "")
        job_id = payload.get("job_id", "")
        stage_id = payload.get("stage_id", "")
        queue_name = payload.get("queue_name", stage_name)
        priority = payload.get("priority", 5)

        # Build task context for the worker
        task_context = {
            "attempt": 1,
            "input_artifact_refs": payload.get("input_artifact_refs", {}),
            "config_hash": payload.get("config_hash", ""),
            "trace_id": payload.get("trace_id", ""),
            "tenant_id": payload.get("tenant_id", "default"),
            "cancelled": False,
        }

        # Map stage name to Celery task name
        task_name_map = {
            "planning": "backend.tasks.stage_tasks.execute_planning",
            "asset_retrieval": "backend.tasks.stage_tasks.execute_asset_retrieval",
            "scene_graph": "backend.tasks.stage_tasks.execute_scene_graph",
            "motion_graphics": "backend.tasks.stage_tasks.execute_motion_graphics",
            "audio": "backend.tasks.stage_tasks.execute_audio",
            "rendering": "backend.tasks.stage_tasks.execute_rendering",
            "critic": "backend.tasks.stage_tasks.execute_critic",
            "revision": "backend.tasks.stage_tasks.execute_revision",
            "export": "backend.tasks.stage_tasks.execute_export",
            "cleanup": "backend.tasks.stage_tasks.execute_cleanup",
        }

        task_name = task_name_map.get(stage_name)
        if not task_name:
            logger.warning(f"No Celery task for stage: {stage_name}")
            return False

        try:
            from backend.celery_app import app as celery_app
            celery_app.send_task(
                task_name,
                args=[job_id, stage_id, task_context],
                queue=queue_name,
                priority=priority,
            )
            logger.info(f"Dispatched {stage_name} to Celery: job={job_id} stage={stage_id}")
            return True
        except Exception as e:
            # Celery not available — execute synchronously for local dev
            logger.warning(f"Celery dispatch failed, executing synchronously: {e}")
            try:
                from backend.tasks.stage_tasks import _execute_stage_task
                _execute_stage_task(stage_name, job_id, stage_id, task_context)
                return True
            except Exception as sync_err:
                logger.error(f"Synchronous execution also failed: {sync_err}")
                return False
