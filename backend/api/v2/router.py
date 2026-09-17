"""
API Versioning Router (v1 and v2) for CraftAI (Upgrade 11).

Provides backward-compatible route prefixing:
- `/api/v1/*`: Enterprise v1 endpoints
- `/api/v2/*`: Enterprise v2 endpoints with enhanced metadata, priority tiers, and FinOps telemetry
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional

router_v1 = APIRouter(prefix="/api/v1", tags=["v1"])
router_v2 = APIRouter(prefix="/api/v2", tags=["v2"])


@router_v1.get("/health")
def v1_health():
    return {"version": "v1", "status": "UP", "compatibility": "legacy"}


@router_v2.get("/health")
def v2_health():
    return {
        "version": "v2",
        "status": "UP",
        "features": {
            "s3_storage": True,
            "distributed_cache": True,
            "priority_scheduler": True,
            "finops_accounting": True,
            "multi_region": True
        }
    }


@router_v2.post("/jobs")
def create_v2_job(payload: Dict[str, Any]):
    """Create job using API v2 schema with priority and SLA attributes."""
    prompt = payload.get("prompt")
    if not prompt:
        raise HTTPException(status_code=422, detail="prompt field is required")

    tenant_id = payload.get("tenant_id", "default")
    user_id = payload.get("user_id", "user_1")
    priority = payload.get("priority", 5)

    from orchestrator.job_orchestrator import ProductionJobOrchestrator
    result = ProductionJobOrchestrator.create_job(
        tenant_id=tenant_id,
        user_id=user_id,
        prompt=prompt,
        priority=priority,
        input_config=payload
    )

    result["api_version"] = "v2"
    return result


@router_v2.get("/jobs/{job_id}")
def get_v2_job(job_id: str):
    """Get job status with itemized cost & stage details."""
    from orchestrator.job_orchestrator import ProductionJobOrchestrator
    from finops.cost_tracker import cost_tracker

    job = ProductionJobOrchestrator.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    cost_summary = cost_tracker.get_job_cost_summary(job_id)
    job["cost_breakdown"] = cost_summary or {"total_cost_usd": 0.0}
    job["api_version"] = "v2"
    return job
