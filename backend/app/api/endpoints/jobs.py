from typing import List
import json
import logging
import os
import re
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.job import Job, JobStatus
from app.models.user import User
from app.schemas.job import JobCreate, JobResponse
from app.core.security import get_current_user
from app.orchestrator.workflow import run_job_workflow
from app.services import credits as credit_service
from app.services.llm import LLMService
from app.services.thumbnail import extract_thumbnail, find_video_for_job

logger = logging.getLogger("uvicorn")

# Settings the UI may attach to a job. Anything outside this set is dropped, so a client
# cannot smuggle in a field the pipeline would trust -- see the brand-kit note below for
# why `brand_kit` itself is deliberately absent.
#
# The report cover fields are here because a PFE report's front page must carry the
# student's own name, university and supervisor. They are free text that only ever
# reaches a PDF, never a filesystem path or a shell.
ALLOWED_RENDER_SETTINGS = (
    # video
    "aspect_ratio", "target_duration_seconds", "tts_engine", "use_brand_kit",
    # shared
    "language",
    # report cover page
    "student_name", "university", "supervisor", "co_supervisor",
    "academic_year", "degree",
)

# Cover text lands in a PDF, so length is the only thing worth bounding: a megabyte of
# "university name" would push the cover off the page and bloat every stored job row.
MAX_COVER_FIELD_CHARS = 160

router = APIRouter()


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    job_in: JobCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submits a new content generation job request bound to current_user.id.
    """
    valid_agents = ["presentation", "latex", "video", "multiagent"]
    if job_in.agent_type.lower() not in valid_agents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid agent_type '{job_in.agent_type}'. Must be one of {valid_agents}"
        )

    # Admission control. Checked before the title LLM call below, so a user with no
    # credits costs nothing to turn away.
    #
    # The check is against AVAILABLE credits, not the raw balance: a credit is debited
    # only when a job succeeds (workflow.py completion gate), so jobs already queued or
    # running have not been paid for yet and must count against the balance here.
    # Without that, a user holding 1 credit could submit ten jobs in the same second and
    # every one of them would pass.
    if not credit_service.can_start_job(db, current_user):
        snap = credit_service.snapshot(db, current_user)
        # This string is rendered verbatim in the UI, so it says what the user can do next
        # rather than dumping the raw record: a readable date, no microseconds.
        resets = snap["credits_reset_at"].strftime("%d %b %Y") if snap["credits_reset_at"] else "soon"
        if snap["jobs_in_flight"] > 0 and snap["credits_remaining"] > 0:
            reason = (
                f"your remaining {snap['credits_remaining']} credit(s) are committed to "
                f"{snap['jobs_in_flight']} job(s) still running"
            )
        else:
            reason = f"you have used all {snap['credits_total']} credits on the {snap['plan']} plan"
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits: {reason}. Credits reset on {resets}.",
        )

    prompt = job_in.prompt.strip()

    # Named from the user's own words, captured before the storyboard branch below
    # replaces `prompt` with a JSON blob -- titling that JSON would be meaningless.
    title_source = prompt

    if job_in.agent_type.lower() == "video" and job_in.video_options:
        if "scenes" in job_in.video_options:
            storyboard_data = dict(job_in.video_options)
            if "title" not in storyboard_data:
                storyboard_data["title"] = prompt
            else:
                # A storyboard that already carries a title has been named by the user.
                title_source = str(storyboard_data["title"])
            prompt = json.dumps(storyboard_data)

    display_title = LLMService.generate_job_title(title_source)

    # Persist the UI's Output-panel render settings (aspect ratio / length / voice /
    # language) so the workflow can hand them to the agent. The storyboard form of
    # video_options is already folded into `prompt` above, so only the render settings are
    # kept here. Anything outside this allowlist is dropped -- 'language' had to be added
    # to it explicitly, otherwise the frontend's choice vanished here without a trace.
    render_settings = None
    if job_in.video_options:
        render_settings = {
            k: v for k, v in job_in.video_options.items()
            if k in ALLOWED_RENDER_SETTINGS and v is not None
        }
        # Trim the free-text report cover fields and drop any that are blank after
        # trimming, so an untouched form field does not overwrite the French placeholder
        # on the cover page with an empty string.
        for field in ("student_name", "university", "supervisor", "co_supervisor",
                      "academic_year", "degree"):
            if field in render_settings:
                value = str(render_settings[field]).strip()[:MAX_COVER_FIELD_CHARS]
                if value:
                    render_settings[field] = value
                else:
                    render_settings.pop(field)

        # Drop a tts_engine that no longer exists rather than storing it.
        #
        # Jobs created before the licence remediation carry tts_engine="piper", and the
        # Library's re-run replays a job's stored settings verbatim. Passing "piper"
        # through would not error -- it simply fails to match Kokoro and falls out of the
        # bottom of the chain into Edge-TTS, so the re-run would quietly use a different
        # voice than the original. Removing the key restores the server default instead.
        engine = render_settings.get("tts_engine")
        if engine is not None and str(engine).strip().lower() not in ("kokoro", "edge"):
            logger.info(
                f"Job create: ignoring unsupported tts_engine {engine!r} "
                f"(removed engine or typo) -- falling back to the server default."
            )
            render_settings.pop("tts_engine", None)

        # Brand kit: resolve it HERE and store a snapshot of the values, rather than
        # letting the pipeline look the user up later.
        #
        # Two reasons. The agents run outside the request and have no database session,
        # so a lookup there would mean handing them one. And a snapshot is the correct
        # semantics: a video carries the brand it was made with, so editing the kit
        # afterwards -- or re-running an old job -- does not silently restyle finished
        # work or reproduce it in a brand the user has since abandoned.
        # Kept in the stored settings, NOT popped. The Library's re-run replays a job's
        # video_options, and this flag is what makes a re-run resolve the brand kit again.
        # The resolved snapshot below cannot serve that purpose: `brand_kit` is absent
        # from the allowlist above on purpose, so a client cannot hand the server a
        # brand_kit of its own -- it carries a logo_path, and an attacker-supplied path
        # would be a filesystem read primitive. Only the server ever writes that key.
        if render_settings.get("use_brand_kit"):
            from app.api.endpoints.brand_kit import get_kit_for_user
            kit = get_kit_for_user(db, current_user.id)
            if kit is None:
                logger.info(
                    f"Job create: use_brand_kit requested by {current_user.email} but no kit "
                    f"is saved -- rendering with the Director's own palette."
                )
            else:
                from app.core.brand import (DEFAULT_ACCENT, DEFAULT_PRIMARY, DEFAULT_SECONDARY,
                                            normalize_font, normalize_hex)
                logo = kit.logo_path if (kit.logo_path and os.path.exists(kit.logo_path)) else None
                render_settings["brand_kit"] = {
                    "primary_color": normalize_hex(kit.primary_color, DEFAULT_PRIMARY),
                    "secondary_color": normalize_hex(kit.secondary_color, DEFAULT_SECONDARY),
                    "accent_color": normalize_hex(kit.accent_color, DEFAULT_ACCENT),
                    "font_choice": normalize_font(kit.font_choice),
                    "logo_path": logo,
                }
                logger.info(
                    f"Job create: brand kit applied for {current_user.email} -- "
                    f"{render_settings['brand_kit']['primary_color']}/"
                    f"{render_settings['brand_kit']['secondary_color']}/"
                    f"{render_settings['brand_kit']['accent_color']}, "
                    f"font={render_settings['brand_kit']['font_choice']}, "
                    f"logo={'yes' if logo else 'no'}"
                )

    new_job = Job(
        user_id=current_user.id,
        prompt=prompt,
        title=display_title,
        agent_type=job_in.agent_type.lower(),
        status=JobStatus.QUEUED.value,
        progress_percent=0,
        current_step="Awaiting media upload" if job_in.defer_start else "Job Queued",
        video_options=json.dumps(render_settings) if render_settings else None
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    # When the client still has media to upload, hold the workflow until it calls
    # /jobs/{id}/start -- otherwise the pipeline would run before the files arrive.
    if not job_in.defer_start:
        background_tasks.add_task(run_job_workflow, new_job.id)
    return new_job


@router.post("/{job_id}/start", response_model=JobResponse)
def start_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Starts a job that was created with defer_start=True, once its uploads are in place.
    Idempotent-guarded: a job already past QUEUED will not be re-dispatched.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access this job."
        )

    if job.status != JobStatus.QUEUED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is already '{job.status}' and cannot be started again."
        )

    # Re-checked here, not just at creation: a deferred job waits for its uploads, and
    # the user may have spent their last credit on something else in the meantime. This
    # job is still QUEUED so it counts itself in the in-flight total -- hence the
    # comparison is against the raw balance rather than available().
    credit_service.ensure_period_current(db, current_user)
    if int(current_user.credits_remaining or 0) < 1:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                "Insufficient credits to start this job. It stays queued -- start it "
                "again once your credits reset or your plan changes."
            ),
        )

    job.current_step = "Job Queued"
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_job_workflow, job.id)
    return job


@router.get("", response_model=List[JobResponse])
def list_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists jobs belonging exclusively to current_user.id.
    """
    return db.query(Job).filter(Job.user_id == current_user.id).order_by(Job.created_at.desc()).all()


@router.get("/{job_id}", response_model=JobResponse)
def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Gets the current status and progress of a specific job owned by current_user.id.
    Returns 403 FORBIDDEN on user ownership mismatch.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access this job."
        )

    return job


# ============================================================================
# USER MEDIA UPLOADS (Phase 3 Track A of VIDEO_PIPELINE_ARCHITECTURE_V2)
# Mounted under the /jobs router -> POST /api/jobs/{job_id}/uploads
# ============================================================================

ALLOWED_UPLOAD_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv", ".jpg", ".jpeg", ".png", ".webp"}
MAX_UPLOAD_BYTES = 200 * 1024 * 1024   # 200 MB per file
MAX_UPLOADS_PER_JOB = 5


def _validate_job_id(job_id: str) -> str:
    """job_id lands in a filesystem path, so reject anything that could traverse out of it."""
    if not re.fullmatch(r"[A-Za-z0-9_\-]{1,128}", job_id or ""):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job_id.")
    return job_id


@router.post("/{job_id}/uploads", status_code=status.HTTP_201_CREATED)
async def upload_job_media(
    job_id: str,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accepts user video/image uploads for a job. The AI Director assigns them to the
    scenes they fit best, taking priority over stock footage.
    """
    from agents.video.user_upload_manager import UserUploadManager

    _validate_job_id(job_id)

    # Only the job's owner may attach media to it.
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access this job."
        )

    if len(files) > MAX_UPLOADS_PER_JOB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many files ({len(files)}); maximum is {MAX_UPLOADS_PER_JOB} per job.",
        )

    upload_dir = UserUploadManager.upload_dir_for_job(job_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for f in files:
        original = os.path.basename(f.filename or "")
        ext = os.path.splitext(original)[1].lower()
        if ext not in ALLOWED_UPLOAD_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_UPLOAD_EXTENSIONS)}",
            )

        safe_name = re.sub(r"[^A-Za-z0-9._\-]", "_", original) or f"upload{ext}"
        dest = upload_dir / safe_name

        content = await f.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"'{safe_name}' is {len(content) / 1e6:.1f} MB; limit is {MAX_UPLOAD_BYTES / 1e6:.0f} MB.",
            )
        with open(dest, "wb") as out:
            out.write(content)
        saved.append({"filename": safe_name, "path": str(dest), "size": len(content)})

    analyzed = UserUploadManager.analyze(upload_dir)
    return {
        "job_id": job_id,
        "uploaded": saved,
        "analyzed": [m.model_dump() for m in analyzed],
    }


@router.get("/{job_id}/uploads")
def list_job_uploads(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists the media already uploaded for a job, with probed metadata."""
    from agents.video.user_upload_manager import UserUploadManager

    _validate_job_id(job_id)

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access this job."
        )

    analyzed = UserUploadManager.analyze(UserUploadManager.upload_dir_for_job(job_id))
    return {"job_id": job_id, "uploads": [m.model_dump() for m in analyzed]}


@router.get("/{job_id}/thumbnail")
def get_job_thumbnail(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Serves the poster frame for a completed video job.

    Generated lazily on the first request when the file is missing, which is what backfills
    jobs that finished before thumbnails existed -- no separate migration pass needed. The
    extraction result is written to disk, so this costs ~0.2 s once per job and is a plain
    file read afterwards.
    """
    _validate_job_id(job_id)

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access this job."
        )

    video_path = find_video_for_job(job)
    if not video_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No rendered video for this job.")

    thumb_path = extract_thumbnail(video_path)
    if not thumb_path or not os.path.exists(thumb_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail could not be generated.")

    return FileResponse(
        path=thumb_path,
        media_type="image/jpeg",
        # Immutable per job: the poster only changes if the video is re-rendered, which
        # writes a new file. Caching keeps the dashboard from re-fetching 14 stills.
        headers={"Cache-Control": "public, max-age=86400"},
    )
