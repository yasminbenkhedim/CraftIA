"""
Cognitive Outline Planner (v2 - PPTAgent Reflective Upgrade)
Inspired by PPTAgent (deep-research pre-pass & reflective context folding),
MultiAgentPPT, and Auto-Slides.

Features:
  - Deep Research Pre-Pass: Upfront topic analysis extracting technical pillars,
    domain terminology, and key insights before generating slide layouts.
  - Reflective Context Folding: Compacts historical execution feedback and past
    critiques into structured context summaries during multi-pass self-correction.
  - Intent-Driven Schema Generation: Produces 5-7 slide specs with rich bullet points.
"""
import logging
from typing import Dict, Any, List, Optional
from app.services.llm import LLMService
from app.schemas.agent_payloads import PresentationDeckSchema, SlideItem

logger = logging.getLogger("uvicorn")


class DeepResearchPrePass:
    """
    Upfront topic exploration inspired by PPTAgent research.py & planner.py.
    Extracts core strategic pillars, domain concepts, and structural angles
    to enrich the LLM presentation specification prompt.
    """

    @classmethod
    def analyze_topic(cls, prompt: str) -> Dict[str, Any]:
        # Trigger threshold: ONLY run DeepResearchPrePass on short/vague prompts (<= 12 words or <= 60 chars)
        if len(prompt.split()) > 12 and len(prompt) > 60:
            logger.info("DeepResearchPrePass: Prompt is sufficiently detailed, skipping pre-pass LLM call.")
            return {
                "pillars": ["System Architecture", "Multi-Agent Automation", "Quality Validation"],
                "context": f"Enterprise execution context for: {prompt[:60]}",
                "value_prop": "High-impact automated asset generation with production reliability",
                "metrics": ["Latency Optimization", "Artifact Quality Score"]
            }

        logger.info(f"DeepResearchPrePass: Short prompt detected ({len(prompt.split())} words), running research pre-pass for '{prompt[:60]}...'")

        system_prompt = (
            "You are a senior technical research analyst. Given a short topic prompt, "
            "perform a deep research analysis. Identify: "
            "1. 3 to 5 key technical pillars and architectural concepts. "
            "2. Problem context and strategic value proposition. "
            "3. Quantitative metrics or benchmark categories. "
            "Output MUST be strict JSON:\n"
            "{\n"
            '  "pillars": ["Pillar 1", "Pillar 2", "Pillar 3"],\n'
            '  "context": "Core problem background",\n'
            '  "value_prop": "Strategic business value",\n'
            '  "metrics": ["Metric A", "Metric B"]\n'
            "}"
        )

        fallback = {
            "pillars": ["System Architecture", "Multi-Agent Automation", "Quality Validation"],
            "context": f"Enterprise execution context for: {prompt[:60]}",
            "value_prop": "High-impact automated asset generation with production reliability",
            "metrics": ["Latency Optimization", "Artifact Quality Score"]
        }

        try:
            return LLMService.generate_json(prompt, system_prompt, fallback)
        except Exception as e:
            logger.warning(f"DeepResearchPrePass failed ({e}), using fallback research context.")
            return fallback


class ReflectiveContextFolder:
    """
    Context compacting engine inspired by PPTAgent compact_history().
    Compacts past attempt logs and reviewer critiques into a lean summary
    to prevent context bloat during multi-pass revision loops.
    """

    @classmethod
    def fold_history(cls, history: List[Dict[str, Any]], latest_feedback: str) -> str:
        if not history and not latest_feedback:
            return ""

        summary_parts = []
        if history:
            summary_parts.append(f"Past Execution Attempts: {len(history)} attempt(s) logged.")
            for idx, entry in enumerate(history, 1):
                summary_parts.append(f"Attempt {idx} Quality Score: {entry.get('quality_score', 'N/A')}")

        if latest_feedback:
            summary_parts.append(f"Reviewer Critique & Revision Guidance: {latest_feedback}")

        folded_text = "\n".join(summary_parts)
        logger.info(f"ReflectiveContextFolder: Compacted {len(history)} history entries into context fold.")
        return folded_text


class CognitivePlanner:
    """
    Cognitive Outline Planner integrating PPTAgent Deep-Research and Reflective Folding.
    Deconstructs user prompt + research context into logical slide taxonomies.
    """

    @classmethod
    def plan_presentation(
        cls,
        prompt: str,
        theme: str = "corporate_navy",
        revision_feedback: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None
    ) -> PresentationDeckSchema:
        logger.info(f"CognitivePlanner: Planning presentation for prompt '{prompt[:60]}...'")

        # 1. Deep Research Pre-Pass (Triggered only if prompt <= 12 words)
        research = DeepResearchPrePass.analyze_topic(prompt)

        # 2. Reflective Context Folding (if revision feedback exists)
        context_fold = ""
        if revision_feedback or history:
            context_fold = ReflectiveContextFolder.fold_history(history or [], revision_feedback or "")

        # 3. Construct Enriched System Prompt
        system_prompt = (
            "You are a master presentation architect and cognitive content planner. "
            "Given a topic prompt and deep research findings, create a structured executive "
            "presentation deck specification. Output MUST be strict raw JSON matching this format:\n"
            "{\n"
            '  "title": "Main Deck Title",\n'
            '  "subtitle": "Executive Subtitle Description",\n'
            f'  "theme": "{theme}",\n'
            '  "slides": [\n'
            '    {\n'
            '      "slide_title": "1. Executive Overview",\n'
            '      "subtitle": "Core Strategy & Vision",\n'
            '      "layout_type": "three_column",\n'
            '      "columns": [\n'
            '        {"title": "Pillar 1", "points": ["Insight A", "Insight B"]},\n'
            '        {"title": "Pillar 2", "points": ["Insight C", "Insight D"]},\n'
            '        {"title": "Pillar 3", "points": ["Insight E", "Insight F"]}\n'
            '      ]\n'
            '    },\n'
            '    {\n'
            '      "slide_title": "2. Comparative Analysis",\n'
            '      "subtitle": "Current vs Target Architecture",\n'
            '      "layout_type": "two_column",\n'
            '      "left_title": "Legacy System", "left_points": ["Point 1", "Point 2"],\n'
            '      "right_title": "Target AI Platform", "right_points": ["Point 3", "Point 4"]\n'
            '    },\n'
            '    {\n'
            '      "slide_title": "3. Technical Specifications",\n'
            '      "subtitle": "Key Architectural Components",\n'
            '      "layout_type": "bullet_list",\n'
            '      "points": ["Specification 1", "Specification 2", "Specification 3"]\n'
            '    },\n'
            '    {\n'
            '      "slide_title": "4. Performance Benchmarks",\n'
            '      "subtitle": "Key Metrics & Target KPIs",\n'
            '      "layout_type": "metrics_grid",\n'
            '      "metrics": [\n'
            '        {"metric": "99.9%", "label": "Uptime SLA"},\n'
            '        {"metric": "< 50ms", "label": "API Latency"},\n'
            '        {"metric": "$5.2M", "label": "ARR Target"},\n'
            '        {"metric": "10x", "label": "Speedup Factor"}\n'
            '      ]\n'
            '    },\n'
            '    {\n'
            '      "slide_title": "5. Implementation Roadmap",\n'
            '      "subtitle": "Phased Execution Steps",\n'
            '      "layout_type": "timeline_steps",\n'
            '      "steps": [\n'
            '        {"step": "01", "title": "Phase 1: Architecture Design", "desc": "Establish core schemas"},\n'
            '        {"step": "02", "title": "Phase 2: Agent Integration", "desc": "Connect cognitive planner"},\n'
            '        {"step": "03", "title": "Phase 3: Production Rollout", "desc": "Deploy high-availability engine"}\n'
            '      ]\n'
            '    }\n'
            '  ]\n'
            "}\n"
            "CRITICAL LAYOUT VARIETY REQUIREMENT:\n"
            "You MUST vary 'layout_type' across slides. A presentation with repetitive layouts is UNACCEPTABLE. "
            "Use at least 3 distinct layout_types in the deck ('three_column', 'two_column', 'bullet_list', 'metrics_grid', 'timeline_steps')."
        )

        user_content = (
            f"Prompt: {prompt}\n"
            f"Research Context:\n"
            f"- Strategic Pillars: {', '.join(research.get('pillars', []))}\n"
            f"- Problem Context: {research.get('context', '')}\n"
            f"- Value Proposition: {research.get('value_prop', '')}\n"
            f"- Key Metrics: {', '.join(research.get('metrics', []))}\n"
        )

        if context_fold:
            user_content += f"\nReflective Feedback Fold (Revisions Needed):\n{context_fold}\n"

        fallback_plan = {
            "title": prompt[:50].title() if prompt else "Executive AI Deliverable Deck",
            "subtitle": f"Planned for: {prompt[:60]}...",
            "theme": theme,
            "slides": [
                {
                    "slide_title": "1. Executive Summary",
                    "subtitle": research.get("value_prop", "Core Vision & Strategy")[:50],
                    "layout_type": "bullet_list",
                    "points": [f"Target Goal: {prompt[:50]}", "Multi-Agent Automation Architecture", "High-Impact Visual Formatting"]
                },
                {
                    "slide_title": "2. Problem & Market Opportunity",
                    "subtitle": research.get("context", "Industry Context")[:50],
                    "layout_type": "bullet_list",
                    "points": ["Manual Content Creation Bottlenecks", "Inconsistent Brand Styling & Colors", "Scalable Enterprise Automation Needs"]
                },
                {
                    "slide_title": "3. Proposed AI Architecture",
                    "subtitle": f"Pillars: {', '.join(research.get('pillars', []))[:50]}",
                    "layout_type": "bullet_list",
                    "points": ["Event-Driven Stream Orchestration", "Cognitive Outline & Repair Agents", "Native PowerPoint & LaTeX Compilers"]
                },
                {
                    "slide_title": "4. Technical Benchmarks & Results",
                    "subtitle": f"Metrics: {', '.join(research.get('metrics', []))[:50]}",
                    "layout_type": "bullet_list",
                    "points": ["Low-Latency REST API Dispatch", "High-Resolution Asset Compilation", "Automated Quality Control Verification"]
                },
                {
                    "slide_title": "5. Strategic Roadmap & Conclusion",
                    "subtitle": "Summary & Next Steps",
                    "layout_type": "bullet_list",
                    "points": ["Production Deployment Readiness", "Agent Memory & Preference Persistence", "Enterprise API Integration Ready"]
                }
            ]
        }

        raw_json = LLMService.generate_json(user_content, system_prompt, fallback_plan)
        try:
            return PresentationDeckSchema(**raw_json)
        except Exception as e:
            logger.error(f"CognitivePlanner: Schema validation error: {e}. Returning fallback plan.")
            return PresentationDeckSchema(**fallback_plan)
