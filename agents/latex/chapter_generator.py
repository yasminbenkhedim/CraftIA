"""
Chapter Content Generator for LaTeX Technical Reports.

Takes a ChapterPlan from the CognitivePlanner and generates rich paragraph content for
each section using LLMService.

NO SILENT FALLBACK. This module used to answer a failed LLM call with a template
paragraph -- English boilerplate about "multi-agent orchestration with event-driven
pipelines", regardless of the report's subject or language. Because LLMService returns
its fallback argument instead of raising, the pipeline logged "Generated: Tests (3
sections)" and reported success. A real French PFE report shipped with its last two
chapters written in English about this product's own architecture.

That is the worst possible failure for a student: it looks finished, so nobody checks it
until a supervisor does. Generation now retries, and if it still cannot produce content
it raises ChapterGenerationError and the whole job fails. A failed job costs no credit
(see workflow.py) and tells the user to try again; a silently wrong report costs them
their submission.
"""
import logging
import random
import time
from typing import Dict, Any, List, Optional

from agents.latex.cognitive_planner import ChapterPlan
from agents.latex.localization import strings

logger = logging.getLogger("uvicorn")


class ChapterGenerationError(RuntimeError):
    """Raised when a chapter cannot be generated. Deliberately fatal to the job."""


# Groq's on-demand tier allows 8000 tokens per minute. Six chapters fired back to back
# exhaust that around the fifth call, which is exactly what produced the English tail.
# A short pause between chapters keeps the sustained rate under the limit; the retry
# below handles the burst case where it is hit anyway.
INTER_CHAPTER_DELAY_SEC = 6.0
MAX_ATTEMPTS = 4
# The API reports "try again in 15.51s", so the first backoff has to clear that window.
BACKOFF_BASE_SEC = 18.0


class GeneratedChapter:
    """Container for a fully generated chapter's content."""
    def __init__(self, chapter_id: str, title: str, sections: Dict[str, str]):
        self.chapter_id = chapter_id
        self.title = title
        self.sections = sections    # {section_title: paragraph_content}

    def to_latex(self) -> str:
        """Render this chapter as LaTeX source."""
        lines = [f"\\chapter{{{_latex_escape(self.title)}}}"]
        for sec_title, content in self.sections.items():
            lines.append(f"\n\\section{{{_latex_escape(sec_title)}}}")
            lines.append(_latex_escape(content))
        return "\n".join(lines)

    def to_text(self) -> str:
        """Render this chapter as plain text (for FPDF2 fallback)."""
        lines = [self.title, "=" * len(self.title), ""]
        for sec_title, content in self.sections.items():
            lines.append(sec_title)
            lines.append("-" * len(sec_title))
            lines.append(content)
            lines.append("")
        return "\n".join(lines)


def _latex_escape(text: str) -> str:
    """Escape special LaTeX characters."""
    if not text:
        return ""
    replacements = {
        "&": "\\&", "%": "\\%", "$": "\\$", "#": "\\#",
        "_": "\\_", "{": "\\{", "}": "\\}", "~": "\\textasciitilde{}",
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    return text


class ChapterGenerator:
    """
    Generates detailed paragraph content for each section of each chapter
    in a report plan.
    """

    @classmethod
    def generate_chapters(cls, chapters: List[ChapterPlan], prompt: str,
                          language: str = "en",
                          tech_stack: str = "") -> List["GeneratedChapter"]:
        """
        Generate every chapter, or raise. There is no partial success.

        Chapters are paced apart rather than fired in a burst: the token-per-minute limit
        is a *rate*, so the cheapest way to stay under it is to not go over it in the
        first place. The delay is skipped before the first chapter and after the last,
        where it would only add dead time.
        """
        logger.info(
            f"ChapterGenerator: Generating {len(chapters)} chapters "
            f"(language={language}, pacing={INTER_CHAPTER_DELAY_SEC}s between calls)"
        )
        # Every chapter is told what the others cover, so it can refer to them instead of
        # re-explaining them -- and so it does not wander into their territory.
        outline = " | ".join(f"{i + 1}. {c.title}" for i, c in enumerate(chapters))
        all_titles = [c.title for c in chapters]

        results = []
        for i, ch in enumerate(chapters):
            if i > 0:
                time.sleep(INTER_CHAPTER_DELAY_SEC)
            generated = cls._generate_single(ch, prompt, language, tech_stack, outline,
                                             i + 1, all_titles)
            results.append(generated)
            words = sum(len(v.split()) for v in generated.sections.values())
            logger.info(
                f"  [{i + 1}/{len(chapters)}] {ch.title} -- "
                f"{len(generated.sections)} sections, {words} words"
            )
        return results

    @classmethod
    def _generate_single(cls, chapter: ChapterPlan, prompt: str, language: str,
                         tech_stack: str = "", outline: str = "",
                         position: int = 0,
                         all_titles: Optional[List[str]] = None) -> "GeneratedChapter":
        """
        One chapter, with retry and backoff. Raises ChapterGenerationError if every
        attempt fails.
        """
        last_reason = "not attempted"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                sections = cls._llm_generate(chapter, prompt, language,
                                             tech_stack, outline, position)
                sections = cls._drop_structural_echoes(sections, chapter, all_titles or [])
                if sections:
                    return GeneratedChapter(chapter.chapter_id, chapter.title, sections)
                last_reason = "LLM returned no usable sections"
            except Exception as exc:
                last_reason = f"{type(exc).__name__}: {exc}"

            if attempt < MAX_ATTEMPTS:
                # Exponential with jitter: several chapters retrying in lockstep would
                # otherwise hit the limit again at the same instant.
                wait = BACKOFF_BASE_SEC * (2 ** (attempt - 1)) + random.uniform(0, 3)
                logger.warning(
                    f"ChapterGenerator: '{chapter.title}' attempt {attempt}/{MAX_ATTEMPTS} "
                    f"failed ({last_reason}) -- retrying in {wait:.0f}s."
                )
                time.sleep(wait)

        raise ChapterGenerationError(
            f"Could not generate chapter '{chapter.title}' after {MAX_ATTEMPTS} attempts "
            f"({last_reason}). Refusing to emit placeholder text in its place -- a report "
            f"that looks complete but contains boilerplate is worse than a failed job."
        )

    # Words that legitimately open or close a chapter in an academic report, even though
    # they are also chapter titles elsewhere in the document.
    _STRUCTURAL = {"introduction", "conclusion", "synthese", "resume", "summary"}

    @classmethod
    def _drop_structural_echoes(cls, sections: Dict[str, str], chapter: ChapterPlan,
                                all_titles: List[str]) -> Dict[str, str]:
        """
        Remove generated sections that reproduce the report's structure inside a chapter.

        Only the planner's outline was validated before, so the chapter writer could still
        invent a section named after another chapter -- which is how a "2.1 Introduction"
        and a "4.1 Introduction" came back after the outline was already clean.

        A structural word (Introduction, Conclusion...) is kept when it is the chapter's
        first or last section, because that is conventional. Anywhere else, or any other
        chapter's title, is dropped.
        """
        from agents.latex.cognitive_planner import ReportCognitivePlanner as _P

        if not sections:
            return sections
        own = _P._normalize_title(chapter.title)
        others = {_P._normalize_title(t) for t in all_titles} - {own}
        if not others:
            return sections

        items = list(sections.items())
        keep, dropped = {}, []
        for idx, (name, body) in enumerate(items):
            n = _P._normalize_title(name)
            if n in others:
                at_edge = idx == 0 or idx == len(items) - 1
                if n in cls._STRUCTURAL and at_edge:
                    keep[name] = body          # conventional opener/closer
                else:
                    dropped.append(name)
                    continue
            else:
                keep[name] = body
        if dropped:
            logger.warning(
                f"ChapterGenerator: '{chapter.title}' returned sections {dropped} that "
                f"restate other chapters -- dropping them."
            )
        # Never reduce a chapter to nothing; if the model returned only echoes, keep what
        # it gave and let the caller's retry ask again.
        return keep if len(keep) >= 2 else sections

    @classmethod
    def _llm_generate(cls, chapter: ChapterPlan, prompt: str, language: str,
                      tech_stack: str = "", outline: str = "",
                      position: int = 0) -> Dict[str, str]:
        """
        Ask for one chapter's sections. Returns {} when the call failed or gave nothing
        usable -- never invented content.
        """
        import sys
        from pathlib import Path
        backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from app.services.llm import LLMService

        loc = strings(language)
        sections_str = ", ".join(chapter.sections) if chapter.sections else "Overview"

        parts = [
            f"Write detailed technical content for a report chapter titled "
            f"'{chapter.title}'"
            + (f" (chapter {position} of the report)" if position else "")
            + f" with sections: {sections_str}.",
            f"The report topic is: {prompt}.",
        ]
        if outline:
            # Knowing the whole outline stops a chapter re-covering its neighbours, which
            # is the other half of the duplicated-section problem.
            parts.append(
                f"The full report outline is: {outline}. Write ONLY the chapter named "
                f"above. Where another chapter's subject comes up, refer to it briefly "
                f"instead of covering it again."
            )
        parts.append(
            "SECTION NAMES: name each section after what it actually covers in THIS "
            "chapter. Do not use another chapter's title as a section name. A brief "
            "opening or closing section is fine, but everything between them must be "
            "specific to this chapter's subject."
        )
        if tech_stack:
            # The decisive constraint. These choices were fixed once during planning; a
            # chapter that picks its own leaves the report contradicting itself -- e.g.
            # PostgreSQL with Sequelize in the design chapter and MongoDB in the tests.
            parts.append(
                f"TECHNICAL STACK -- already decided for this project, use EXACTLY these "
                f"and no alternatives: {tech_stack}. Do not introduce a different "
                f"database, ORM, framework or test library anywhere in this chapter, and "
                f"do not present these as options still to be chosen."
            )
        parts.append(loc.llm_instruction)
        parts.append(
            'Output strict JSON: {"sections": {"Section Title": "2-3 paragraph content", ...}}'
        )
        user_msg = " ".join(parts)
        system_prompt = (
            "You are a senior technical writer producing a final-year engineering project "
            "report. Generate detailed, specific, academic content for each section of the "
            "specified chapter. Write about the SUBJECT the user names -- never about the "
            "tool generating the document. Output strict JSON. "
            + loc.llm_instruction
        )

        # An EMPTY fallback, on purpose. LLMService returns this argument instead of
        # raising when the API fails, so passing real text here is what made a failure
        # indistinguishable from success. {} is unambiguous: a successful call always
        # carries "sections".
        raw = LLMService.generate_json(user_msg, system_prompt, {})

        raw_sections = raw.get("sections")
        if not isinstance(raw_sections, dict) or not raw_sections:
            return {}

        sections: Dict[str, str] = {}
        for sec_title, content in raw_sections.items():
            text = str(content or "").strip()
            # A section of a few words is a stub, not content -- treat the chapter as
            # failed rather than shipping a one-line "chapter".
            if len(text.split()) >= 25:
                sections[str(sec_title).strip()] = text
            else:
                logger.warning(
                    f"ChapterGenerator: section '{sec_title}' of '{chapter.title}' came "
                    f"back with {len(text.split())} words -- discarding as a stub."
                )
        return sections
