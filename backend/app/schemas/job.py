import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, computed_field, field_validator

class JobCreate(BaseModel):
    prompt: str = Field(..., min_length=1, description="Description of the content to generate")
    agent_type: str = Field(..., description="Target agent: presentation, latex, or video")
    video_options: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional JSON storyboard for video jobs: {scenes: [{scene_id, scene_title, duration_sec, user_speech, ...}]}"
    )
    defer_start: bool = Field(
        False,
        description=(
            "Create the job without starting the workflow. Used when the client still has "
            "media to upload -- it uploads to /jobs/{id}/uploads, then calls /jobs/{id}/start. "
            "Without this the pipeline would begin before the uploads land and ignore them."
        )
    )

class JobResponse(BaseModel):
    id: str
    user_id: str
    prompt: str
    # Absent on jobs created before titles existed; clients fall back to the prompt.
    title: Optional[str] = None
    agent_type: str
    status: str
    progress_percent: int = 0
    current_step: str = "Job Queued"
    artifact_path: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    # Stamped when the artifact file was found to be gone. See the Job model.
    artifact_expired_at: Optional[datetime] = None
    # The render settings this job was created with (aspect ratio, length, voice,
    # language), parsed back from the stored JSON. Exposed so the Library's "Re-run"
    # can recreate a job identically instead of silently falling back to defaults --
    # a re-run of a 9:16 French video must not come back 16:9 in English.
    video_options: Optional[Dict[str, Any]] = None

    @field_validator("progress_percent", mode="before")
    @classmethod
    def _percent_never_null(cls, v: Any) -> int:
        """
        Guarantees a number reaches the client, for every job in every state.

        The column is NOT NULL with a default of 0, so a QUEUED job already serializes as
        0 -- but a row predating the column, or one built in memory and not yet refreshed,
        would otherwise send null and make the UI compute NaN.
        """
        if v is None:
            return 0
        return max(0, min(100, int(v)))

    @field_validator("current_step", mode="before")
    @classmethod
    def _step_never_null(cls, v: Any) -> str:
        return v or "Job Queued"

    @field_validator("video_options", mode="before")
    @classmethod
    def _parse_video_options(cls, v: Any) -> Optional[Dict[str, Any]]:
        """
        The column stores JSON text; clients want the object.

        Unreadable or non-object content yields None rather than raising: a malformed
        blob on one old row must not make the whole job list fail to serialize.
        """
        if v is None or isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
            except (ValueError, TypeError):
                return None
            if not isinstance(parsed, dict):
                return None
            return cls._redact(parsed)
        return None

    @staticmethod
    def _redact(settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Strip server-side paths before the settings leave the building.

        A resolved brand kit carries logo_path -- an absolute path on the server. It is
        needed by the renderer, which reads the stored JSON directly, but publishing it
        would hand every client a map of the server's filesystem. The client is told
        whether a logo was applied, not where it lives.
        """
        brand = settings.get("brand_kit")
        if isinstance(brand, dict) and "logo_path" in brand:
            safe = dict(settings)
            safe["brand_kit"] = {k: v for k, v in brand.items() if k != "logo_path"}
            safe["brand_kit"]["has_logo"] = bool(brand.get("logo_path"))
            return safe
        return settings

    # `progress` / `stage_label` are the names the UI reads. They are serialized aliases of
    # the two columns above rather than new columns: duplicating the state in the database
    # would need a migration and would let the two copies disagree after a partial write.
    @computed_field
    @property
    def progress(self) -> int:
        return self.progress_percent

    @computed_field
    @property
    def stage_label(self) -> str:
        return self.current_step

    @computed_field
    @property
    def artifact_available(self) -> bool:
        """
        True only when there is a file the download endpoint can actually serve.

        Checked against the filesystem on every read rather than trusting
        artifact_expired_at alone: that column is only stamped at startup, so a file
        removed while the server is running would otherwise keep a live download button
        until the next restart. The column records WHEN the artifact went missing; this
        answers whether it is there right now, which is what the button needs.
        """
        if self.status != "COMPLETED":
            return False
        return bool(self.artifact_path) and os.path.exists(self.artifact_path)

    @computed_field
    @property
    def artifact_expired(self) -> bool:
        """
        A job that finished successfully but whose deliverable is no longer on disk.

        Deliberately distinct from `not artifact_available`: a QUEUED or RUNNING job has
        no artifact either, and calling that "expired" would be wrong. This is only true
        for work that WAS delivered and has since been swept away by storage retention.
        """
        return self.status == "COMPLETED" and not self.artifact_available

    @computed_field
    @property
    def thumbnail_url(self) -> Optional[str]:
        """
        Path to this job's poster frame, or None when it cannot have one.

        Derived rather than stored: a column would have to be kept in step with the
        filesystem, and would be wrong for every job that finished before thumbnails
        existed. The endpoint generates the image on first request, so a URL here is a
        promise that one can be produced, not that the file is already on disk.

        Relative on purpose -- the browser loads it as an <img> src and has to append its
        own ?token=, exactly as it does for artifact downloads. Putting the caller's JWT
        in a response body would leak it into logs and caches.
        """
        if self.status != "COMPLETED":
            return None
        # No source file, no poster frame. The endpoint extracts the thumbnail from the
        # MP4 on first request, so advertising a URL for a deleted video guarantees a 404
        # -- which is what the dashboard was hitting after a retention sweep.
        if not self.artifact_available:
            return None
        is_video = self.agent_type == "video" or (self.artifact_path or "").lower().endswith(".mp4")
        return f"/api/jobs/{self.id}/thumbnail" if is_video else None

    class Config:
        from_attributes = True

class JobStatusUpdate(BaseModel):
    status: Optional[str] = None
    progress_percent: Optional[int] = None
    current_step: Optional[str] = None
    artifact_path: Optional[str] = None
