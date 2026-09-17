"""
H.264 Video Renderer v3 -- final encoding stage with style continuity.
Inspired by code2mp4 core/, mcp-video editor, and CutAgent style harness.

v3 additions:
  - Inter-scene visual continuity via CutAgent last-frame reference chaining
  - Cross-fade blending from previous scene's exact final frame buffer
  - Animated visual overlays (charts, diagrams) per scene
  - Text entrance animation scheduling & title bar rendering
  - Vignette cinematic effect & scene counter overlay
  - Audio muxing support
"""
import os
import math
import logging
import cv2
import numpy as np
from typing import List, Optional

from agents.video.storyboard import Storyboard
from agents.video.scene_composer import SceneComposer, TimelineSegment, StyleContext, StyleEngine
from agents.video.python_editor.compositing import Compositor
from agents.video.python_editor.text_overlays import TextOverlayEngine, FontManager
from agents.video.python_editor.brand_logo import BrandLogoOverlay
from agents.video.python_editor import brand_theme
from agents.video.python_editor.animated_visuals import AnimatedVisualsEngine
from agents.video.motion_graphics_overlays import MotionGraphicsOverlayEngine

logger = logging.getLogger("uvicorn")


class VideoRenderer:
    """
    End-to-end frame renderer and H.264 encoder v3.
    Pipeline per frame:
      1. Background fill (gradient/dark/light)
      2. CutAgent last-frame reference cross-blend for scene continuity
      3. Apply transition effect (fade/slide_left/dissolve/zoom_in)
      4. AnimatedVisualsEngine renders chart/diagram overlays
      5. TextOverlayEngine draws text with entrance animations
      6. Scene title bar + progress bar + scene counter
      7. Vignette cinematic effect
      8. Capture final frame buffer of scene N for scene N+1 reference
      9. Frame piped to libx264 encoder
    """

    @classmethod
    def render(cls, storyboard: Storyboard, output_path: str,
               audio_path: str = None,
               style_context: Optional[StyleContext] = None) -> str:
        return cls.render_storyboard(storyboard, output_path, audio_path=audio_path, style_context=style_context)

    @classmethod
    def render_storyboard(cls, storyboard: Storyboard, output_path: str,
                         audio_path: str = None,
                         fps: int = 30,
                         style_context: Optional[StyleContext] = None,
                         crf: Optional[int] = None,
                         preset: Optional[str] = None,
                         max_bitrate: Optional[str] = None,
                         audio_codec: Optional[str] = None,
                         audio_bitrate: Optional[str] = None,
                         audio_sample_rate: Optional[int] = None,
                         progress: Optional["PipelineProgress"] = None) -> str:
        import imageio_ffmpeg
        from agents.video.progress import PipelineProgress

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        width, height = storyboard.resolution

        # Brand kit, if this job carries one. The palette already reached the scenes via
        # the Director's brief; the typeface and the logo are applied here.
        brand = getattr(storyboard, "brand_kit", None) or {}
        FontManager.use(brand.get("font_choice"))
        # Accent colours for the overlays drawn on top of the footage: the rule under a
        # stat, the text-card border, the caption underline, the progress bar. Without
        # this the brand reaches only the scene backgrounds, which stock footage covers
        # completely -- so a branded video looked unbranded apart from the logo.
        brand_theme.use(brand)
        logo_overlay = BrandLogoOverlay.prepare(brand.get("logo_path"), width, height)
        if brand:
            theme = brand_theme.active()
            logger.info(
                f"VideoRenderer: brand kit active -- font={FontManager.active_choice()}, "
                f"accent=RGB{theme.accent}, secondary=RGB{theme.secondary}, "
                f"logo={'loaded' if logo_overlay else 'none'}"
            )
        fps = storyboard.fps
        progress = progress or PipelineProgress(None)

        # Initialize CutAgent style context for last-frame chaining if not provided
        if style_context is None:
            style_context = StyleContext(auto_chain_last_frame=True)

        # compose_timeline queries the media providers and downloads the stock clips, so
        # this is where the job actually spends its "collecting footage" time.
        progress.report("footage")
        segments = SceneComposer.compose_timeline(storyboard, style=style_context)

        # Upgrade 5: Build Hierarchical MasterSceneGraph as source of truth
        from agents.video.compositor.scene_graph_builder import SceneGraphBuilder
        master_scene_graph = SceneGraphBuilder.build_scene_graph(storyboard, segments)
        storyboard._scene_graph = master_scene_graph
        cls.last_scene_graph = master_scene_graph

        total_frames = sum(seg.frame_count for seg in segments)
        total_scenes = len(segments)

        logger.info(f"VideoRenderer v3: Rendering {total_frames} frames (last-frame chained) -> {output_path}")

        output_params = ["-movflags", "+faststart", "-vf", f"crop={width}:{height}"]
        if crf is not None:
            output_params.extend(["-crf", str(crf)])
        if preset is not None:
            output_params.extend(["-preset", str(preset)])
        if max_bitrate is not None:
            output_params.extend(["-maxrate", str(max_bitrate), "-bufsize", str(max_bitrate)])

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        actual_writer_cmd = [
            ffmpeg_exe, "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{width}x{height}",
            "-pix_fmt", "bgr24",
            "-r", f"{fps:.2f}",
            "-i", "-",
            "-an",
            "-vcodec", "libx264",
            "-pix_fmt", "yuv420p"
        ] + output_params + [output_path]
        logger.info(f"VideoRenderer [FFmpeg Writer Invocation]: {' '.join(actual_writer_cmd)}")

        writer = imageio_ffmpeg.write_frames(
            output_path,
            size=(width, height),
            fps=fps,
            codec="libx264",
            pix_fmt_in="bgr24",
            pix_fmt_out="yuv420p",
            output_params=output_params
        )
        writer.send(None)

        global_frame = 0
        last_rendered_frame: Optional[np.ndarray] = None

        progress.report("compositing")

        for seg_idx, seg in enumerate(segments):
            progress.report_scene(seg_idx, total_scenes)
            scene = seg.scene
            bg_color = tuple(scene.background_color) if scene.background_color else (42, 23, 15)
            bg_style = getattr(scene, "background_style", "gradient")

            # B-Roll Image Layer: Load once per scene via MediaAssetLoader (no per-frame disk I/O)
            from agents.video.python_editor.media_asset_loader import MediaAssetLoader
            loaded_asset = MediaAssetLoader.load(
                candidate=getattr(seg, "media_candidate", None),
                width=width,
                height=height
            )
            broll_image: Optional[np.ndarray] = loaded_asset.frame  # BGR or None → procedural fallback
            broll_video_frames: Optional[List[np.ndarray]] = loaded_asset.video_frames if loaded_asset.is_video else None

            # Presenter clip: if a scene carries a pre-rendered avatar clip, preload its
            # frames as the scene background. Inert since the Wav2Lip stage was removed
            # (LICENSES.md R2) -- nothing populates presenter_clip_path any more -- but the
            # branch is licence-neutral and kept for a future commercial-safe lip-sync.
            presenter_frames: Optional[list] = None
            presenter_clip_path = getattr(scene, "presenter_clip_path", None)
            if getattr(scene, "presenter_mode", False) and presenter_clip_path and os.path.exists(presenter_clip_path):
                try:
                    _cap = cv2.VideoCapture(presenter_clip_path)
                    _frames = []
                    while True:
                        _ok, _fr = _cap.read()
                        if not _ok:
                            break
                        _frames.append(cv2.resize(_fr, (width, height)))
                    _cap.release()
                    if _frames:
                        presenter_frames = _frames
                        logger.info(
                            f"VideoRenderer: presenter clip loaded for '{scene.scene_id}' "
                            f"({len(_frames)} frames, real_lipsync={getattr(scene, 'presenter_is_real_lipsync', None)})."
                        )
                except Exception as _pe:
                    logger.warning(f"VideoRenderer: failed to load presenter clip for '{scene.scene_id}' ({_pe}).")

            # Retrieve last-frame reference from preceding scene
            last_frame_ref = getattr(style_context, "last_frame_buffer", None)
            if last_frame_ref is None and style_context.references:
                last_ref_entry = next((r for r in style_context.references if r.ref_type == "last-frame"), None)
                if last_ref_entry and last_ref_entry.frame_buffer is not None:
                    last_frame_ref = last_ref_entry.frame_buffer

            entrance_schedules = SceneComposer.compute_text_entrance_schedule(scene)

            # Priority 3: Generate word-level caption timeline
            # Use real Edge-TTS WordBoundary timestamps when available (attached by TTSEngine v4)
            speech_text = getattr(scene, "user_speech", None) or getattr(scene, "speech_text", None) or scene.narration
            seg_start_sec = seg.start_frame / max(fps, 1)
            seg_end_sec = seg.end_frame / max(fps, 1)
            tts_word_timestamps = getattr(scene, "_tts_word_timestamps", None)

            from agents.video.caption_engine import CaptionEngine
            scene_words = CaptionEngine.generate_word_timeline(
                speech_text=speech_text,
                start_sec=seg_start_sec,
                end_sec=seg_end_sec,
                scene_id=scene.scene_id,
                wav_path=audio_path,
                tts_word_timestamps=tts_word_timestamps
            ) if speech_text else []

            for local_frame in range(seg.frame_count):
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                scene_progress = (local_frame + 1) / max(seg.frame_count, 1)
                current_global_sec = global_frame / max(fps, 1)

                # 1. Background Fill (Presenter clip > B-Roll Video > B-Roll Image > Procedural) + Floating Particles
                if presenter_frames:
                    # Talking-presenter scene: use the corresponding avatar frame as background
                    p_idx = min(local_frame, len(presenter_frames) - 1)
                    frame[:] = presenter_frames[p_idx]
                elif broll_video_frames:
                    # Real stock-footage clip: map scene progress across the decoded clip frames
                    # so a short 5-15s clip plays smoothly for the full scene duration.
                    v_idx = min(int(scene_progress * len(broll_video_frames)), len(broll_video_frames) - 1)
                    frame[:] = broll_video_frames[v_idx]
                elif broll_image is not None:
                    frame[:] = broll_image.copy()
                else:
                    from agents.video.domain_palette_engine import DomainPaletteEngine
                    domain_text_signal = f"{storyboard.title} {getattr(scene, 'scene_title', '')} {getattr(scene, 'narration', '') or ''}"
                    domain_key, palette_info = DomainPaletteEngine.infer_domain(domain_text_signal)

                    if bg_style == "light":
                        Compositor.apply_light_background(frame)
                    elif bg_style == "dark":
                        Compositor.apply_dark_background(frame)
                    elif bg_style == "dense_noise" or "dense noise" in (getattr(scene, "scene_title", "") or "").lower() or "dense noise" in (getattr(scene, "narration", "") or "").lower():
                        Compositor.apply_dense_noise_background(frame, scene_progress)
                    else:
                        # Use domain palette if bg_color is default or if domain signal is matched
                        bg_top = tuple(scene.background_color) if (scene.background_color and scene.background_color != [42, 23, 15]) else palette_info["top_color"]
                        bg_bottom = palette_info["bottom_color"]
                        Compositor.apply_gradient_overlay(
                            frame,
                            top_color=bg_top,
                            bottom_color=bg_bottom
                        )

                # 2. 12 Transition Types
                alpha = Compositor.compute_transition_alpha(
                    local_frame, seg.frame_count,
                    seg.transition_in_frames,
                    scene.transition
                )

                trans = scene.transition
                if trans == "slide_left":
                    Compositor.apply_slide_left(frame, alpha)
                elif trans == "slide_right":
                    Compositor.apply_slide_right(frame, alpha)
                elif trans == "slide_up":
                    Compositor.apply_slide_up(frame, alpha)
                elif trans == "slide_down":
                    Compositor.apply_slide_down(frame, alpha)
                elif trans == "iris_circle":
                    Compositor.apply_iris_circle(frame, alpha)
                elif trans == "whip_pan_blur":
                    Compositor.apply_whip_pan_blur(frame, alpha)
                elif trans == "morph_crossfade":
                    Compositor.apply_morph_crossfade(frame, alpha)
                elif trans == "zoom_in":
                    Compositor.apply_fade(frame, alpha)
                    Compositor.apply_zoom_in(frame, alpha, max_zoom=1.08, mode="transition")
                elif trans == "zoom_out":
                    Compositor.apply_fade(frame, alpha)
                    Compositor.apply_zoom_out(frame, alpha, max_zoom=1.12)
                elif trans == "dissolve":
                    Compositor.apply_dissolve(frame, alpha)
                elif trans == "wipe":
                    Compositor.apply_wipe(frame, alpha)
                else:
                    Compositor.apply_fade(frame, alpha)

                # 3. Animated visual overlay (chart/diagram)
                visual = getattr(scene, "visual_overlay", None)
                if visual and visual.overlay_type != "none":
                    overlay_progress = max(0.0, min(1.0,
                        (scene_progress - seg.overlay_start_frac) /
                        max(seg.overlay_end_frac - seg.overlay_start_frac, 0.01)
                    ))
                    if overlay_progress > 0:
                        AnimatedVisualsEngine.render_overlay(
                            frame, visual, width, height, overlay_progress
                        )

                # 3b. Apply Ken Burns Sub-Pixel Camera Motion Transformation
                # Skipped when a real video clip supplies the background -- the footage already
                # has genuine motion, so a synthetic zoom/pan on top of it looks unnatural.
                if not broll_video_frames:
                    motion_zoom_val = getattr(scene, "motion_zoom", 1.08)
                    motion_profile = getattr(scene, "motion_profile", None) or ("zoom_out" if (seg_idx % 2 == 1) else "zoom_in")
                    from agents.video.python_editor.ken_burns_engine import KenBurnsMotionEngine
                    frame = KenBurnsMotionEngine.apply_motion(
                        frame,
                        scene_progress,
                        motion_profile=motion_profile,
                        motion_zoom=motion_zoom_val
                    )

                # 3c. Camera Motion Treatment (Zoom Punch-In scaling on the background only,
                # applied before any text so captions/titles never zoom/wobble with it)
                trans = getattr(scene, "transition", "none")
                if trans == "zoom_in" or getattr(scene, "motion_zoom", 1.0) > 1.05:
                    zoom_factor = float(getattr(scene, "motion_zoom", 1.15))
                    if zoom_factor < 1.05:
                        zoom_factor = 1.15
                    Compositor.apply_zoom_in(frame, scene_progress, max_zoom=zoom_factor)

                # 3d. Commercial Cinematic 3D Color Grading
                try:
                    from agents.video.color_grading_engine import ColorGradingEngine
                    topic_signal = f"{storyboard.title} {getattr(scene, 'scene_title', '')} {getattr(scene, 'narration', '') or ''}"
                    color_profile = ColorGradingEngine.infer_profile_from_topic(topic_signal)
                    frame[:] = ColorGradingEngine.apply_grade(frame, profile_name=color_profile, strength=0.55)
                except Exception as e:
                    logger.debug(f"VideoRenderer: Color grading error: {e}")

                # 3e. Vignette effect
                Compositor.apply_vignette(frame, strength=0.18)

                # 4. Inter-scene visual continuity & multi-frame Cosine S-curve crossfade transition blend.
                # Runs on the pure background/visual layer ONLY, before any text is drawn -- otherwise the
                # previous scene's caption (baked into its last frame) would cross-fade underneath this
                # scene's freshly-drawn caption, producing two overlapping subtitle bars during every cut.
                if local_frame < seg.transition_in_frames and last_frame_ref is not None:
                    t = local_frame / max(seg.transition_in_frames, 1)
                    # Non-linear Cosine S-curve: smooth acceleration, peak velocity at mid-transition, smooth deceleration
                    w1 = 0.5 * (1.0 + math.cos(math.pi * t))
                    w2 = 1.0 - w1
                    frame[:] = (
                        frame.astype(np.float32) * w2 +
                        last_frame_ref.astype(np.float32) * w1
                    ).clip(0, 255).astype(np.uint8)

                # Capture the pure-visual frame buffer (no text/captions baked in) as the
                # continuity reference for the NEXT scene's crossfade -- keeps transitions
                # free of any ghosted caption/title text from this scene.
                last_rendered_frame = frame.copy()

                # 5. Text layers with spring-physics entrance animations.
                # Top-positioned layers are intentionally dropped: a headline at the top
                # competed with the narration captions and read as a second subtitle.
                # The bottom caption is the only text track for spoken content.
                visible_layers = [
                    tl for tl in (scene.text_layers or [])
                    if getattr(tl, "position", "center") not in ("top", "top_left")
                ]
                if visible_layers:
                    visible_schedules = [
                        sched for tl, sched in zip(scene.text_layers or [], entrance_schedules or [])
                        if getattr(tl, "position", "center") not in ("top", "top_left")
                    ] if entrance_schedules else None
                    TextOverlayEngine.render_text_layers(
                        frame, visible_layers, width, height,
                        scene_progress=scene_progress,
                        entrance_schedules=visible_schedules
                    )

                # 5b. Motion graphics: animated stat counters authored by the AI screenwriter.
                scene_stats = getattr(scene, "on_screen_stats", None)
                if scene_stats:
                    MotionGraphicsOverlayEngine.render_stat_counter(
                        frame, scene_stats, width, height, scene_progress
                    )

                # 6. Single-line captions in reserved safe zone (bottom center)
                if scene_words:
                    TextOverlayEngine.render_animated_word_captions(
                        frame, scene_words, current_global_sec, width, height
                    )

                # 7. Scene title bar: removed. It painted a coloured band with the scene
                # title across the top of every scene, which is exactly the top-of-frame
                # text the design calls for eliminating. The bottom caption carries all text.

                # 8. Radial progress ring + progress bar + scene counter
                TextOverlayEngine.render_progress_bar(frame, scene_progress, width, height)

                # 9. Brand logo. Last, so nothing composites over it -- a watermark that
                # a caption can cover is not a watermark.
                if logo_overlay is not None:
                    BrandLogoOverlay.stamp(frame, logo_overlay)

                writer.send(frame)
                global_frame += 1

            # Update style context with scene N's final frame for scene N+1
            style_context = StyleEngine.on_scene_completed(
                scene.scene_id, last_rendered_frame, style_context
            )

        writer.close()

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise RuntimeError(f"Renderer produced empty file at {output_path}")

        # Audio muxing (if voiceover available)
        if audio_path and os.path.exists(audio_path):
            cls._mux_audio(output_path, audio_path, audio_codec=audio_codec, audio_bitrate=audio_bitrate, audio_sample_rate=audio_sample_rate)

        size_kb = os.path.getsize(output_path) / 1024.0
        logger.info(f"VideoRenderer v3: Encoded {output_path} "
                     f"({size_kb:.1f} KB, {total_frames} frames, {global_frame / fps:.1f}s)")
        return output_path

    @classmethod
    def _mux_audio(cls, video_path: str, audio_path: str,
                   audio_codec: Optional[str] = None,
                   audio_bitrate: Optional[str] = None,
                   audio_sample_rate: Optional[int] = None):
        """Mux audio track into MP4 using imageio-ffmpeg bundled executable."""
        import subprocess
        import shutil
        import imageio_ffmpeg

        ffmpeg_path = None
        try:
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass

        if not ffmpeg_path:
            ffmpeg_path = shutil.which("ffmpeg")

        if not ffmpeg_path or not os.path.exists(ffmpeg_path):
            logger.warning("VideoRenderer: ffmpeg executable not found, skipping audio mux")
            return

        a_codec = audio_codec or "aac"
        a_rate = str(audio_sample_rate or 44100)
        a_bitrate = audio_bitrate or "192k"

        temp_path = video_path + ".muxed.mp4"
        cmd = [
            ffmpeg_path, "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", a_codec,
            "-b:a", a_bitrate,
            "-ar", a_rate,
            "-map", "0:v:0", "-map", "1:a:0",
            "-shortest",
            "-movflags", "+faststart",
            temp_path
        ]
        logger.info(f"VideoRenderer [FFmpeg Audio Muxer Invocation]: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and os.path.exists(temp_path):
                os.replace(temp_path, video_path)
                logger.info(f"VideoRenderer: Audio muxed into {video_path}")
            else:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        except Exception as e:
            logger.warning(f"VideoRenderer: Audio mux exception: {e}")

    @classmethod
    def concatenate_scenes(cls, scene_paths: List[str], output_path: str) -> str:
        """Concatenate multiple scene MP4 files into a single deliverable."""
        import subprocess
        import imageio_ffmpeg
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        if not scene_paths:
            raise ValueError("No scene paths provided for concatenation.")
        if len(scene_paths) == 1:
            import shutil
            shutil.copyfile(scene_paths[0], output_path)
            return output_path

        try:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_exe = "ffmpeg"

        concat_txt = output_path + ".txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for p in scene_paths:
                clean_p = os.path.abspath(p).replace("\\", "/")
                f.write(f"file '{clean_p}'\n")

        cmd = [
            ffmpeg_exe, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_txt,
            "-c", "copy",
            "-movflags", "+faststart",
            output_path
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode != 0 or not os.path.exists(output_path):
                import shutil
                shutil.copyfile(scene_paths[0], output_path)
        except Exception as e:
            import shutil
            shutil.copyfile(scene_paths[0], output_path)
        finally:
            if os.path.exists(concat_txt):
                try:
                    os.remove(concat_txt)
                except Exception:
                    pass
        return output_path
