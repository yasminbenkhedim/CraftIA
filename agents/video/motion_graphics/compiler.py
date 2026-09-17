"""
MotionGraphicsCompiler & SceneGraphAdapter for CraftAI (Upgrade 7).
Compiles intermediate SemanticGraphicTree nodes into typed DeclarativeSceneNode sub-layers.
"""
import logging
import hashlib
from typing import List, Dict, Any, Optional
from agents.video.compositor.schemas import (
    DeclarativeSceneNode, LayerGroupNode, BaseCompositorLayer,
    ChartLayer, TitleLayer, CaptionLayer, ShapeLayer, LowerThirdLayer,
    AnimationTrack, Keyframe, KeyframeValue, EasingType
)
from agents.video.motion_graphics.schemas import MotionGraphicsPlan, VisualGrammarType

logger = logging.getLogger("uvicorn")


class MotionGraphicsCompiler:
    """
    Compiles semantic graphic nodes into typed SceneGraph sub-layers with deterministic asset identities.
    """

    @classmethod
    def compile_plan(cls, plan: MotionGraphicsPlan, scene_node: DeclarativeSceneNode) -> List[BaseCompositorLayer]:
        layers: List[BaseCompositorLayer] = []
        tree = plan.tree
        palette = plan.style_token_palette

        # Generate deterministic asset identity hash
        asset_id = hashlib.md5(f"{plan.scene_id}_{plan.grammar_type.value}_{plan.template_name}".encode("utf-8")).hexdigest()[:8]

        if plan.grammar_type in (VisualGrammarType.KPI_CARD, VisualGrammarType.PERCENTAGE_GAUGE, VisualGrammarType.STATISTIC_HIGHLIGHT):
            # Compile metric highlight card layer
            lt_layer = LowerThirdLayer(
                layer_id=f"mg_kpi_{plan.scene_id}_{asset_id}",
                layer_name=f"KPI Highlight Card ({plan.grammar_type.value})",
                z_index=25,
                name_text=f"Metric Highlight ({plan.grammar_type.value.upper()})",
                title_text=scene_node.scene_title or "Performance Indicator",
                accent_color=palette[1] if len(palette) > 1 else "#38BDF8"
            )
            layers.append(lt_layer)

        elif plan.grammar_type in (VisualGrammarType.PROCESS_FLOW, VisualGrammarType.TIMELINE, VisualGrammarType.ROADMAP):
            # Compile process timeline shape layer
            shape_layer = ShapeLayer(
                layer_id=f"mg_flow_{plan.scene_id}_{asset_id}",
                layer_name=f"Process Flow Diagram ({plan.grammar_type.value})",
                z_index=24,
                shape_type="rectangle",
                fill_color=palette[0] if palette else "#0F172A",
                stroke_color=palette[1] if len(palette) > 1 else "#38BDF8"
            )
            layers.append(shape_layer)

        return layers


class SceneGraphAdapter:
    """
    Attaches compiled motion graphics sub-layers into DeclarativeSceneNode layer groups while preserving z-order.
    """

    @classmethod
    def attach_motion_graphics(cls, plan: MotionGraphicsPlan, scene_node: DeclarativeSceneNode):
        compiled_layers = MotionGraphicsCompiler.compile_plan(plan, scene_node)
        if not compiled_layers:
            return

        if not scene_node.graphics_group:
            scene_node.graphics_group = LayerGroupNode(group_id="gfx_group", group_name="GraphicsGroup", z_index_base=20)

        for lyr in compiled_layers:
            scene_node.graphics_group.layers.append(lyr)

        scene_node.diagnostics["motion_graphics_plan"] = plan.dict()
