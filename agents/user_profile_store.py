"""
User Customization Profile & Preference Store.

Manages persistent user preferences (presentation theme, default voice language, LaTeX document class) across content generation requests.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class UserCustomizationProfile(BaseModel):
    user_id: str
    default_presentation_theme: str = "corporate_navy"
    default_voice_language: str = "en"
    default_voice_gender: str = "female"
    default_report_class: str = "report"
    preferences: Dict[str, Any] = Field(default_factory=dict)


class UserProfileStore:
    """
    In-memory / Persistent User Profile Store.
    """
    _profiles: Dict[str, UserCustomizationProfile] = {}

    @classmethod
    def set_profile(cls, profile: UserCustomizationProfile):
        cls._profiles[profile.user_id] = profile

    @classmethod
    def get_profile(cls, user_id: str) -> UserCustomizationProfile:
        if user_id in cls._profiles:
            return cls._profiles[user_id]
        # Default profile
        return UserCustomizationProfile(user_id=user_id)
