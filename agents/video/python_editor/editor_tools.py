"""
Dynamic Video Transformations and FX Compositing Tools for VideoAgent.
"""
import numpy as np


class EditorTools:
    """
    Dynamic frame transformations and video editor tools.
    """

    @staticmethod
    def apply_zoom_punch_in(frame: np.ndarray, zoom_factor: float = 1.15) -> np.ndarray:
        """
        Applies a smooth digital zoom punch-in to a video frame.
        """
        if zoom_factor <= 1.0 or frame is None or frame.ndim < 3:
            return frame

        h, w, _ = frame.shape
        new_h, new_w = int(h / zoom_factor), int(w / zoom_factor)
        top = (h - new_h) // 2
        left = (w - new_w) // 2

        cropped = frame[top:top + new_h, left:left + new_w]

        try:
            import cv2
            return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
        except ImportError:
            # Fallback PIL resize if OpenCV is unavailable
            from PIL import Image
            img = Image.fromarray(cropped)
            resized = img.resize((w, h), Image.Resampling.BILINEAR)
            return np.array(resized)
