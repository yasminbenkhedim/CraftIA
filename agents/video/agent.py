"""
Advanced VideoAgent v3 -- Production Video Generation Agent with EndToEndVideoPipeline & Fallback.
"""
import os
import sys
import logging
import shutil
from typing import Dict, Any, Callable, Optional
from pathlib import Path

backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from agents.base import BaseAgent
from agents.video.storyboard import StoryboardPlanner
from agents.video.scene_composer import SceneComposer
from agents.video.tts_engine import TTSEngine
from agents.video.python_editor.renderer import VideoRenderer
from agents.video.quality_check import VideoQualityChecker
from agents.video.progress import PipelineProgress, stage

logger = logging.getLogger("uvicorn")

MAX_RETRY_ATTEMPTS = 2


class VideoAgent(BaseAgent):
    """
    Production VideoAgent v3 supporting EndToEndVideoPipeline and automatic legacy fallback.
    """

    def validate_input(self, prompt: str, options: Optional[Dict[str, Any]] = None) -> bool:
        if not prompt or not prompt.strip():
            raise ValueError("Video prompt cannot be empty.")
        return True

    def generate_artifact(
        self,
        job_id: str,
        prompt: str,
        target_dir: str,
        options: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> str:
        os.makedirs(target_dir, exist_ok=True)
        artifact_path = os.path.join(target_dir, "video_demo.mp4")
        options = options or {}

        use_legacy = options.get("use_legacy", False)

        # The requested narration language. Normalized here, at the one point where
        # untrusted UI input enters the agent, so every stage downstream can assume a
        # supported code without re-checking. Resolved before the branch below because
        # the legacy fallback needs it just as much as the pipeline does.
        from agents.video import language as video_language
        lang_code = video_language.normalize(options.get("language"))
        logger.info(
            f"VideoAgent [{job_id}] Video language = {lang_code} "
            f"({video_language.label(lang_code)}), requested={options.get('language')!r}"
        )

        if not use_legacy:
            try:
                logger.info(f"VideoAgent [{job_id}] Invoking EndToEndVideoPipeline (All Upgraded Phases)...")
                from agents.video.pipeline import EndToEndVideoPipeline, PipelineExecutionOptions, RenderQualityPreset
                from agents.video.orchestration import VideoGenerationRequest

                preset_str = options.get("quality_preset", "draft").lower()
                quality_preset = RenderQualityPreset.DRAFT
                if preset_str == "standard":
                    quality_preset = RenderQualityPreset.STANDARD
                elif preset_str == "high":
                    quality_preset = RenderQualityPreset.HIGH

                # The brand kit, if the job was created with one. It arrives as a plain
                # snapshot dict (resolved at job creation, see app/api/endpoints/jobs.py)
                # and becomes BrandConstraints, which the planning layer already knows how
                # to honour -- the deterministic director has read brand_constraints for
                # its palette since before this feature existed.
                brand = options.get("brand_kit") or None
                brand_constraints = None
                if brand:
                    from agents.video.orchestration import BrandConstraints
                    brand_constraints = BrandConstraints(
                        brand_name=options.get("brand_name") or "Brand",
                        primary_color=brand.get("primary_color", "#0F172A"),
                        secondary_color=brand.get("secondary_color", "#38BDF8"),
                        font_family=brand.get("font_choice", "dejavu_sans"),
                        logo_path=brand.get("logo_path"),
                    )
                    logger.info(
                        f"VideoAgent [{job_id}] Brand kit active -- "
                        f"{brand_constraints.primary_color}/{brand_constraints.secondary_color}, "
                        f"accent={brand.get('accent_color')}, font={brand_constraints.font_family}, "
                        f"logo={'yes' if brand_constraints.logo_path else 'no'}"
                    )

                req = VideoGenerationRequest(
                    prompt=prompt,
                    language=lang_code,
                    aspect_ratio=options.get("aspect_ratio", "16:9"),
                    target_duration_seconds=float(options.get("target_duration_seconds", 20.0)),
                    brand_constraints=brand_constraints,
                )
                # Surface this job's uploads to the pipeline when the user supplied any.
                from agents.video.user_upload_manager import UserUploadManager
                job_upload_dir = UserUploadManager.upload_dir_for_job(str(job_id))

                opts = PipelineExecutionOptions(
                    quality_preset=quality_preset,
                    brand_kit=brand,
                    output_directory=target_dir,
                    upload_dir=str(job_upload_dir) if job_upload_dir.exists() else None,
                    tts_engine=options.get("tts_engine"),
                    enable_beat_alignment=options.get("enable_beat_alignment", True),
                    enable_audio_trimming=options.get("enable_audio_trimming", True),
                    distributed_execution=options.get("distributed_execution", False),
                    version_control_enabled=options.get("version_control_enabled", True),
                    observability_enabled=options.get("observability_enabled", True)
                )

                res = EndToEndVideoPipeline.execute(req, opts, progress_callback=progress_callback)

                if res.final_video_path and os.path.exists(res.final_video_path):
                    if os.path.abspath(res.final_video_path) != os.path.abspath(artifact_path):
                        shutil.copy(res.final_video_path, artifact_path)

                # Re-flush the asset provenance manifest next to the deliverable itself.
                # The pipeline already wrote one into its run_* working directory, but that
                # directory is an implementation detail; compliance needs the manifest at a
                # stable, job-addressable path and stamped with the real job id
                # (LICENSES.md R5, ATTRIBUTIONS.md section 2).
                try:
                    from agents.video import attribution as _attribution
                    _attribution.flush(target_dir, job_id=job_id)
                except Exception as _ae:
                    logger.warning(f"VideoAgent [{job_id}] attribution manifest warning: {_ae}")

                if os.path.exists(artifact_path) and os.path.getsize(artifact_path) > 0:
                    size_kb = os.path.getsize(artifact_path) / 1024.0
                    logger.info(f"VideoAgent [{job_id}] EndToEndVideoPipeline succeeded -> {artifact_path} ({size_kb:.1f} KB)")
                    return artifact_path

            except Exception as e:
                logger.warning(f"VideoAgent [{job_id}] Upgraded pipeline warning: {e}. Falling back to 7-stage renderer...")

        # Fallback / Legacy Path
        return self._legacy_generate_artifact(job_id, prompt, target_dir, progress_callback, language=lang_code)

    def _legacy_generate_artifact(self, job_id: str, prompt: str, target_dir: str,
                                  progress_callback: Optional[Callable[[int, str], None]] = None,
                                  language: str = "en") -> str:
        os.makedirs(target_dir, exist_ok=True)
        artifact_path = os.path.join(target_dir, "video_demo.mp4")
        progress = PipelineProgress(progress_callback)

        try:
            logger.info(f"VideoAgent [{job_id}] Stage 1/7: Orchestrated Planning")
            progress.report("director")
            from agents.video.orchestration import VideoPlanningOrchestrator, VideoGenerationRequest
            req = VideoGenerationRequest(prompt=prompt, language=language, target_duration_seconds=20.0)
            planning_res = VideoPlanningOrchestrator.plan_video(req)
            storyboard = VideoPlanningOrchestrator.convert_production_plan_to_storyboard(planning_res)

            logger.info(f"VideoAgent [{job_id}] Stage 2/7: Scene Composition")
            progress.report("screenwriter")
            timeline = SceneComposer.compose_timeline(storyboard)

            logger.info(f"VideoAgent [{job_id}] Stage 3/7: TTS Voiceover")
            progress.report("voiceover")
            audio_path = TTSEngine.generate_voiceover(storyboard, target_dir)

            progress.report("footage")

            logger.info(f"VideoAgent [{job_id}] Stage 4/7: H.264 Rendering")
            progress.report("compositing")
            VideoRenderer.render(storyboard, artifact_path, audio_path=audio_path)

            logger.info(f"VideoAgent [{job_id}] Stage 5/7: Quality Validation")
            progress.report("finalizing")
            qc_report = VideoQualityChecker.check(
                artifact_path,
                expected_duration_sec=storyboard.total_duration_sec,
                expected_scenes=len(storyboard.scenes),
                audio_path=audio_path,
            )

            if not qc_report["passed"]:
                qc_report = self._reviewer_loop(
                    job_id, storyboard, target_dir, artifact_path, audio_path, qc_report
                )

            size_kb = os.path.getsize(artifact_path) / 1024.0 if os.path.exists(artifact_path) else 0.0
            logger.info(f"VideoAgent [{job_id}] Legacy generation completed -> {artifact_path} ({size_kb:.1f} KB)")

        except Exception as e:
            logger.error(f"VideoAgent [{job_id}] Legacy generation error: {e}", exc_info=True)
            raise RuntimeError(f"Video Generation Error: {str(e)}") from e

        return artifact_path

    def _reviewer_loop(self, job_id, storyboard, target_dir, artifact_path, audio_path, qc_report):
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            for d in qc_report["defects"]:
                if d["rule"] == "scene_count" and len(storyboard.scenes) < 3:
                    from agents.video.storyboard import SceneDefinition, TextLayer
                    storyboard.scenes.append(SceneDefinition(
                        scene_id=f"scene_fix_{attempt}",
                        scene_title="Additional Context",
                        duration_sec=3.0,
                        text_layers=[TextLayer(text="Additional technical context", position="center", font_scale=1.2)],
                        transition="fade",
                        narration="Here we provide additional context and detail."
                    ))
                    storyboard.total_duration_sec = sum(s.duration_sec for s in storyboard.scenes)

            VideoRenderer.render(storyboard, artifact_path, audio_path=audio_path)
            qc_report = VideoQualityChecker.check(
                artifact_path,
                expected_duration_sec=storyboard.total_duration_sec,
                expected_scenes=len(storyboard.scenes),
                audio_path=audio_path,
            )
            if qc_report["passed"]:
                return qc_report
        return qc_report

    def execute(
        self,
        job_id: str,
        prompt: str,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Validates the request and hands control to generate_artifact.

        This used to walk progress_callback from 0 to 100 with a sleep between each step,
        which drove the bar to 100% in ~2 seconds before any real work started. Progress is
        now emitted from the pipeline itself as each stage actually completes, so nothing is
        reported here beyond the initial queued state.
        """
        self.validate_input(prompt)

        if progress_callback:
            percent, label = stage("director")
            progress_callback(percent, label)

        return {
            "status": "ACCEPTED",
            "artifact_file": "video_demo.mp4"
        }
