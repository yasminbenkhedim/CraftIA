"""
Collaborative Studio Service for VideoAgent (Phase 8).
Manages multi-user WebSocket presence, scene-level locking, comments, approvals, and role permissions.
"""
import time
import logging
from enum import Enum
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


class CollaborationRole(str, Enum):
    OWNER = "OWNER"
    EDITOR = "EDITOR"
    REVIEWER = "REVIEWER"
    VIEWER = "VIEWER"


class Collaborator(BaseModel):
    user_id: str
    name: str
    role: CollaborationRole = CollaborationRole.EDITOR
    active_scene_id: Optional[str] = None


class ReviewComment(BaseModel):
    comment_id: str
    user_id: str
    scene_id: str
    text: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class ApprovalDecision(BaseModel):
    approval_id: str
    project_id: str
    reviewer_id: str
    approved: bool
    comments: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class CollaborationSession(BaseModel):
    session_id: str
    project_id: str
    collaborators: Dict[str, Collaborator] = Field(default_factory=dict)
    scene_locks: Dict[str, str] = Field(default_factory=dict)  # scene_id -> user_id
    comments: List[ReviewComment] = Field(default_factory=list)
    approvals: List[ApprovalDecision] = Field(default_factory=list)


class CollaborationService:
    """
    Collaboration Service.
    Enforces role permissions and handles live presence and scene-level locking.
    """

    _sessions: Dict[str, CollaborationSession] = {}

    @classmethod
    def get_or_create_session(cls, session_id: str, project_id: str) -> CollaborationSession:
        if session_id not in cls._sessions:
            cls._sessions[session_id] = CollaborationSession(session_id=session_id, project_id=project_id)
        return cls._sessions[session_id]

    @classmethod
    def join_session(cls, session_id: str, user_id: str, name: str, role: CollaborationRole = CollaborationRole.EDITOR) -> Collaborator:
        sess = cls.get_or_create_session(session_id, "proj_default")
        collab = Collaborator(user_id=user_id, name=name, role=role)
        sess.collaborators[user_id] = collab
        logger.info(f"CollaborationService: User '{user_id}' joined session '{session_id}' as '{role.value}'")
        return collab

    @classmethod
    def lock_scene(cls, session_id: str, scene_id: str, user_id: str) -> bool:
        sess = cls._sessions.get(session_id)
        if not sess:
            return False

        collab = sess.collaborators.get(user_id)
        if not collab or collab.role in [CollaborationRole.VIEWER, CollaborationRole.REVIEWER]:
            logger.warning(f"CollaborationService: Permission denied for user '{user_id}' with role '{collab.role if collab else 'None'}'")
            return False

        if scene_id in sess.scene_locks and sess.scene_locks[scene_id] != user_id:
            logger.warning(f"CollaborationService: Scene '{scene_id}' locked by user '{sess.scene_locks[scene_id]}'")
            return False

        sess.scene_locks[scene_id] = user_id
        collab.active_scene_id = scene_id
        return True

    @classmethod
    def unlock_scene(cls, session_id: str, scene_id: str, user_id: str) -> bool:
        sess = cls._sessions.get(session_id)
        if sess and sess.scene_locks.get(scene_id) == user_id:
            del sess.scene_locks[scene_id]
            return True
        return False

    @classmethod
    def add_comment(cls, session_id: str, user_id: str, scene_id: str, text: str) -> ReviewComment:
        sess = cls.get_or_create_session(session_id, "proj_default")
        c = ReviewComment(comment_id=f"cmt_{int(time.time())}", user_id=user_id, scene_id=scene_id, text=text)
        sess.comments.append(c)
        return c

    @classmethod
    def submit_approval(cls, session_id: str, reviewer_id: str, approved: bool, comments: Optional[str] = None) -> ApprovalDecision:
        sess = cls.get_or_create_session(session_id, "proj_default")
        ap = ApprovalDecision(approval_id=f"app_{int(time.time())}", project_id=sess.project_id, reviewer_id=reviewer_id, approved=approved, comments=comments)
        sess.approvals.append(ap)
        return ap
