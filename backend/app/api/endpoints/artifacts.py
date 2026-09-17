import os
import mimetypes
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.job import Job, JobStatus
from app.models.user import User
from app.core.security import get_current_user

router = APIRouter()


@router.get("/{job_id}")
def download_artifact(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Downloads or previews the generated artifact file for a completed job.
    Enforces JWT authentication and user ownership checks (returns 403 on mismatch).
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Security check: User Ownership Verification
    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access this artifact."
        )

    if job.status != JobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not completed yet. Current status: {job.status}"
        )

    if not job.artifact_path or not os.path.exists(job.artifact_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file does not exist on server")

    filename = os.path.basename(job.artifact_path)
    
    if filename.endswith(".mp4"):
        media_type = "video/mp4"
    elif filename.endswith(".pptx"):
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    elif filename.endswith(".pdf"):
        media_type = "application/pdf"
    else:
        media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    return FileResponse(
        path=job.artifact_path,
        filename=filename,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
