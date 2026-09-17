"""
Cinematic 3D Color Grading Engine v1.0.
Provides professional color grading, Lut simulation, tone mapping, and contrast curves
for commercial-grade AI video generation.
"""
import cv2
import numpy as np
from typing import Dict, Tuple, Optional


class ColorGradingEngine:
    """
    Applies professional cinematic color grading profiles to video frames in BGR space.
    """

    PROFILES = {
        "teal_orange": {
            "name": "Cinematic Teal & Orange",
            "shadow_color": np.array([120, 80, 20], dtype=np.float32),   # Teal in BGR
            "highlight_color": np.array([30, 140, 240], dtype=np.float32), # Orange in BGR
            "contrast": 1.15,
            "saturation": 1.12,
            "gamma": 0.95
        },
        "cyberpunk_neon": {
            "name": "Cyberpunk Neon",
            "shadow_color": np.array([160, 40, 90], dtype=np.float32),   # Deep Purple/Blue
            "highlight_color": np.array([220, 60, 255], dtype=np.float32),# Neon Magenta/Pink
            "contrast": 1.22,
            "saturation": 1.25,
            "gamma": 0.90
        },
        "crisp_tech": {
            "name": "Crisp High-Tech",
            "shadow_color": np.array([60, 40, 20], dtype=np.float32),    # Cool Navy
            "highlight_color": np.array([245, 235, 220], dtype=np.float32),# Crisp Clean White
            "contrast": 1.10,
            "saturation": 1.05,
            "gamma": 1.0
        },
        "medical_pristine": {
            "name": "Medical & Clinical Pristine",
            "shadow_color": np.array([70, 60, 30], dtype=np.float32),    # Subtle Teal/Cyan
            "highlight_color": np.array([255, 250, 245], dtype=np.float32),# Clean White
            "contrast": 1.08,
            "saturation": 1.02,
            "gamma": 1.02
        },
        "documentary_organic": {
            "name": "Documentary Organic",
            "shadow_color": np.array([30, 45, 40], dtype=np.float32),    # Earthy Olive/Brown
            "highlight_color": np.array([40, 180, 240], dtype=np.float32), # Golden Sun
            "contrast": 1.06,
            "saturation": 1.04,
            "gamma": 0.98
        },
        "warm_sunset": {
            "name": "Warm Sunset",
            "shadow_color": np.array([20, 40, 80], dtype=np.float32),    # Warm Amber
            "highlight_color": np.array([40, 160, 250], dtype=np.float32), # Deep Gold
            "contrast": 1.12,
            "saturation": 1.18,
            "gamma": 0.96
        },
        "marketing_vibrant": {
            "name": "Marketing High Impact",
            "shadow_color": np.array([40, 30, 20], dtype=np.float32),
            "highlight_color": np.array([250, 245, 240], dtype=np.float32),
            "contrast": 1.18,
            "saturation": 1.20,
            "gamma": 0.95
        },
        "film_noir": {
            "name": "Film Noir",
            "shadow_color": np.array([10, 10, 10], dtype=np.float32),
            "highlight_color": np.array([240, 240, 240], dtype=np.float32),
            "contrast": 1.30,
            "saturation": 0.20,  # Desaturated mono
            "gamma": 0.90
        }
    }

    @classmethod
    def apply_grade(
        cls,
        frame: np.ndarray,
        profile_name: str = "crisp_tech",
        strength: float = 0.65
    ) -> np.ndarray:
        """
        Applies non-destructive color grading to input BGR frame.
        """
        if profile_name not in cls.PROFILES:
            profile_name = "crisp_tech"

        prof = cls.PROFILES[profile_name]
        h, w, c = frame.shape

        # Work in float32 for high-precision color transformations
        img_f = frame.astype(np.float32) / 255.0

        # 1. Luminance map
        lum = 0.114 * img_f[:, :, 0] + 0.587 * img_f[:, :, 1] + 0.299 * img_f[:, :, 2]
        lum = np.clip(lum, 0.0, 1.0)[:, :, np.newaxis]

        # 2. Split tones: Shadows (<0.5) and Highlights (>0.5)
        shadow_weight = (1.0 - lum) ** 2
        highlight_weight = lum ** 2

        graded = img_f.copy()

        # Apply shadow and highlight color tinting
        sh_color = prof["shadow_color"] / 255.0
        hi_color = prof["highlight_color"] / 255.0

        graded = graded + (sh_color - graded) * (shadow_weight * 0.25 * strength)
        graded = graded + (hi_color - graded) * (highlight_weight * 0.25 * strength)

        # 3. Contrast Adjustment around midtone (0.5)
        contrast = 1.0 + (prof["contrast"] - 1.0) * strength
        graded = (graded - 0.5) * contrast + 0.5

        # 4. Gamma Correction
        gamma = prof["gamma"]
        if abs(gamma - 1.0) > 0.01:
            graded = np.power(np.maximum(graded, 0.0), gamma)

        # 5. Saturation Adjustment in HSV
        saturation_scale = 1.0 + (prof["saturation"] - 1.0) * strength
        if abs(saturation_scale - 1.0) > 0.01:
            graded_u8 = (np.clip(graded, 0.0, 1.0) * 255.0).astype(np.uint8)
            hsv = cv2.cvtColor(graded_u8, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation_scale, 0, 255)
            graded = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32) / 255.0

        # Blend with original according to strength
        output_f = img_f * (1.0 - strength) + graded * strength
        return (np.clip(output_f, 0.0, 1.0) * 255.0).astype(np.uint8)

    @classmethod
    def infer_profile_from_topic(cls, topic_text: str) -> str:
        """
        Infer optimal color grading profile based on prompt or scene content.
        """
        txt = topic_text.lower()
        if any(k in txt for k in ["medical", "health", "doctor", "hospital", "pharma", "clinical"]):
            return "medical_pristine"
        elif any(k in txt for k in ["tech", "cyber", "ai", "quantum", "software", "data", "cloud", "saas"]):
            return "crisp_tech"
        elif any(k in txt for k in ["neon", "future", "futuristic", "robot", "hacker"]):
            return "cyberpunk_neon"
        elif any(k in txt for k in ["ocean", "sea", "space", "nature", "history", "ancient", "documentary"]):
            return "documentary_organic"
        elif any(k in txt for k in ["car", "sport", "promo", "launch", "marketing", "brand", "product"]):
            return "marketing_vibrant"
        elif any(k in txt for k in ["movie", "cinema", "cinematic", "drama"]):
            return "teal_orange"
        return "crisp_tech"
