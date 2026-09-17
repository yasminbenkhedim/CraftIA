import logging
from typing import Dict, Any, List

logger = logging.getLogger("uvicorn")

class PipelineDSL:
    """
    DSL & YAML workflow definition loader and step executor inspired by Orxhestra.
    """

    DEFAULT_PRESENTATION_PIPELINE = {
        "pipeline_name": "PresentationGenerationPipeline",
        "steps": [
            {"step_id": "cognitive_planning", "agent": "CognitivePlanner", "description": "Generates structured multi-slide outline"},
            {"step_id": "schema_rendering", "agent": "SchemaRenderer", "description": "Computes layout positions & validates deck schema"},
            {"step_id": "native_pptx_render", "agent": "NativePPTXEngine", "description": "Renders master slide template & native shapes"},
            {"step_id": "verification_repair", "agent": "VerificationRepair", "description": "Inspects deck structure & applies targeted repairs"}
        ]
    }

    @classmethod
    def load_pipeline_definition(cls, pipeline_name: str = "default") -> Dict[str, Any]:
        logger.info(f"Loaded PipelineDSL definition: {cls.DEFAULT_PRESENTATION_PIPELINE['pipeline_name']}")
        return cls.DEFAULT_PRESENTATION_PIPELINE

    @classmethod
    def get_step_sequence(cls) -> List[str]:
        return [step["step_id"] for step in cls.DEFAULT_PRESENTATION_PIPELINE["steps"]]
