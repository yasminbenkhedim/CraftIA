"""
Domain Palette Engine v1 (Domain-Aware Color Palette & Background Generator)
Selects topic-tailored background color gradients based on prompt text,
scene titles, and screenplay metadata.
"""
import re
import logging
from typing import Dict, Any, Tuple, List

logger = logging.getLogger("uvicorn")


class DomainPaletteEngine:
    """
    Domain-Aware Color Palette & Background Diversity Engine.
    Maps topic domain signals to curated BGR color gradient tuples.
    """

    PALETTES: Dict[str, Dict[str, Any]] = {
        "financial_tech": {
            "top_color": (40, 30, 15),       # #0F1E28 Deep Emerald Navy
            "bottom_color": (20, 15, 5),     # #050F14
            "accent_color": (180, 200, 40),  # #28C8B4 Teal Emerald
            "hex_top": "#0F1E28",
            "hex_bottom": "#050F14",
            "keywords": ["finance", "tech", "economic", "economy", "growth", "infrastructure", "ai", "market", "stock", "trading", "crypto", "blockchain", "financial"]
        },
        "educational_science": {
            "top_color": (55, 30, 15),       # #0F1E37 Deep Indigo
            "bottom_color": (30, 10, 10),     # #0A0A1E
            "accent_color": (255, 180, 50),  # #32B4FF Cyan Blue
            "hex_top": "#0F1E37",
            "hex_bottom": "#0A0A1E",
            "keywords": ["quantum", "physics", "computing", "qubit", "entanglement", "science", "stem", "research", "space", "astronomy", "atom", "molecule", "lab", "educational"]
        },
        "news_city": {
            "top_color": (25, 20, 45),       # #2D1419 Dark Amber Slate
            "bottom_color": (10, 10, 25),     # #190A0A
            "accent_color": (40, 140, 250),  # #FA8C28 Amber Dusk
            "hex_top": "#2D1419",
            "hex_bottom": "#190A0A",
            "keywords": ["city", "skyline", "metropolitan", "dusk", "urban", "news", "breaking", "downtown", "traffic", "building", "skyscraper"]
        },
        "nature_environment": {
            "top_color": (20, 45, 20),       # #142D14 Deep Forest Green
            "bottom_color": (10, 25, 10),     # #0A190A
            "accent_color": (50, 220, 120),  # #78DC32 Leaf Green
            "hex_top": "#142D14",
            "hex_bottom": "#0A190A",
            "keywords": ["nature", "forest", "environment", "ecology", "green", "agriculture", "climate", "ocean", "river", "mountain", "wildlife", "earth"]
        },
        "corporate_business": {
            "top_color": (50, 35, 20),       # #142332 Slate Sapphire
            "bottom_color": (25, 15, 10),     # #0A0F19
            "accent_color": (240, 160, 50),  # #32A0F0 Royal Blue
            "hex_top": "#142332",
            "hex_bottom": "#0A0F19",
            "keywords": ["business", "corporate", "strategy", "enterprise", "marketing", "leadership", "management", "startup", "office", "executive"]
        },
        "default_slate": {
            "top_color": (42, 23, 15),       # #0F172A Slate Dark Blue
            "bottom_color": (20, 10, 5),      # #050A14
            "accent_color": (246, 130, 59),  # #3B82F6 Standard Slate
            "hex_top": "#0F172A",
            "hex_bottom": "#050A14",
            "keywords": []
        }
    }

    @classmethod
    def infer_domain(cls, text_signal: str) -> Tuple[str, Dict[str, Any]]:
        """
        Infers the domain palette from prompt / scene metadata text.
        Returns tuple of (domain_key, palette_dict).
        Falls back cleanly to 'default_slate' if no confident keyword match is found.
        """
        if not text_signal or not isinstance(text_signal, str):
            logger.info("DomainPaletteEngine: Empty text signal -> fallback to 'default_slate'")
            return "default_slate", cls.PALETTES["default_slate"]

        text_lower = text_signal.lower()

        for key, palette in cls.PALETTES.items():
            if key == "default_slate":
                continue
            for kw in palette["keywords"]:
                if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                    logger.info(f"DomainPaletteEngine: Matched keyword '{kw}' -> Classified as '{key}' palette (Top Hex: {palette['hex_top']})")
                    return key, palette

        logger.info(f"DomainPaletteEngine: No domain keywords matched for '{text_signal[:50]}...' -> Fallback to 'default_slate' (Top Hex: {cls.PALETTES['default_slate']['hex_top']})")
        return "default_slate", cls.PALETTES["default_slate"]
