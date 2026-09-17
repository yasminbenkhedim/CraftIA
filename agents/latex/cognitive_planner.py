"""
Cognitive Report Planner for LaTeX Technical Reports.

Uses LLMService to decompose a user prompt into a structured, multi-chapter
report plan with chapter titles, section outlines, abstract, and bibliography
keywords -- following the same Cognitive Planner pattern as the
PresentationAgent (inspired by MultiAgentPPT & Auto-Slides).
"""
import logging
import re
import time
import unicodedata
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from agents.latex.localization import strings

logger = logging.getLogger("uvicorn")

MAX_PLAN_ATTEMPTS = 3
PLAN_BACKOFF_SEC = 18.0


class ReportPlanningError(RuntimeError):
    """Raised when the report outline cannot be produced. Fatal to the job."""


# ---------------------------------------------------------------------------
# Pydantic models for report structure
# ---------------------------------------------------------------------------

class ChapterPlan(BaseModel):
    chapter_id: str
    title: str
    sections: List[str] = Field(default_factory=list)
    include_diagram: bool = False
    include_chart: bool = False


class ReportPlan(BaseModel):
    title: str
    subtitle: str = ""
    abstract: str = ""
    chapters: List[ChapterPlan] = Field(default_factory=list)
    bibliography_keywords: List[str] = Field(default_factory=list)
    # The technical choices, decided ONCE here and handed to every chapter.
    #
    # Without this each chapter invented its own stack: a report said PostgreSQL with
    # Sequelize in the design and implementation chapters, then tested against MongoDB
    # two chapters later. Each chapter was internally plausible, which is precisely why
    # nobody notices until a jury reads the whole document.
    tech_stack: Dict[str, str] = Field(default_factory=dict)

    def tech_stack_brief(self) -> str:
        """One line naming every fixed technical decision, for a chapter prompt."""
        if not self.tech_stack:
            return ""
        return "; ".join(f"{k}: {v}" for k, v in self.tech_stack.items() if v)


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class ReportCognitivePlanner:
    """
    Analyses a user prompt and produces a structured ReportPlan with
    chapter breakdown, section outlines, and figure placement hints.
    """

    @classmethod
    def plan(cls, prompt: str, language: str = "en") -> ReportPlan:
        """
        Build the report outline. Retries, then raises -- it does not fall back.

        The old template fallback produced a generic English outline ("System
        Architecture", "Evaluation & Benchmarks") that had nothing to do with the user's
        subject, and the pipeline carried on as if planning had succeeded. For a student's
        PFE report a wrong outline is not a degraded result, it is a wasted submission.
        """
        logger.info(
            f"ReportCognitivePlanner: Planning report (language={language}) "
            f"for '{prompt[:60]}...'"
        )
        last = "not attempted"
        for attempt in range(1, MAX_PLAN_ATTEMPTS + 1):
            try:
                plan = cls._llm_plan(prompt, language)
                if plan.chapters:
                    return plan
                last = "LLM returned a plan with no chapters"
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
            if attempt < MAX_PLAN_ATTEMPTS:
                wait = PLAN_BACKOFF_SEC * attempt
                logger.warning(
                    f"ReportCognitivePlanner: attempt {attempt}/{MAX_PLAN_ATTEMPTS} failed "
                    f"({last}) -- retrying in {wait:.0f}s."
                )
                time.sleep(wait)

        raise ReportPlanningError(
            f"Could not plan the report after {MAX_PLAN_ATTEMPTS} attempts ({last}). "
            f"Refusing to fall back to a generic outline unrelated to the requested subject."
        )

    @classmethod
    def _llm_plan(cls, prompt: str, language: str = "en") -> ReportPlan:
        import sys
        from pathlib import Path
        backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from app.services.llm import LLMService

        loc = strings(language)
        system_prompt = (
            "You are a senior academic technical writer. Given a topic, produce a report plan JSON. "
            f"{loc.llm_instruction} "
            "Every chapter title, section title, the report title, subtitle and abstract must be "
            "written in that language. "
            "SECTION NAMING -- this is the most common failure, so be careful. Each chapter's "
            "sections must name what THAT chapter actually covers. Never use another "
            "chapter's title as a section inside a different chapter. "
            "WRONG: a chapter 'Analyse des besoins' containing sections "
            "['Introduction', 'Conception', 'Implementation', 'Tests', 'Conclusion'] -- those "
            "are the other chapters, repeated. "
            "RIGHT: a chapter 'Analyse des besoins' containing sections "
            "['Acteurs et cas d'utilisation', 'Exigences fonctionnelles', "
            "'Exigences non fonctionnelles', 'Contraintes techniques']. "
            "Give 3 to 5 sections per chapter. "
            "TECHNICAL STACK -- choose the concrete technologies ONCE, in tech_stack, and pick "
            "only ones that genuinely fit the topic. Every chapter will be written against "
            "exactly these choices, so they must be mutually coherent (do not pair a SQL ORM "
            "with a document database). "
            "Output MUST be strict raw JSON matching this schema:\n"
            '{"title":"...","subtitle":"...","abstract":"Executive summary paragraph",'
            '"tech_stack":{"frontend":"React 18","backend":"Node.js / Express",'
            '"database":"PostgreSQL","orm":"Sequelize","auth":"JWT","tests":"Jest + Supertest"},'
            '"chapters":['
            '{"chapter_id":"ch1","title":"Introduction","sections":["Contexte","Problematique","Objectifs"],'
            '"include_diagram":false,"include_chart":false},'
            '{"chapter_id":"ch2","title":"Analyse des besoins",'
            '"sections":["Acteurs et cas d utilisation","Exigences fonctionnelles","Exigences non fonctionnelles"],'
            '"include_diagram":true,"include_chart":false}'
            '],"bibliography_keywords":["keyword1","keyword2"]}'
        )
        # Empty fallback on purpose: LLMService returns this argument instead of raising,
        # so a real structure here would make a failed call look like a successful one.
        raw = LLMService.generate_json(prompt, system_prompt, {})
        if not isinstance(raw, dict) or not raw.get("chapters"):
            raise ReportPlanningError("LLM returned no chapters.")

        chapters = []
        for ch in raw.get("chapters", []):
            chapters.append(ChapterPlan(
                chapter_id=ch.get("chapter_id", f"ch{len(chapters)+1}"),
                title=ch.get("title", f"Chapter {len(chapters)+1}"),
                sections=[str(x).strip() for x in (ch.get("sections") or []) if str(x).strip()],
                include_diagram=ch.get("include_diagram", False),
                include_chart=ch.get("include_chart", False),
            ))

        cls._drop_echoed_sections(chapters)

        stack = raw.get("tech_stack")
        stack = {str(k): str(v) for k, v in stack.items()} if isinstance(stack, dict) else {}
        if stack:
            logger.info(f"ReportCognitivePlanner: fixed tech stack -- "
                        f"{'; '.join(f'{k}={v}' for k, v in stack.items())}")
        else:
            logger.warning("ReportCognitivePlanner: the plan carries no tech_stack; chapters "
                           "may each choose their own technologies.")

        return ReportPlan(
            title=raw.get("title", prompt[:60]),
            subtitle=raw.get("subtitle", ""),
            abstract=raw.get("abstract", ""),
            chapters=chapters,
            bibliography_keywords=raw.get("bibliography_keywords", []),
            tech_stack=stack,
        )

    @staticmethod
    def _normalize_title(text: str) -> str:
        """Lowercase, unaccented, punctuation-free -- for comparing titles by meaning."""
        t = unicodedata.normalize("NFKD", str(text or "").lower())
        t = "".join(c for c in t if not unicodedata.combining(c))
        t = re.sub(r"^\d+[.)\s]*", "", t)          # drop any leading "2." numbering
        t = re.sub(r"[^a-z0-9 ]+", " ", t)
        return re.sub(r"\s+", " ", t).strip()

    @classmethod
    def _drop_echoed_sections(cls, chapters: List[ChapterPlan]) -> None:
        """
        Remove sections that merely repeat another chapter's title.

        The model is told not to do this, but it still does: a chapter "Analyse des
        besoins" came back with sections "Conception", "Implémentation", "Tests" and
        "Conclusion" -- the names of chapters 3 to 6. Rendered, those became "2.5
        Conception", "2.6 Implémentation" and so on, which reads as though the report
        covers its own subject four times.

        Prompting alone cannot guarantee this, so it is enforced here. A section is
        dropped only when it echoes a DIFFERENT chapter's title; a chapter legitimately
        opening with its own framing keeps it.
        """
        titles = {cls._normalize_title(ch.title): i for i, ch in enumerate(chapters)}
        for i, ch in enumerate(chapters):
            kept, dropped = [], []
            for sec in ch.sections:
                owner = titles.get(cls._normalize_title(sec))
                if owner is not None and owner != i:
                    dropped.append(sec)
                else:
                    kept.append(sec)
            if dropped:
                logger.warning(
                    f"ReportCognitivePlanner: chapter '{ch.title}' listed "
                    f"{dropped} as sections -- those are other chapters' titles, dropping."
                )
            # Never strip a chapter down to nothing: if the model filled it entirely with
            # echoes there is no salvageable outline, so keep what came back and let the
            # retry in plan() ask again.
            ch.sections = kept if len(kept) >= 2 else ch.sections

    # _template_plan was removed. It emitted a fixed English outline -- "System
    # Architecture", "Evaluation & Benchmarks", bibliography keywords about multi-agent
    # systems -- for any subject at all, and plan() silently used it whenever the LLM
    # was rate-limited. Planning now fails loudly instead (see ReportPlanningError).
