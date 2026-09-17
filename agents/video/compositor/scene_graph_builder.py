"""
SceneGraphBuilder for Professional Multi-Layer Compositor (Upgrade 5).
Maps Storyboard scenes, TimelineSegments, and SceneContinuityContext into hierarchical DeclarativeSceneNodes.
"""
import uuid
import logging
from typing import List, Dict, Any, Optional
from agents.video.storyboard import Storyboard, SceneDefinition
from agents.video.continuity.schemas import VisualStyleAnchor
from agents.video.continuity.engine_schemas import SceneContinuityContext
from agents.video.compositor.schemas import (
    MasterSceneGraph, DeclarativeSceneNode, LayerGroupNode,
    BackgroundLayer, VideoLayer, ImageLayer, ChartLayer, CaptionLayer,
    OverlayLayer, LogoLayer, LowerThirdLayer, ShapeLayer, TitleLayer,
    LayerMask, MaskType, BlurEffect, ShadowEffect, GlowEffect, VignetteEffect,
    AnimationTrack, Keyframe, KeyframeValue, EasingType
)

logger = logging.getLogger("uvicorn")


class SceneGraphBuilder:
    """
    Constructs MasterSceneGraph and DeclarativeSceneNodes for VideoRenderer execution.
    """

    @classmethod
    def build_scene_graph(
        cls,
        storyboard: Storyboard,
        timeline_segments: List[Any],
        anchor: Optional[VisualStyleAnchor] = None
    ) -> MasterSceneGraph:
        master_uuid = str(uuid.uuid4())
        width, height = storyboard.resolution
        fps = storyboard.fps

        base_palette = ["#0F172A", "#38BDF8"]
        if anchor and anchor.palette and anchor.palette.colors:
            base_palette = [c.hex_value for c in anchor.palette.colors]

        from agents.video.camera.ai_camera_director import AICameraDirector

        # Upgrade 6: AI Camera Director Shot & Motion Track Planning
        continuity_contexts = [getattr(seg, "continuity_context", None) for seg in timeline_segments]
        continuity_contexts = [c for c in continuity_contexts if c is not None]
        camera_tracks = AICameraDirector.plan_camera_tracks(storyboard, continuity_contexts=continuity_contexts)
        camera_map = {tr.scene_id: tr for tr in camera_tracks}

        scene_nodes: List[DeclarativeSceneNode] = []

        for idx, seg in enumerate(timeline_segments):
            scene = seg.scene
            cont_ctx: Optional[SceneContinuityContext] = getattr(seg, "continuity_context", None)
            cand = getattr(seg, "media_candidate", None)

            # 1. Background Group
            bg_layer = BackgroundLayer(
                layer_id=f"bg_{scene.scene_id}",
                layer_name=f"Background {scene.scene_id}",
                z_index=0,
                fill_style=getattr(scene, "background_style", "gradient"),
                colors=cont_ctx.target_palette_hex if cont_ctx else base_palette
            )
            bg_group = LayerGroupNode(group_id="bg_grp", group_name="BackgroundGroup", z_index_base=0, layers=[bg_layer])

            # 2. Media Group (B-Roll Image or Video)
            media_layers = []
            if cand and getattr(cand, "asset_path", None):
                asset_name = getattr(cand, "asset_id", None) or getattr(cand, "provider_id", "broll_asset")
                img_layer = ImageLayer(
                    layer_id=f"img_{scene.scene_id}",
                    layer_name=f"B-Roll Asset {asset_name}",
                    z_index=1,
                    asset_path=cand.asset_path,
                    aspect_mode="cover"
                )
                media_layers.append(img_layer)

            media_group = LayerGroupNode(group_id="media_grp", group_name="MediaGroup", z_index_base=10, layers=media_layers)

            # 3. Graphics Group (Charts / Diagrams)
            gfx_layers = []
            if scene.visual_overlay and scene.visual_overlay.overlay_type != "none":
                chart_type = scene.visual_overlay.overlay_type
                chart_title = scene.visual_overlay.title
                labels = getattr(scene.visual_overlay, "data_labels", []) or (getattr(scene.visual_overlay, "labels", []) or [])
                values = getattr(scene.visual_overlay, "data_values", []) or (getattr(scene.visual_overlay, "data", []) or [])

                chart_layer = ChartLayer(
                    layer_id=f"chart_{scene.scene_id}",
                    layer_name=f"Animated Chart {chart_type}",
                    z_index=2,
                    chart_type=chart_type,
                    title=chart_title,
                    labels=labels,
                    data=values,
                    palette_colors=base_palette
                )
                gfx_layers.append(chart_layer)

            graphics_group = LayerGroupNode(group_id="gfx_grp", group_name="GraphicsGroup", z_index_base=20, layers=gfx_layers)

            # 4. Text Group (Titles & Captions)
            text_layers = []
            if scene.scene_title:
                title_layer = TitleLayer(
                    layer_id=f"title_{scene.scene_id}",
                    layer_name=f"Scene Title {scene.scene_title}",
                    z_index=3,
                    title_text=scene.scene_title,
                    font_family="Inter"
                )
                text_layers.append(title_layer)

            if scene.narration:
                cap_layer = CaptionLayer(
                    layer_id=f"cap_{scene.scene_id}",
                    layer_name="Word Captions",
                    z_index=4,
                    text=scene.narration,
                    highlight_color="#FACC15"
                )
                text_layers.append(cap_layer)

            text_group = LayerGroupNode(group_id="text_grp", group_name="TextGroup", z_index_base=30, layers=text_layers)

            # 5. Overlay Group (Vignette, Particles)
            overlay_layers = [
                OverlayLayer(
                    layer_id=f"ov_{scene.scene_id}",
                    layer_name="Cinematic Vignette",
                    z_index=5,
                    overlay_kind="vignette",
                    effects=[VignetteEffect(strength=0.30)]
                )
            ]
            overlay_group = LayerGroupNode(group_id="ov_grp", group_name="OverlayGroup", z_index_base=40, layers=overlay_layers)

            # Assemble Declarative Scene Node
            node = DeclarativeSceneNode(
                node_uuid=str(uuid.uuid4()),
                scene_id=scene.scene_id,
                scene_title=scene.scene_title,
                duration_sec=scene.duration_sec,
                fps=fps,
                width=width,
                height=height,
                background_group=bg_group,
                media_group=media_group,
                graphics_group=graphics_group,
                text_group=text_group,
                overlay_group=overlay_group,
                camera_track=camera_map.get(scene.scene_id)
            )
            scene_nodes.append(node)

        master_sg = MasterSceneGraph(
            node_uuid=master_uuid,
            project_title=storyboard.title,
            resolution=(width, height),
            fps=fps,
            scenes=scene_nodes
        )

        # Upgrade 7: Declarative Motion Graphics & Animated Infographics Engine
        from agents.video.motion_graphics.engine import MotionGraphicsEngine
        mg_report = MotionGraphicsEngine.apply_motion_graphics(storyboard, master_sg)
        master_sg.scenes[0].diagnostics["motion_graphics_report"] = mg_report.dict() if master_sg.scenes else {}

        return master_sg
