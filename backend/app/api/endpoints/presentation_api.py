from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.job import Job, JobStatus
from app.orchestrator.workflow import run_job_workflow
from agents.presentation.theme import ThemeManager

from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()

class PresentationRequest(BaseModel):
    prompt: str
    theme: str = "corporate_navy"
    slide_count: int = 5

@router.get("/templates")
def get_presentation_templates(current_user: User = Depends(get_current_user)):
    """
    Returns available presentation themes and layout specs inspired by Presenton.
    """
    return {
        "themes": list(ThemeManager.PALETTES.keys()),
        "palettes": ThemeManager.PALETTES,
        "layouts": ["title_slide", "bullet_list", "metric_card", "2_column_comparison"]
    }

@router.post("/generate")
def generate_presentation_api(
    req: PresentationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Direct API endpoint to submit a presentation generation job inspired by Presenton API.
    """
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt cannot be empty.")

    job = Job(
        user_id=current_user.id,
        prompt=req.prompt,
        agent_type="presentation",
        status=JobStatus.QUEUED.value
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Run workflow asynchronously or synchronously for immediate processing
    run_job_workflow(job.id)
    db.refresh(job)

    return {
        "job_id": job.id,
        "status": job.status,
        "artifact_path": job.artifact_path,
        "progress_percent": job.progress_percent,
        "current_step": job.current_step
    }
