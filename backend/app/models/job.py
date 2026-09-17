import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, DateTime, Text
from app.core.database import Base

class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), nullable=False, default="demo_user_123")
    prompt = Column(Text, nullable=False)
    # Short display name generated from the prompt at creation (see LLMService.
    # generate_job_title). Nullable so rows created before this column still load.
    title = Column(String(120), nullable=True)
    agent_type = Column(String(32), nullable=False)  # presentation, latex, video
    status = Column(String(32), nullable=False, default=JobStatus.QUEUED.value)
    progress_percent = Column(Integer, nullable=False, default=0)
    current_step = Column(String(255), nullable=False, default="Job Queued")
    artifact_path = Column(String(512), nullable=True)
    # JSON blob of per-job render settings chosen in the UI Output panel
    # (aspect_ratio, target_duration_seconds, tts_engine). Nullable so existing rows
    # and non-video jobs are unaffected.
    video_options = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    # Set when the artifact file is found to be gone -- deleted by the storage retention
    # sweep, by hand, or with a wiped volume. The job stays COMPLETED because it did
    # complete; this records that the deliverable is no longer retrievable, so the UI can
    # say "expired" instead of offering a download that can only 404. Cleared if the file
    # ever reappears (see startup_cleanup_and_governance in app/main.py).
    artifact_expired_at = Column(DateTime, nullable=True)
