"""
Video AI Overlay Generator for CreateFlow AI.

Generates AI B-roll visual overlays, kinetic frame cards, and lower third graphics for VideoAgent.
"""
import os
import uuid
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont


class VideoAIOverlayGenerator:
    """
    AI Overlay Generator for VideoAgent scenes.
    """

    @classmethod
    def generate_broll_card(
        cls,
        title_text: str,
        subtitle_text: str = "",
        width: int = 1280,
        height: int = 720,
        output_dir: str = "./storage/video_assets"
    ) -> str:
        os.makedirs(output_dir, exist_ok=True)
        asset_id = f"broll_{uuid.uuid4().hex[:8]}.png"
        output_path = os.path.join(output_dir, asset_id)

        # Transparent overlay base
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Dark sleek card container
        card_rect = [100, 100, width - 100, height - 100]
        draw.rounded_rectangle(card_rect, radius=20, fill=(15, 23, 42, 230), outline=(56, 189, 248, 255), width=3)

        img.save(output_path, "PNG")
        return output_path
