"""
Animated Visuals Engine -- renders animated charts and diagrams per-scene.
Inspired by OpenMontage remotion-composer/ components (StatCard, ProgressBar)
and code2mp4 skills/ visual asset generation.

Renders directly onto NumPy BGR frames using matplotlib + OpenCV:
  - Animated bar charts (bars grow from 0 to target height)
  - Animated line charts (line draws left-to-right)
  - Animated pie charts (wedge sweep)
  - Architecture diagram overlay (box-and-arrow)
  - Workflow pipeline overlay (step boxes)
"""
import os
import io
import logging
import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from typing import List, Tuple, Optional
from agents.video.storyboard import VisualOverlay

logger = logging.getLogger("uvicorn")


class AnimatedVisualsEngine:
    """
    Renders animated charts and diagrams directly onto video frames.
    Each render method accepts a progress parameter [0,1] to animate.
    """

    @classmethod
    def render_overlay(cls, frame: np.ndarray, overlay: VisualOverlay,
                        width: int, height: int, progress: float):
        """Dispatch to the appropriate overlay renderer."""
        if not overlay or overlay.overlay_type == "none":
            return

        # architecture_diagram / workflow_diagram are intentionally NOT dispatched here:
        # the auto-generated box-and-arrow diagrams looked unpolished, so those overlay
        # types are disabled outright -- the scene's real video/photo background shows
        # through untouched instead. Kept as a hard backstop even if some upstream path
        # (LLM output, legacy template, user-provided JSON) still requests one.
        renderers = {
            "bar_chart": cls._render_bar_chart,
            "line_chart": cls._render_line_chart,
            "pie_chart": cls._render_pie_chart,
        }

        renderer = renderers.get(overlay.overlay_type)
        if renderer:
            renderer(frame, overlay, width, height, progress)

    @classmethod
    def _render_bar_chart(cls, frame: np.ndarray, overlay: VisualOverlay,
                           width: int, height: int, progress: float):
        """Animated bar chart -- bars grow from bottom up with resolution-proportional fonts/strokes."""
        scale_h = height / 1080.0
        labels = overlay.data_labels or ["A", "B", "C"]
        values = overlay.data_values or [80, 60, 90]
        max_val = max(values) if values else 100

        chart_x = int(width * 0.15)
        chart_y = int(height * 0.30)
        chart_w = int(width * 0.70)
        chart_h = int(height * 0.45)
        bar_gap = int(15 * scale_h)
        n = len(values)
        bar_w = max(int(20 * scale_h), (chart_w - (n + 1) * bar_gap) // n)

        colors = [(59, 130, 246), (139, 92, 246), (249, 115, 22), (16, 185, 129), (244, 63, 94)]

        # Background panel
        overlay_bg = frame.copy()
        cv2.rectangle(overlay_bg, (chart_x - int(10 * scale_h), chart_y - int(30 * scale_h)),
                      (chart_x + chart_w + int(10 * scale_h), chart_y + chart_h + int(40 * scale_h)),
                      (30, 30, 30), -1)
        cv2.addWeighted(overlay_bg, 0.7, frame, 0.3, 0, frame)

        # Title
        title = overlay.title or "Performance"
        cv2.putText(frame, title, (chart_x, chart_y - int(8 * scale_h)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7 * scale_h, (248, 250, 252), max(1, int(2 * scale_h)), cv2.LINE_AA)

        for i, (label, val) in enumerate(zip(labels, values)):
            x = chart_x + bar_gap + i * (bar_w + bar_gap)
            full_h = int((val / max_val) * chart_h * 0.85)
            animated_h = int(full_h * min(progress, 1.0))
            y_bottom = chart_y + chart_h
            y_top = y_bottom - animated_h

            color = colors[i % len(colors)]
            if animated_h > 0:
                cv2.rectangle(frame, (x, y_top), (x + bar_w, y_bottom), color, -1)

            # Label below bar
            cv2.putText(frame, label[:8], (x, y_bottom + int(18 * scale_h)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45 * scale_h, (200, 200, 200), max(1, int(1 * scale_h)), cv2.LINE_AA)
            # Value on top of bar
            if animated_h > int(15 * scale_h):
                cv2.putText(frame, f"{int(val * min(progress, 1.0))}", (x + int(2 * scale_h), y_top - int(5 * scale_h)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45 * scale_h, (248, 250, 252), max(1, int(1 * scale_h)), cv2.LINE_AA)

    @classmethod
    def _render_line_chart(cls, frame: np.ndarray, overlay: VisualOverlay,
                            width: int, height: int, progress: float):
        """Animated line chart -- line draws left-to-right with resolution-proportional fonts/strokes."""
        scale_h = height / 1080.0
        values = overlay.data_values or [30, 55, 45, 80, 72, 95]
        n = len(values)
        max_val = max(values) if values else 100

        chart_x = int(width * 0.15)
        chart_y = int(height * 0.30)
        chart_w = int(width * 0.70)
        chart_h = int(height * 0.45)

        # Background panel
        overlay_bg = frame.copy()
        cv2.rectangle(overlay_bg, (chart_x - int(10 * scale_h), chart_y - int(30 * scale_h)),
                      (chart_x + chart_w + int(10 * scale_h), chart_y + chart_h + int(20 * scale_h)),
                      (30, 30, 30), -1)
        cv2.addWeighted(overlay_bg, 0.7, frame, 0.3, 0, frame)

        title = overlay.title or "Trend Analysis"
        cv2.putText(frame, title, (chart_x, chart_y - int(8 * scale_h)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7 * scale_h, (248, 250, 252), max(1, int(2 * scale_h)), cv2.LINE_AA)

        visible_points = max(1, int(n * progress))
        points = []
        for i in range(visible_points):
            px = chart_x + int((i / max(n - 1, 1)) * chart_w)
            py = chart_y + chart_h - int((values[i] / max_val) * chart_h * 0.85)
            points.append((px, py))

        # Draw line segments
        stroke_w = max(1, int(2 * scale_h))
        dot_r = max(2, int(5 * scale_h))
        for i in range(len(points) - 1):
            cv2.line(frame, points[i], points[i + 1], (59, 130, 246), stroke_w, cv2.LINE_AA)
        # Draw dots
        for pt in points:
            cv2.circle(frame, pt, dot_r, (139, 92, 246), -1, cv2.LINE_AA)

    @classmethod
    def _render_pie_chart(cls, frame: np.ndarray, overlay: VisualOverlay,
                           width: int, height: int, progress: float):
        """Animated pie chart rendered via matplotlib onto the frame."""
        labels = overlay.data_labels or ["A", "B", "C"]
        values = overlay.data_values or [40, 35, 25]

        # Render to matplotlib buffer
        fig, ax = plt.subplots(figsize=(3, 3), dpi=100)
        fig.patch.set_alpha(0.0)
        ax.set_facecolor("none")

        sweep = [v * progress for v in values]
        if sum(sweep) == 0:
            sweep = [1]
            labels = [""]

        colors = ["#3b82f6", "#8b5cf6", "#f97316", "#10b981", "#f43f5e"]
        ax.pie(sweep, labels=labels[:len(sweep)], colors=colors[:len(sweep)],
               autopct=lambda p: f"{p:.0f}%" if p > 5 else "",
               textprops={"color": "white", "fontsize": 8})

        buf = io.BytesIO()
        plt.savefig(buf, format="png", transparent=True, bbox_inches="tight", dpi=100)
        plt.close()
        buf.seek(0)

        # Decode and overlay
        img_arr = np.frombuffer(buf.read(), np.uint8)
        pie_img = cv2.imdecode(img_arr, cv2.IMREAD_UNCHANGED)
        if pie_img is not None:
            cls._overlay_rgba(frame, pie_img, int(width * 0.35), int(height * 0.25))

    @classmethod
    def _render_architecture_diagram(cls, frame: np.ndarray, overlay: VisualOverlay,
                                      width: int, height: int, progress: float):
        """Animated architecture diagram -- boxes appear sequentially."""
        boxes = [
            ("Frontend", int(width * 0.08), int(height * 0.35), (59, 130, 246)),
            ("API Router", int(width * 0.30), int(height * 0.35), (16, 185, 129)),
            ("Orchestrator", int(width * 0.52), int(height * 0.25), (139, 92, 246)),
            ("Agent Engines", int(width * 0.52), int(height * 0.55), (249, 115, 22)),
            ("Storage", int(width * 0.75), int(height * 0.35), (244, 63, 94)),
        ]

        visible_count = max(1, int(len(boxes) * progress))
        box_w, box_h = int(width * 0.16), int(height * 0.15)

        for i, (label, bx, by, color) in enumerate(boxes[:visible_count]):
            cv2.rectangle(frame, (bx, by), (bx + box_w, by + box_h), color, 2, cv2.LINE_AA)
            cv2.putText(frame, label, (bx + 8, by + box_h // 2 + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (248, 250, 252), 1, cv2.LINE_AA)

            if i > 0 and i < visible_count:
                prev_bx = boxes[i - 1][1] + box_w
                prev_by = boxes[i - 1][2] + box_h // 2
                cv2.arrowedLine(frame, (prev_bx, prev_by), (bx, by + box_h // 2),
                                (148, 163, 184), 2, cv2.LINE_AA, tipLength=0.15)

    @classmethod
    def _render_workflow_diagram(cls, frame: np.ndarray, overlay: VisualOverlay,
                                  width: int, height: int, progress: float):
        """Animated workflow pipeline -- steps appear left to right."""
        steps = ["Prompt", "Plan", "Generate", "Render", "Validate"]
        visible = max(1, int(len(steps) * progress))
        step_w = int(width * 0.14)
        step_h = int(height * 0.12)
        start_x = int(width * 0.06)
        y = int(height * 0.45)

        for i, label in enumerate(steps[:visible]):
            x = start_x + i * (step_w + 20)
            cv2.rectangle(frame, (x, y), (x + step_w, y + step_h),
                          (99, 102, 241), 2, cv2.LINE_AA)
            cv2.putText(frame, label, (x + 8, y + step_h // 2 + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (248, 250, 252), 1, cv2.LINE_AA)

            if i < visible - 1:
                cv2.arrowedLine(frame, (x + step_w, y + step_h // 2),
                                (x + step_w + 20, y + step_h // 2),
                                (148, 163, 184), 2, cv2.LINE_AA, tipLength=0.3)

    @staticmethod
    def _overlay_rgba(frame: np.ndarray, overlay_img: np.ndarray, x: int, y: int):
        """Composite an RGBA image onto a BGR frame."""
        if overlay_img.shape[2] < 4:
            return
        oh, ow = overlay_img.shape[:2]
        fh, fw = frame.shape[:2]

        # Clip to frame bounds
        if x + ow > fw:
            ow = fw - x
        if y + oh > fh:
            oh = fh - y
        if ow <= 0 or oh <= 0:
            return

        roi = overlay_img[:oh, :ow]
        alpha = roi[:, :, 3:4].astype(np.float32) / 255.0
        bgr = roi[:, :, :3]

        region = frame[y:y + oh, x:x + ow]
        frame[y:y + oh, x:x + ow] = (
            bgr.astype(np.float32) * alpha + region.astype(np.float32) * (1 - alpha)
        ).clip(0, 255).astype(np.uint8)
