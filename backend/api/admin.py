"""
Admin Operations Endpoints for CraftAI (Upgrade 11).

Provides operational control endpoints for:
- Pause / Resume workers
- Replay Dead Letter Queue (DLQ) entries
- Clear / Invalidate Redis cache
- Rotate secrets and API keys
- Invalidate corrupted checkpoints
- Manage worker node quarantine
- Force metrics rebuild
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional

admin_router = APIRouter(prefix="/admin", tags=["admin_operations"])


@admin_router.post("/workers/pause")
def pause_workers(reason: str = "Admin requested pause"):
    """Pause worker task execution across queues."""
    from app.config_manager import config_manager
    config_manager.set_tenant_config("global", "workers_paused", True)
    return {"status": "PAUSED", "reason": reason}


@admin_router.post("/workers/resume")
def resume_workers():
    """Resume worker task execution."""
    from app.config_manager import config_manager
    config_manager.set_tenant_config("global", "workers_paused", False)
    return {"status": "RESUMED"}


@admin_router.post("/dlq/replay")
def replay_dlq_entry(dead_letter_id: str, actor: str = "admin"):
    """Replay a specific DLQ entry."""
    from scheduler.render_scheduler import RenderScheduler
    success = RenderScheduler.replay_dead_letter(dead_letter_id, actor=actor)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to replay DLQ entry")
    return {"status": "REPLAYED", "dead_letter_id": dead_letter_id}


@admin_router.post("/cache/clear")
def clear_cache(namespace: Optional[str] = None, tenant_id: str = "global"):
    """Clear Redis cache entries by namespace or tenant."""
    from cache.distributed_cache import cache
    if namespace:
        cleared = cache.invalidate_prefix(namespace, tenant_id=tenant_id)
    else:
        cleared = cache.invalidate_prefix("*", tenant_id=tenant_id)
    return {"status": "SUCCESS", "keys_cleared": cleared}


@admin_router.post("/secrets/rotate")
def rotate_secret(key_id: str, new_secret: str):
    """Rotate an active secret key with grace period support."""
    from security.enterprise_security import key_rotator
    key_rotator.register_secret(key_id, new_secret)
    return {"status": "ROTATED", "key_id": key_id}


@admin_router.post("/checkpoints/invalidate")
def invalidate_checkpoint(checkpoint_id: str):
    """Invalidate corrupted checkpoint record."""
    from orchestrator.failure_recovery import failure_recovery_engine
    result = failure_recovery_engine.repair_checkpoint_record(checkpoint_id)
    return result


@admin_router.get("/quarantine/status")
def quarantine_status():
    """Get worker node quarantine status."""
    from orchestrator.failure_recovery import failure_recovery_engine
    return failure_recovery_engine.get_quarantine_status()


@admin_router.post("/metrics/rebuild")
def rebuild_metrics():
    """Force observability metrics rebuild."""
    from observability.metrics import metrics
    output = metrics.export()
    return {"status": "REBUILT", "bytes_exported": len(output)}
