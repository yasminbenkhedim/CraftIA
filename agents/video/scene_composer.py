"""
Scene Composer v3 -- maps storyboard scenes to a rendering timeline.
Inspired by OpenMontage skills/, remotion-video-skill scene_composer.js,
Scene Composition Engine inspired by OpenMontage, code2mp4, and CutAgent.
"""
import os
import logging
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from pydantic import BaseModel, Field
from agents.video.storyboard import Storyboard, SceneDefinition, TextLayer

logger = logging.getLogger("uvicorn")


# ---------------------------------------------------------------------------
# Style Harness & Reference Models (CutAgent style-engine.ts inspiration)
# ---------------------------------------------------------------------------

class ReferenceImage(BaseModel):
    id: str
    ref_type: str = "last-frame"      # last-frame, character, style, product
    label: str = ""
    source_scene_id: Optional[str] = None
    frame_buffer: Optional[Any] = Field(default=None, exclude=True)  # NumPy BGR array


class StyleContext(BaseModel):
    auto_chain_last_frame: bool = True
    references: List[ReferenceImage] = Field(default_factory=list)
    last_frame_buffer: Optional[Any] = None  # Holds raw NumPy BGR array for next scene transition

    class Config:
        arbitrary_types_allowed = True


class StyleEngine:
    """
    Style continuity manager -- tracks reference images, visual anchors,
    and scene-to-scene style persistence across timeline rendering.
    """

    @classmethod
    def on_scene_completed(cls, scene_id: str,
                           final_frame: Optional[np.ndarray],
                           current_style: StyleContext) -> StyleContext:
        """
        After scene N completes, extract its final frame and store as 'last-frame'
        reference in the reference bank (replacing stale last-frame entries).
        """
        if final_frame is None:
            return current_style

        # Remove old last-frame references
        updated_refs = [r for r in current_style.references if r.ref_type != "last-frame"]

        if current_style.auto_chain_last_frame:
            frame_copy = final_frame.copy()
            new_ref = ReferenceImage(
                id=f"last-frame-{scene_id}",
                ref_type="last-frame",
                label=f"Last frame from {scene_id}",
                source_scene_id=scene_id,
                frame_buffer=frame_copy
            )
            updated_refs.append(new_ref)
            current_style.last_frame_buffer = frame_copy
            logger.info(f"StyleEngine: Chained last frame ({frame_copy.shape}) from '{scene_id}' for next scene visual continuity.")

        current_style.references = updated_refs
        return current_style

    @classmethod
    def plan_generation_order(cls, scenes: List[SceneDefinition],
                               style: StyleContext) -> List[List[SceneDefinition]]:
        """
        Plan generation order:
        If auto_chain_last_frame is True, scenes must run sequentially (each in its own batch).
        Otherwise, all scenes can run in a single parallel batch.
        """
        if not style.auto_chain_last_frame:
            return [scenes]

        # Fully sequential when last-frame chaining is active
        logger.info(f"StyleEngine: Planning sequential generation order for {len(scenes)} scenes (last-frame chained).")
        return [[s] for s in scenes]


# ---------------------------------------------------------------------------
# Timeline & Scheduling
# ---------------------------------------------------------------------------

class TimelineSegment:
    """One contiguous segment on the video timeline."""
    def __init__(self, scene: SceneDefinition, start_frame: int, end_frame: int,
                 transition_in_frames: int = 0):
        self.scene = scene
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.transition_in_frames = transition_in_frames
        self.frame_count = end_frame - start_frame
        self.overlay_start_frac = 0.15
        self.overlay_end_frac = 0.90
        self.last_frame_reference: Optional[np.ndarray] = None  # Reference frame from previous scene
        self.scene_graph_node: Optional[Any] = None
        self.continuity_context: Optional[Any] = None

    def __repr__(self):
        return (f"<TimelineSegment {self.scene.scene_id} "
                f"frames={self.start_frame}-{self.end_frame} "
                f"transition={self.scene.transition}>")


class TextEntranceSchedule:
    """
    Timing for a text layer's entrance/hold/exit within a segment, expressed as
    fractions of scene progress [0, 1]. Text layers (on-screen titles/hooks) fade
    out after a hold window instead of staying glued to the screen for the whole
    scene -- otherwise they visually compete with the bottom narration captions
    and read as a second, duplicate subtitle bar.
    """
    def __init__(self, layer_index: int, start_frac: float, duration_frac: float,
                 hold_frac: float = 0.35, exit_frac: float = 0.15):
        self.layer_index = layer_index
        self.start_frac = start_frac
        self.duration_frac = duration_frac
        self.hold_frac = hold_frac
        self.exit_frac = exit_frac


class SceneComposer:
    """
    Builds a frame-accurate timeline from a Storyboard, resolving
    transitions, computing text-layer positions, and managing style continuity.
    """

    TRANSITION_DURATION_SEC = 1.0

    TRANSITION_OVERLAP = {
        "fade": 1.0,
        "slide_left": 1.0,
        "dissolve": 1.0,
        "zoom_in": 1.0,
        "morph_crossfade": 1.0,
        "cut": 0.0,
    }

    @classmethod
    def compose_timeline(cls, storyboard: Storyboard,
                         style: Optional[StyleContext] = None) -> List[TimelineSegment]:
        logger.info(f"SceneComposer: Building timeline for '{storyboard.title}' "
                     f"({len(storyboard.scenes)} scenes, {storyboard.fps} fps)")

        if style is None:
            style = StyleContext()

        # Phase 3 Track A: probe any user uploads once up front, so scenes the director
        # assigned an upload to can resolve it without re-probing per scene.
        uploaded_media = []
        upload_dir = getattr(storyboard, "upload_dir", None)
        if upload_dir:
            try:
                from agents.video.user_upload_manager import UserUploadManager
                uploaded_media = UserUploadManager.analyze(upload_dir)
            except Exception as e:
                logger.warning(f"SceneComposer: Upload analysis failed ({e}); continuing with stock media.")

        # Compute batch order
        batches = StyleEngine.plan_generation_order(storyboard.scenes, style)

        # Step 9 Real Pipeline Integration: Batch Visual Query Generation (Upgrade 2)
        from agents.video.visual_query_generator import VisualQueryGenerator
        from agents.video.visual_query_schemas import VisualQueryInput, VisualQueryDiagnostics, VisualQueryBudget
        from agents.video.scene_visual_memory import SceneVisualMemory
        from agents.video.continuity.visual_continuity_engine import VisualContinuityEngine
        from agents.video.continuity.anchor_builder import VisualStyleAnchorBuilder
        from agents.video.continuity.scene_graph import (
            SceneGraphNode, BackgroundNode, MediaNode, ChartNode, OverlayNode, CaptionNode, TitleNode, CameraMotionNode, TransitionNode
        )
        from agents.video.orchestration.schemas import (
            VideoGenerationRequest, DirectorBrief, GlobalVisualDirection,
            NarrativeStructure, PacingStrategy, AudioDirection
        )

        memory = SceneVisualMemory()
        budget = VisualQueryBudget()

        # Build or retrieve VisualStyleAnchor for whole-video visual trajectory
        dir_brief = DirectorBrief(
            project_title=storyboard.title,
            objective="Visual story consistency",
            target_audience="General Audience",
            core_message="Visual story consistency",
            narrative_structure=NarrativeStructure.PROBLEM_SOLUTION,
            tone="Professional",
            emotional_progression=[],
            opening_hook="Visual continuity opening",
            closing_message="Visual continuity conclusion",
            pacing_strategy=PacingStrategy(average_scene_duration_sec=3.0, rhythm_style="moderate"),
            total_duration_seconds=30.0,
            recommended_scene_count=max(len(storyboard.scenes), 1),
            scene_duration_budget=[3.0] * max(len(storyboard.scenes), 1),
            global_visual_direction=GlobalVisualDirection(color_palette=["#0F172A", "#38BDF8"]),
            audio_direction=AudioDirection()
        )
        req_gen = VideoGenerationRequest(prompt=storyboard.title)
        anchor = VisualStyleAnchorBuilder.build_anchor(req_gen, dir_brief)
        continuity_contexts = VisualContinuityEngine.plan_video_continuity(storyboard, anchor)
        context_map = {ctx.scene_id: ctx for ctx in continuity_contexts}

        vq_inputs = [
            VisualQueryInput(
                scene_id=sc.scene_id,
                scene_title=sc.scene_title,
                narration=sc.narration or sc.user_speech or sc.speech_text,
                storyboard_title=storyboard.title,
                visual_overlay_type=sc.visual_overlay.overlay_type if sc.visual_overlay else None,
                background_style=sc.background_style,
                aspect_ratio="16:9" if not storyboard.resolution else (
                    "16:9" if storyboard.resolution[0] >= storyboard.resolution[1] else "9:16"
                )
            ) for sc in storyboard.scenes
        ]

        vq_results = VisualQueryGenerator.generate_batch(vq_inputs, memory=memory, budget=budget)
        vq_map = {inp.scene_id: res for inp, res in zip(vq_inputs, vq_results)}

        segments: List[TimelineSegment] = []
        current_frame = 0

        for batch in batches:
            prev_provider = None
            for scene in batch:
                scene_frames = int(scene.duration_sec * storyboard.fps)
                overlap_mult = cls.TRANSITION_OVERLAP.get(scene.transition, 1.0)
                trans_frames = int(cls.TRANSITION_DURATION_SEC * storyboard.fps * overlap_mult)

                from agents.video.providers import (
                    ProviderRegistry, MediaRequest, MediaType, AssetValidator, ProviderSelectionProfile
                )

                vq_res = vq_map.get(scene.scene_id)
                cont_ctx = context_map.get(scene.scene_id)

                # Phase 3 (Smart Media Assembly): the AI screenwriter authored search terms
                # describing what the viewer should SEE in this scene. Those beat queries
                # derived from narration text, so promote them ahead of the generated ones.
                authored_queries = [q for q in (getattr(scene, "stock_search_queries", []) or []) if q and q.strip()]
                if authored_queries and vq_res is not None:
                    generated_primary = vq_res.primary_query
                    vq_res.primary_query = authored_queries[0]
                    # Keep the generated query as a fallback behind the remaining authored ones.
                    alternates = authored_queries[1:] + [generated_primary] + list(vq_res.alternate_queries or [])
                    seen, deduped = set(), []
                    for q in alternates:
                        if q and q not in seen and q != vq_res.primary_query:
                            seen.add(q)
                            deduped.append(q)
                    vq_res.alternate_queries = deduped[:4]
                    logger.info(
                        f"SceneComposer: Scene '{scene.scene_id}' using screenwriter-authored "
                        f"search query '{vq_res.primary_query}' (was '{generated_primary}')."
                    )

                query_str = vq_res.primary_query if vq_res else (scene.narration[:60] if scene.narration else scene.scene_id)

                pref_types = [MediaType.PROCEDURAL_GRAPHIC, MediaType.TITLE_CARD] if scene.visual_overlay else [MediaType.STOCK_VIDEO, MediaType.STOCK_IMAGE, MediaType.LOCAL_ASSET, MediaType.GENERATED_IMAGE]
                req = MediaRequest(
                    scene_id=scene.scene_id,
                    query=query_str,
                    media_type_preferences=pref_types,
                    target_width=storyboard.resolution[0],
                    target_height=storyboard.resolution[1],
                    minimum_duration=scene.duration_sec,
                    previous_scene_provider=prev_provider,
                    quality_profile=ProviderSelectionProfile.CINEMATIC_QUALITY,
                    visual_query_result=vq_res
                )

                selection_res = ProviderRegistry.select_provider(req)

                # Upgrade 3 & 4: Multi-Candidate Collection, Visual Continuity Context, & Semantic Media Ranking
                from agents.video.media_candidate_collector import MediaCandidateCollector
                from agents.video.semantic_media_ranker import SemanticMediaRanker
                from agents.video.media_ranking_schemas import MediaRankingInput, LatencyBreakdown

                lat_tracker = LatencyBreakdown()
                collected_pool, providers_queried = MediaCandidateCollector.collect_pool(
                    req, memory=memory, latency_tracker=lat_tracker
                )

                ranking_input = MediaRankingInput(
                    scene_id=scene.scene_id,
                    visual_query_result=vq_res,
                    scene_definition=scene,
                    storyboard_title=storyboard.title,
                    domain=getattr(storyboard, "domain", "general") or "general",
                    visual_style={"background_style": getattr(storyboard, "visual_style", "gradient") or "gradient"},
                    aspect_ratio="16:9",
                    candidates=collected_pool,
                    scene_memory=memory,
                    continuity_context=cont_ctx
                )

                ranked_selection = SemanticMediaRanker.rank(ranking_input, latency_tracker=lat_tracker)
                candidate = ranked_selection.selected_candidate

                # Scene media priority #1: a user upload the AI Director assigned to this
                # scene outranks anything the stock providers found.
                upload_ref = getattr(scene, "uploaded_file_ref", None)
                if upload_ref and uploaded_media:
                    from agents.video.user_upload_manager import UserUploadManager
                    matched = UserUploadManager.resolve_reference(uploaded_media, upload_ref)
                    if matched is not None:
                        candidate = UserUploadManager.build_media_candidate(
                            matched, scene.scene_id, storyboard.resolution[0], storyboard.resolution[1]
                        )
                        logger.info(
                            f"SceneComposer: Scene '{scene.scene_id}' using USER UPLOAD "
                            f"'{matched.filename}' (director-assigned)."
                        )

                # Fallback to ProviderRegistry legacy selection if collector returned empty pool
                if not candidate:
                    if selection_res.selected_provider_id:
                        provider = ProviderRegistry.get(selection_res.selected_provider_id)
                        candidate = provider.generate_or_retrieve(req)
                        if not AssetValidator.validate_candidate(candidate, req):
                            for fb_pid in selection_res.fallback_chain:
                                fb_prov = ProviderRegistry.get(fb_pid)
                                cand_fb = fb_prov.generate_or_retrieve(req)
                                if AssetValidator.validate_candidate(cand_fb, req):
                                    candidate = cand_fb
                                    selection_res.selected_provider_id = fb_pid
                                    break

                # Record the asset's provenance for the per-job attributions manifest.
                # Done here, after the user-upload override and the legacy fallback, so
                # what is recorded is the candidate actually composited (LICENSES.md R5).
                if candidate is not None:
                    from agents.video import attribution as _attribution
                    from agents.video.license_policy import LicensePolicyEvaluator as _LPE
                    _ok, _ltype, _score, _reason = _LPE.evaluate(
                        getattr(candidate, "license_name", None),
                        getattr(candidate, "attribution", None),
                        getattr(candidate, "provider_id", ""),
                    )
                    _attribution.record(candidate, scene_id=scene.scene_id, license_type=_ltype.value)

                # Record scene choices in upgraded SceneVisualMemory
                memory.record_scene(vq_res, candidate, cont_ctx)

                # Construct Declarative SceneGraphNode for Scene Graph
                sg_node = SceneGraphNode(
                    scene_id=scene.scene_id,
                    scene_title=scene.scene_title,
                    duration_sec=scene.duration_sec,
                    fps=storyboard.fps,
                    width=storyboard.resolution[0],
                    height=storyboard.resolution[1],
                    background=BackgroundNode(colors=anchor.palette.accent_colors or ["#0F172A", "#1E293B"]),
                    media=MediaNode(
                        asset_path=getattr(candidate, "asset_path", None),
                        remote_url=getattr(candidate, "remote_url", None),
                        provider_id=getattr(candidate, "provider_id", "procedural"),
                        attribution=getattr(candidate, "attribution", None)
                    ) if candidate else None,
                    chart=ChartNode(
                        chart_type=getattr(scene.visual_overlay, "overlay_type", None) if scene.visual_overlay else None,
                        title=getattr(scene.visual_overlay, "title", None) if scene.visual_overlay else None,
                        labels=getattr(scene.visual_overlay, "data_labels", None) or (getattr(scene.visual_overlay, "labels", None) or []),
                        data=getattr(scene.visual_overlay, "data_values", None) or (getattr(scene.visual_overlay, "data", None) or []),
                        palette_colors=[c.hex_value for c in anchor.palette.colors]
                    ) if scene.visual_overlay else None,
                    camera=CameraMotionNode(
                        framing=cont_ctx.target_framing if cont_ctx else CameraFraming.WIDE,
                        motion_vector=cont_ctx.recommended_motion if cont_ctx else CameraMotionVector.PUSH_IN
                    ),
                    transition=TransitionNode(
                        transition_type=cont_ctx.recommended_transition if cont_ctx else scene.transition,
                        duration_sec=cls.TRANSITION_DURATION_SEC
                    ),
                    continuity_context=cont_ctx
                )

                seg = TimelineSegment(
                    scene=scene,
                    start_frame=current_frame,
                    end_frame=current_frame + scene_frames,
                    transition_in_frames=trans_frames
                )
                seg.selected_provider_id = getattr(candidate, "provider_id", "procedural_background") if candidate else "procedural_background"
                seg.media_candidate = candidate
                seg.provider_selection_result = selection_res
                seg.visual_query_result = vq_res
                seg.ranked_media_selection = ranked_selection
                seg.scene_graph_node = sg_node
                seg.continuity_context = cont_ctx

                if vq_res:
                    seg.visual_query_diagnostics = VisualQueryDiagnostics(
                        scene_id=scene.scene_id,
                        original_narration=scene.narration or "",
                        storyboard_title=storyboard.title,
                        domain=vq_res.environment or "default",
                        primary_query=vq_res.primary_query,
                        alternate_queries=vq_res.alternate_queries,
                        fallback_query=vq_res.fallback_query,
                        quality_score=vq_res.quality_score,
                        confidence=vq_res.confidence,
                        extracted_subjects=vq_res.subjects,
                        extracted_actions=vq_res.actions,
                        extracted_environment=vq_res.environment,
                        generation_source=vq_res.generation_source,
                        llm_model=vq_res.llm_model,
                        token_usage=vq_res.token_usage,
                        generation_latency_ms=vq_res.generation_latency_ms,
                        cache_hit=vq_res.cache_hit,
                        cache_key=vq_res.cache_key,
                        provider_optimized_for=vq_res.provider_optimized_for,
                        skipped_reason=vq_res.skipped_reason
                    )

                if candidate:
                    prev_provider = candidate.provider_id

                segments.append(seg)
                current_frame += scene_frames

        logger.info(f"SceneComposer: Timeline composed -- {len(segments)} segments, {current_frame} total frames with VisualQueryGenerator semantic resolution.")
        return segments

    @classmethod
    def compute_text_entrance_schedule(cls, scene: SceneDefinition) -> List[TextEntranceSchedule]:
        schedules = []
        num_layers = len(scene.text_layers)
        for i, layer in enumerate(scene.text_layers):
            start_frac = (i / max(num_layers, 1)) * 0.4
            duration_frac = 0.3 if layer.entrance == "typewriter" else 0.2
            # Short hold + quick exit: on-screen titles/hooks are a brief flash (roughly
            # the first third of the scene), not a fixture that sits on screen next to
            # the narration captions for most of the scene's runtime.
            schedules.append(TextEntranceSchedule(i, start_frac, duration_frac, hold_frac=0.05, exit_frac=0.10))
        return schedules

    @classmethod
    def resolve_text_positions(cls, layer: TextLayer,
                                width: int, height: int) -> Tuple[int, int]:
        positions = {
            "center":       (width // 2, height // 2),
            "top":          (width // 2, int(height * 0.15)),
            "bottom":       (width // 2, int(height * 0.82)),
            "top_left":     (int(width * 0.08), int(height * 0.15)),
            "bottom_right": (int(width * 0.75), int(height * 0.85)),
        }
        return positions.get(layer.position, positions["center"])

    @classmethod
    def compose_and_render_scene(
        cls,
        scene_id: str,
        visual_description: str,
        duration_seconds: float,
        output_path: str,
        audio_path: Optional[str] = None,
        width: int = 1280,
        height: int = 720,
        fps: float = 30.0
    ) -> str:
        from agents.video.storyboard import Storyboard, SceneDefinition, TextLayer
        from agents.video.python_editor.renderer import VideoRenderer
        sb = Storyboard(
            title=f"Scene {scene_id}",
            aspect_ratio="16:9",
            resolution=[width, height],
            scenes=[SceneDefinition(
                scene_id=scene_id,
                scene_title=visual_description,
                duration_sec=duration_seconds,
                background_style="gradient",
                text_layers=[TextLayer(text=visual_description[:40], position="center")]
            )]
        )
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        VideoRenderer.render_storyboard(sb, output_path, fps=int(fps))
        return output_path
