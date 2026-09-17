import os
from pathlib import Path
from app.core.config import settings

class StorageService:
    @staticmethod
    def get_artifact_path(job_id: str, filename: str = None) -> Path:
        job_dir = settings.STORAGE_PATH / job_id
        if filename:
            return job_dir / filename
        return job_dir

    @staticmethod
    def exists(file_path: str) -> bool:
        return os.path.exists(file_path)
