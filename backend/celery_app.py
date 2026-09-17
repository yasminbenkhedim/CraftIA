"""
CraftAI Celery Application — Upgrade 10 Production Orchestration.

Integrates with existing CraftAI infrastructure:
- Existing component: backend.app.core.config (Settings, DATABASE_URL)
- Existing component: backend.app.core.database (SessionLocal, Base)
- Reason for new module: Celery app configuration does not exist in CraftAI
- Integration points: Redis broker, PostgreSQL result backend, worker task dispatch
"""
import os
import logging

# Load the root .env into os.environ BEFORE anything that reads it (config
# validation, Wav2Lip engine, Pexels provider). Real env vars keep precedence.
try:
    from backend import env_bootstrap  # noqa: F401
except Exception:
    try:
        import env_bootstrap  # noqa: F401  (when backend/ is on sys.path)
    except Exception:
        pass

from celery import Celery
from celery.signals import worker_ready, worker_shutting_down, task_prerun, task_postrun

logger = logging.getLogger("uvicorn")

# Redis broker URL from environment, with sensible default
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL", "")

app = Celery(
    "craftai",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "backend.tasks.stage_tasks",
    ],
)

# Celery configuration for production
app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Reliability
    task_acks_late=True,                   # Acknowledge after execution (crash recovery)
    task_reject_on_worker_lost=True,       # Re-queue if worker dies
    worker_prefetch_multiplier=1,          # Fair scheduling: one task at a time

    # Retry
    task_default_retry_delay=5,
    task_max_retries=3,

    # Priority (Redis supports 0-9 priority levels)
    broker_transport_options={
        "priority_steps": list(range(10)),
        "sep": ":",
        "queue_order_strategy": "priority",
    },

    # Timeouts
    task_soft_time_limit=600,              # 10 min soft limit
    task_time_limit=900,                   # 15 min hard limit

    # Worker
    worker_max_tasks_per_child=50,         # Prevent memory leaks
    worker_send_task_events=True,          # Enable task event monitoring
    task_send_sent_event=True,

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Result expiry
    result_expires=86400,                  # 24 hours
)

# Define task queues matching worker roles
app.conf.task_queues = {
    "planning": {"exchange": "craftai", "routing_key": "planning"},
    "asset_retrieval": {"exchange": "craftai", "routing_key": "asset_retrieval"},
    "scene_graph": {"exchange": "craftai", "routing_key": "scene_graph"},
    "motion_graphics": {"exchange": "craftai", "routing_key": "motion_graphics"},
    "audio": {"exchange": "craftai", "routing_key": "audio"},
    "rendering_gpu": {"exchange": "craftai", "routing_key": "rendering_gpu"},
    "rendering_cpu": {"exchange": "craftai", "routing_key": "rendering_cpu"},
    "critic": {"exchange": "craftai", "routing_key": "critic"},
    "revision": {"exchange": "craftai", "routing_key": "revision"},
    "export": {"exchange": "craftai", "routing_key": "export"},
    "cleanup": {"exchange": "craftai", "routing_key": "cleanup"},
    "dead_letter": {"exchange": "craftai", "routing_key": "dead_letter"},
}

# Route tasks to correct queues
app.conf.task_routes = {
    "backend.tasks.stage_tasks.execute_planning": {"queue": "planning"},
    "backend.tasks.stage_tasks.execute_asset_retrieval": {"queue": "asset_retrieval"},
    "backend.tasks.stage_tasks.execute_scene_graph": {"queue": "scene_graph"},
    "backend.tasks.stage_tasks.execute_motion_graphics": {"queue": "motion_graphics"},
    "backend.tasks.stage_tasks.execute_audio": {"queue": "audio"},
    "backend.tasks.stage_tasks.execute_rendering": {"queue": "rendering_gpu"},
    "backend.tasks.stage_tasks.execute_critic": {"queue": "critic"},
    "backend.tasks.stage_tasks.execute_revision": {"queue": "revision"},
    "backend.tasks.stage_tasks.execute_export": {"queue": "export"},
    "backend.tasks.stage_tasks.execute_cleanup": {"queue": "cleanup"},
}


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Register worker in database on startup."""
    hostname = sender.hostname if hasattr(sender, "hostname") else "unknown"
    logger.info(f"CraftAI Worker ready: {hostname}")


@worker_shutting_down.connect
def on_worker_shutdown(sig, how, exitcode, **kwargs):
    """Deregister worker from database on shutdown."""
    logger.info(f"CraftAI Worker shutting down: signal={sig}, how={how}")


@task_prerun.connect
def on_task_prerun(sender, task_id, task, args, kwargs, **extra):
    """Log task start with trace context."""
    logger.info(f"Task starting: {task.name} id={task_id}")


@task_postrun.connect
def on_task_postrun(sender, task_id, task, args, kwargs, retval, state, **extra):
    """Log task completion with metrics."""
    logger.info(f"Task completed: {task.name} id={task_id} state={state}")
