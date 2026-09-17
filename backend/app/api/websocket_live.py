"""
FastAPI WebSocket Handler for Live Editing Sessions (Phase 7).
Exposes /ws/v1/live-edit for real-time instruction execution, heartbeats, and progress updates.
"""
import json
import logging
from typing import Dict, Any
from agents.video.live_session import LiveSessionManager, LiveInstruction, LiveSessionResult

logger = logging.getLogger("uvicorn")


class LiveWebSocketHandler:
    """
    WebSocket message router for live editing connections.
    """

    @classmethod
    def handle_message(cls, message_raw: str) -> Dict[str, Any]:
        try:
            msg = json.loads(message_raw)
            msg_type = msg.get("type", "")

            if msg_type == "connect":
                session = LiveSessionManager.create_session(
                    session_id=msg.get("session_id", "sess_001"),
                    project_id=msg.get("project_id", "proj_001")
                )
                return {"type": "connected", "session_id": session.session_id, "status": "ACTIVE"}

            elif msg_type == "heartbeat":
                ok = LiveSessionManager.heartbeat(msg.get("session_id", ""))
                return {"type": "heartbeat_ack", "session_id": msg.get("session_id"), "status": "ACTIVE" if ok else "EXPIRED"}

            elif msg_type == "instruction":
                instr = LiveInstruction(
                    session_id=msg.get("session_id", ""),
                    project_id=msg.get("project_id", ""),
                    instruction_id=msg.get("instruction_id", "instr_001"),
                    action_type=msg.get("action_type", "trim_scene"),
                    parameters=msg.get("parameters", {}),
                    dry_run=msg.get("dry_run", False)
                )
                res: LiveSessionResult = LiveSessionManager.execute_instruction(instr)
                return {"type": "instruction_result", "data": res.model_dump()}

            elif msg_type == "disconnect":
                LiveSessionManager.terminate_session(msg.get("session_id", ""))
                return {"type": "disconnected", "session_id": msg.get("session_id")}

            else:
                return {"type": "error", "message": f"Unknown message type '{msg_type}'"}

        except Exception as e:
            return {"type": "error", "message": str(e)}
