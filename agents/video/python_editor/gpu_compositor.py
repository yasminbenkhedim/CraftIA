"""
GPU-Accelerated Frame Compositing & Transformations for VideoAgent.
"""
import numpy as np
import logging
from typing import Dict, Any, Optional, Tuple
from agents.video.python_editor.editor_tools import EditorTools

logger = logging.getLogger("uvicorn")


class GPUCompositor:
    """
    Hardware-accelerated frame compositor leveraging PyTorch / Kornia CUDA tensors with OpenCV CPU fallback.
    """

    _gpu_available: Optional[bool] = None

    @classmethod
    def is_gpu_available(cls) -> bool:
        if cls._gpu_available is None:
            try:
                import torch
                cls._gpu_available = torch.cuda.is_available()
            except ImportError:
                cls._gpu_available = False
        return cls._gpu_available

    @classmethod
    def get_device_report(cls) -> Dict[str, Any]:
        """
        Returns runtime device inspection report.
        """
        try:
            import torch
            torch_ver = torch.__version__
            cuda_avail = torch.cuda.is_available()
            cuda_ver = torch.version.cuda if cuda_avail else None
            gpu_model = torch.cuda.get_device_name(0) if cuda_avail else None
            device_used = "CUDA" if cuda_avail else "CPU (OpenCV Fallback)"
            fallback_reason = None if cuda_avail else "CUDA path implemented but not verified on compatible hardware (torch / CUDA not installed in host environment)."
        except ImportError:
            torch_ver = "not_installed"
            cuda_avail = False
            cuda_ver = None
            gpu_model = None
            device_used = "CPU (OpenCV Fallback)"
            fallback_reason = "PyTorch library not installed in host environment."

        return {
            "device_used": device_used,
            "torch_version": torch_ver,
            "cuda_available": cuda_avail,
            "cuda_version": cuda_ver,
            "gpu_model": gpu_model,
            "fallback_reason": fallback_reason,
            "statement": "CUDA path implemented but not verified on compatible hardware." if not cuda_avail else "GPU accelerated rendering active."
        }

    @classmethod
    def apply_zoom_punch_in(cls, frame: np.ndarray, zoom_factor: float = 1.15, force_gpu: bool = False) -> np.ndarray:
        """
        Applies a zoom punch-in transformation using PyTorch / Kornia GPU acceleration if available.
        """
        if zoom_factor <= 1.0 or frame is None or frame.ndim < 3:
            return frame

        if (force_gpu or cls.is_gpu_available()):
            try:
                import torch
                import kornia.geometry.transform as K
                tensor = torch.from_numpy(frame).permute(2, 0, 1).unsqueeze(0).float() / 255.0
                if cls.is_gpu_available():
                    tensor = tensor.cuda()

                scaled = K.scale(tensor, scale=torch.tensor([[zoom_factor, zoom_factor]], device=tensor.device))
                out_tensor = (scaled.squeeze(0).permute(1, 2, 0) * 255.0).byte().cpu().numpy()
                return out_tensor
            except Exception as e:
                logger.debug(f"GPU transformation fallback to OpenCV CPU: {e}")

        # Fallback to standard OpenCV / PIL EditorTools CPU implementation
        return EditorTools.apply_zoom_punch_in(frame, zoom_factor)

    @classmethod
    def compare_cpu_vs_gpu_output(cls, frame: np.ndarray, zoom_factor: float = 1.15) -> Dict[str, Any]:
        """
        Compares output resolution, aspect ratio, and mean pixel difference between CPU and GPU compositing paths.
        """
        cpu_out = EditorTools.apply_zoom_punch_in(frame, zoom_factor)
        gpu_out = cls.apply_zoom_punch_in(frame, zoom_factor, force_gpu=False)

        pixel_diff = np.mean(np.abs(cpu_out.astype(np.float32) - gpu_out.astype(np.float32)))

        return {
            "input_shape": frame.shape,
            "cpu_output_shape": cpu_out.shape,
            "gpu_output_shape": gpu_out.shape,
            "mean_pixel_difference": round(float(pixel_diff), 4),
            "aspect_ratio_match": (cpu_out.shape[1] / cpu_out.shape[0]) == (gpu_out.shape[1] / gpu_out.shape[0]),
            "resolution_match": cpu_out.shape == gpu_out.shape
        }
