"""
Post-Production Advisory Module (v1)
Text-in / Text-out Expert Advisory System powered by LLMService.
Integrates 7 senior post-production specialist personas & Pydantic response schemas:
  1. EditingBlueprintSchema
  2. ScriptOptimizationSchema
  3. StyleReverseEngineeringSchema
  4. TechnicalExportSchema
  5. RawFootageTriageSchema
  6. FinalPolishReviewSchema
  7. RetentionAuditSchema
"""
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.services.llm import LLMService

logger = logging.getLogger("uvicorn")


# =============================================================================
# 1. PYDANTIC RESPONSE SCHEMAS
# =============================================================================

# --- 1. The Editing Blueprint ---
class TimelineItem(BaseModel):
    timestamp: str = Field(description="Timecode or scene range e.g. '00:00 - 00:05'")
    editing_action: str = Field(description="Cut type, pacing change, jump cut, or speed ramp")
    broll_visuals: str = Field(description="B-roll replacement, motion graphic, text callout, or visual transition")
    audio_sfx: str = Field(description="Music cue, riser, impact SFX, or audio crossfade")
    editing_notes: str = Field(description="Retention directive and emotional intent")


class EditingBlueprintSchema(BaseModel):
    summary: str = Field(description="High-level directorial summary of the editing approach")
    timeline: List[TimelineItem] = Field(default_factory=list, description="Step-by-step editing blueprint timeline items")


# --- 2. Script Flow Optimization ---
class WeakSectionItem(BaseModel):
    section_name: str = Field(description="Script section or line identifier")
    issue_description: str = Field(description="Why attention drops or pacing stumbles")
    suggested_fix: str = Field(description="Actionable rewrite or cut recommendation")


class ScriptOptimizationSchema(BaseModel):
    weak_moments: List[WeakSectionItem] = Field(default_factory=list)
    hook_rewrite: str = Field(description="Instantly attention-grabbing hook rewrite")
    first_10s_rewrite: str = Field(description="Curiosity-maximizing rewrite for the first 10 seconds")
    revised_sections: List[Dict[str, str]] = Field(default_factory=list, description="List of original vs revised section pairs")
    editing_strategy: List[str] = Field(default_factory=list, description="Pacing, jump-cut, and pattern interrupt directives")


# --- 3. Style Reverse Engineering ---
class StyleRecreationStep(BaseModel):
    step_number: int
    category: str = Field(description="e.g. Pacing, Color, Audio, Transitions")
    instructions: str = Field(description="Actionable instruction to replicate reference aesthetic")


class StyleReverseEngineeringSchema(BaseModel):
    pacing_analysis: str = Field(description="Average shot duration and cut cadence")
    transition_style: str = Field(description="Dominant transition types and timing")
    camera_movement_framing: str = Field(description="Framing, zooms, and focal length style")
    color_grading_lighting: str = Field(description="Color palette, contrast, and mood parameters")
    sound_design_layering: str = Field(description="Music layering, ambiance, and SFX texture")
    recreation_guide: List[StyleRecreationStep] = Field(default_factory=list)


# --- 4. Technical Export Setup ---
class TechnicalExportSchema(BaseModel):
    resolution_aspect: str = Field(description="Target resolution e.g. '3840x2160 (16:9)'")
    frame_rate_motion: str = Field(description="Frame rate and motion blur settings e.g. '23.976 fps'")
    codec_container: str = Field(description="Video codec & container format e.g. 'H.264 / MP4'")
    bitrate_range: str = Field(description="Target bitrate range e.g. '45 - 68 Mbps'")
    color_profile: str = Field(description="Color space e.g. 'Rec.709 / Gamma 2.4'")
    audio_spec: str = Field(description="Audio codec, sample rate, bitrate e.g. 'AAC LC, 48 kHz, 320 kbps'")
    compression_tips: List[str] = Field(default_factory=list)
    common_mistakes_to_avoid: List[str] = Field(default_factory=list)


# --- 5. Raw Footage Triage ---
class TriageItem(BaseModel):
    timestamp: str = Field(description="Timecode or shot log marker")
    reason: str = Field(description="Why this moment belongs in this category")
    suggested_edit: str = Field(description="Actionable editing instruction")


class RawFootageTriageSchema(BaseModel):
    gold_moments: List[TriageItem] = Field(default_factory=list, description="🥇 Best takes and cinematic moments to keep")
    trims: List[TriageItem] = Field(default_factory=list, description="✂️ Dead air, pauses, mistakes, and filler content to remove")
    polish_items: List[TriageItem] = Field(default_factory=list, description="✨ Sections needing B-roll, zooms, SFX, or color polish")


# --- 6. Final Polish Review ---
class PolishScores(BaseModel):
    pacing_retention: float = Field(description="Score out of 10")
    audio_balance: float = Field(description="Score out of 10")
    visual_quality: float = Field(description="Score out of 10")
    color_consistency: float = Field(description="Score out of 10")
    storytelling_flow: float = Field(description="Score out of 10")
    overall_experience: float = Field(description="Score out of 10")


class HighLeverageFix(BaseModel):
    title: str = Field(description="Short title of the fix")
    why_it_matters: str = Field(description="Impact on viewer perception and retention")
    exact_change: str = Field(description="Specific editing cut or adjustment")
    retention_impact: str = Field(description="Expected gain in watch time")


class FinalPolishReviewSchema(BaseModel):
    overall_score: float = Field(description="Overall rating out of 10")
    scores: PolishScores
    top_3_improvements: List[HighLeverageFix] = Field(default_factory=list)


# --- 7. The Retention Audit ---
class DropOffPoint(BaseModel):
    timestamp_or_section: str = Field(description="Timestamp or script section identifier")
    cause_description: str = Field(description="Why viewer attention stumbles")
    likely_viewer_reaction: str = Field(description="Viewer psychological reaction")
    targeted_fix: str = Field(description="Pattern interrupt, cut, SFX, or visual payoff fix")


class RetentionAuditSchema(BaseModel):
    drop_off_points: List[DropOffPoint] = Field(default_factory=list)
    alternative_hooks: List[str] = Field(default_factory=list, description="🔥 3 high-energy alternative 10-second hooks")


# =============================================================================
# 2. POST-PRODUCTION ADVISOR ENGINE
# =============================================================================

class PostProductionAdvisor:
    """
    Expert Post-Production Advisory Engine.
    Processes text inputs through senior editor personas and generates structured JSON outputs.
    """

    TEMPLATES: Dict[str, Dict[str, Any]] = {
        "editing_blueprint": {
            "name": "The Editing Blueprint",
            "persona": "Senior Video Editor (15+ years YouTube & Documentary editing)",
            "required_inputs": ["footage_description"],
            "schema_cls": EditingBlueprintSchema,
            "fallback": {
                "summary": "High-retention editing blueprint focusing on fast cuts, visual pattern interrupts, and audio dynamics.",
                "timeline": [
                    {
                        "timestamp": "00:00 - 00:03",
                        "editing_action": "Hard cut / Hook zoom",
                        "broll_visuals": "Kinetic typography text overlay with flash frame",
                        "audio_sfx": "Impact bass drop + Whoosh SFX",
                        "editing_notes": "Grab viewer attention immediately within first 3 seconds"
                    }
                ]
            }
        },
        "script_flow_optimization": {
            "name": "Script Flow Optimization",
            "persona": "Content Retention Strategist (Short-Form & YouTube Specialist)",
            "required_inputs": ["script"],
            "schema_cls": ScriptOptimizationSchema,
            "fallback": {
                "weak_moments": [
                    {
                        "section_name": "Intro Preamble",
                        "issue_description": "Slow backstory lowers retention",
                        "suggested_fix": "Cut preamble and jump straight into action"
                    }
                ],
                "hook_rewrite": "Stop doing this mistake before it ruins your workflow.",
                "first_10s_rewrite": "Here is the exact framework top creators use to scale retention by 300%.",
                "revised_sections": [{"original": "Welcome back to the channel today...", "revised": "Here is what nobody tells you about..."}],
                "editing_strategy": ["Apply punch-in zooms on key nouns", "Add text highlight overlays"]
            }
        },
        "style_reverse_engineering": {
            "name": "Style Reverse Engineering",
            "persona": "Master Video Editor & Visual Style Analyst",
            "required_inputs": ["style_description", "video_concept"],
            "schema_cls": StyleReverseEngineeringSchema,
            "fallback": {
                "pacing_analysis": "Fast-paced documentary style with 1.8s average shot duration.",
                "transition_style": "Whip pans, optical blurs, and match cuts.",
                "camera_movement_framing": "Handheld micro-jitters with tight center framing.",
                "color_grading_lighting": "High contrast teal and orange color grade.",
                "sound_design_layering": "Layered Foley sound design with ducked ambient synth pad.",
                "recreation_guide": [
                    {"step_number": 1, "category": "Pacing", "instructions": "Cut every 1.5 to 2.5 seconds on beat changes."}
                ]
            }
        },
        "technical_export_setup": {
            "name": "Technical Export Setup",
            "persona": "Post-Production Supervisor (Broadcast Quality & Platform Compression Specialist)",
            "required_inputs": ["platform", "content_style"],
            "schema_cls": TechnicalExportSchema,
            "fallback": {
                "resolution_aspect": "3840x2160 (16:9 4K UHD)",
                "frame_rate_motion": "23.976 fps (180 degree shutter angle)",
                "codec_container": "H.264 / MP4 (High Profile, Level 5.1)",
                "bitrate_range": "45 - 68 Mbps (VBR 2-Pass)",
                "color_profile": "Rec.709 / Gamma 2.4",
                "audio_spec": "AAC-LC, 48.0 kHz, 320 kbps Stereo",
                "compression_tips": ["Render at 4K resolution even for 1080p target to get VP09/AV1 codec allocation on YouTube."],
                "common_mistakes_to_avoid": ["Exporting in RGB full range instead of legal video range."]
            }
        },
        "raw_footage_triage": {
            "name": "Raw Footage Triage",
            "persona": "Lead Video Editor (Footage Triage & Assembly Lead)",
            "required_inputs": ["footage_log"],
            "schema_cls": RawFootageTriageSchema,
            "fallback": {
                "gold_moments": [
                    {"timestamp": "01:14 - 01:30", "reason": "High-energy delivery with clean explanation", "suggested_edit": "Use as main A-roll core take"}
                ],
                "trims": [
                    {"timestamp": "00:45 - 00:52", "reason": "Awkward pause and false start", "suggested_edit": "Cut out completely"}
                ],
                "polish_items": [
                    {"timestamp": "02:10", "reason": "Key concept mentioned", "suggested_edit": "Overlay 3D text graphic"}
                ]
            }
        },
        "final_polish_review": {
            "name": "Final Polish Review",
            "persona": "Creative Director (Pre-Publication Quality & Polish Reviewer)",
            "required_inputs": ["current_cut_description"],
            "schema_cls": FinalPolishReviewSchema,
            "fallback": {
                "overall_score": 8.5,
                "scores": {
                    "pacing_retention": 8.5,
                    "audio_balance": 9.0,
                    "visual_quality": 8.5,
                    "color_consistency": 8.0,
                    "storytelling_flow": 8.5,
                    "overall_experience": 8.5
                },
                "top_3_improvements": [
                    {
                        "title": "Tighten Intro Gap",
                        "why_it_matters": "Prevents 5-second viewer drop-off",
                        "exact_change": "Trim 12 frames before first spoken word",
                        "retention_impact": "+15% retention in first 30 seconds"
                    }
                ]
            }
        },
        "the_retention_audit": {
            "name": "The Retention Audit",
            "persona": "Audience Retention Analyst (YouTube & Short-Form Performance Specialist)",
            "required_inputs": ["script_or_timeline_log"],
            "schema_cls": RetentionAuditSchema,
            "fallback": {
                "drop_off_points": [
                    {
                        "timestamp_or_section": "00:45",
                        "cause_description": "Static talking head with no visual change for 8 seconds",
                        "likely_viewer_reaction": "Boredom and scroll away",
                        "targeted_fix": "Add B-roll overlay and punch-in zoom"
                    }
                ],
                "alternative_hooks": [
                    "What if everything you knew about video editing was wrong?",
                    "This 10-second edit trick doubled my channel watch time.",
                    "Here is the secret post-production workflow used by million-subscriber channels."
                ]
            }
        }
    }

    @classmethod
    def list_templates(cls) -> List[Dict[str, Any]]:
        """Returns metadata for all available advisory templates."""
        result = []
        for t_id, info in cls.TEMPLATES.items():
            result.append({
                "template_id": t_id,
                "name": info["name"],
                "persona": info["persona"],
                "required_inputs": info["required_inputs"]
            })
        return result

    @classmethod
    def analyze_advisory(cls, template_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes advisory analysis for the given template_id and inputs text dictionary.
        Returns structured JSON output conforming to the template's Pydantic schema.
        """
        t_info = cls.TEMPLATES.get(template_id)
        if not t_info:
            raise ValueError(f"Invalid template_id '{template_id}'. Available: {list(cls.TEMPLATES.keys())}")

        # Validate required inputs
        missing = [inp for inp in t_info["required_inputs"] if not inputs.get(inp) or not str(inputs[inp]).strip()]
        if missing:
            raise ValueError(f"Missing required text input(s) for template '{template_id}': {missing}")

        persona = t_info["persona"]

        # Build template-specific prompt & JSON schema prompt
        if template_id == "editing_blueprint":
            user_prompt = f"Footage Description: {inputs.get('footage_description')}"
            schema_fmt = (
                "{\n"
                '  "summary": "High-level directorial summary",\n'
                '  "timeline": [\n'
                '    {\n'
                '      "timestamp": "00:00 - 00:05",\n'
                '      "editing_action": "Cut type or zoom",\n'
                '      "broll_visuals": "B-roll or overlay graphic",\n'
                '      "audio_sfx": "Music cue or SFX",\n'
                '      "editing_notes": "Retention directive"\n'
                '    }\n'
                '  ]\n'
                "}"
            )
        elif template_id == "script_flow_optimization":
            aud = inputs.get("target_audience", "General Audience")
            user_prompt = f"Target Audience: {aud}\nScript Text:\n{inputs.get('script')}"
            schema_fmt = (
                "{\n"
                '  "weak_moments": [{"section_name": "...", "issue_description": "...", "suggested_fix": "..."}],\n'
                '  "hook_rewrite": "Attention-grabbing hook rewrite",\n'
                '  "first_10s_rewrite": "Curiosity-maximizing first 10s rewrite",\n'
                '  "revised_sections": [{"original": "...", "revised": "..."}],\n'
                '  "editing_strategy": ["Jump cut rule", "Zoom rule"]\n'
                "}"
            )
        elif template_id == "style_reverse_engineering":
            user_prompt = f"Reference Video Style:\n{inputs.get('style_description')}\n\nMy Video Concept:\n{inputs.get('video_concept')}"
            schema_fmt = (
                "{\n"
                '  "pacing_analysis": "Pacing description",\n'
                '  "transition_style": "Transition styles",\n'
                '  "camera_movement_framing": "Framing styles",\n'
                '  "color_grading_lighting": "Color parameters",\n'
                '  "sound_design_layering": "Sound design",\n'
                '  "recreation_guide": [{"step_number": 1, "category": "Pacing", "instructions": "..."}]\n'
                "}"
            )
        elif template_id == "technical_export_setup":
            user_prompt = f"Target Platform: {inputs.get('platform')}\nContent Style: {inputs.get('content_style')}"
            schema_fmt = (
                "{\n"
                '  "resolution_aspect": "3840x2160 (16:9)",\n'
                '  "frame_rate_motion": "23.976 fps",\n'
                '  "codec_container": "H.264 / MP4",\n'
                '  "bitrate_range": "45 - 68 Mbps",\n'
                '  "color_profile": "Rec.709",\n'
                '  "audio_spec": "AAC-LC 48kHz 320kbps",\n'
                '  "compression_tips": ["Tip 1"],\n'
                '  "common_mistakes_to_avoid": ["Mistake 1"]\n'
                "}"
            )
        elif template_id == "raw_footage_triage":
            user_prompt = f"Raw Footage Shot Log / Transcript:\n{inputs.get('footage_log')}"
            schema_fmt = (
                "{\n"
                '  "gold_moments": [{"timestamp": "01:00", "reason": "...", "suggested_edit": "..."}],\n'
                '  "trims": [{"timestamp": "00:30", "reason": "...", "suggested_edit": "..."}],\n'
                '  "polish_items": [{"timestamp": "02:00", "reason": "...", "suggested_edit": "..."}]\n'
                "}"
            )
        elif template_id == "final_polish_review":
            user_prompt = f"Current Cut Description & Specifics:\n{inputs.get('current_cut_description')}"
            schema_fmt = (
                "{\n"
                '  "overall_score": 8.5,\n'
                '  "scores": {"pacing_retention": 8.5, "audio_balance": 9.0, "visual_quality": 8.5, "color_consistency": 8.0, "storytelling_flow": 8.5, "overall_experience": 8.5},\n'
                '  "top_3_improvements": [{"title": "Fix 1", "why_it_matters": "...", "exact_change": "...", "retention_impact": "..."}]\n'
                "}"
            )
        elif template_id == "the_retention_audit":
            user_prompt = f"Content Script or Timeline Log:\n{inputs.get('script_or_timeline_log')}"
            schema_fmt = (
                "{\n"
                '  "drop_off_points": [{"timestamp_or_section": "00:45", "cause_description": "...", "likely_viewer_reaction": "...", "targeted_fix": "..."}],\n'
                '  "alternative_hooks": ["Hook 1", "Hook 2", "Hook 3"]\n'
                "}"
            )
        else:
            user_prompt = str(inputs)
            schema_fmt = "{}"

        system_prompt = (
            f"You are a world-class post-production specialist acting as: {persona}.\n"
            "Analyze the user's provided text input thoroughly and provide expert post-production advisory.\n"
            f"Output MUST be strict raw JSON without markdown codeblock syntax matching this EXACT schema structure:\n{schema_fmt}"
        )

        try:
            raw_result = LLMService.generate_json(user_prompt, system_prompt, fallback_dict=t_info["fallback"])
            # Validate schema
            schema_cls = t_info["schema_cls"]
            validated_obj = schema_cls(**raw_result)
            return validated_obj.dict()
        except Exception as e:
            logger.warning(f"PostProductionAdvisor: Exception during LLM generation/validation for '{template_id}' ({e}), using fallback.")
            return t_info["fallback"]
