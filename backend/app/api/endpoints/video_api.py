"""
Video Agent & Post-Production Blueprint API Endpoints.
Exposes the 7 master editing personas & prompt templates, retention analysis, and export presets.
"""
import os
import re
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from pydantic import BaseModel
from agents.video.prompts import VideoPromptRegistry
from app.services.llm import LLMService
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()


class PromptTemplateResponse(BaseModel):
    id: str
    name: str
    persona: str
    description: str


class RenderPromptRequest(BaseModel):
    prompt_id: str
    parameters: Dict[str, Any]


class AnalyzeVideoRequest(BaseModel):
    prompt_id: str
    input_text: str
    additional_context: Optional[str] = None


@router.get("/prompts", response_model=List[PromptTemplateResponse])
def list_video_prompts(current_user: User = Depends(get_current_user)):
    """
    Returns the list of 7 master post-production editing personas & prompt templates.
    """
    return VideoPromptRegistry.list_all_prompts()


@router.get("/prompts/{prompt_id}")
def get_video_prompt_details(prompt_id: str, current_user: User = Depends(get_current_user)):
    """
    Gets full details and raw template structure for a specific post-production prompt template.
    """
    prompt_info = VideoPromptRegistry.get_prompt_template(prompt_id)
    if not prompt_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt template '{prompt_id}' not found."
        )
    return prompt_info


@router.post("/prompts/render")
def render_video_prompt(req: RenderPromptRequest, current_user: User = Depends(get_current_user)):
    """
    Renders a prompt template with user-supplied arguments (footage description, script, platform, etc.).
    """
    try:
        rendered_prompt = VideoPromptRegistry.build_prompt(req.prompt_id, **req.parameters)
        return {
            "prompt_id": req.prompt_id,
            "rendered_prompt": rendered_prompt
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/analyze")
def run_post_production_analysis(req: AnalyzeVideoRequest, current_user: User = Depends(get_current_user)):
    """
    Executes a direct post-production analysis using LLMService and the selected expert persona prompt.
    """
    """
    Executes a direct post-production analysis using LLMService and the selected expert persona prompt.
    """
    prompt_info = VideoPromptRegistry.get_prompt_template(req.prompt_id)
    if not prompt_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt template '{req.prompt_id}' not found."
        )

    # Build prompt
    if req.prompt_id == "editing_blueprint":
        rendered = VideoPromptRegistry.build_prompt(req.prompt_id, footage_description=req.input_text)
    elif req.prompt_id == "script_flow_optimization":
        rendered = VideoPromptRegistry.build_prompt(req.prompt_id, target_audience=req.additional_context or "General YouTube Audience", script=req.input_text)
    elif req.prompt_id == "style_reverse_engineering":
        rendered = VideoPromptRegistry.build_prompt(req.prompt_id, video_concept=req.additional_context or "High Retention Video", reference_video=req.input_text)
    elif req.prompt_id == "technical_export_setup":
        rendered = VideoPromptRegistry.build_prompt(req.prompt_id, platform=req.additional_context or "YouTube 4K", content_style=req.input_text)
    elif req.prompt_id == "raw_footage_triage":
        rendered = VideoPromptRegistry.build_prompt(req.prompt_id, raw_footage=req.input_text)
    elif req.prompt_id == "final_polish_review":
        rendered = VideoPromptRegistry.build_prompt(req.prompt_id, video_description=req.input_text)
    elif req.prompt_id == "the_retention_audit":
        rendered = VideoPromptRegistry.build_prompt(req.prompt_id, content=req.input_text)
    else:
        rendered = req.input_text

    system_prompt = f"You are acting as: {prompt_info['persona']}. Follow the instructions precisely and respond in clear, professional markdown."
    
    analysis_result = LLMService.generate_content(rendered, system_prompt=system_prompt)
    return {
        "prompt_id": req.prompt_id,
        "persona": prompt_info["persona"],
        "analysis_markdown": analysis_result
    }


class SemanticMashupRequest(BaseModel):
    user_prompt: str
    input_videos: List[str]


@router.post("/semantic_mashup")
def create_semantic_mashup(req: SemanticMashupRequest, current_user: User = Depends(get_current_user)):
    """
    Analyzes multiple input videos, extracts semantic highlights, trims low-value filler, and generates a single consolidated video plan.
    """
    from agents.video.semantic_analyzer import SemanticAnalyzer
    from agents.video.video_consolidator import VideoConsolidator, MultiInputConsolidationRequest

    plan = SemanticAnalyzer.analyze_and_plan_mashup(req.user_prompt, req.input_videos)
    
    consolidation_req = MultiInputConsolidationRequest(
        user_prompt=req.user_prompt,
        input_videos=req.input_videos
    )
    
    output_path = f"./storage/artifacts/mashup_output_{req.user_prompt[:15].replace(' ', '_')}.mp4"
    result = VideoConsolidator.consolidate_videos(consolidation_req, output_path)

    return {
        "user_prompt": req.user_prompt,
        "input_videos_count": len(req.input_videos),
        "semantic_mashup_plan": plan.dict(),
        "consolidated_output": result
    }


class MasterVideoGenerateAPIRequest(BaseModel):
    prompt: str
    target_duration_seconds: float = 20.0
    aspect_ratio: str = "16:9"
    quality_preset: str = "standard"


@router.post("/generate")
def generate_master_remix_video(req: MasterVideoGenerateAPIRequest, current_user: User = Depends(get_current_user)):
    """
    Executes the Master Remix End-to-End Video Generation Pipeline.
    Combines Local ComfyUI (FLUX.1 fp8 + AnimateDiff), FLORA AI Cloud Canvas,
    Live Pexels Stock, and Wav2Lip Lip-Sync Avatars into 1080p / 4K MP4 deliverables.
    """
    from agents.video.pipeline import EndToEndVideoPipeline, PipelineExecutionOptions, RenderQualityPreset
    from agents.video.orchestration import VideoGenerationRequest

    gen_req = VideoGenerationRequest(
        prompt=req.prompt,
        target_duration_seconds=req.target_duration_seconds,
        aspect_ratio=req.aspect_ratio
    )

    preset_map = {
        "draft": RenderQualityPreset.DRAFT,
        "standard": RenderQualityPreset.STANDARD,
        "high": RenderQualityPreset.HIGH,
        "ultra": RenderQualityPreset.ULTRA
    }
    selected_preset = preset_map.get(req.quality_preset.lower(), RenderQualityPreset.STANDARD)

    options = PipelineExecutionOptions(
        quality_preset=selected_preset
    )

    try:
        pipeline_result = EndToEndVideoPipeline.execute(gen_req, options)
        return pipeline_result.dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video Generation Pipeline error: {str(e)}"
        )


class VideoUpscaleRequest(BaseModel):
    video_path: str
    target_fps: float = 60.0


@router.post("/upscale_4k")
def upscale_video_to_4k(req: VideoUpscaleRequest, current_user: User = Depends(get_current_user)):
    """
    Upscales an input 720p/1080p video to 4K UHD (3840x2160 @ 60 FPS) using Real-ESRGAN GPU Tiled Super-Resolution.
    """
    from agents.video.upscaler import RealESRGANVideoUpscaler

    try:
        upscaler = RealESRGANVideoUpscaler()
        output_4k = upscaler.upscale_video_to_4k(req.video_path, target_fps=req.target_fps)
        return {
            "source_video": req.video_path,
            "upscaled_4k_video": output_4k,
            "resolution": "3840x2160",
            "frame_rate": req.target_fps
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video Upscaling error: {str(e)}"
        )


class VoiceCloneRequest(BaseModel):
    text: str
    target_language: str = "es"
    output_filename: str = "cloned_speech.mp3"


@router.post("/clone_voice")
def clone_and_translate_voice(req: VoiceCloneRequest, current_user: User = Depends(get_current_user)):
    """
    Clones voice tone and translates speech into 30+ languages.
    """
    from agents.video.voice_cloner import TTSVoiceCloner

    try:
        cloner = TTSVoiceCloner()
        audio_path = cloner.clone_and_synthesize(
            text=req.text,
            target_language=req.target_language,
            output_filename=req.output_filename
        )
        return {
            "text": req.text,
            "target_language": req.target_language,
            "audio_path": audio_path
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice Cloning error: {str(e)}"
        )


