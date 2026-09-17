"""
FastAPI Autonomous Research & Publishing Control API (Phase 6).
Exposes REST endpoints for trend discovery, autonomous video generation, and platform publishing queues.
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from agents.video.trend_researcher import TrendResearcher
from agents.video.autonomous_planner import AutonomousPlanner
from app.tasks.publishing_queue import PublishingQueue, PublishingTask, PublishingPlatform, PublishStatus

router = APIRouter()


class AutonomousRunRequest(BaseModel):
    user_topic: Optional[str] = None
    target_duration_seconds: float = 20.0
    aspect_ratios: List[str] = Field(default_factory=lambda: ["16:9", "9:16"])
    platforms: List[PublishingPlatform] = Field(default_factory=lambda: [PublishingPlatform.YOUTUBE])


class AutonomousRunResponse(BaseModel):
    selected_topic: str
    pipeline_run_id: str
    project_id: str
    manifest_checksum: str
    exported_formats: List[str]
    published_tasks: List[Dict[str, Any]]


@router.get("/trends")
def discover_trends(query: Optional[str] = None):
    """Discovers trending topics across GitHub, Hacker News, and Reddit."""
    return {"trends": TrendResearcher.fetch_all_trends(query)}


@router.post("/run", response_model=AutonomousRunResponse)
def execute_autonomous_run(req: AutonomousRunRequest):
    """Executes full autonomous discovery, video production, multi-format export, and publishing."""
    try:
        topic = req.user_topic or TrendResearcher.fetch_all_trends()[0]["topic"]
        res = AutonomousPlanner.run_autonomous_pipeline(
            topic=topic,
            target_duration=req.target_duration_seconds,
            aspect_ratios=req.aspect_ratios
        )
        
        # Enqueue publishing tasks
        published_info = []
        for plt in req.platforms:
            task = PublishingTask(
                project_id=res["project_id"],
                video_file_path=res["exported_formats"].get("16:9") or list(res["exported_formats"].values())[0],
                title=f"Autonomous Video: {topic}",
                description=f"Generated and published by CreateFlow-AI VideoAgent for topic '{topic}'.",
                tags=["AI", "CreateFlow", "Autonomous"],
                platform=plt
            )
            task_id = PublishingQueue.enqueue(task)
            PublishingQueue.process_pending()
            published_info.append(PublishingQueue.get_task(task_id).dict())

        return AutonomousRunResponse(
            selected_topic=topic,
            pipeline_run_id=res["pipeline_run_id"],
            project_id=res["project_id"],
            manifest_checksum=res["manifest_checksum"],
            exported_formats=list(res["exported_formats"].values()),
            published_tasks=published_info
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
