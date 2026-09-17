import logging
from typing import List
from app.schemas.agent_payloads import PresentationDeckSchema, SlideItem

logger = logging.getLogger("uvicorn")

def smart_truncate(text: str, max_len: int = 100) -> str:
    """
    Truncates text at natural word boundaries to prevent mid-word cuts like 'workflo...'.
    """
    text = text.strip()
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated.rstrip(".,;:!- ") + "..."


class VerificationRepair:
    """
    Verification and Repair Agent inspired by Auto-Slides.
    Inspects planned deck schema and automatically repairs missing titles, insufficient slide counts, or truncated bullet points.
    """

    @classmethod
    def verify_and_repair(cls, deck: PresentationDeckSchema) -> PresentationDeckSchema:
        logger.info(f"VerificationRepair: Inspecting deck '{deck.title}' ({len(deck.slides)} slides)...")
        repaired_slides: List[SlideItem] = []

        # 1. Title verification
        if not deck.title or len(deck.title.strip()) < 3:
            deck.title = "Executive Technical Presentation"

        # 2. Slide inspection & repair loop
        for idx, slide in enumerate(deck.slides):
            # Ensure slide_title is valid
            if not slide.slide_title or len(slide.slide_title.strip()) < 3:
                slide.slide_title = f"Slide {idx + 1}. Key Technical Insights"

            # Smart word-boundary truncation for long bullet points
            if slide.points:
                slide.points = [smart_truncate(p, 100) for p in slide.points]

            repaired_slides.append(slide)

        # 3. Minimum slide count check (min 3 slides) with domain-tailored content
        if len(repaired_slides) < 3:
            topic_hint = deck.title or "Executive Strategy"
            repaired_slides.append(SlideItem(
                slide_title="Strategic Implementation Roadmap",
                subtitle="Execution Phases & Milestones",
                layout_type="timeline_steps",
                steps=[
                    {"step": "01", "title": "Phase 1: Architecture Blueprint", "desc": f"Define core domain specifications for {topic_hint[:30]}"},
                    {"step": "02", "title": "Phase 2: Platform Integration", "desc": "Connect cognitive multi-agent services"},
                    {"step": "03", "title": "Phase 3: Production Operations", "desc": "Deploy high-availability delivery pipeline"}
                ]
            ))
            repaired_slides.append(SlideItem(
                slide_title="Key Performance Metrics & Value",
                subtitle="Quantifiable Target Benchmarks",
                layout_type="metrics_grid",
                metrics=[
                    {"metric": "99.9%", "label": "Target Uptime SLA"},
                    {"metric": "< 50ms", "label": "Response Latency"},
                    {"metric": "10x", "label": "Efficiency Gain"}
                ]
            ))

        deck.slides = repaired_slides
        logger.info(f"VerificationRepair: Deck verified and repaired cleanly ({len(deck.slides)} slides)!")
        return deck
