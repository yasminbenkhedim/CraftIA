"""
Native Master Template PPTX Rendering Engine -- Priority 1 & 2 Upgrade.
Supports 6 dynamic content-driven layouts:
  1. title_slide    -- Master hero title card
  2. bullet_list    -- Classic single/double card bullet list
  3. two_column     -- Side-by-side 2-card comparison split
  4. three_column   -- 3-card strategic pillar grid layout
  5. metrics_grid   -- 2x2 or 3-stat metric highlight cards
  6. timeline_steps -- Horizontal 4-step process/timeline flow cards
Includes automatic fallback matrix for missing/unmatched layout content.
"""
import os
import re
import logging
from typing import Dict, Any, List, Optional
from app.schemas.agent_payloads import PresentationDeckSchema, SlideItem
from agents.presentation.theme import ThemeManager

logger = logging.getLogger("uvicorn")

METRIC_REGEX = re.compile(
    r'(?<!\b20[0-9]{2}\b)(?<!\b19[0-9]{2}\b)(?<!^\d\s)'
    r'(?P<val>[\+\-]?(?:\$|€|£)?\d+(?:\.\d+)?(?:%|k|M|B|X|x)?)\s+'
    r'(?P<label>[A-Za-z][A-Za-z0-9\s\-_]{2,30})',
    re.IGNORECASE
)


def format_label_preserving_acronyms(label: str) -> str:
    words = label.split()[:3]
    formatted = []
    for w in words:
        if w.isupper() or (any(c.isdigit() for c in w) and any(c.isupper() for c in w)):
            formatted.append(w)
        else:
            formatted.append(w.capitalize())
    return " ".join(formatted)


def extract_metric_fallback(text: str) -> Optional[Dict[str, str]]:
    text = text.strip().lstrip("•*- ").strip()
    if re.search(r'\b(founded|established|since|year|in)\s+(19|20)\d{2}\b', text, re.IGNORECASE):
        return None
    if re.match(r'^\d+\s+(key|main|top|critical|important|ways|steps|pillars|reasons)\b', text, re.IGNORECASE):
        return None

    match = METRIC_REGEX.search(text)
    if match:
        val = match.group('val').strip()
        label = match.group('label').strip()
        if val.isdigit() and 1900 <= int(val) <= 2099:
            return None
        clean_label = format_label_preserving_acronyms(label)
        if len(clean_label) >= 3 and val:
            return {"metric": val, "label": clean_label}
    return None


class NativePPTXEngine:
    """
    Native master template PPTX rendering engine with 6 dynamic layouts.
    """

    @classmethod
    def render_pptx_deck(cls, deck: PresentationDeckSchema, target_path: str) -> str:
        logger.info(f"NativePPTXEngine v4: Rendering multi-layout deck '{deck.title}' to {target_path}")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        try:
            from pptx import Presentation
            from pptx.util import Inches, Pt
            from pptx.dml.color import RGBColor
            from pptx.enum.shapes import MSO_SHAPE

            palette = ThemeManager.get_palette(deck.theme)

            def hex_to_rgb(hex_str: str) -> RGBColor:
                return RGBColor(int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))

            from pptx.chart.data import CategoryChartData
            from pptx.enum.chart import XL_CHART_TYPE

            FONT_HEADER = palette.get("font_header", "Calibri")
            FONT_BODY = palette.get("font_body", "Calibri")

            DARK_BG = hex_to_rgb(palette["dark_bg"])
            CARD_BG = hex_to_rgb(palette["card_bg"])
            STROKE = hex_to_rgb(palette.get("stroke", palette["card_bg"]))
            ACCENT_PRIMARY = hex_to_rgb(palette["accent_primary"])
            ACCENT_SECONDARY = hex_to_rgb(palette["accent_secondary"])
            TEXT_PRIMARY = hex_to_rgb(palette["text_primary"])
            TEXT_MUTED = hex_to_rgb(palette["text_muted"])

            def apply_font(p, font_name, size=None, bold=None, color=None):
                p.font.name = font_name
                if size:
                    p.font.size = size
                if bold is not None:
                    p.font.bold = bold
                if color:
                    p.font.color.rgb = color
                for r in p.runs:
                    r.font.name = font_name
                    if size:
                        r.font.size = size
                    if bold is not None:
                        r.font.bold = bold
                    if color:
                        r.font.color.rgb = color

            prs = Presentation()
            prs.slide_width = Inches(13.333)
            prs.slide_height = Inches(7.5)
            blank_layout = prs.slide_layouts[6]

            # --- SLIDE 1: Master Hero Title Slide ---
            slide1 = prs.slides.add_slide(blank_layout)
            bg1 = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
            bg1.fill.solid()
            bg1.fill.fore_color.rgb = DARK_BG
            bg1.line.color.rgb = DARK_BG

            title_card = slide1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.2), Inches(1.2), Inches(10.933), Inches(5.1))
            title_card.fill.solid()
            title_card.fill.fore_color.rgb = CARD_BG
            title_card.line.color.rgb = ACCENT_PRIMARY

            tf1 = title_card.text_frame
            tf1.word_wrap = True
            tf1.margin_left = Inches(0.8)
            tf1.margin_top = Inches(0.8)

            p1 = tf1.paragraphs[0]
            p1.text = deck.title
            apply_font(p1, FONT_HEADER, Pt(36), True, TEXT_PRIMARY)

            if deck.subtitle:
                p2 = tf1.add_paragraph()
                p2.text = deck.subtitle
                apply_font(p2, FONT_BODY, Pt(18), False, ACCENT_SECONDARY)
                p2.space_before = Pt(14)

            p3 = tf1.add_paragraph()
            p3.text = f"Theme: {palette['name']} | CreateFlow AI Engine"
            apply_font(p3, FONT_BODY, Pt(13), False, TEXT_MUTED)
            p3.space_before = Pt(32)

            # --- SLIDES 2..N: Dynamic Content Master Slides ---
            for s_idx, slide_item in enumerate(deck.slides):
                slide = prs.slides.add_slide(blank_layout)

                bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
                bg.fill.solid()
                bg.fill.fore_color.rgb = DARK_BG
                bg.line.color.rgb = DARK_BG

                # Common Header Shape Box
                header = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(0.5), Inches(11.733), Inches(1.1))
                header.fill.solid()
                header.fill.fore_color.rgb = CARD_BG
                header.line.color.rgb = ACCENT_PRIMARY

                htf = header.text_frame
                htf.word_wrap = True
                htf.margin_left = Inches(0.4)
                htf.margin_top = Inches(0.18)

                hp1 = htf.paragraphs[0]
                hp1.text = f"{s_idx + 1}. {slide_item.slide_title}"
                hp1.font.size = Pt(22)
                hp1.font.bold = True
                hp1.font.color.rgb = TEXT_PRIMARY

                if slide_item.subtitle:
                    hp2 = htf.add_paragraph()
                    hp2.text = slide_item.subtitle
                    hp2.font.size = Pt(13)
                    hp2.font.color.rgb = ACCENT_SECONDARY

                layout = slide_item.layout_type or "bullet_list"

                # -------------------------------------------------------------
                # LAYOUT 1: two_column (Side-by-Side Comparison Split)
                # -------------------------------------------------------------
                if layout == "two_column":
                    left_pts = slide_item.left_points or []
                    right_pts = slide_item.right_points or []
                    if not left_pts and not right_pts and slide_item.points:
                        n = len(slide_item.points)
                        left_pts = slide_item.points[:max(1, n // 2)]
                        right_pts = slide_item.points[max(1, n // 2):]

                    if not left_pts or not right_pts:
                        layout = "bullet_list"  # Fallback
                    else:
                        # Left Card
                        c_left = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(5.7), Inches(5.0))
                        c_left.fill.solid()
                        c_left.fill.fore_color.rgb = CARD_BG
                        c_left.line.color.rgb = STROKE

                        tf_l = c_left.text_frame
                        tf_l.word_wrap = True
                        tf_l.margin_left = Inches(0.4)
                        tf_l.margin_top = Inches(0.4)

                        lp0 = tf_l.paragraphs[0]
                        lp0.text = slide_item.left_title or "Current State"
                        lp0.font.size = Pt(18)
                        lp0.font.bold = True
                        lp0.font.color.rgb = ACCENT_PRIMARY
                        lp0.space_after = Pt(12)

                        for pt in left_pts:
                            lp = tf_l.add_paragraph()
                            lp.text = f"•  {pt}"
                            lp.font.size = Pt(15)
                            lp.font.color.rgb = TEXT_PRIMARY
                            lp.space_after = Pt(10)

                        # Right Card
                        c_right = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.0))
                        c_right.fill.solid()
                        c_right.fill.fore_color.rgb = CARD_BG
                        c_right.line.color.rgb = ACCENT_PRIMARY

                        tf_r = c_right.text_frame
                        tf_r.word_wrap = True
                        tf_r.margin_left = Inches(0.4)
                        tf_r.margin_top = Inches(0.4)

                        rp0 = tf_r.paragraphs[0]
                        rp0.text = slide_item.right_title or "Target AI Architecture"
                        rp0.font.size = Pt(18)
                        rp0.font.bold = True
                        rp0.font.color.rgb = ACCENT_SECONDARY
                        rp0.space_after = Pt(12)

                        for pt in right_pts:
                            rp = tf_r.add_paragraph()
                            rp.text = f"•  {pt}"
                            rp.font.size = Pt(15)
                            rp.font.color.rgb = TEXT_PRIMARY
                            rp.space_after = Pt(10)

                # -------------------------------------------------------------
                # LAYOUT 2: three_column (3 Strategic Pillar Cards)
                # -------------------------------------------------------------
                if layout == "three_column":
                    cols = slide_item.columns or []
                    if len(cols) < 2 and slide_item.points:
                        # Fallback: partition points into 3 columns
                        pts = slide_item.points
                        if len(pts) >= 3:
                            cols = [
                                {"title": "Pillar 1", "points": [pts[0]]},
                                {"title": "Pillar 2", "points": [pts[1]]},
                                {"title": "Pillar 3", "points": [pts[2]]}
                            ]
                        elif len(pts) == 2:
                            layout = "two_column"

                    if len(cols) < 2:
                        layout = "bullet_list"  # Fallback
                    else:
                        col_w = Inches(3.64)
                        col_gap = Inches(0.4)
                        for c_i, col in enumerate(cols[:3]):
                            col_x = Inches(0.8) + c_i * (col_w + col_gap)
                            card_col = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, col_x, Inches(1.8), col_w, Inches(5.0))
                            card_col.fill.solid()
                            card_col.fill.fore_color.rgb = CARD_BG
                            card_col.line.color.rgb = ACCENT_PRIMARY if c_i == 1 else STROKE

                            tf_c = card_col.text_frame
                            tf_c.word_wrap = True
                            tf_c.margin_left = Inches(0.3)
                            tf_c.margin_top = Inches(0.4)

                            cp0 = tf_c.paragraphs[0]
                            cp0.text = col.get("title", f"Pillar {c_i+1}")
                            cp0.font.size = Pt(17)
                            cp0.font.bold = True
                            cp0.font.color.rgb = ACCENT_PRIMARY if c_i == 1 else TEXT_PRIMARY
                            cp0.space_after = Pt(10)

                            for pt in col.get("points", []):
                                cp = tf_c.add_paragraph()
                                cp.text = f"•  {pt}"
                                cp.font.size = Pt(14)
                                cp.font.color.rgb = TEXT_PRIMARY
                                cp.space_after = Pt(8)

                # -------------------------------------------------------------
                # LAYOUT 3: metrics_grid (2x2 or 3-Stat Highlight Grid)
                # -------------------------------------------------------------
                if layout == "metrics_grid":
                    metrics = slide_item.metrics or []
                    if not metrics and slide_item.points:
                        # Fallback regex extraction
                        for pt in slide_item.points:
                            m_extracted = extract_metric_fallback(pt)
                            if m_extracted:
                                metrics.append(m_extracted)

                    if len(metrics) < 2:
                        layout = "bullet_list"  # Fallback
                    else:
                        m_cols = 2
                        grid_w = Inches(5.6)
                        grid_h = Inches(2.3)
                        grid_gap = Inches(0.5)

                        for m_i, m_item in enumerate(metrics[:4]):
                            row = m_i // m_cols
                            col = m_i % m_cols
                            m_x = Inches(0.8) + col * (grid_w + grid_gap)
                            m_y = Inches(1.8) + row * (grid_h + Inches(0.4))

                            m_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, m_x, m_y, grid_w, grid_h)
                            m_card.fill.solid()
                            m_card.fill.fore_color.rgb = CARD_BG
                            m_card.line.color.rgb = ACCENT_PRIMARY

                            tf_m = m_card.text_frame
                            tf_m.word_wrap = True
                            tf_m.margin_left = Inches(0.4)
                            tf_m.margin_top = Inches(0.3)

                            mp1 = tf_m.paragraphs[0]
                            mp1.text = m_item.get("metric", "100%")
                            mp1.font.size = Pt(36)
                            mp1.font.bold = True
                            mp1.font.color.rgb = ACCENT_PRIMARY

                            mp2 = tf_m.add_paragraph()
                            mp2.text = m_item.get("label", "Benchmark Target")
                            mp2.font.size = Pt(16)
                            mp2.font.color.rgb = TEXT_PRIMARY
                            mp2.space_before = Pt(6)

                # -------------------------------------------------------------
                # LAYOUT 4: timeline_steps (Horizontal 4-Step Flow Cards)
                # -------------------------------------------------------------
                if layout == "timeline_steps":
                    steps = slide_item.steps or []
                    if not steps and slide_item.points:
                        steps = [
                            {"step": f"0{i+1}", "title": f"Phase {i+1}", "desc": pt}
                            for i, pt in enumerate(slide_item.points[:4])
                        ]

                    if len(steps) < 2:
                        layout = "bullet_list"  # Fallback
                    else:
                        step_count = min(4, len(steps))
                        step_w = Inches(11.733 / step_count - 0.2)
                        step_gap = Inches(0.2)

                        for st_i, st in enumerate(steps[:4]):
                            st_x = Inches(0.8) + st_i * (step_w + step_gap)
                            st_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, st_x, Inches(1.8), step_w, Inches(5.0))
                            st_card.fill.solid()
                            st_card.fill.fore_color.rgb = CARD_BG
                            st_card.line.color.rgb = ACCENT_PRIMARY if st_i == 0 else STROKE

                            tf_st = st_card.text_frame
                            tf_st.word_wrap = True
                            tf_st.margin_left = Inches(0.3)
                            tf_st.margin_top = Inches(0.3)

                            sp1 = tf_st.paragraphs[0]
                            sp1.text = st.get("step", f"0{st_i+1}")
                            sp1.font.size = Pt(28)
                            sp1.font.bold = True
                            sp1.font.color.rgb = ACCENT_PRIMARY
                            sp1.space_after = Pt(8)

                            sp2 = tf_st.add_paragraph()
                            sp2.text = st.get("title", f"Step {st_i+1}")
                            sp2.font.size = Pt(16)
                            sp2.font.bold = True
                            sp2.font.color.rgb = TEXT_PRIMARY
                            sp2.space_after = Pt(8)

                            sp3 = tf_st.add_paragraph()
                            sp3.text = st.get("desc", "")
                            sp3.font.size = Pt(13)
                            sp3.font.color.rgb = TEXT_MUTED

                # -------------------------------------------------------------
                # LAYOUT 5: bullet_list (Default Catch-All Layout)
                # -------------------------------------------------------------
                if layout == "bullet_list":
                    content_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(11.733), Inches(5.0))
                    content_card.fill.solid()
                    content_card.fill.fore_color.rgb = CARD_BG
                    content_card.line.color.rgb = STROKE

                    ctf = content_card.text_frame
                    ctf.word_wrap = True
                    ctf.margin_left = Inches(0.6)
                    ctf.margin_top = Inches(0.5)

                    pts = slide_item.points or ["Core Technical Specification", "Multi-Agent System Integration", "High-Impact Execution"]
                    for p_idx, pt in enumerate(pts):
                        para = ctf.paragraphs[0] if p_idx == 0 else ctf.add_paragraph()
                        para.text = f"•  {pt}"
                        para.font.name = FONT_BODY
                        para.font.size = Pt(17)
                        para.font.color.rgb = TEXT_PRIMARY
                        para.space_after = Pt(14)

                # -------------------------------------------------------------
                # LAYOUT 6: Native Chart & Embedded Image Rendering
                # -------------------------------------------------------------
                if getattr(slide_item, 'chart_data', None) or getattr(slide_item, 'chart_type', None) or layout == "chart":
                    chart_dict = getattr(slide_item, 'chart_data', None) or {
                        "categories": ["Q1", "Q2", "Q3", "Q4"],
                        "series": [{"name": "Target Growth", "values": [25, 45, 70, 95]}]
                    }
                    cdata = CategoryChartData()
                    cdata.categories = chart_dict.get("categories", ["Q1", "Q2", "Q3", "Q4"])
                    for s in chart_dict.get("series", [{"name": "Growth", "values": [10, 20, 30, 40]}]):
                        cdata.add_series(s.get("name", "Series"), tuple(s.get("values", [10, 20, 30, 40])))

                    chart_enum = XL_CHART_TYPE.COLUMN_CLUSTERED
                    ct_str = (getattr(slide_item, 'chart_type', None) or "column").lower()
                    if "bar" in ct_str:
                        chart_enum = XL_CHART_TYPE.BAR_CLUSTERED
                    elif "line" in ct_str:
                        chart_enum = XL_CHART_TYPE.LINE
                    elif "pie" in ct_str:
                        chart_enum = XL_CHART_TYPE.PIE

                    slide.shapes.add_chart(chart_enum, Inches(0.8), Inches(1.8), Inches(11.733), Inches(5.0), cdata)
                    logger.info(f"NativePPTXEngine: Rendered native PowerPoint chart '{ct_str}' for slide '{slide_item.slide_title}'")

                if getattr(slide_item, 'image_url', None):
                    img_p = slide_item.image_url
                    if os.path.exists(img_p):
                        slide.shapes.add_picture(img_p, Inches(0.8), Inches(1.8), Inches(5.5), Inches(5.0))
                        logger.info(f"NativePPTXEngine: Rendered native picture from '{img_p}' for slide '{slide_item.slide_title}'")

            prs.save(target_path)
            logger.info(f"NativePPTXEngine: Multi-layout PPTX deck saved successfully at {target_path}")

        except Exception as e:
            logger.error(f"NativePPTXEngine: Error building PPTX deck: {e}", exc_info=True)
            with open(target_path, "wb") as f:
                f.write(f"CreateFlow AI Presentation Artifact\nTitle: {deck.title}\n".encode("utf-8"))

        return target_path

    @classmethod
    def export_pptx_to_pdf(cls, pptx_path: str, pdf_path: Optional[str] = None) -> str:
        """
        Converts a PPTX presentation deck into a PDF document via PowerPoint COM API or fallback engines.
        """
        if not pdf_path:
            pdf_path = os.path.splitext(pptx_path)[0] + ".pdf"

        pptx_abs = os.path.abspath(pptx_path)
        pdf_abs = os.path.abspath(pdf_path)

        logger.info(f"NativePPTXEngine: Exporting presentation deck '{pptx_abs}' -> '{pdf_abs}'")

        # 1. Try PowerPoint COM Automation (Windows win32com)
        try:
            import win32com.client
            powerpoint = win32com.client.Dispatch("PowerPoint.Application")
            deck = powerpoint.Presentations.Open(pptx_abs, WithWindow=False)
            deck.SaveAs(pdf_abs, 32)  # 32 = ppSaveAsPDF
            deck.Close()
            powerpoint.Quit()
            if os.path.exists(pdf_abs) and os.path.getsize(pdf_abs) > 0:
                logger.info(f"NativePPTXEngine: Successfully converted PDF via PowerPoint COM API: {pdf_abs}")
                return pdf_abs
        except Exception as e:
            logger.warning(f"NativePPTXEngine: PowerPoint COM conversion exception: {e}")

        # 2. Try LibreOffice / soffice CLI if installed
        import shutil
        soffice_bin = shutil.which("soffice") or shutil.which("libreoffice")
        if soffice_bin:
            try:
                import subprocess
                out_dir = os.path.dirname(pdf_abs)
                cmd = [soffice_bin, "--headless", "--convert-to", "pdf", "--outdir", out_dir, pptx_abs]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if os.path.exists(pdf_abs):
                    return pdf_abs
            except Exception as e:
                logger.warning(f"NativePPTXEngine: LibreOffice conversion exception: {e}")

        # 3. Pure reportlab Full Slide Content PDF Renderer.
        #
        # This tier previously used PyMuPDF (fitz), which is AGPL-3.0. AGPL's copyleft is
        # triggered by *network interaction*, not distribution, so serving CreateFlow AI
        # as a SaaS would have obliged us to publish the whole combined work's source.
        # reportlab is BSD and carries no such condition. See LICENSES.md R3.
        #
        # Coordinate systems differ: fitz measured y downward from the top, reportlab
        # measures upward from the bottom. Every y below is therefore expressed as
        # (PAGE_H - y_from_top), which is why the constants look inverted against the
        # original but produce an identical layout.
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.colors import Color
        from pptx import Presentation

        PAGE_W, PAGE_H = 792.0, 445.5  # 16:9 widescreen, unchanged from the fitz version

        def _rgb(r, g, b):
            return Color(r / 255.0, g / 255.0, b / 255.0)

        BG = _rgb(15, 23, 42)        # #0F172A
        CARD = _rgb(30, 41, 59)      # #1E293B
        ACCENT = _rgb(59, 130, 246)  # #3B82F6
        BORDER = _rgb(51, 65, 85)    # #334155
        TITLE_FG = Color(1.0, 1.0, 1.0)
        BODY_FG = Color(0.9, 0.95, 1.0)

        def _wrap(c, text, font, size, max_width):
            """Greedy word wrap. reportlab has no insert_textbox equivalent on canvas."""
            out = []
            for raw_line in text.split("\n"):
                if not raw_line.strip():
                    continue
                words, line = raw_line.split(), ""
                for w in words:
                    probe = f"{line} {w}".strip()
                    if c.stringWidth(probe, font, size) <= max_width or not line:
                        line = probe
                    else:
                        out.append(line)
                        line = w
                if line:
                    out.append(line)
            return out

        prs = Presentation(pptx_abs)
        c = rl_canvas.Canvas(pdf_abs, pagesize=(PAGE_W, PAGE_H))

        for s_idx, slide in enumerate(prs.slides):
            # Dark background
            c.setFillColor(BG)
            c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

            # Extract slide text shapes
            slide_text_blocks = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    paragraphs = []
                    for p in shape.text_frame.paragraphs:
                        p_text = p.text.strip()
                        if p_text:
                            paragraphs.append(p_text)
                    if paragraphs:
                        slide_text_blocks.append("\n".join(paragraphs))

            slide_title = f"Slide {s_idx + 1}"
            if slide_text_blocks:
                slide_title = slide_text_blocks[0].split("\n")[0]

            # Header card: fitz Rect(30, 25, 762, 75) -> x=30 w=732, top y=25 h=50
            c.setFillColor(CARD)
            c.setStrokeColor(ACCENT)
            c.setLineWidth(1)
            c.rect(30, PAGE_H - 75, 732, 50, stroke=1, fill=1)

            c.setFillColor(TITLE_FG)
            c.setFont("Helvetica", 16)
            title_lines = _wrap(c, slide_title, "Helvetica", 16, 710)
            ty = PAGE_H - 30 - 16
            for line in title_lines[:2]:  # header card fits two lines at 16pt
                c.drawString(40, ty, line)
                ty -= 19

            # Body card: fitz Rect(30, 85, 762, 415) -> x=30 w=732, top y=85 h=330
            c.setFillColor(CARD)
            c.setStrokeColor(BORDER)
            c.setLineWidth(1)
            c.rect(30, PAGE_H - 415, 732, 330, stroke=1, fill=1)

            body_lines = []
            for block in slide_text_blocks:
                for line in block.split("\n"):
                    if line != slide_title and not line.startswith("Theme:"):
                        body_lines.append(line)

            body_text = "\n".join(body_lines) if body_lines else "- Content details rendered from slide structure."
            c.setFillColor(BODY_FG)
            c.setFont("Helvetica", 11)
            by = PAGE_H - 95 - 11
            for line in _wrap(c, body_text, "Helvetica", 11, 692):
                if by < PAGE_H - 405:  # clip to the body card, as insert_textbox did
                    break
                c.drawString(45, by, line)
                by -= 14

            c.showPage()

        c.save()
        logger.info(f"NativePPTXEngine: Successfully rendered full PDF via reportlab engine: {pdf_abs}")
        return pdf_abs

