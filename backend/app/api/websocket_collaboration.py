"""
FastAPI WebSocket Handler for Multi-User Collaboration (Phase 8).
Exposes /ws/v1/collaboration for real-time presence, scene locking, comments, and approvals.
"""
import json
import logging
from typing import Dict, Any
from backend.app.services.collaboration_service import CollaborationService, CollaborationRole

logger = logging.getLogger("uvicorn")


class CollaborationWebSocketHandler:
    """
    WebSocket message router for multi-user collaboration.
    """

    @classmethod
    def handle_message(cls, message_raw: str) -> Dict[str, Any]:
        try:
            msg = json.loads(message_raw)
            msg_type = msg.get("type", "")
            session_id = msg.get("session_id", "collab_sess_1")
            user_id = msg.get("user_id", "u_001")

            if msg_type == "join":
                role_str = msg.get("role", "EDITOR").upper()
                role = CollaborationRole(role_str) if role_str in CollaborationRole.__members__ else CollaborationRole.EDITOR
                collab = CollaborationService.join_session(session_id, user_id, msg.get("name", "User"), role=role)
                return {"type": "joined", "collaborator": collab.model_dump()}

            elif msg_type == "lock_scene":
                ok = CollaborationService.lock_scene(session_id, msg.get("scene_id", ""), user_id)
                return {"type": "lock_result", "scene_id": msg.get("scene_id"), "locked": ok}

            elif msg_type == "unlock_scene":
                ok = CollaborationService.unlock_scene(session_id, msg.get("scene_id", ""), user_id)
                return {"type": "unlock_result", "scene_id": msg.get("scene_id"), "unlocked": ok}

            elif msg_type == "add_comment":
                cmt = CollaborationService.add_comment(session_id, user_id, msg.get("scene_id", ""), msg.get("text", ""))
                return {"type": "comment_added", "comment": cmt.model_dump()}

            elif msg_type == "submit_approval":
                ap = CollaborationService.submit_approval(session_id, user_id, msg.get("approved", True), msg.get("comments"))
                return {"type": "approval_result", "approval": ap.model_dump()}

            else:
                return {"type": "error", "message": f"Unknown collaboration message type '{msg_type}'"}

        except Exception as e:
            return {"type": "error", "message": str(e)}
