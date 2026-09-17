"""
FastAPI Router for Post-Production Advisory API (/api/v1/advisory).
Provides REST endpoints for expert post-production advisory analysis and template inspection.
"""
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from agents.video.postproduction_advisor import PostProductionAdvisor
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()


class AdvisoryTemplateResponse(BaseModel):
    template_id: str
    name: str
    persona: str
    required_inputs: List[str]


class AdvisoryAnalysisRequest(BaseModel):
    template_id: str = Field(description="One of the 7 advisory template IDs")
    inputs: Dict[str, Any] = Field(description="Dictionary of required text input fields")


@router.get("/templates", response_model=List[AdvisoryTemplateResponse])
def list_advisory_templates(current_user: User = Depends(get_current_user)):
    """
    Lists all 7 post-production advisory templates, their personas, and required text inputs.
    """
    return PostProductionAdvisor.list_templates()


@router.post("/analyze")
def analyze_post_production_advisory(
    req: AdvisoryAnalysisRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Executes post-production advisory analysis on text inputs (scripts, footage logs, style notes).
    Returns structured JSON conforming to the template's Pydantic schema.
    """
    try:
        result = PostProductionAdvisor.analyze_advisory(req.template_id, req.inputs)
        return {
            "status": "SUCCESS",
            "template_id": req.template_id,
            "data": result
        }
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during post-production advisory processing: {e}"
        )
