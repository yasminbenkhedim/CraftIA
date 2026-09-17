"""
Project Version Control System for VideoAgent (Phase 8).
Provides Git-like immutable commits, branches, diffs, merges, and rollbacks storing checksums and asset references.
"""
import hashlib
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from agents.video.manifest import EditableVideoProjectManifest

logger = logging.getLogger("uvicorn")


class VersionCommit(BaseModel):
    commit_hash: str
    parent_commit_hash: Optional[str] = None
    message: str
    author: str = "editor"
    manifest_checksum: str
    asset_references: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class VersionBranch(BaseModel):
    branch_name: str
    head_commit_hash: str


class VersionDiff(BaseModel):
    added_scenes: List[str] = Field(default_factory=list)
    removed_scenes: List[str] = Field(default_factory=list)
    modified_scenes: List[str] = Field(default_factory=list)


class ProjectVersionControl:
    """
    Project Version Control Service.
    Manages Git-style commits, branches, diffs, merges, and rollbacks for project manifests.
    """

    _commits: Dict[str, Dict[str, VersionCommit]] = {}  # proj_id -> {commit_hash -> VersionCommit}
    _branches: Dict[str, Dict[str, VersionBranch]] = {}  # proj_id -> {branch_name -> VersionBranch}
    _manifest_snapshots: Dict[str, Dict[str, EditableVideoProjectManifest]] = {}  # proj_id -> {commit_hash -> manifest}

    @classmethod
    def commit(
        cls,
        project_id: str,
        message: str,
        manifest: EditableVideoProjectManifest,
        author: str = "editor",
        branch_name: str = "main"
    ) -> VersionCommit:
        if project_id not in cls._commits:
            cls._commits[project_id] = {}
            cls._branches[project_id] = {}
            cls._manifest_snapshots[project_id] = {}

        parent_hash = cls._branches[project_id][branch_name].head_commit_hash if branch_name in cls._branches[project_id] else None
        raw = f"{project_id}:{message}:{manifest.manifest_checksum}:{time.time()}"
        chash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

        commit_obj = VersionCommit(
            commit_hash=chash,
            parent_commit_hash=parent_hash,
            message=message,
            author=author,
            manifest_checksum=manifest.manifest_checksum,
            asset_references=[s.scene_id for s in manifest.screenplay.scenes] if manifest.screenplay else []
        )

        cls._commits[project_id][chash] = commit_obj
        cls._branches[project_id][branch_name] = VersionBranch(branch_name=branch_name, head_commit_hash=chash)
        cls._manifest_snapshots[project_id][chash] = manifest
        logger.info(f"ProjectVersionControl: Created commit '{chash}' on branch '{branch_name}' for project '{project_id}'")
        return commit_obj

    @classmethod
    def create_branch(cls, project_id: str, new_branch_name: str, source_branch: str = "main") -> VersionBranch:
        if project_id in cls._branches and source_branch in cls._branches[project_id]:
            head_hash = cls._branches[project_id][source_branch].head_commit_hash
            br = VersionBranch(branch_name=new_branch_name, head_commit_hash=head_hash)
            cls._branches[project_id][new_branch_name] = br
            logger.info(f"ProjectVersionControl: Created branch '{new_branch_name}' at '{head_hash}'")
            return br
        raise ValueError(f"Source branch '{source_branch}' not found for project '{project_id}'")

    @classmethod
    def diff(cls, project_id: str, commit_hash1: str, commit_hash2: str) -> VersionDiff:
        c1 = cls._commits.get(project_id, {}).get(commit_hash1)
        c2 = cls._commits.get(project_id, {}).get(commit_hash2)
        if not c1 or not c2:
            return VersionDiff()

        set1 = set(c1.asset_references)
        set2 = set(c2.asset_references)
        return VersionDiff(
            added_scenes=list(set2 - set1),
            removed_scenes=list(set1 - set2),
            modified_scenes=list(set1 & set2) if c1.manifest_checksum != c2.manifest_checksum else []
        )

    @classmethod
    def rollback(cls, project_id: str, target_commit_hash: str, branch_name: str = "main") -> EditableVideoProjectManifest:
        if project_id in cls._manifest_snapshots and target_commit_hash in cls._manifest_snapshots[project_id]:
            cls._branches[project_id][branch_name] = VersionBranch(branch_name=branch_name, head_commit_hash=target_commit_hash)
            logger.info(f"ProjectVersionControl: Rolled back branch '{branch_name}' to commit '{target_commit_hash}'")
            return cls._manifest_snapshots[project_id][target_commit_hash]
        raise ValueError(f"Commit '{target_commit_hash}' not found for project '{project_id}'")
