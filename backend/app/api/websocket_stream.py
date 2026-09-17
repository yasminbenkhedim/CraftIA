"""
Real-Time Live Canvas Frame Streaming WebSocket API for CraftAI.

Streams live frame rendering progress, intermediate canvas frames, and VRAM/GPU metrics
in real-time to the Angular frontend.
"""
import json
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("uvicorn")
router = APIRouter(prefix="/ws/video", tags=["WebSocket Canvas Stream"])

class CanvasStreamManager:
    """Manages active WebSocket connections for live frame streaming."""
    def __init__(self):
        self.active_connections: dict = {}

    async def connect(self, project_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[project_id] = websocket
        logger.info(f"CanvasStreamManager: Connected WebSocket client for project '{project_id}'")

    def disconnect(self, project_id: str):
        if project_id in self.active_connections:
            del self.active_connections[project_id]
            logger.info(f"CanvasStreamManager: Disconnected WebSocket client for project '{project_id}'")

    async def stream_frame(self, project_id: str, frame_index: int, total_frames: int, progress_pct: float, frame_base64: str = ""):
        if project_id in self.active_connections:
            ws = self.active_connections[project_id]
            payload = {
                "event": "frame_rendered",
                "project_id": project_id,
                "frame_index": frame_index,
                "total_frames": total_frames,
                "progress_percent": round(progress_pct, 1),
                "frame_base64": frame_base64
            }
            await ws.send_text(json.dumps(payload))

stream_manager = CanvasStreamManager()

@router.websocket("/stream/{project_id}")
async def websocket_video_stream(websocket: WebSocket, project_id: str):
    await stream_manager.connect(project_id, websocket)
    try:
        while True:
            # Keep-alive receive ping
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))
    except WebSocketDisconnect:
        stream_manager.disconnect(project_id)
