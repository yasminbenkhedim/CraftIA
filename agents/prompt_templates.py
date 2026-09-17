"""
Centralized Gemini Expert Prompt Templates & Agent Persona Registry.
Maps 7 master post-production & content strategy templates across CreateFlow AI agents:
  - VideoAgent: editing_blueprint, script_flow_optimization, style_reverse_engineering, retention_audit, final_polish_review
  - PresentationAgent: script_flow_optimization, style_reverse_engineering
  - LaTeXReportAgent: script_flow_optimization, style_reverse_engineering
"""
import sys
from pathlib import Path
from typing import Dict, Any, Optional

backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.llm import LLMService

GEMINI_PROMPTS: Dict[str, Dict[str, Any]] = {
    "editing_blueprint": {
        "name": "The Editing Blueprint",
        "persona": "Senior Video Editor (15+ years experience in YouTube and documentary editing)",
        "mapped_agents": ["video"],
        "system_prompt": (
            "You are a senior video editor with 15+ years of experience in YouTube and documentary editing. "
            "Analyze the provided text footage description and produce a high-retention, step-by-step editing blueprint table. "
            "Output MUST be strict valid JSON containing 'summary' and 'timeline' array of items with 'timestamp', 'editing_action', 'broll_visuals', 'audio_sfx', and 'editing_notes'."
        ),
        "fallback": {
            "summary": "High-retention editing blueprint focusing on fast cuts, visual pattern interrupts, and audio dynamics.",
            "timeline": [
                {"timestamp": "00:00 - 00:05", "editing_action": "Hook zoom", "broll_visuals": "Kinetic typography overlay", "audio_sfx": "Impact bass drop", "editing_notes": "Grab attention immediately"}
            ]
        }
    },
    "script_flow_optimization": {
        "name": "Script Flow Optimization",
        "persona": "Content Retention Strategist (YouTube & Short-Form Video Specialist)",
        "mapped_agents": ["video", "presentation", "latex"],
        "system_prompt": (
            "You are a content retention strategist specializing in high-engagement media, presentations, and technical reports. "
            "Analyze the provided text script or topic outline for pacing, clarity, and emotional flow. "
            "Identify weak moments where attention drops, rewrite the hook and first 10 seconds to maximize curiosity, and construct an editing strategy. "
            "Output MUST be strict valid JSON containing 'weak_moments', 'hook_rewrite', 'first_10s_rewrite', 'revised_sections', and 'editing_strategy'."
        ),
        "fallback": {
            "weak_moments": [{"section_name": "Intro", "issue_description": "Preamble lowers watch time", "suggested_fix": "Cut preamble"}],
            "hook_rewrite": "Stop making this critical architectural error.",
            "first_10s_rewrite": "Here is how top enterprise engineering teams achieve 99.99% uptime with multi-agent orchestration.",
            "revised_sections": [{"original": "Welcome back...", "revised": "Here is what nobody tells you..."}],
            "editing_strategy": ["Punch-in zoom on key nouns", "Kinetic text highlights"]
        }
    },
    "style_reverse_engineering": {
        "name": "Style Reverse Engineering",
        "persona": "Master Video Editor & Visual Style Analyst",
        "mapped_agents": ["video", "presentation", "latex"],
        "system_prompt": (
            "You are a master visual style analyst and creative director. "
            "Deconstruct the reference style description (shot duration, framing, color grading, sound design, typography) and create a step-by-step recreation guide for the user's concept. "
            "Output MUST be strict valid JSON containing 'pacing_analysis', 'transition_style', 'camera_movement_framing', 'color_grading_lighting', 'sound_design_layering', and 'recreation_guide'."
        ),
        "fallback": {
            "pacing_analysis": "Fast-paced documentary style with 1.8s average shot duration.",
            "transition_style": "Whip pans, optical blurs, and match cuts.",
            "camera_movement_framing": "Handheld micro-jitters with tight center framing.",
            "color_grading_lighting": "High contrast teal and orange color grade.",
            "sound_design_layering": "Layered Foley sound design with ducked ambient synth pad.",
            "recreation_guide": [{"step_number": 1, "category": "Pacing", "instructions": "Cut every 1.5 to 2.5 seconds on beat changes."}]
        }
    },
    "technical_export_setup": {
        "name": "Technical Export Setup",
        "persona": "Post-Production Supervisor (Broadcast Quality & Platform Compression Specialist)",
        "mapped_agents": ["video"],
        "system_prompt": (
            "You are a post-production supervisor responsible for broadcast quality delivery. "
            "Based on the target platform and content style, recommend exact export parameters (resolution, frame rate, codec, bitrate range, color space, audio format) to preserve maximum visual/audio quality. "
            "Output MUST be strict valid JSON containing 'resolution_aspect', 'frame_rate_motion', 'codec_container', 'bitrate_range', 'color_profile', 'audio_spec', 'compression_tips', and 'common_mistakes_to_avoid'."
        ),
        "fallback": {
            "resolution_aspect": "3840x2160 (16:9 4K UHD)",
            "frame_rate_motion": "59.94 fps",
            "codec_container": "H.264 / MP4",
            "bitrate_range": "45 - 68 Mbps",
            "color_profile": "Rec.709",
            "audio_spec": "AAC-LC 48kHz 320kbps",
            "compression_tips": ["Render at 4K resolution even for 1080p target to get VP09 codec on YouTube."],
            "common_mistakes_to_avoid": ["Exporting in RGB full range instead of legal video range."]
        }
    },
    "raw_footage_triage": {
        "name": "Raw Footage Triage",
        "persona": "Lead Video Editor (Footage Triage & Assembly Lead)",
        "mapped_agents": ["video"],
        "system_prompt": (
            "You are a lead video editor reviewing raw footage shot logs and transcripts. "
            "Organize footage into 🥇 Gold (must keep highlights), ✂️ Trims (dead air, pauses, mistakes), and ✨ Polish (overlays, zooms, SFX enhancements). "
            "Output MUST be strict valid JSON containing 'gold_moments', 'trims', and 'polish_items'."
        ),
        "fallback": {
            "gold_moments": [{"timestamp": "01:00", "reason": "High-energy delivery", "suggested_edit": "Use as main A-roll core take"}],
            "trims": [{"timestamp": "00:30", "reason": "Awkward pause", "suggested_edit": "Cut out completely"}],
            "polish_items": [{"timestamp": "02:00", "reason": "Key concept mentioned", "suggested_edit": "Overlay graphic"}]
        }
    },
    "final_polish_review": {
        "name": "Final Polish Review",
        "persona": "Creative Director (Pre-Publication Quality & Polish Reviewer)",
        "mapped_agents": ["video"],
        "system_prompt": (
            "You are a creative director reviewing a near-finished deliverable before publication. "
            "Score the content out of 10 across 6 categories (pacing, audio, visual quality, color consistency, storytelling flow, overall experience) and identify the top 3 highest-leverage improvements. "
            "Output MUST be strict valid JSON containing 'overall_score', 'scores', and 'top_3_improvements'."
        ),
        "fallback": {
            "overall_score": 8.5,
            "scores": {"pacing_retention": 8.5, "audio_balance": 9.0, "visual_quality": 8.5, "color_consistency": 8.0, "storytelling_flow": 8.5, "overall_experience": 8.5},
            "top_3_improvements": [{"title": "Tighten Intro Gap", "why_it_matters": "Prevents drop-off", "exact_change": "Trim 12 frames", "retention_impact": "+15% watch time"}]
        }
    },
    "the_retention_audit": {
        "name": "The Retention Audit",
        "persona": "Audience Retention Analyst (YouTube & Short-Form Performance Specialist)",
        "mapped_agents": ["video"],
        "system_prompt": (
            "You are an audience retention analyst specializing in viewer drop-off patterns and watch-time optimization. "
            "Identify exact drop-off points, explain viewer psychological reactions, provide targeted fixes (pattern interrupts, dynamic captions, SFX), and generate 🔥 3 alternative high-energy 10-second hooks. "
            "Output MUST be strict valid JSON containing 'drop_off_points' and 'alternative_hooks'."
        ),
        "fallback": {
            "drop_off_points": [{"timestamp_or_section": "00:45", "cause_description": "Static talking head", "likely_viewer_reaction": "Boredom", "targeted_fix": "Add B-roll overlay"}],
            "alternative_hooks": ["What if everything you knew about software architecture was wrong?"]
        }
    }
}


def get_prompt_template(template_name: str) -> Optional[Dict[str, Any]]:
    """Retrieve prompt template info by name."""
    return GEMINI_PROMPTS.get(template_name)


def get_prompts_for_agent(agent_name: str) -> Dict[str, Dict[str, Any]]:
    """Return all prompt templates mapped to a specific agent ('video', 'presentation', 'latex')."""
    return {
        key: info for key, info in GEMINI_PROMPTS.items()
        if agent_name.lower() in info.get("mapped_agents", [])
    }


def generate_with_prompt_template(
    template_name: str,
    user_prompt: str,
    context_data: Optional[Dict[str, Any]] = None,
    fallback: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Executes an LLMService generation call using the designated Gemini expert prompt template.
    """
    template_info = get_prompt_template(template_name)
    if not template_info:
        raise ValueError(f"Unknown prompt template '{template_name}'. Available: {list(GEMINI_PROMPTS.keys())}")

    system_prompt = template_info["system_prompt"]
    
    formatted_user_prompt = f"User Prompt / Input: {user_prompt}"
    if context_data:
        ctx_str = "\n".join(f"- {k}: {v}" for k, v in context_data.items())
        formatted_user_prompt += f"\n\nContext Data:\n{ctx_str}"

    return LLMService.generate_json(
        prompt=formatted_user_prompt,
        system_prompt=system_prompt,
        fallback_dict=fallback or template_info.get("fallback", {})
    )
