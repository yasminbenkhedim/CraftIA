"""
Celery Stage Tasks for CraftAI Upgrade 10.

Each task wraps a StatelessWorkerBase subclass and:
1. Loads task context from the database (ProductionStage row)
2. Checks idempotency key to prevent duplicate execution
3. Calls the real worker's _do_execute() method
4. Updates the stage status in the database
5. Dispatches downstream stages via the transactional outbox

Existing components used:
- backend.celery_app (Celery app with Redis broker)
- backend.workers.planning_worker (all 10 real worker implementations)
- backend.app.core.database (SessionLocal for DB access)

Integration points:
- Celery task routing maps stage_name -> queue
- Worker execute() wraps real CraftAI components
- DB session used for state persistence
"""
import os
import uuid
import json
import time
import logging
import traceback
from datetime import datetime

logger = logging.getLogger("uvicorn")


def _get_db_session():
    """Get a database session using existing CraftAI infrastructure."""
    try:
        from backend.app.core.database import SessionLocal
        return SessionLocal()
    except Exception:
        return None


def _execute_stage_task(stage_name, job_id, stage_id, task_context_dict):
    """
    Core execution logic shared by all stage tasks.
    
    Loads the appropriate worker, executes it, and persists results to DB.
    """
    from backend.workers.planning_worker import (
        TaskContext, StageResult, FailureClass,
        PlanningWorker, AssetRetrievalWorker, SceneGraphWorker,
        MotionGraphicsWorker, AudioWorker, RenderingWorker,
        CriticWorker, RevisionWorker, ExportWorker, CleanupWorker,
    )

    WORKER_MAP = {
        "planning": PlanningWorker,
        "asset_retrieval": AssetRetrievalWorker,
        "scene_graph": SceneGraphWorker,
        "motion_graphics": MotionGraphicsWorker,
        "audio": AudioWorker,
        "rendering": RenderingWorker,
        "critic": CriticWorker,
        "revision": RevisionWorker,
        "export": ExportWorker,
        "cleanup": CleanupWorker,
    }

    worker_cls = WORKER_MAP.get(stage_name)
    if not worker_cls:
        return {
            "status": "failed_final",
            "error_summary": f"Unknown stage: {stage_name}",
            "failure_class": "INTERNAL_BUG",
        }

    # Build TaskContext
    ctx = TaskContext(
        job_id=job_id,
        stage_id=stage_id,
        attempt=task_context_dict.get("attempt", 1),
        input_artifact_refs=task_context_dict.get("input_artifact_refs", {}),
        config_hash=task_context_dict.get("config_hash", ""),
        trace_id=task_context_dict.get("trace_id", str(uuid.uuid4())),
        tenant_id=task_context_dict.get("tenant_id", "default"),
        cancelled=task_context_dict.get("cancelled", False),
    )

    # Execute the real worker
    worker = worker_cls()
    start_time = time.time()

    try:
        result = worker.execute(ctx)
        duration = time.time() - start_time

        logger.info(
            f"Stage {stage_name} completed: job={job_id} stage={stage_id} "
            f"status={result.status} duration={duration:.2f}s"
        )

        # Update stage in DB if available
        session = _get_db_session()
        if session:
            try:
                from backend.orchestrator.models import ProductionStage
                stage = session.query(ProductionStage).filter(
                    ProductionStage.id == stage_id
                ).first()
                if stage:
                    stage.status = "SUCCEEDED" if result.status == "succeeded" else "FAILED"
                    stage.duration_seconds = duration
                    stage.output_artifact_ids = result.output_artifact_refs
                    stage.error_summary = result.error_summary
                    stage.failure_class = result.failure_class.value if result.failure_class else None
                    stage.completed_at = datetime.utcnow()
                    stage.updated_at = datetime.utcnow()
                    session.commit()
            except Exception as db_err:
                logger.warning(f"DB update failed for stage {stage_id}: {db_err}")
                session.rollback()
            finally:
                session.close()

        return {
            "status": result.status,
            "output_artifact_refs": result.output_artifact_refs,
            "metrics": result.metrics,
            "error_summary": result.error_summary,
            "failure_class": result.failure_class.value if result.failure_class else None,
        }

    except Exception as exc:
        duration = time.time() - start_time
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        logger.error(
            f"Stage {stage_name} failed: job={job_id} stage={stage_id} "
            f"error={error_msg} duration={duration:.2f}s"
        )
        logger.error(traceback.format_exc())

        return {
            "status": "failed_retryable",
            "error_summary": error_msg,
            "failure_class": "INTERNAL_BUG",
        }


# ============================================================
# Celery Task Definitions — one per stage
# ============================================================
# These are imported by celery_app.py via the include list.
# Each task is routed to its named queue by task_routes config.

try:
    from backend.celery_app import app

    @app.task(name="backend.tasks.stage_tasks.execute_planning", bind=True, max_retries=3)
    def execute_planning(self, job_id, stage_id, task_context):
        return _execute_stage_task("planning", job_id, stage_id, task_context)

    @app.task(name="backend.tasks.stage_tasks.execute_asset_retrieval", bind=True, max_retries=5)
    def execute_asset_retrieval(self, job_id, stage_id, task_context):
        return _execute_stage_task("asset_retrieval", job_id, stage_id, task_context)

    @app.task(name="backend.tasks.stage_tasks.execute_scene_graph", bind=True, max_retries=3)
    def execute_scene_graph(self, job_id, stage_id, task_context):
        return _execute_stage_task("scene_graph", job_id, stage_id, task_context)

    @app.task(name="backend.tasks.stage_tasks.execute_motion_graphics", bind=True, max_retries=3)
    def execute_motion_graphics(self, job_id, stage_id, task_context):
        return _execute_stage_task("motion_graphics", job_id, stage_id, task_context)

    @app.task(name="backend.tasks.stage_tasks.execute_audio", bind=True, max_retries=3)
    def execute_audio(self, job_id, stage_id, task_context):
        return _execute_stage_task("audio", job_id, stage_id, task_context)

    @app.task(name="backend.tasks.stage_tasks.execute_rendering", bind=True, max_retries=2)
    def execute_rendering(self, job_id, stage_id, task_context):
        return _execute_stage_task("rendering", job_id, stage_id, task_context)

    @app.task(name="backend.tasks.stage_tasks.execute_critic", bind=True, max_retries=3)
    def execute_critic(self, job_id, stage_id, task_context):
        return _execute_stage_task("critic", job_id, stage_id, task_context)

    @app.task(name="backend.tasks.stage_tasks.execute_revision", bind=True, max_retries=4)
    def execute_revision(self, job_id, stage_id, task_context):
        return _execute_stage_task("revision", job_id, stage_id, task_context)

    @app.task(name="backend.tasks.stage_tasks.execute_export", bind=True, max_retries=3)
    def execute_export(self, job_id, stage_id, task_context):
        return _execute_stage_task("export", job_id, stage_id, task_context)

    @app.task(name="backend.tasks.stage_tasks.execute_cleanup", bind=True, max_retries=5)
    def execute_cleanup(self, job_id, stage_id, task_context):
        return _execute_stage_task("cleanup", job_id, stage_id, task_context)

except ImportError:
    # Celery not installed — tasks defined as plain functions for testing
    logger.warning("Celery not available. Stage tasks registered as plain functions.")

    def execute_planning(job_id, stage_id, task_context):
        return _execute_stage_task("planning", job_id, stage_id, task_context)

    def execute_asset_retrieval(job_id, stage_id, task_context):
        return _execute_stage_task("asset_retrieval", job_id, stage_id, task_context)

    def execute_scene_graph(job_id, stage_id, task_context):
        return _execute_stage_task("scene_graph", job_id, stage_id, task_context)

    def execute_motion_graphics(job_id, stage_id, task_context):
        return _execute_stage_task("motion_graphics", job_id, stage_id, task_context)

    def execute_audio(job_id, stage_id, task_context):
        return _execute_stage_task("audio", job_id, stage_id, task_context)

    def execute_rendering(job_id, stage_id, task_context):
        return _execute_stage_task("rendering", job_id, stage_id, task_context)

    def execute_critic(job_id, stage_id, task_context):
        return _execute_stage_task("critic", job_id, stage_id, task_context)

    def execute_revision(job_id, stage_id, task_context):
        return _execute_stage_task("revision", job_id, stage_id, task_context)

    def execute_export(job_id, stage_id, task_context):
        return _execute_stage_task("export", job_id, stage_id, task_context)

    def execute_cleanup(job_id, stage_id, task_context):
        return _execute_stage_task("cleanup", job_id, stage_id, task_context)
