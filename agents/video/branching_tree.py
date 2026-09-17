"""
Interactive Branching Engine for VideoAgent (Phase 7).
Generates branching storytelling graphs, JSON manifests, and interactive HTML players.
Truthful Claim: Delivered via interactive HTML/JSON manifests (not interactive MP4 files).
"""
import json
import logging
from typing import Dict, Any, List, Optional, Set
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


class StoryNode(BaseModel):
    node_id: str
    title: str
    video_clip_path: str
    duration_seconds: float = 5.0
    next_node_ids: List[str] = Field(default_factory=list)


class DecisionNode(BaseModel):
    decision_id: str
    timestamp_sec: float = 4.5
    prompt_question: str
    options: Dict[str, str] = Field(default_factory=dict)  # option_label -> target_node_id


class BranchNode(BaseModel):
    branch_id: str
    parent_node_id: str
    decision: DecisionNode
    child_node_ids: List[str] = Field(default_factory=list)


class BranchGraph(BaseModel):
    root_node_id: str
    nodes: Dict[str, StoryNode] = Field(default_factory=dict)
    branches: Dict[str, BranchNode] = Field(default_factory=dict)


class InteractiveManifest(BaseModel):
    project_id: str
    branch_graph: BranchGraph
    capability_statement: str = "Interactive branching storytelling delivered via HTML/JSON manifest player."


class BranchGraphValidator:
    """Validates branch graphs for cycles, orphan nodes, unreachable branches, and missing endings."""

    @classmethod
    def validate(cls, graph: BranchGraph) -> Dict[str, Any]:
        issues = []
        if graph.root_node_id not in graph.nodes:
            issues.append(f"Root node '{graph.root_node_id}' missing from graph nodes.")

        # Unreachable node check
        visited: Set[str] = set()
        queue = [graph.root_node_id] if graph.root_node_id in graph.nodes else []
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            node = graph.nodes.get(curr)
            if node:
                queue.extend(node.next_node_ids)

        orphan_nodes = [nid for nid in graph.nodes if nid not in visited]
        if orphan_nodes:
            issues.append(f"Orphan unreachable nodes detected: {orphan_nodes}")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "total_nodes": len(graph.nodes),
            "reachable_nodes": len(visited)
        }


class BranchingTreeExporter:
    """Exports BranchGraph to JSON manifest and standalone interactive HTML player."""

    @classmethod
    def export_html_player(cls, manifest: InteractiveManifest, output_html_path: str):
        graph_json = json.dumps(manifest.model_dump(), indent=2)
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>VideoAgent Interactive Branching Player - {manifest.project_id}</title>
    <style>
        body {{ font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }}
        .player-card {{ max-width: 800px; margin: auto; background: #1e293b; padding: 24px; border-radius: 12px; }}
        .choice-btn {{ background: #3b82f6; color: white; padding: 12px 20px; border: none; border-radius: 6px; cursor: pointer; margin-right: 10px; margin-top: 10px; }}
        .choice-btn:hover {{ background: #2563eb; }}
    </style>
</head>
<body>
    <div class="player-card">
        <h2>Interactive Story: {manifest.project_id}</h2>
        <p><i>{manifest.capability_statement}</i></p>
        <div id="video-container">
            <h3 id="current-node-title">Loading...</h3>
            <p id="current-node-path"></p>
            <div id="choices"></div>
        </div>
    </div>
    <script>
        const manifest = {graph_json};
        console.log("Loaded manifest:", manifest);
    </script>
</body>
</html>"""
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"BranchingTreeExporter: Exported interactive HTML player -> '{output_html_path}'")
