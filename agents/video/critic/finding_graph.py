"""
CriticFindingGraph & Root-Cause Deduplication for CraftAI (Upgrade 8).
Maps causal relationships between findings and prevents duplicate recommendations for shared root causes.
"""
import logging
from typing import List, Dict, Any, Optional, Set
from agents.video.critic.schemas import CriticFinding

logger = logging.getLogger("uvicorn")


class FindingNode:
    def __init__(self, finding: CriticFinding):
        self.finding = finding
        self.caused_by_ids: Set[str] = set()
        self.contributes_to_ids: Set[str] = set()
        self.duplicate_ids: Set[str] = set()


class CriticFindingGraph:
    """
    Causal graph representing relationships between findings and identifying primary root causes.
    """

    def __init__(self):
        self.nodes: Dict[str, FindingNode] = {}

    def add_finding(self, finding: CriticFinding):
        if finding.finding_id not in self.nodes:
            self.nodes[finding.finding_id] = FindingNode(finding)

    def add_relationship(self, source_id: str, rel_type: str, target_id: str):
        if source_id in self.nodes and target_id in self.nodes:
            if rel_type == "caused_by":
                self.nodes[source_id].caused_by_ids.add(target_id)
                self.nodes[target_id].contributes_to_ids.add(source_id)
            elif rel_type == "duplicates":
                self.nodes[source_id].duplicate_ids.add(target_id)

    def get_root_cause_findings(self) -> List[CriticFinding]:
        """
        Returns findings that represent root causes (not caused by other findings).
        """
        root_findings: List[CriticFinding] = []
        for node_id, node in self.nodes.items():
            if not node.caused_by_ids:
                root_findings.append(node.finding)
        return root_findings
