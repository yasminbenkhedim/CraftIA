"""
FastAPI Autonomous Endpoint for VideoAgent (Phase 6).
Triggers autonomous research, planning, video generation, multi-format export, and distribution queuing.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from agents.video.autonomous_planner import AutonomousPlanner, PlanningResult
from agents.video.pipeline import EndToEndVideoPipeline, PipelineExecutionOptions
from agents.video.python_editor.multi_format_exporter import MultiFormatExporter
from backend.app.services.publishing_queue import PublishingQueue, PublishingTask, PublishingRequest, PublishingTaskStatus
from backend.app.services.publishing_history import PublishingHistory


class AutonomousRunRequest(BaseModel):
    topic: Optional[str] = None
    auto_research: bool = True
    publish_targets: List[str] = Field(default_factory=lambda: ["youtube"])
    aspect_ratios: List[str] = Field(default_factory=lambda: ["16:9"])
    schedule_publish: bool = False
    publish_time: Optional[str] = None
    dry_run: bool = False


class AutonomousRunResponse(BaseModel):
    planning_result: PlanningResult
    selected_pipeline: str
    render_results: Dict[str, Any]
    export_results: List[Dict[str, Any]] = Field(default_factory=list)
    publishing_results: List[Dict[str, Any]] = Field(default_factory=list)
    history_id: Optional[str] = None


class AutonomousEndpointHandler:
    """Handler function logic for POST /api/v1/autonomous/run."""

    @classmethod
    def handle_run(cls, request: AutonomousRunRequest) -> AutonomousRunResponse:
        # 1. Autonomous Planning & Research
        plan_res = AutonomousPlanner.plan_autonomous_video(
            manual_prompt=request.topic,
            target_duration=15.0
        )

        # Dry Run Mode
        if request.dry_run:
            return AutonomousRunResponse(
                planning_result=plan_res,
                selected_pipeline=plan_res.decision.selected_pipeline_profile,
                render_results={"dry_run": True, "status": "planned_only"},
                export_results=[],
                publishing_results=[],
                history_id="hist_dry_run"
            )

        # 2. Pipeline Execution
        opts = PipelineExecutionOptions(
            pipeline_profile=plan_res.decision.selected_pipeline_profile,
            mcp_enabled=True,
            auto_research=request.auto_research
        )
        pipe_res = EndToEndVideoPipeline.execute(plan_res.video_request, opts)

        # 3. Multi-Format Export
        output_dir = opts.output_directory
        export_manifest = MultiFormatExporter.export_multi_format(
            project_id=f"proj_{plan_res.decision.selected_topic[:10]}",
            source_video_path=pipe_res.final_video_path or "video.mp4",
            output_directory=output_dir,
            target_aspect_ratios=request.aspect_ratios
        )

        # 4. Distribution Queuing & Publishing
        pub_results = []
        for target in request.publish_targets:
            pub_req = PublishingRequest(
                project_id=f"proj_{plan_res.decision.selected_topic[:10]}",
                platform=target,
                video_path=pipe_res.final_video_path or "video.mp4",
                title=plan_res.decision.selected_topic,
                description=f"Autonomous video on {plan_res.decision.selected_topic}",
                hashtags=["#AI", "#VideoAgent", "#CreateFlow"]
            )
            task = PublishingTask(
                task_id=f"task_{target}_{plan_res.decision.selected_topic[:8]}",
                project_id=pub_req.project_id,
                platform=target,
                request=pub_req
            )
            PublishingQueue.enqueue(task)

        # Process immediate publishing
        processed = PublishingQueue.process_queue()
        for p in processed:
            pub_results.append(p.model_dump())

        history_id = f"hist_auto_{plan_res.decision.selected_topic[:8]}"
        return AutonomousRunResponse(
            planning_result=plan_res,
            selected_pipeline=plan_res.decision.selected_pipeline_profile,
            render_results={"outcome": pipe_res.outcome.value, "manifest_checksum": pipe_res.manifest_checksum},
            export_results=[v.model_dump() for v in export_manifest.variants],
            publishing_results=pub_results,
            history_id=history_id
        )


from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/run", response_model=AutonomousRunResponse)
def execute_autonomous_run(request: AutonomousRunRequest, current_user: User = Depends(get_current_user)):
    return AutonomousEndpointHandler.handle_run(request)


