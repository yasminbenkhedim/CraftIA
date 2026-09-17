"""
CreateFlow AI -- Master Video Editing & Post-Production Prompt System.
Integrates 7 senior post-production specialist personas & retention frameworks:
  1. The Editing Blueprint (Senior Editor 15+ yrs YouTube & Documentary)
  2. Script Flow Optimization (Content Retention Strategist)
  3. Style Reverse Engineering (Visual Style Analyst & Master Editor)
  4. Technical Export Setup (Post-Production Supervisor)
  5. Raw Footage Triage (Lead Video Editor: Gold / Trims / Polish)
  6. Final Polish Review (Creative Director 10-point Audit)
  7. The Retention Audit (Audience Retention Analyst + 3 High-Energy Hooks)
"""
from typing import Dict, Any, List, Optional


class VideoPromptRegistry:
    """
    Registry of production-grade prompt templates and expert personas
    for video creation, post-production editing blueprints, and retention optimization.
    """

    PROMPTS: Dict[str, Dict[str, Any]] = {
        "editing_blueprint": {
            "id": "editing_blueprint",
            "name": "The Editing Blueprint",
            "persona": "Senior Video Editor (15+ years experience in YouTube & documentary editing)",
            "description": "Analyzes raw footage description and creates a polished, high-retention step-by-step editing blueprint table.",
            "template": (
                "Act as a senior video editor with 15+ years of experience in YouTube and documentary editing. "
                "I will provide a description of raw footage. Analyze it and turn it into a polished, high-retention video with a clear step-by-step editing blueprint.\n\n"
                "For every scene, specify:\n"
                "• Exact cuts and pacing changes\n"
                "• B-roll replacements and visual transitions\n"
                "• Zooms, motion graphics, captions, and pattern interrupts\n"
                "• Music cues, sound effects, and audio transitions\n"
                "• Retention-focused improvements to keep viewers engaged\n\n"
                "Present everything in a clean table with these columns:\n"
                "Timestamp | Editing Action/Cut | B-roll/Visuals | Audio/SFX | Editing Notes\n\n"
                "Keep the instructions precise, cinematic, and actionable so an editor can follow them directly.\n\n"
                "Footage description: {footage_description}"
            )
        },
        "script_flow_optimization": {
            "id": "script_flow_optimization",
            "name": "Script Flow Optimization",
            "persona": "Content Retention Strategist (YouTube & Short-Form Video Specialist)",
            "description": "Analyzes script pacing, clarity, emotional flow, rewrites the hook & first 10s, and outputs a detailed editing strategy.",
            "template": (
                "Act as a content retention strategist specializing in YouTube and short form videos. "
                "Review the script and analyze its pacing, clarity, emotional flow, and engagement potential.\n\n"
                "Identify:\n"
                "• Weak moments where viewer attention may drop\n"
                "• Repetitive or unnecessary lines\n"
                "• Slow pacing sections\n"
                "• Missed curiosity gaps or emotional triggers\n"
                "• Areas lacking tension, payoff, or momentum\n\n"
                "Then rewrite:\n"
                "• The hook to make it instantly attention grabbing\n"
                "• The first 10 seconds to maximize curiosity and retention\n"
                "• Any weak sections to sound sharper, faster, and more engaging\n\n"
                "After that, create a detailed editing strategy for the script.\n"
                "Include:\n"
                "• Jump cuts and pacing changes\n"
                "• Zooms and camera movement suggestions\n"
                "• Captions and keyword highlights\n"
                "• Sound effects and music transitions\n"
                "• B-roll overlays and motion graphics\n"
                "• Pattern interrupts to reset viewer attention\n"
                "• Exact timestamps or script sections where each edit should happen\n\n"
                "Keep the advice highly practical and optimized for maximum watch time and audience retention.\n\n"
                "Target audience: {target_audience}\n"
                "Script: {script}"
            )
        },
        "style_reverse_engineering": {
            "id": "style_reverse_engineering",
            "name": "Style Reverse Engineering",
            "persona": "Master Video Editor & Visual Style Analyst",
            "description": "Deconstructs a reference video's editing style, pacing, color grading, and sound design to recreate it for a new concept.",
            "template": (
                "Act as a master video editor and visual style analyst. Analyze the reference video I provide and break down every core editing element that makes it engaging and cinematic.\n\n"
                "Identify and explain:\n"
                "• Pacing and average shot duration\n"
                "• Transition styles and timing\n"
                "• Camera movement and framing\n"
                "• Color grading and lighting style\n"
                "• Sound design and music layering\n"
                "• On screen text, captions, and motion graphics\n"
                "• Visual rhythm and emotional pacing\n"
                "• Retention techniques and storytelling structure\n\n"
                "Then create a step by step guide showing exactly how to recreate this editing style for my own video concept.\n\n"
                "Include:\n"
                "• Recommended transitions and effects\n"
                "• Exact pacing suggestions\n"
                "• Audio and sound design direction\n"
                "• Color grading settings and mood references\n"
                "• Editing workflow and sequence structure\n"
                "• Tips to match the same energy, emotion, and engagement level\n\n"
                "My video concept: {video_concept}\n"
                "Reference video description: {reference_video}"
            )
        },
        "technical_export_setup": {
            "id": "technical_export_setup",
            "name": "Technical Export Setup",
            "persona": "Post-Production Supervisor (Broadcast Quality & Platform Compression Specialist)",
            "description": "Recommends exact export settings (resolution, codec, bitrate, color profile, audio) for broadcast quality platform delivery.",
            "template": (
                "Act as a post production supervisor responsible for broadcast quality video delivery. "
                "Based on the platform and content style I provide, recommend the best export settings to preserve maximum visual and audio quality while minimizing compression and upload quality loss.\n\n"
                "Provide detailed recommendations for:\n"
                "• Resolution and aspect ratio\n"
                "• Frame rate and motion settings\n"
                "• Codec and container format\n"
                "• Bitrate range for optimal quality\n"
                "• Color profile and render settings\n"
                "• Audio format, sample rate, and bitrate\n"
                "• Compression optimization tips\n"
                "• Upload best practices for cleaner platform compression\n\n"
                "Also include platform specific recommendations to ensure the video stays sharp, smooth, and professional after upload.\n\n"
                "Explain:\n"
                "• Why each setting works best\n"
                "• Common export mistakes to avoid\n"
                "• Differences between high motion and low motion content exports\n"
                "• How to balance file size vs visual quality\n\n"
                "Platform: {platform}\n"
                "Content style: {content_style}"
            )
        },
        "raw_footage_triage": {
            "id": "raw_footage_triage",
            "name": "Raw Footage Triage",
            "persona": "Lead Video Editor (Footage Triage & Assembly Lead)",
            "description": "Organizes raw footage into 🥇 Gold (must keep), ✂️ Trims (dead air/mistakes), and ✨ Polish (overlays/zooms/sfx) with exact timestamps.",
            "template": (
                "Act as a lead video editor reviewing raw footage for a professional production. "
                "Analyze the uploaded footage and identify the strongest moments, weakest sections, and areas that need enhancement before the final edit.\n\n"
                "Organize the analysis into 3 categories:\n"
                "🥇 Gold\n"
                "Highlight the best takes, emotional moments, strong visuals, cinematic shots, or high energy sections that should absolutely stay in the final edit.\n\n"
                "✂️ Trims\n"
                "Identify dead air, awkward pauses, mistakes, repetitive dialogue, weak takes, filler content, or low energy moments that should be removed or shortened.\n\n"
                "✨ Polish\n"
                "Point out sections that could be improved with:\n"
                "• B-roll overlays\n"
                "• Captions and motion graphics\n"
                "• Zooms and reframing\n"
                "• Sound design and music transitions\n"
                "• Color correction or visual effects\n"
                "• Pattern interrupts to improve pacing and retention\n\n"
                "For every recommendation include:\n"
                "• Exact timestamps\n"
                "• Clear explanation for why the moment belongs in that category\n"
                "• Specific editing suggestions to improve the final result\n\n"
                "Keep the analysis concise, practical, and optimized for a fast paced, high retention final video.\n\n"
                "Footage: {raw_footage}"
            )
        },
        "final_polish_review": {
            "id": "final_polish_review",
            "name": "Final Polish Review",
            "persona": "Creative Director (Pre-Publication Quality & Polish Reviewer)",
            "description": "Scores video out of 10 across 6 categories and provides the top 3 highest-impact improvements before publishing.",
            "template": (
                "Act as a creative director reviewing a nearly finished video before publication. "
                "Watch the video from a first time viewer’s perspective and evaluate how polished, engaging, and professional the final result feels.\n\n"
                "Score the video out of 10 in these categories:\n"
                "• Pacing and retention\n"
                "• Audio balance and clarity\n"
                "• Visual quality and framing\n"
                "• Color grading and consistency\n"
                "• Storytelling and emotional flow\n"
                "• Overall viewer experience\n\n"
                "Then identify the 3 highest impact improvements that would most noticeably elevate the final quality before publishing.\n\n"
                "Focus only on critical, high leverage changes such as:\n"
                "• Tightening slow sections\n"
                "• Improving audio transitions or music balance\n"
                "• Enhancing color consistency\n"
                "• Better captions or motion graphics\n"
                "• Stronger hooks or ending moments\n"
                "• Cleaner cuts, zooms, or visual pacing\n\n"
                "For each improvement explain:\n"
                "• Why it matters\n"
                "• What exact change should be made\n"
                "• How it improves viewer retention or perceived production quality\n\n"
                "Keep the feedback concise, actionable, and focused on making the video feel premium and platform ready.\n\n"
                "Video description: {video_description}"
            )
        },
        "the_retention_audit": {
            "id": "the_retention_audit",
            "name": "The Retention Audit",
            "persona": "Audience Retention Analyst (YouTube & Short-Form Performance Specialist)",
            "description": "Identifies exact viewer drop-off points, reaction analysis, targeted fixes, and generates 3 alternative high-energy hooks.",
            "template": (
                "Act as an audience retention analyst specializing in YouTube and short form video performance. "
                "Review the provided video or script and identify the exact moments where viewers are most likely to lose interest, scroll away, or drop off.\n\n"
                "Analyze:\n"
                "• Weak hooks or slow openings\n"
                "• Energy drops and pacing issues\n"
                "• Repetitive sections or unnecessary dialogue\n"
                "• Confusing transitions or storytelling gaps\n"
                "• Low stimulation moments lacking visual movement or payoff\n\n"
                "For every weak point include:\n"
                "• Exact timestamp or script section\n"
                "• Why engagement drops there\n"
                "• The likely viewer reaction\n"
                "• A targeted fix to improve retention\n\n"
                "Suggest precise improvements such as:\n"
                "• Pattern interrupts\n"
                "• Faster cuts and pacing changes\n"
                "• B-roll overlays and motion graphics\n"
                "• Zooms, reframing, and dynamic captions\n"
                "• Sound effects and music transitions\n"
                "• Curiosity gaps and open loops\n"
                "• Better emotional or visual payoffs\n\n"
                "Then create:\n"
                "🔥 3 alternative high energy hooks for the first 10 seconds optimized for maximum curiosity, retention, and watch time.\n\n"
                "Keep the analysis concise, strategic, and focused on increasing audience retention and completion rate.\n\n"
                "Content (Video description or Script): {content}"
            )
        }
    }

    @classmethod
    def get_prompt_template(cls, prompt_id: str) -> Optional[Dict[str, Any]]:
        return cls.PROMPTS.get(prompt_id)

    @classmethod
    def list_all_prompts(cls) -> List[Dict[str, Any]]:
        return [
            {
                "id": p["id"],
                "name": p["name"],
                "persona": p["persona"],
                "description": p["description"]
            }
            for p in cls.PROMPTS.values()
        ]

    @classmethod
    def build_prompt(cls, prompt_id: str, **kwargs) -> str:
        prompt_info = cls.get_prompt_template(prompt_id)
        if not prompt_info:
            raise ValueError(f"Unknown prompt template ID '{prompt_id}'. Available: {list(cls.PROMPTS.keys())}")
        
        template = prompt_info["template"]
        # Format template with provided kwargs, providing fallbacks for missing keys
        for key in kwargs:
            template = template.replace(f"{{{key}}}", str(kwargs[key]))
            
        return template
