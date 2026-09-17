"""
Production LaTeX Report Agent -- 4-stage pipeline.

Workflow:
  1. ReportCognitivePlanner  -> structured ReportPlan (language-aware)
  2. ChapterGenerator        -> rich section content per chapter
  3. Renderer                -> pdflatex when available, else the FPDF2 renderer
  4. ArtifactValidator + ReviewerAgent quality gate

The former stages 3 and 4 -- DiagramGenerator and ChartGenerator -- are gone. They drew
this product's own architecture and invented benchmark numbers into every report, whoever
it was for. See generators/figure_placeholder.py. A report now carries an explicitly
empty, labelled frame where a figure belongs, written in the report's own language.

Three other behaviours changed with them, all for one reason: a student submits this
document under their own name, so it must never contain something that merely looks
finished.

  * Planning and chapter generation RAISE when the LLM cannot answer, instead of emitting
    English boilerplate and reporting success.
  * The bibliography is no longer three fabricated citations.
  * The cover page carries the student's own details, not this engine's name and its
    internal compilation mode.
"""
import os
import sys
import shutil
import subprocess
import time
import logging
from typing import Dict, Any, Callable, Optional
from pathlib import Path

backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from agents.base import BaseAgent
from agents.latex.cognitive_planner import ReportCognitivePlanner
from agents.latex.chapter_generator import ChapterGenerator
from agents.latex.diagram_extractor import DiagramExtractor
from agents.latex.generators import structural_diagrams
from agents.latex.generators.figure_placeholder import draw_placeholder
from agents.latex.localization import normalize as normalize_language, strings

logger = logging.getLogger("uvicorn")

# The Unicode face used for the PDF. FPDF2's built-in Helvetica is a latin-1 core font,
# so it silently turned every character outside that set into "?" -- 102 of them in one
# French report: "front-end" (non-breaking hyphen), "coeur" (oe ligature), and the narrow
# no-break spaces French typography puts inside guillemets. DejaVu already ships with the
# repo for the video renderer and is properly licensed (LICENSES.md R4).
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "video", "assets", "fonts")
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
FONT_NAME = "DejaVu"

# Table-of-contents metrics. Shared by the page-count arithmetic and the renderer below:
# if these two ever disagree, the reservation is wrong and fpdf2 raises at output() time.
TOC_ROW_MM = 6.5
TOC_TITLE_MM = 13.0


def _fit_text(pdf, text: str, max_width_mm: float) -> str:
    """
    Shorten `text` until it fits `max_width_mm`, ending on a word boundary plus an
    ellipsis.

    Measures the rendered width with the active font rather than counting characters:
    a character budget is meaningless in a proportional face, which is how the running
    header ended up cut at "React et" and how a long chapter title would have run into
    the contents page's page-number column.
    """
    text = (text or "").strip()
    if not text or pdf.get_string_width(text) <= max_width_mm:
        return text

    ellipsis = "\u2026"
    budget = max_width_mm - pdf.get_string_width(ellipsis)
    if budget <= 0:
        return ellipsis

    cut = text
    while cut and pdf.get_string_width(cut) > budget:
        cut = cut[:-1]
    # Back up to a word boundary so the label does not end mid-word, but only if that
    # leaves something substantial -- one very long word should still be shown clipped
    # rather than reduced to an ellipsis.
    spaced = cut.rstrip().rsplit(" ", 1)[0] if " " in cut.strip() else cut
    if len(spaced) >= len(cut) * 0.6:
        cut = spaced
    return cut.rstrip(" ,;:-") + ellipsis


def clean_text(text: str) -> str:
    """
    Light normalisation for PDF output. Deliberately NOT an encoding filter.

    This replaces clean_latin1(), which existed only because the PDF used a latin-1 core
    font: it encoded with errors="replace", so every character outside latin-1 became a
    literal "?" in the finished report -- 102 of them in one French PFE report. With a
    Unicode TTF there is nothing to strip: the font draws what the LLM actually wrote.

    The one substitution left is the narrow no-break space (U+202F), which DejaVu has no
    glyph for; a normal no-break space is what French typography means by it anyway.
    """
    if not text:
        return ""
    return str(text).replace(" ", " ")


class LaTeXReportAgent(BaseAgent):
    """
    Production LaTeX Report Agent executing a 6-stage pipeline:
    Plan -> Generate Chapters -> Diagrams & Charts -> Compile -> Validate
    """

    def validate_input(self, prompt: str, options: Optional[Dict[str, Any]] = None) -> bool:
        if not prompt or not prompt.strip():
            raise ValueError("LaTeX report prompt cannot be empty.")
        return True

    # ------------------------------------------------------------------
    # Primary entry point: progress callbacks fire at REAL stage boundaries
    # ------------------------------------------------------------------

    def execute(
        self,
        job_id: str,
        prompt: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes the full 6-stage pipeline and fires progress_callback at each
        stage's actual completion, not on a timer. If a stage fails the callback
        is called with a FAILED message before the exception propagates.
        """
        self.validate_input(prompt)

        def cb(percent: int, msg: str) -> None:
            logger.info(f"LaTeXAgent [{job_id}] progress {percent}%: {msg}")
            if progress_callback:
                progress_callback(percent, msg)

        cb(0, "Initializing LaTeX Report Pipeline...")

        target_dir = getattr(self, "_pending_target_dir", None)
        if target_dir is None:
            # Called standalone (not via workflow.py which sets _pending_target_dir)
            from app.core.config import settings
            target_dir = os.path.join(settings.STORAGE_PATH, job_id)

        artifact_path = self._run_pipeline(job_id, prompt, target_dir, cb, options or {})

        return {
            "status": "COMPLETED",
            "artifact_file": os.path.basename(artifact_path),
            "artifact_path": artifact_path,
        }

    def generate_artifact(self, job_id: str, prompt: str, target_dir: str,
                          options: Optional[Dict[str, Any]] = None) -> str:
        """
        Called by workflow.py after execute(). Returns the path of the generated PDF.

        `options` carries the create page's settings -- `language` plus the cover fields
        a student supplies. It had no such parameter before, so workflow.py (which
        inspects the signature) dropped every option for reports: the language selector
        existed but could not reach this agent.
        """
        # workflow.py calls execute() first (for progress), then generate_artifact().
        # We run the pipeline here; progress_callback is not available at this call site,
        # so we pass None (execute() already fired the callbacks during its own call).
        return self._run_pipeline(job_id, prompt, target_dir, cb=None, options=options or {})

    # ------------------------------------------------------------------
    # Core pipeline — single implementation, called by both entry points
    # ------------------------------------------------------------------

    def _run_pipeline(
        self,
        job_id: str,
        prompt: str,
        target_dir: str,
        cb: Optional[Callable[[int, str], None]],
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Executes all 6 stages. Fires cb(percent, message) at the completion of
        each stage so progress reflects true pipeline state. On failure, cb is
        called with a FAILED message before the exception re-raises.
        """
        def _cb(percent: int, msg: str) -> None:
            if cb:
                cb(percent, msg)

        options = options or {}
        language = normalize_language(options.get("language"))
        loc = strings(language)

        os.makedirs(target_dir, exist_ok=True)
        tex_dir = os.path.join(target_dir, "tex")
        os.makedirs(tex_dir, exist_ok=True)

        artifact_path = os.path.join(target_dir, "report_demo.pdf")
        logger.info(f"LaTeXAgent [{job_id}] language={language} ({loc.language_name})")

        # ---- Stage 1: Cognitive Report Planning ----
        # No try/except that swallows: a planning failure must reach the workflow, which
        # marks the job FAILED and -- because credits are only charged on success --
        # costs the student nothing. The old code caught this and carried on with a
        # generic English outline.
        logger.info(f"LaTeXAgent [{job_id}] Stage 1/4: Cognitive Planning")
        try:
            plan = ReportCognitivePlanner.plan(prompt, language=language)
        except Exception as exc:
            _cb(15, f"Stage 1/4 FAILED: could not plan the report — {exc}")
            raise
        logger.info(f"  Planned: '{plan.title}' -- {len(plan.chapters)} chapters")
        _cb(15, f"Stage 1/4 done: Report planned — '{plan.title}' ({len(plan.chapters)} chapters)")

        # ---- Stage 2: Chapter Content Generation ----
        logger.info(f"LaTeXAgent [{job_id}] Stage 2/4: Chapter Generation")
        try:
            chapters = ChapterGenerator.generate_chapters(
                plan.chapters, prompt, language=language,
                tech_stack=plan.tech_stack_brief(),
            )
        except Exception as exc:
            _cb(55, f"Stage 2/4 FAILED: could not generate chapters — {exc}")
            raise
        logger.info(f"  Generated {len(chapters)} chapters with section content")
        _cb(55, f"Stage 2/4 done: {len(chapters)} chapters generated")

        # ---- Stage 2.5: Structural diagrams ----
        #
        # Derived from the chapters just written, not from a template: the extractor reads
        # the report's own text and every component, entity and actor it returns is then
        # verified to appear in that text before anything is drawn (diagram_spec.ground).
        #
        # Only STRUCTURE is generated this way -- architecture, data model, interaction
        # flows -- because those are already stated in the prose. Anything involving
        # measurement (performance, latency, coverage, load tests) keeps its placeholder:
        # those numbers belong to the student's own experiments and inventing a plausible
        # curve would be fabricating results.
        diagram_images = []
        try:
            images_dir = os.path.join(target_dir, "figures")
            spec = DiagramExtractor.extract(chapters, language=language)
            if spec.any_renderable():
                diagram_images = structural_diagrams.render_all(spec, images_dir)
        except Exception as exc:
            # Never fatal: a report with placeholder figures is complete and honest.
            logger.warning(f"LaTeXAgent [{job_id}] diagram stage skipped ({exc}).")
        _cb(70, f"Stage 2.5 done: {len(diagram_images)} structural diagram(s) generated"
                if diagram_images else "Stage 2.5: no verifiable structure to draw")

        # ---- Stage 3: Render the PDF ----
        try:
            logger.info(f"LaTeXAgent [{job_id}] Stage 3/4: PDF Rendering")

            main_tex_src = self._assemble_main_tex(plan, chapters, loc)
            with open(os.path.join(tex_dir, "main.tex"), "w", encoding="utf-8") as f:
                f.write(main_tex_src)

            pdflatex_path = shutil.which("pdflatex")
            if pdflatex_path and self._compile_pdflatex(tex_dir, artifact_path):
                logger.info(f"  pdflatex found at {pdflatex_path}")
                _cb(85, f"Stage 3/4 done: pdflatex compilation succeeded "
                        f"({os.path.getsize(artifact_path)//1024} KB)")
            else:
                if pdflatex_path:
                    logger.warning("  pdflatex compilation failed, using the FPDF2 renderer")
                else:
                    logger.info("  pdflatex not on PATH — using the FPDF2 renderer")
                self._render_pdf(plan, chapters, artifact_path, loc, options, diagram_images)
                _cb(85, f"Stage 3/4 done: PDF rendered "
                        f"({os.path.getsize(artifact_path)//1024} KB)")
        except Exception as exc:
            _cb(85, f"Stage 3/4 FAILED: rendering error — {exc}")
            raise

        # ---- Stage 4: Done ----
        _cb(100, f"Report compiled successfully! ({os.path.getsize(artifact_path)//1024} KB, "
                 f"artifact: {os.path.basename(artifact_path)})")
        logger.info(f"LaTeXAgent [{job_id}] pipeline complete → {artifact_path}")
        return artifact_path

    # ------------------------------------------------------------------
    # TeX assembly
    # ------------------------------------------------------------------
    def _assemble_main_tex(self, plan, chapters, loc) -> str:
        """
        Build a standalone main.tex.

        Only reached when pdflatex is installed. It is not on this machine, so every
        report currently takes the FPDF2 path -- but the TeX is written to disk either
        way, so a student with a LaTeX toolchain can compile it themselves.

        babel/french gives real French typography: correct spacing around : ; ! ?,
        guillemets, and "Table des matieres" rather than "Contents".
        """
        babel = "french" if loc.code == "fr" else "english"
        esc = self._tex_esc
        out = [
            r"\documentclass[12pt,a4paper]{report}",
            r"\usepackage[utf8]{inputenc}",
            r"\usepackage[T1]{fontenc}",
            r"\usepackage{graphicx}",
            r"\usepackage{hyperref}",
            r"\usepackage{geometry}",
            r"\geometry{margin=2.5cm}",
            "\\usepackage[%s]{babel}" % babel,
            "",
            "\\title{%s}" % esc(plan.title),
            r"\date{\today}",
            "",
            r"\begin{document}",
            r"\maketitle",
            "",
            r"\begin{abstract}",
            esc(plan.abstract),
            r"\end{abstract}",
            "",
            r"\tableofcontents",
            r"\newpage",
            "",
        ]

        for ch in chapters:
            out.append(ch.to_latex())
            out.append("")

        # No \bibitem entries. Three fabricated citations used to be emitted here --
        # Groq, CreateFlow, OpenMontage -- into every report regardless of its subject.
        out.extend([
            "",
            "\\chapter*{%s}" % esc(loc.references_title),
            "\\addcontentsline{toc}{chapter}{%s}" % esc(loc.references_title),
            esc(loc.ph_references_note),
            "",
            r"\end{document}",
        ])
        return chr(10).join(out)

    @staticmethod
    def _tex_esc(text: str) -> str:
        if not text:
            return ""
        for ch in ["&", "%", "$", "#", "_", "{", "}"]:
            text = text.replace(ch, "\\" + ch)
        return text

    # ------------------------------------------------------------------
    # pdflatex compilation
    # ------------------------------------------------------------------

    def _compile_pdflatex(self, tex_dir: str, output_pdf: str) -> bool:
        main_tex = os.path.join(tex_dir, "main.tex")
        cmd = ["pdflatex", "-interaction=nonstopmode", "-output-directory", tex_dir, main_tex]

        for attempt in range(2):
            logger.info(f"  pdflatex attempt {attempt + 1}...")
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            compiled_pdf = os.path.join(tex_dir, "main.pdf")

            if res.returncode == 0 and os.path.exists(compiled_pdf):
                shutil.copy(compiled_pdf, output_pdf)
                return True

            log_file = os.path.join(tex_dir, "main.log")
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="latin-1", errors="ignore") as f:
                    log_text = f.read()
                logger.warning(f"  pdflatex log tail: {log_text[-300:]}")

        return False
    # ------------------------------------------------------------------
    # PDF renderer
    # ------------------------------------------------------------------

    # Cover fields a student can supply. Anything absent renders as a bracketed
    # placeholder in the report's language, so the finished PDF shows exactly which
    # blanks still need filling rather than quietly inventing a value.
    COVER_FIELDS = ("student_name", "university", "supervisor", "academic_year",
                    "co_supervisor", "degree")

    @staticmethod
    def _assign_diagrams(diagram_images, chapters):
        """
        Map each rendered diagram to the chapter that describes it.

        Scored by how many of the diagram's own labels appear in a chapter's text. That
        is the same evidence the grounding check uses, so a figure lands beside the prose
        it was derived from -- no keyword list, no assumption about chapter names, and it
        works whatever language or subject the report is in.
        """
        from agents.latex.diagram_spec import _normalize

        # Section HEADINGS weigh far more than body prose.
        #
        # Scoring on body text alone put the architecture diagram in the Introduction:
        # that chapter names React, Node.js and PostgreSQL once each while listing the
        # project's objectives, which scored as well as the design chapter that actually
        # describes them. A chapter with a section called "Architecture globale" or
        # "Modélisation des données" is unambiguously where those figures belong, so a
        # heading match counts for much more than a passing mention.
        HEADING_WEIGHT = 6

        headings = [_normalize(" ".join((ch.sections or {}).keys())) for ch in chapters]
        bodies = [_normalize(" ".join(str(v) for v in (ch.sections or {}).values()))
                  for ch in chapters]

        assigned = {}
        for entry in diagram_images:
            path, caption = entry[0], entry[1]
            labels = entry[2] if len(entry) > 2 else []
            tokens = {t for lab in labels for t in _normalize(lab).split() if len(t) >= 4}
            best = 0
            if tokens:
                scores = [
                    HEADING_WEIGHT * sum(1 for t in tokens if t in headings[i])
                    + sum(1 for t in tokens if t in bodies[i])
                    for i in range(len(chapters))
                ]
                if scores and max(scores) > 0:
                    best = max(range(len(scores)), key=lambda i: scores[i])
                logger.debug(f"LaTeXAgent: placement scores for '{caption}': {scores}")
            assigned.setdefault(best, []).append((path, caption))
            logger.info(
                f"LaTeXAgent: '{caption}' -> chapter {best + 1} "
                f"({chapters[best].title if chapters else '?'})"
            )
        return assigned

    def _render_pdf(self, plan, chapters, artifact_path, loc, options, diagram_images=None):
        """
        Render the report with FPDF2 and a Unicode TTF.

        Two structural changes from the previous renderer:

        * The table of contents is produced by insert_toc_placeholder + start_section, so
          its page numbers come from the real layout. They used to be computed as
          `index + 3`, which assumed every chapter was exactly one page long -- in a
          17-page report six of the seven entries pointed at the wrong page, drifting by
          up to eight. As a bonus this also gives the PDF real outline bookmarks.

        * Figures are empty labelled frames, not generated images. See
          generators/figure_placeholder.py.
        """
        from fpdf import FPDF

        cover = {k: str(options.get(k) or "").strip() for k in self.COVER_FIELDS}
        title = plan.title or ""

        class ReportPDF(FPDF):
            def header(self):
                # Nothing on the cover or the contents page: a running head above the
                # title block looks like a mistake.
                if self.page_no() <= 2:
                    return
                self.set_font(FONT_NAME, "", 8)
                self.set_text_color(148, 163, 184)
                # Trimmed to the printable width, at a word boundary, with an ellipsis.
                #
                # This used to be `title[:70]` -- a fixed character count with no regard
                # for the actual string width, which sliced the running head mid-phrase
                # ("... avec React et"). _fit_text measures the rendered width and backs
                # up to the last space, so the header reads as a deliberate short form
                # rather than a truncation bug.
                self.cell(0, 8, _fit_text(self, clean_text(title), self.epw - 2.0),
                          border=0, new_x="LMARGIN", new_y="NEXT", align="R")
                self.ln(2)

            def footer(self):
                if self.page_no() <= 1:
                    return
                self.set_y(-15)
                self.set_font(FONT_NAME, "", 9)
                self.set_text_color(148, 163, 184)
                self.cell(0, 10, str(self.page_no()), border=0, align="C")

        pdf = ReportPDF()
        # Unicode TTFs: with these registered, French renders as written -- no "?" where
        # an oe ligature or a non-breaking hyphen used to be.
        pdf.add_font(FONT_NAME, "", FONT_REGULAR)
        pdf.add_font(FONT_NAME, "B", FONT_BOLD)
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.set_title(clean_text(title))
        if cover["student_name"]:
            pdf.set_author(clean_text(cover["student_name"]))

        # ---------------------------------------------------------- cover
        pdf.add_page()
        epw = pdf.epw

        pdf.ln(6)
        pdf.set_font(FONT_NAME, "", 11)
        pdf.set_text_color(71, 85, 105)
        pdf.multi_cell(epw, 6, clean_text(cover["university"] or loc.ph_university), align="C")
        pdf.ln(24)

        pdf.set_font(FONT_NAME, "B", 12)
        pdf.set_text_color(100, 116, 139)
        pdf.multi_cell(epw, 7, clean_text(cover["degree"] or loc.cover_degree), align="C")
        pdf.ln(8)

        pdf.set_draw_color(203, 213, 225)
        pdf.set_line_width(0.3)
        pdf.line(pdf.l_margin + epw * 0.2, pdf.get_y(), pdf.l_margin + epw * 0.8, pdf.get_y())
        pdf.ln(10)

        pdf.set_font(FONT_NAME, "B", 22)
        pdf.set_text_color(15, 23, 42)
        pdf.multi_cell(epw, 11, clean_text(title), align="C")
        pdf.ln(4)

        if plan.subtitle:
            pdf.set_font(FONT_NAME, "", 12)
            pdf.set_text_color(71, 85, 105)
            pdf.multi_cell(epw, 7, clean_text(plan.subtitle), align="C")
        pdf.ln(22)

        # Two columns: the student on the left, the supervisor on the right, which is how
        # a PFE cover is conventionally laid out.
        col = epw / 2
        y_block = pdf.get_y()
        pdf.set_font(FONT_NAME, "", 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(col, 6, clean_text(loc.cover_author), align="C")
        pdf.cell(col, 6, clean_text(loc.cover_supervisor), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(FONT_NAME, "B", 11)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(col, 7, clean_text(cover["student_name"] or loc.ph_author), align="C")
        pdf.cell(col, 7, clean_text(cover["supervisor"] or loc.ph_supervisor), align="C",
                 new_x="LMARGIN", new_y="NEXT")

        if cover["co_supervisor"]:
            pdf.set_font(FONT_NAME, "", 10)
            pdf.set_text_color(71, 85, 105)
            pdf.cell(col, 6, "", align="C")
            pdf.cell(col, 6, clean_text(cover["co_supervisor"]), align="C",
                     new_x="LMARGIN", new_y="NEXT")

        pdf.ln(18)
        pdf.set_font(FONT_NAME, "", 10)
        pdf.set_text_color(100, 116, 139)
        pdf.multi_cell(epw, 6, clean_text(
            f"{loc.cover_year} : {cover['academic_year'] or loc.ph_year}"), align="C")

        # NOTE: the cover deliberately carries no "Author: CreateFlow AI Multi-Agent
        # Engine" and no "Compilation Mode: Fallback PDF (FPDF2)". Both used to be
        # printed here. Internal build detail on the front page of a document a student
        # hands to a jury is indefensible, and the engine is not the author.

        # -------------------------------------------------- abstract + TOC
        pdf.add_page()
        pdf.set_font(FONT_NAME, "B", 15)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(epw, 10, clean_text(loc.abstract_title), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.set_font(FONT_NAME, "", 10)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(epw, 5.6, clean_text(plan.abstract))
        pdf.ln(8)

        def draw_toc_rows(doc, rows):
            """
            Draw the contents heading and every row. Shared by the measuring pass and the
            real render so the two can never disagree about how much space is needed.

            `rows` is a list of (level, label, page_string).
            """
            # Reset x explicitly, exactly as every row below does.
            #
            # fpdf2 renders the contents at output() time and restores only `page` and `y`
            # from the placeholder (_insert_table_of_contents), never `x`. So the heading
            # inherited whatever x the document happened to end on -- the right margin --
            # and was drawn entirely off the page, showing as "Tab". The rows already set
            # their own x, which is why only the heading was affected.
            doc.set_x(doc.l_margin)
            doc.set_font(FONT_NAME, "B", 15)
            doc.set_text_color(15, 23, 42)
            doc.cell(epw, TOC_TITLE_MM, clean_text(loc.toc_title), new_x="LMARGIN", new_y="NEXT")
            doc.ln(3)

            page_col_w = 12.0
            for level, name, page in rows:
                indent = 4.0 * (level or 0)
                is_chapter = (level or 0) == 0

                doc.set_font(FONT_NAME, "B" if is_chapter else "", 10.5)
                doc.set_text_color(*((30, 41, 59) if is_chapter else (71, 85, 105)))

                label = clean_text(name)

                # Position with set_x, never with a spacer cell.
                #
                # This row used to begin with `doc.cell(indent)`. For a chapter entry the
                # indent is 0, and fpdf2 reads cell(w=0) as "extend to the right margin" --
                # so the cursor jumped from x=10 to x=200 and the title was drawn off the
                # page. Subsection rows (indent 4) were unaffected, which is exactly the
                # reported symptom: "1. In" instead of "1. Introduction", while "1.1
                # Contexte" looked fine.
                left = doc.l_margin + indent
                doc.set_x(left)

                avail = epw - indent - page_col_w
                # A very long chapter title is shortened with an ellipsis rather than
                # allowed to run into the page-number column.
                label = _fit_text(doc, label, avail - 6.0)
                text_w = doc.get_string_width(label)

                doc.cell(text_w, TOC_ROW_MM, label)

                # Leader dots tie the title to its page number, and are what make a
                # contents page readable at a glance.
                dots_w = max(avail - text_w - 2.0, 0.0)
                if dots_w > 0:
                    unit = doc.get_string_width(".") or 1.0
                    doc.set_text_color(203, 213, 225)
                    doc.set_x(left + text_w + 1.0)
                    doc.cell(dots_w, TOC_ROW_MM, "." * int(dots_w / unit))

                doc.set_text_color(71, 85, 105)
                doc.set_x(doc.l_margin + epw - page_col_w)
                doc.cell(page_col_w, TOC_ROW_MM, page, align="R",
                         new_x="LMARGIN", new_y="NEXT")

        def render_toc(doc, outline):
            draw_toc_rows(doc, [(e.level or 0, e.name, str(e.page_number)) for e in outline])

        # Give the contents its own page before reserving anything.
        #
        # fpdf2 renders the ToC starting from the cursor position recorded when
        # insert_toc_placeholder was called (_insert_table_of_contents restores
        # `self.y = tocp.y`). Calling it straight after the abstract meant the first ToC
        # page began halfway down, with far less room than the arithmetic below assumed --
        # so a 33-entry contents that fits comfortably on one page overflowed onto three
        # and fpdf2 refused to render it. Starting on a fresh page makes the geometry
        # predictable and reads better anyway.
        pdf.add_page()

        # Reserve EXACTLY the pages the contents needs, by laying it out first.
        #
        # fpdf2 rejects both directions: too few reserved pages raises, and so does too
        # many. Estimating from row heights cannot be exact -- so the same drawing routine
        # is run over a throwaway document that mirrors this one's page geometry, and the
        # page count it produces is what gets reserved.
        toc_rows = []
        for i, ch in enumerate(chapters):
            toc_rows.append((0, f"{i + 1}. {ch.title}", "00"))
            for j, sec in enumerate(ch.sections, start=1):
                toc_rows.append((1, f"{i + 1}.{j} {sec}", "00"))
        toc_rows.append((0, loc.references_title, "00"))

        probe = FPDF()
        probe.add_font(FONT_NAME, "", FONT_REGULAR)
        probe.add_font(FONT_NAME, "B", FONT_BOLD)
        probe.set_auto_page_break(auto=True, margin=18)
        probe.add_page()
        probe.set_y(pdf.get_y())          # start where the real contents will start
        draw_toc_rows(probe, toc_rows)
        toc_pages = probe.pages_count
        logger.info(
            f"LaTeXAgent: table of contents — {len(toc_rows)} entries, "
            f"measured at {toc_pages} page(s)"
        )

        pdf.insert_toc_placeholder(render_toc, pages=toc_pages)

        # ------------------------------------------------------- chapters
        # Decide where each figure belongs before drawing anything.
        by_chapter = self._assign_diagrams(diagram_images or [], chapters)
        for ch_idx, ch in enumerate(chapters):
            pdf.add_page()
            heading = f"{ch_idx + 1}. {ch.title}"
            # Registers the chapter with the TOC and the PDF outline at its real page.
            pdf.start_section(clean_text(heading), level=0)

            pdf.set_font(FONT_NAME, "B", 16)
            pdf.set_text_color(15, 23, 42)
            pdf.multi_cell(epw, 9, clean_text(heading))
            pdf.ln(3)

            for sec_idx, (sec_title, content) in enumerate(ch.sections.items(), start=1):
                numbered = f"{ch_idx + 1}.{sec_idx} {sec_title}"
                pdf.start_section(clean_text(numbered), level=1)
                pdf.set_font(FONT_NAME, "B", 11.5)
                pdf.set_text_color(30, 58, 138)
                pdf.multi_cell(epw, 7, clean_text(numbered))
                pdf.ln(1)
                pdf.set_font(FONT_NAME, "", 10)
                pdf.set_text_color(51, 65, 85)
                pdf.multi_cell(epw, 5.6, clean_text(content))
                pdf.ln(4)

            plan_ch = next((p for p in plan.chapters if p.chapter_id == ch.chapter_id), None)
            fig_no = 0

            # Real diagrams go in the chapter that asked for one -- in practice the design
            # chapter, which is where the architecture and data model are described.
            mine = by_chapter.get(ch_idx, [])
            if mine:
                for img_path, caption in mine:
                    if not os.path.exists(img_path):
                        continue
                    fig_no += 1
                    # Keep a figure and its caption together: starting a new page is
                    # better than an image orphaned from the line that names it.
                    if pdf.get_y() > pdf.h - 110:
                        pdf.add_page()
                    try:
                        pdf.image(img_path, w=min(epw, 155), x="C")
                    except Exception as exc:
                        logger.warning(f"LaTeXAgent: could not place {img_path} ({exc}).")
                        continue
                    pdf.ln(1)
                    pdf.set_font(FONT_NAME, "", 8.5)
                    pdf.set_text_color(100, 116, 139)
                    pdf.multi_cell(epw, 5,
                                   clean_text(f"{loc.figure_label} {ch_idx + 1}.{fig_no} — {caption}"),
                                   align="C")
                    pdf.ln(4)

            elif getattr(plan_ch, "include_diagram", False):
                # Nothing verifiable could be drawn, so the honest empty frame stays.
                fig_no += 1
                draw_placeholder(pdf, epw, clean_text(loc.ph_figure), clean_text(loc.ph_figure_hint))
                pdf.set_font(FONT_NAME, "", 8.5)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(epw, 6, clean_text(f"{loc.figure_label} {ch_idx + 1}.{fig_no}"),
                         new_x="LMARGIN", new_y="NEXT", align="C")
                pdf.ln(4)

            # Results charts are ALWAYS a placeholder. They need measurements the student
            # took; a generated curve here would be invented data presented as evidence.
            if getattr(plan_ch, "include_chart", False):
                fig_no += 1
                draw_placeholder(pdf, epw, clean_text(loc.ph_chart), clean_text(loc.ph_chart_hint))
                pdf.set_font(FONT_NAME, "", 8.5)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(epw, 6, clean_text(f"{loc.figure_label} {ch_idx + 1}.{fig_no}"),
                         new_x="LMARGIN", new_y="NEXT", align="C")
                pdf.ln(4)

        # ----------------------------------------------------- references
        pdf.add_page()
        pdf.start_section(clean_text(loc.references_title), level=0)
        pdf.set_font(FONT_NAME, "B", 16)
        pdf.set_text_color(15, 23, 42)
        pdf.multi_cell(epw, 9, clean_text(loc.references_title))
        pdf.ln(4)
        pdf.set_font(FONT_NAME, "", 10)
        pdf.set_text_color(100, 116, 139)
        pdf.multi_cell(epw, 5.6, clean_text(loc.ph_references_note))
        # The three fabricated citations that used to sit here -- Groq, CreateFlow,
        # OpenMontage, none of them related to any report's subject -- are gone. The LLM
        # is deliberately NOT asked to supply real ones either: language models invent
        # plausible citations, which is the same academic-integrity problem wearing a
        # better disguise. An empty section the student fills is the honest answer.

        pdf.output(artifact_path)
        logger.info(f"LaTeXAgent: PDF rendered ({os.path.getsize(artifact_path) / 1024:.1f} KB, "
                    f"{pdf.pages_count} pages)")
