"""
Storyboard Schema & Scene Sequencer (v2 - Advanced)
Inspired by OpenMontage schemas/ and code2mp4 storyboard/ modules.

v2 additions over v1:
  - User-provided multi-scene JSON storyboard input (custom speech per scene)
  - Animated visual hints per scene: chart, diagram, or slide embed
  - Background image/gradient style selection
  - parse_user_storyboard() to accept raw JSON from Angular UI
"""
import json
import logging
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


# ---------------------------------------------------------------------------
# Pydantic data models  (OpenMontage JSON storyboard schema v2)
# ---------------------------------------------------------------------------

class TextLayer(BaseModel):
    """A single text element rendered on a scene frame."""
    text: str
    position: str = "center"
    font_scale: float = 1.2
    color: List[int] = Field(default_factory=lambda: [248, 250, 252])
    bold: bool = False
    entrance: str = "typewriter"    # typewriter, fade_in, slide_up, instant


from pydantic import BaseModel, Field, field_validator

class VisualOverlay(BaseModel):
    """An animated chart, diagram, or image overlay on a scene."""
    overlay_type: str = "none"      # none, bar_chart, line_chart, pie_chart, architecture_diagram, workflow_diagram
    title: str = ""
    data_labels: List[str] = Field(default_factory=list)
    data_values: List[float] = Field(default_factory=list)

    @field_validator("data_values", mode="before")
    @classmethod
    def sanitize_values(cls, v):
        if isinstance(v, list):
            flat = []
            for item in v:
                if isinstance(item, (int, float)):
                    flat.append(float(item))
                elif isinstance(item, list):
                    for sub in item:
                        try:
                            flat.append(float(sub))
                        except (ValueError, TypeError):
                            pass
                elif isinstance(item, str):
                    try:
                        flat.append(float(item))
                    except ValueError:
                        pass
            return flat
        return v


class SceneDefinition(BaseModel):
    """One scene in a storyboard -- the atomic unit of a montage."""
    scene_id: str
    scene_title: str
    duration_sec: float = 4.0
    background_color: List[int] = Field(default_factory=lambda: [42, 23, 15])
    background_style: str = "gradient"    # solid, gradient, dark, light
    text_layers: List[TextLayer] = Field(default_factory=list)
    transition: str = "fade"              # fade, slide_left, dissolve, cut, zoom_in
    narration: Optional[str] = None       # Auto-generated TTS text
    user_speech: Optional[str] = None     # User-provided exact speech text (takes priority)
    speech_text: Optional[str] = None     # Alias for user-provided speech text
    voice: Optional[str] = "en-US-JennyNeural" # Edge-TTS neural voice per scene
    visual_overlay: Optional[VisualOverlay] = None
    motion_zoom: float = 1.08
    motion_profile: Optional[str] = "zoom_in"  # zoom_in, zoom_out, pan_left_to_right, pan_right_to_left
    # Search terms authored by the AI screenwriter for this specific scene. When present
    # they take priority over queries derived from narration, because the screenwriter
    # knows what the viewer is meant to SEE, not just what is being said.
    stock_search_queries: List[str] = Field(default_factory=list)
    on_screen_stats: List[str] = Field(default_factory=list)
    # Filename of a user upload the AI Director assigned to this scene (highest media priority).
    uploaded_file_ref: Optional[str] = None
    # Talking-presenter support (inert: engine removed, see LICENSES.md R2)
    presenter_mode: bool = False              # If True, render this scene as an audio-driven talking avatar
    presenter_avatar_image: Optional[str] = None  # Path/URL to the presenter portrait or base video
    presenter_clip_path: Optional[str] = None      # Populated at runtime with the generated avatar clip
    presenter_is_real_lipsync: Optional[bool] = None  # Runtime flag (unused since the lip-sync engine was removed)


class Storyboard(BaseModel):
    """Full storyboard document -- the input contract for the rendering pipeline."""
    title: str
    resolution: List[int] = Field(default_factory=lambda: [1280, 720])
    fps: int = 30
    music_mood: str = "corporate"         # corporate, upbeat, dramatic, calm
    scenes: List[SceneDefinition] = Field(default_factory=list)
    total_duration_sec: float = 0.0
    tts_provenance_manifest: Optional[List[str]] = None
    has_degraded_audio_placeholder: Optional[bool] = False
    editing_blueprint: Optional[Any] = None
    sfx_cues: Optional[List[Any]] = Field(default_factory=list)
    # Directory holding this job's user uploads, if any (Phase 3 Track A).
    upload_dir: Optional[str] = None
    # Per-job TTS engine override ('kokoro' | 'edge'). None falls back to the
    # TTS_ENGINE environment variable. Carried here rather than mutating the
    # environment so concurrent jobs can't race each other's engine choice.
    tts_engine: Optional[str] = None
    # Narration language for this video ('en' | 'fr'), carried over from the planning
    # request. The storyboard is the only object handed to the TTS stage, so without this
    # field the language chosen at planning time was lost in between and every video was
    # voiced in English -- including ones whose script the LLM had correctly written in
    # French. See agents/video/language.py for the voice each code resolves to.
    language: str = "en"
    # Snapshot of the user's brand kit for this job, or None. Only the font and logo are
    # read from here -- the palette already reached the scenes as background colours via
    # the Director's brief, so duplicating it would give the renderer a second copy that
    # could disagree with what was actually planned.
    brand_kit: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# User storyboard parser  (accepts JSON from Angular UI)
# ---------------------------------------------------------------------------

class StoryboardParser:
    """
    Parses user-provided multi-scene storyboard JSON from the Angular frontend.
    Accepts either a free-form prompt or structured scene definitions.
    """

    @classmethod
    def parse(cls, input_data: Union[str, Dict]) -> Optional[Storyboard]:
        """
        Try to parse input_data as a JSON storyboard (str or dict).
        Returns a Storyboard if valid with scenes, else None (use planner).
        """
        if isinstance(input_data, dict):
            if "scenes" in input_data:
                return cls._from_json(input_data)
            return None

        try:
            data = json.loads(input_data)
            if isinstance(data, dict) and "scenes" in data:
                return cls._from_json(data)
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    @classmethod
    def _from_json(cls, data: Dict) -> Storyboard:
        scenes = []
        for i, s in enumerate(data.get("scenes", [])):
            text_layers = []
            for tl in s.get("text_layers", []):
                text_layers.append(TextLayer(**{k: v for k, v in tl.items() if k in TextLayer.__fields__}))
            if not text_layers and s.get("scene_title"):
                text_layers.append(TextLayer(text=s["scene_title"], position="center", font_scale=1.5, bold=True))

            visual = None
            if s.get("visual_overlay"):
                if isinstance(s["visual_overlay"], dict):
                    visual = VisualOverlay(**{k: v for k, v in s["visual_overlay"].items() if k in VisualOverlay.__fields__})
                elif isinstance(s["visual_overlay"], str):
                    visual = VisualOverlay(overlay_type=s["visual_overlay"], title=s.get("scene_title") or s.get("title", ""))

            speech = s.get("user_speech") or s.get("speech_text")
            sc_title = s.get("scene_title") or s.get("title") or f"Scene {i+1}"

            scenes.append(SceneDefinition(
                scene_id=s.get("scene_id", f"scene_{i+1}"),
                scene_title=sc_title,
                duration_sec=float(s.get("duration_sec", 4)),
                background_style=s.get("background_style", "gradient"),
                text_layers=text_layers,
                transition=s.get("transition", "fade"),
                narration=s.get("narration"),
                user_speech=speech,
                speech_text=speech,
                voice=s.get("voice", "en-US-JennyNeural"),
                visual_overlay=visual,
            ))

        total = sum(sc.duration_sec for sc in scenes)
        mood = data.get("music_mood") or (scenes[0].music_mood if hasattr(scenes[0], "music_mood") else "corporate")
        for sc in data.get("scenes", []):
            if isinstance(sc, dict) and sc.get("music_mood"):
                mood = sc["music_mood"]
                break

        return Storyboard(
            title=data.get("video_title") or data.get("title", "Custom Video"),
            resolution=data.get("resolution", [1280, 720]),
            fps=data.get("fps", 30),
            music_mood=mood,
            scenes=scenes,
            total_duration_sec=total,
        )


# ---------------------------------------------------------------------------
# Storyboard Planner  (code2mp4 storyboard/ sequencing + LLM)
# ---------------------------------------------------------------------------

class StoryboardPlanner:
    """
    Analyses a user prompt and builds a structured Storyboard with multiple
    scenes, text layers, transitions, visual overlays, and narration cues.
    """

    @classmethod
    def plan(cls, prompt: str, num_scenes: int = 5) -> Storyboard:
        logger.info(f"StoryboardPlanner: Building {num_scenes}-scene storyboard for '{prompt[:60]}...'")

        # First try parsing as user-provided JSON storyboard
        parsed = StoryboardParser.parse(prompt)
        if parsed:
            logger.info(f"StoryboardPlanner: Parsed user-provided storyboard ({len(parsed.scenes)} scenes)")
            return parsed

        # Try LLM-powered planning; fall back to deterministic template
        try:
            return cls._llm_plan(prompt, num_scenes)
        except Exception as e:
            logger.warning(f"StoryboardPlanner: LLM planning failed ({e}), using template plan")
            return cls._template_plan(prompt, num_scenes)

    @classmethod
    def _llm_plan(cls, prompt: str, num_scenes: int) -> Storyboard:
        import sys
        from pathlib import Path
        backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from app.services.llm import LLMService

        system_prompt = (
            "You are a professional video storyboard planner. Given a topic, "
            "produce a JSON storyboard with multiple scenes. Each scene can have "
            "visual overlays (bar_chart, line_chart, architecture_diagram). "
            "Output strict JSON:\n"
            '{"title":"...","scenes":['
            '{"scene_id":"scene_1","scene_title":"...","duration_sec":4,'
            '"narration":"voiceover text","transition":"fade",'
            '"text_layers":[{"text":"...","position":"center","font_scale":1.2,'
            '"entrance":"typewriter"}],'
            '"visual_overlay":{"overlay_type":"bar_chart","title":"Performance",'
            '"data_labels":["A","B"],"data_values":[85,92]}}]}'
        )
        fallback = cls._template_plan(prompt, num_scenes).dict()
        raw = LLMService.generate_json(prompt, system_prompt, fallback)

        scenes = []
        for i, s in enumerate(raw.get("scenes", [])):
            layers = [TextLayer(**tl) for tl in s.get("text_layers", [{"text": s.get("scene_title", f"Scene {i+1}")}])]
            visual = None
            if s.get("visual_overlay") and s["visual_overlay"].get("overlay_type", "none") != "none":
                visual = VisualOverlay(**s["visual_overlay"])

            scenes.append(SceneDefinition(
                scene_id=s.get("scene_id", f"scene_{i+1}"),
                scene_title=s.get("scene_title", f"Scene {i+1}"),
                duration_sec=float(s.get("duration_sec", 4)),
                text_layers=layers,
                transition=s.get("transition", "fade"),
                narration=s.get("narration"),
                user_speech=s.get("user_speech"),
                visual_overlay=visual,
            ))

        if len(scenes) < 4:
            logger.warning(f"StoryboardPlanner: LLM generated {len(scenes)} scenes (<4), using template plan")
            return cls._template_plan(prompt, num_scenes)

        total = sum(sc.duration_sec for sc in scenes)
        return Storyboard(title=raw.get("title", prompt[:60]), scenes=scenes, total_duration_sec=total)

    @classmethod
    def _template_plan(cls, prompt: str, num_scenes: int) -> Storyboard:
        snippet = prompt[:50] + ("..." if len(prompt) > 50 else "")
        scenes = [
            SceneDefinition(
                scene_id="scene_1", scene_title="Title Card", duration_sec=4.0,
                text_layers=[
                    TextLayer(text="CreateFlow AI", position="center", font_scale=2.0,
                              color=[247, 85, 168], bold=True, entrance="fade_in"),
                    TextLayer(text=snippet, position="bottom", font_scale=0.9,
                              color=[200, 200, 200], entrance="slide_up"),
                ],
                transition="fade",
                narration=f"Welcome to CreateFlow AI. Today we explore: {snippet}"
            ),
            SceneDefinition(
                scene_id="scene_2", scene_title="Platform Overview", duration_sec=4.0,
                text_layers=[
                    TextLayer(text="Platform Overview", position="top", font_scale=1.6,
                              color=[248, 250, 252], bold=True, entrance="typewriter"),
                    TextLayer(text="Multi-Agent Content Pipeline", position="center",
                              font_scale=1.0, color=[148, 163, 184], entrance="fade_in"),
                ],
                transition="slide_left",
                narration="Our platform uses a multi-agent pipeline to generate professional content.",
            ),
            SceneDefinition(
                scene_id="scene_3", scene_title="Key Metrics", duration_sec=4.0,
                text_layers=[
                    TextLayer(text="Performance Metrics", position="top", font_scale=1.6,
                              color=[248, 250, 252], bold=True, entrance="typewriter"),
                ],
                transition="dissolve",
                narration="Our benchmarks show exceptional throughput and quality scores.",
                visual_overlay=VisualOverlay(
                    overlay_type="bar_chart",
                    title="Agent Performance",
                    data_labels=["Presentation", "LaTeX Report", "Video"],
                    data_values=[95, 92, 88],
                ),
            ),
            SceneDefinition(
                scene_id="scene_4", scene_title="Key Features", duration_sec=4.0,
                text_layers=[
                    TextLayer(text="Key Features", position="top", font_scale=1.6,
                              color=[248, 250, 252], bold=True, entrance="typewriter"),
                    TextLayer(text="Presentations | Reports | Videos", position="center",
                              font_scale=1.1, color=[99, 102, 241], entrance="slide_up"),
                ],
                transition="zoom_in",
                narration="We generate professional presentations, technical reports, and video montages."
            ),
            SceneDefinition(
                scene_id="scene_5", scene_title="Conclusion", duration_sec=4.0,
                text_layers=[
                    TextLayer(text="Thank You", position="center", font_scale=2.0,
                              color=[16, 185, 129], bold=True, entrance="fade_in"),
                    TextLayer(text="Generated by CreateFlow AI Engine", position="bottom",
                              font_scale=0.8, color=[148, 163, 184], entrance="slide_up"),
                ],
                transition="fade",
                narration="Thank you for watching. This video was generated automatically by CreateFlow AI."
            ),
        ]
        total = sum(s.duration_sec for s in scenes)
        return Storyboard(title=f"CreateFlow AI -- {snippet}", scenes=scenes, total_duration_sec=total)
