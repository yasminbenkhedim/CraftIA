import os
import logging
from typing import Dict, Any
from app.schemas.agent_payloads import CritiqueReportSchema, DefectItem

logger = logging.getLogger("uvicorn")

class ReviewerAgent:
    """
    Reviewer Agent implementing Evaluator-Optimizer quality checks across deliverables.
    """

    @classmethod
    def review_deliverable(cls, agent_type: str, artifact_path: str, prompt: str) -> CritiqueReportSchema:
        """
        Evaluates deliverable against technical quality rubrics and returns a CritiqueReportSchema.
        """
        defects = []
        score = 1.0

        if not os.path.exists(artifact_path) or os.path.getsize(artifact_path) == 0:
            return CritiqueReportSchema(
                is_approved=False,
                quality_score=0.0,
                defects=[DefectItem(location="artifact_file", severity="CRITICAL", description="Artifact file missing or 0 bytes.", suggested_fix="Regenerate artifact file.")],
                revision_instructions="Artifact file was missing or corrupt. Re-execute generation."
            )

        file_size = os.path.getsize(artifact_path)

        if agent_type == "presentation":
            # Presentation Quality Metrics
            if file_size < 10000:
                score -= 0.3
                defects.append(DefectItem(location="slides", severity="MEDIUM", description="Presentation file size unusually small (< 10 KB).", suggested_fix="Ensure python-pptx rendered all slides."))

            # PPTX Inspection
            try:
                from pptx import Presentation
                prs = Presentation(artifact_path)
                slide_count = len(prs.slides)
                
                if slide_count < 3:
                    score -= 0.4
                    defects.append(DefectItem(location="slide_count", severity="HIGH", description=f"Insufficient slides ({slide_count} slides). Expected at least 3.", suggested_fix="Add more content slides."))
                
                shape_counts = []
                truncation_detected = False
                for slide in prs.slides:
                    text_content = ""
                    for shape in slide.shapes:
                        if shape.has_text_frame:
                            text_content += shape.text_frame.text
                            for p in shape.text_frame.paragraphs:
                                if p.text.endswith("...") and len(p.text) > 80 and not p.text.rstrip(". ").isalpha():
                                    truncation_detected = True
                    shape_counts.append(len(slide.shapes))
                    if len(text_content.strip()) < 5:
                        score -= 0.2
                        defects.append(DefectItem(location="empty_slide", severity="MEDIUM", description="Detected low-density or empty slide.", suggested_fix="Populate slide with text content."))

                # Layout distribution check: Flag decks where > 50% of content slides have identical shape count (monotony check)
                if len(shape_counts) > 3:
                    content_shape_counts = shape_counts[1:]  # Exclude title slide
                    most_common_count = max(set(content_shape_counts), key=content_shape_counts.count)
                    monotony_ratio = content_shape_counts.count(most_common_count) / len(content_shape_counts)
                    if monotony_ratio > 0.50:
                        score -= 0.25
                        defects.append(DefectItem(location="layout_monotony", severity="MEDIUM", description=f"Layout Monotony Warning: {monotony_ratio*100:.0f}% of slides use identical single-card layout.", suggested_fix="Vary slide layouts across three_column, two_column, metrics_grid, and timeline_steps."))

            except Exception as e:
                logger.error(f"Error inspecting PPTX in ReviewerAgent: {e}")

        elif agent_type == "latex":
            # ------------------------------------------------------------------
            # LaTeX Quality Metrics
            # ------------------------------------------------------------------

            # 1. File-size sanity (catches degenerate/empty PDFs)
            if file_size < 3000:
                score -= 0.3
                defects.append(DefectItem(
                    location="pdf_report", severity="MEDIUM",
                    description="PDF report file size small (< 3 KB).",
                    suggested_fix="Verify multi-chapter TeX compilation."
                ))

            # 2. TeX artefact directory — main.tex must exist
            tex_dir = os.path.join(os.path.dirname(artifact_path), "tex")
            main_tex = os.path.join(tex_dir, "main.tex")
            if not os.path.exists(main_tex):
                score -= 0.4
                defects.append(DefectItem(
                    location="tex_structure", severity="HIGH",
                    description="Missing main.tex — TeX pipeline did not run.",
                    suggested_fix="Assemble modular TeX structure."
                ))

            # 3. PDF structural check: page count via pypdf (or binary fallback)
            pdf_page_count = 0
            pdf_text_by_page: list = []
            try:
                from pypdf import PdfReader
                reader = PdfReader(artifact_path)
                pdf_page_count = len(reader.pages)
                pdf_text_by_page = [
                    (reader.pages[i].extract_text() or "") for i in range(pdf_page_count)
                ]
                logger.info(f"ReviewerAgent: PDF parsed — {pdf_page_count} pages")
            except ImportError:
                # pypdf not available — use binary page count
                logger.warning("ReviewerAgent: pypdf not installed; using binary page count.")
                import re
                with open(artifact_path, "rb") as f:
                    raw = f.read()
                page_objs = re.findall(b"/Type\\s*/Page[^s]", raw)
                if page_objs:
                    pdf_page_count = len(page_objs)
                else:
                    counts = re.findall(b"/Count\\s+(\\d+)", raw)
                    pdf_page_count = sum(int(c) for c in counts)
                logger.info(f"ReviewerAgent: binary page count — {pdf_page_count} pages")
            except Exception as pdf_exc:
                logger.error(f"ReviewerAgent: PDF parse error — {pdf_exc}")
                score -= 0.3
                defects.append(DefectItem(
                    location="pdf_parse", severity="HIGH",
                    description=f"PDF could not be parsed: {pdf_exc}",
                    suggested_fix="Regenerate the PDF artifact."
                ))

            MIN_PAGES = 3
            if pdf_page_count < MIN_PAGES:
                score -= 0.3
                defects.append(DefectItem(
                    location="page_count", severity="HIGH",
                    description=(
                        f"PDF has only {pdf_page_count} page(s); expected at least {MIN_PAGES}. "
                        "A real multi-chapter report requires cover + TOC + content pages."
                    ),
                    suggested_fix="Verify pdflatex or FPDF2 pipeline produced full content."
                ))
            else:
                logger.info(f"ReviewerAgent: page count OK ({pdf_page_count} >= {MIN_PAGES})")

            # 4. Chapter heading check — verify planned chapters appear in extracted text
            #    Read planned chapter titles from main.tex (\\chapter{...} lines)
            if pdf_text_by_page and os.path.exists(main_tex):
                import re as _re
                with open(main_tex, "r", encoding="utf-8", errors="replace") as f:
                    tex_src = f.read()
                planned_chapters = _re.findall(r"\\chapter\{([^}]+)\}", tex_src)
                full_text_norm = _re.sub(r"\s+", " ", "\n".join(pdf_text_by_page)).lower()

                missing_chapters = []
                for ch_title in planned_chapters:
                    ch_clean = _re.sub(r"\s+", " ", ch_title.strip()).lower()
                    # Check for normalized chapter title in normalized extracted text
                    if ch_clean not in full_text_norm:
                        missing_chapters.append(ch_title)

                if missing_chapters:
                    score -= 0.15 * len(missing_chapters)
                    defects.append(DefectItem(
                        location="chapter_headings", severity="MEDIUM",
                        description=(
                            f"Chapter heading(s) not found in extracted PDF text: "
                            f"{missing_chapters}. Possible encoding or compilation issue."
                        ),
                        suggested_fix="Verify TeX source compiles all chapters."
                    ))
                    logger.warning(
                        f"ReviewerAgent: {len(missing_chapters)}/{len(planned_chapters)} "
                        f"chapter headings missing from extracted text: {missing_chapters}"
                    )
                else:
                    logger.info(
                        f"ReviewerAgent: all {len(planned_chapters)} chapter headings "
                        "found in extracted PDF text"
                    )

        elif agent_type == "video":
            # Video Quality Metrics via VideoQualityChecker
            if file_size < 20000:
                score -= 0.4
                defects.append(DefectItem(location="video_file", severity="HIGH", description="Video file size small (< 20 KB).", suggested_fix="Verify H.264 frame encoding pipe."))

            try:
                from agents.video.quality_check import VideoQualityChecker
                qc_report = VideoQualityChecker.check(artifact_path)
                if not qc_report.get("passed", True):
                    score = min(score, qc_report.get("score", 0.5))
                    for d in qc_report.get("defects", []):
                        defects.append(DefectItem(
                            location=d.get("rule", "video_quality"),
                            severity=d.get("severity", "MEDIUM"),
                            description=d.get("message", "Video quality check defect"),
                            suggested_fix=d.get("fix_hint", "Re-render video")
                        ))
            except Exception as ve:
                logger.warning(f"ReviewerAgent: Video quality check exception ({ve})")

        is_approved = score >= 0.7 and len([d for d in defects if d.severity == "CRITICAL"]) == 0
        revision_text = "; ".join([d.description for d in defects]) if defects else "Deliverable passed quality review."

        logger.info(f"ReviewerAgent evaluation for {agent_type}: Score={score:.2f}, Approved={is_approved}")
        return CritiqueReportSchema(
            is_approved=is_approved,
            quality_score=max(0.0, score),
            defects=defects,
            revision_instructions=revision_text
        )
