"""
FastAPI Production Control API Endpoint for VideoAgent (Phase 8).
Exposes REST routes for job submission, status lookup, cancellation, retries, workers, health, and metrics.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from agents.video.distributed.job_orchestrator import DistributedJobOrchestrator, DistributedJob, JobPriority, JobStatus
from agents.video.distributed.worker_registry import WorkerRegistry
from backend.app.observability.metrics import MetricsCollector
from backend.app.observability.health import HealthChecker


from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()


class SubmitJobRequest(BaseModel):
    project_id: str
    stages: List[str] = Field(default_factory=lambda: ["planning", "rendering", "export"])
    priority: JobPriority = JobPriority.NORMAL
    idempotency_key: Optional[str] = None


class ProductionAPIHandler:
    """Production Control REST API Handler logic."""

    @classmethod
    def submit_job(cls, req: SubmitJobRequest) -> Dict[str, Any]:
        job = DistributedJobOrchestrator.submit_job(
            project_id=req.project_id,
            stage_names=req.stages,
            priority=req.priority,
            idempotency_key=req.idempotency_key
        )
        return {"status": "submitted", "job": job.model_dump()}

    @classmethod
    def get_job(cls, job_id: str) -> Dict[str, Any]:
        job = DistributedJobOrchestrator.get_job(job_id)
        if not job:
            return {"error": "Job not found"}
        return {"job": job.model_dump()}

    @classmethod
    def cancel_job(cls, job_id: str) -> Dict[str, Any]:
        ok = DistributedJobOrchestrator.cancel_job(job_id)
        return {"status": "cancelled" if ok else "failed", "job_id": job_id}

    @classmethod
    def retry_job(cls, job_id: str) -> Dict[str, Any]:
        ok = DistributedJobOrchestrator.retry_job(job_id)
        return {"status": "retried" if ok else "failed", "job_id": job_id}

    @classmethod
    def list_workers(cls) -> Dict[str, Any]:
        workers = WorkerRegistry.list_workers()
        return {"workers": [w.model_dump() for w in workers]}

    @classmethod
    def get_health(cls) -> Dict[str, Any]:
        report = HealthChecker.get_health_report()
        return report.model_dump()

    @classmethod
    def get_metrics(cls) -> Dict[str, Any]:
        metrics = MetricsCollector.get_report()
        return metrics.model_dump()


@router.post("/jobs")
def submit_production_job(req: SubmitJobRequest, current_user: User = Depends(get_current_user)):
    return ProductionAPIHandler.submit_job(req)


@router.get("/jobs/{job_id}")
def get_production_job(job_id: str, current_user: User = Depends(get_current_user)):
    return ProductionAPIHandler.get_job(job_id)


@router.post("/jobs/{job_id}/cancel")
def cancel_production_job(job_id: str, current_user: User = Depends(get_current_user)):
    return ProductionAPIHandler.cancel_job(job_id)


@router.post("/jobs/{job_id}/retry")
def retry_production_job(job_id: str, current_user: User = Depends(get_current_user)):
    return ProductionAPIHandler.retry_job(job_id)


@router.get("/workers")
def list_production_workers(current_user: User = Depends(get_current_user)):
    return ProductionAPIHandler.list_workers()


@router.get("/health")
def get_production_health(current_user: User = Depends(get_current_user)):
    return ProductionAPIHandler.get_health()


@router.get("/metrics")
def get_production_metrics(current_user: User = Depends(get_current_user)):
    return ProductionAPIHandler.get_metrics()

