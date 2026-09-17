"""
Local ComfyUI Generative Provider for CraftAI Master Remix Architecture.

Interfaces headlessly with ComfyUI REST/WebSocket API (default: http://127.0.0.1:8188)
for local GPU-accelerated image synthesis (FLUX.1-schnell, SDXL) and video motion (AnimateDiff).

Real generation flow:
  1. POST the FLUX workflow graph to /prompt (queues the job).
  2. Poll /history/{prompt_id} until the job completes and reports output images.
  3. Download the produced image via /view and cache it on disk.
  4. Only if any of these steps fail/time out do we fall back to a clearly-labelled
     procedural placeholder (is_placeholder=True).
"""
import os
import json
import time
import urllib.parse
import urllib.request
import urllib.error
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Set

from agents.video.providers.base import (
    MediaProvider,
    MediaRequest,
    MediaCandidate,
    MediaCandidateStatus,
    MediaType,
    ProviderCapabilities,
    ProviderHealth,
    ProviderSelectionProfile
)

logger = logging.getLogger("uvicorn")

# ── Configurable runtime tuning (via environment) ──────────────────────────────
COMFYUI_STEPS = int(os.environ.get("COMFYUI_STEPS", "4"))          # FLUX.1-schnell => 4 steps
COMFYUI_CFG = float(os.environ.get("COMFYUI_CFG", "1.0"))
COMFYUI_SEED = int(os.environ.get("COMFYUI_SEED", "42"))
COMFYUI_UNET = os.environ.get("COMFYUI_UNET_NAME", "flux1-schnell-fp8.safetensors")
COMFYUI_CLIP1 = os.environ.get("COMFYUI_CLIP_NAME1", "t5xxl_fp8_e4m3fn.safetensors")
COMFYUI_CLIP2 = os.environ.get("COMFYUI_CLIP_NAME2", "clip_l.safetensors")
COMFYUI_VAE = os.environ.get("COMFYUI_VAE_NAME", "ae.safetensors")
COMFYUI_DISPATCH_TIMEOUT = float(os.environ.get("COMFYUI_DISPATCH_TIMEOUT", "10"))
COMFYUI_POLL_TIMEOUT = float(os.environ.get("COMFYUI_POLL_TIMEOUT", "120"))   # max wait for the image
COMFYUI_POLL_INTERVAL = float(os.environ.get("COMFYUI_POLL_INTERVAL", "1.5"))
COMFYUI_DOWNLOAD_TIMEOUT = float(os.environ.get("COMFYUI_DOWNLOAD_TIMEOUT", "30"))


class ComfyUIGenerativeProvider(MediaProvider):
    """
    Local GPU Generative Provider interfacing with ComfyUI headless API.
    Provides 100% free local image and motion synthesis on a local GPU (e.g. RTX 4050).
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8188):
        self._provider_id = "local_comfyui_generative"
        self.host = os.environ.get("COMFYUI_HOST", host)
        self.port = int(os.environ.get("COMFYUI_PORT", str(port)))
        self.base_url = f"http://{self.host}:{self.port}"

        # Cache directory for generated local assets
        self.cache_dir = Path(__file__).resolve().parent.parent.parent.parent / "storage" / "comfyui_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def provider_id(self) -> str:
        return self._provider_id

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            media_types={MediaType.GENERATED_IMAGE, MediaType.GENERATED_VIDEO},
            supported_aspect_ratios={"16:9", "9:16", "1:1"},
            supports_duration_control=True,
            supports_seed=True,
            supports_style_reference=True,
            supports_image_reference=True,
            supports_character_reference=True,
            supports_palette_control=True,
            supports_camera_control=True,
            supports_motion_control=True,
            requires_network=False,
            requires_api_key=False,
            supports_offline=True,
            returns_attribution=False
        )

    def readiness(self) -> ProviderHealth:
        """Probes local ComfyUI API /system_stats endpoint."""
        try:
            req = urllib.request.Request(f"{self.base_url}/system_stats", headers={"User-Agent": "CraftAI-Agent"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    return ProviderHealth(
                        available=True,
                        configuration_ready=True,
                        rolling_success_rate=1.0,
                        rolling_average_latency_sec=3.5,
                        temporary_penalty=0.0
                    )
        except Exception:
            pass

        # Available as offline fallback provider if ComfyUI service is starting up
        return ProviderHealth(
            available=True,
            configuration_ready=False,
            rolling_success_rate=0.8,
            rolling_average_latency_sec=4.0,
            temporary_penalty=0.1
        )

    def estimate_cost(self, request: MediaRequest) -> float:
        """100% Free Local GPU Generation."""
        return 0.0

    def estimate_latency(self, request: MediaRequest) -> float:
        """Local GPU Latency: ~3.5 seconds per scene for FLUX fp8."""
        return 3.5

    def generate_or_retrieve(self, request: MediaRequest) -> MediaCandidate:
        health = self.readiness()

        # If ComfyUI live daemon is online, execute a real workflow API call
        if health.configuration_ready:
            try:
                candidate = self._execute_comfy_workflow(request)
                if candidate:
                    return candidate
                logger.warning(
                    "ComfyUIGenerativeProvider: Workflow produced no image for scene "
                    f"'{request.scene_id}'. Falling back to procedural placeholder."
                )
            except Exception as e:
                logger.warning(
                    f"ComfyUIGenerativeProvider: Live workflow execution failed ({e}). "
                    "Falling back to procedural placeholder."
                )

        # Standalone / Offline procedural local synthesis fallback
        return self._generate_local_procedural_fallback(request)

    # ──────────────────────────────────────────────────────────────────────────
    # Real ComfyUI generation
    # ──────────────────────────────────────────────────────────────────────────
    def _build_flux_workflow(self, request: MediaRequest) -> Dict[str, Any]:
        """
        Builds a complete, executable FLUX.1-schnell workflow graph.

        The previous implementation was missing the CLIP loader, VAE loader,
        VAEDecode and SaveImage nodes, so ComfyUI could never emit an image.
        This graph is self-contained and terminates in a SaveImage node whose
        output we can retrieve from /history.
        """
        positive_prompt = f"cinematic high quality photorealistic 8k, {request.query}"
        return {
            # Diffusion model (UNET) loader
            "4": {
                "inputs": {"unet_name": COMFYUI_UNET, "weight_dtype": "fp8_e4m3fn"},
                "class_type": "UNETLoader"
            },
            # Dual CLIP loader required by FLUX (t5xxl + clip_l)
            "11": {
                "inputs": {
                    "clip_name1": COMFYUI_CLIP1,
                    "clip_name2": COMFYUI_CLIP2,
                    "type": "flux"
                },
                "class_type": "DualCLIPLoader"
            },
            # VAE loader for decoding the latent back to pixels
            "10": {
                "inputs": {"vae_name": COMFYUI_VAE},
                "class_type": "VAELoader"
            },
            # Positive conditioning
            "6": {
                "inputs": {"text": positive_prompt, "clip": ["11", 0]},
                "class_type": "CLIPTextEncode"
            },
            # Negative conditioning (unused by schnell but kept for graph validity)
            "7": {
                "inputs": {"text": "blurry, low quality, distortion, noise", "clip": ["11", 0]},
                "class_type": "CLIPTextEncode"
            },
            # Empty latent canvas at requested resolution
            "5": {
                "inputs": {
                    "width": request.target_width,
                    "height": request.target_height,
                    "batch_size": 1
                },
                "class_type": "EmptyLatentImage"
            },
            # Sampler
            "3": {
                "inputs": {
                    "seed": COMFYUI_SEED,
                    "steps": COMFYUI_STEPS,
                    "cfg": COMFYUI_CFG,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0]
                },
                "class_type": "KSampler"
            },
            # Decode latent -> image
            "8": {
                "inputs": {"samples": ["3", 0], "vae": ["10", 0]},
                "class_type": "VAEDecode"
            },
            # Persist the image so it appears in /history outputs
            "9": {
                "inputs": {"filename_prefix": f"craftai_{request.scene_id}", "images": ["8", 0]},
                "class_type": "SaveImage"
            }
        }

    def _queue_prompt(self, workflow: Dict[str, Any]) -> Optional[str]:
        """Queues the workflow and returns the ComfyUI prompt_id."""
        payload = json.dumps({"prompt": workflow}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/prompt",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "CraftAI-Agent"}
        )
        with urllib.request.urlopen(req, timeout=COMFYUI_DISPATCH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI returned no prompt_id (response: {data})")
        return prompt_id

    def _poll_for_output(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """
        Polls /history/{prompt_id} until the job completes and returns the first
        image descriptor {filename, subfolder, type}, or None on timeout.
        """
        deadline = time.time() + COMFYUI_POLL_TIMEOUT
        history_url = f"{self.base_url}/history/{prompt_id}"

        while time.time() < deadline:
            try:
                req = urllib.request.Request(history_url, headers={"User-Agent": "CraftAI-Agent"})
                with urllib.request.urlopen(req, timeout=COMFYUI_DISPATCH_TIMEOUT) as resp:
                    history = json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                logger.debug(f"ComfyUIGenerativeProvider: history poll transient error ({e}).")
                time.sleep(COMFYUI_POLL_INTERVAL)
                continue

            entry = history.get(prompt_id)
            if entry:
                outputs = entry.get("outputs", {})
                for node_output in outputs.values():
                    images = node_output.get("images") or []
                    for image in images:
                        if image.get("filename"):
                            return image
                # Job finished but produced no image node
                if entry.get("status", {}).get("completed") is True:
                    return None

            time.sleep(COMFYUI_POLL_INTERVAL)

        logger.warning(
            f"ComfyUIGenerativeProvider: Timed out after {COMFYUI_POLL_TIMEOUT}s "
            f"waiting for prompt {prompt_id}."
        )
        return None

    def _download_image(self, image_desc: Dict[str, Any], out_path: Path) -> bool:
        """Downloads a generated image from /view into out_path."""
        params = urllib.parse.urlencode({
            "filename": image_desc.get("filename", ""),
            "subfolder": image_desc.get("subfolder", ""),
            "type": image_desc.get("type", "output")
        })
        view_url = f"{self.base_url}/view?{params}"
        req = urllib.request.Request(view_url, headers={"User-Agent": "CraftAI-Agent"})
        with urllib.request.urlopen(req, timeout=COMFYUI_DOWNLOAD_TIMEOUT) as resp:
            data = resp.read()
        if not data:
            return False
        out_path.write_bytes(data)
        return out_path.exists() and out_path.stat().st_size > 0

    def _execute_comfy_workflow(self, request: MediaRequest) -> Optional[MediaCandidate]:
        """Dispatches the FLUX workflow, waits for completion, and downloads the real image."""
        workflow = self._build_flux_workflow(request)
        prompt_id = self._queue_prompt(workflow)
        logger.info(f"ComfyUIGenerativeProvider: Dispatched prompt {prompt_id} to local ComfyUI.")

        image_desc = self._poll_for_output(prompt_id)
        if not image_desc:
            return None  # caller will fall back to procedural placeholder

        out_path = self.cache_dir / f"comfy_{request.scene_id}.png"
        if not self._download_image(image_desc, out_path):
            logger.warning(
                f"ComfyUIGenerativeProvider: Failed to download image for prompt {prompt_id}."
            )
            return None

        logger.info(
            f"ComfyUIGenerativeProvider: Retrieved real FLUX image -> {out_path} "
            f"(prompt {prompt_id})."
        )
        return MediaCandidate(
            provider_id=self.provider_id,
            media_type=MediaType.GENERATED_IMAGE,
            asset_path=str(out_path),
            width=request.target_width,
            height=request.target_height,
            duration=request.minimum_duration or 4.0,
            candidate_status=MediaCandidateStatus.VALIDATED_RENDER_READY,
            generation_method="ai_image_synthesis",
            generation_metadata={
                "source": "comfyui_api",
                "model": COMFYUI_UNET,
                "prompt_id": prompt_id,
                "query": request.query,
                "cost_usd": 0.0,
                "is_placeholder": False
            }
        )

    def _generate_local_procedural_fallback(self, request: MediaRequest) -> MediaCandidate:
        out_path = self.cache_dir / f"procedural_{request.scene_id}.png"
        self._create_procedural_broll(request, str(out_path))

        return MediaCandidate(
            provider_id=self.provider_id,
            media_type=MediaType.GENERATED_IMAGE,
            asset_path=str(out_path),
            width=request.target_width,
            height=request.target_height,
            duration=request.minimum_duration or 4.0,
            candidate_status=MediaCandidateStatus.VALIDATED_RENDER_READY,
            generation_method="procedural",
            generation_metadata={
                "source": "comfyui_offline_procedural",
                "query": request.query,
                "cost_usd": 0.0,
                "is_placeholder": True
            }
        )

    def _create_procedural_broll(self, request: MediaRequest, out_path: str):
        import cv2
        import numpy as np
        w, h = request.target_width, request.target_height
        img = np.zeros((h, w, 3), dtype=np.uint8)

        # Deep cinematic gradient background
        for y in range(h):
            r = int(15 + (40 * y / h))
            g = int(23 + (60 * y / h))
            b = int(42 + (90 * y / h))
            img[y, :] = (b, g, r)

        # Draw visual prompt text overlay
        cv2.putText(img, "CRAFTAI LOCAL GENERATIVE ENGINE", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 215, 255), 2)
        cv2.putText(img, f"Scene: {request.scene_id}", (50, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        query_text = request.query[:50] + "..." if len(request.query) > 50 else request.query
        cv2.putText(img, f"Prompt: {query_text}", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)

        cv2.imwrite(out_path, img)
