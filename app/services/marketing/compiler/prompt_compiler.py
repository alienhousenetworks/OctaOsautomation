"""Deterministic Media Prompt Compiler.

Workstream C:
- Translates structured CreativeIntentJSON into target-specific syntax
- Custom templates for Midjourney v6.1, FLUX.1, DALL-E 3, Google Imagen 3, and Pika/Veo/Runway
- Enforces anti-samey lexicon sampling and strict negative constraint handling
"""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from app.services.marketing.compiler.lexicon import (
    sample_lexicon,
    TARGET_NEGATIVE_PROMPTS,
)


class CreativeIntentJSON(BaseModel):
    """Structured creative intent emitted by small LLM."""
    subject: str = Field(..., description="Primary focal subject or physical product")
    action_or_state: str = Field(..., description="Action, posture, or interaction occurring")
    environment_setting: str = Field(..., description="Physical backdrop, architectural context")
    emotional_mood: str = Field(..., description="Tonal atmosphere (e.g., contemplative, energetic, rigorous)")
    shot_type: str = Field("medium shot", description="Camera framing: macro, low-angle wide, eye-level medium, Dutch angle")
    lighting_intent: str = Field("soft diffused key light", description="Lighting setup description")
    negative_space_direction: str = Field("balanced", description="top, bottom, left_40pct, right_40pct, centered")
    brand_style_id: Optional[str] = Field(None, description="UUID or token identifier from Brand Kit")
    color_accents: List[str] = Field(default_factory=list, description="Specific hex or color tokens")


class VideoShotPlan(BaseModel):
    """Structured video shot specification."""
    scene_description: str
    duration_seconds: int = 5
    camera_movement: str = "slow cinematic dolly forward at 0.5m/s"
    focal_motion: str = "subject subtly turns gaze toward window"
    atmosphere_notes: str = "subtle ambient dust motes catching backlighting"
    aspect_ratio: str = "16:9"


class MediaPromptCompiler:
    """Deterministic compiler transforming CreativeIntentJSON into target-specific media prompts."""

    @staticmethod
    def get_aspect_ratio_for_platform(platform: str, media_type: str = "image") -> str:
        p = platform.lower()
        if media_type == "video":
            if p in ("reels", "tiktok", "shorts", "instagram_story"):
                return "9:16"
            return "16:9"
        
        # Image aspect ratios
        if p in ("instagram", "instagram_feed"):
            return "1:1"
        elif p in ("reels", "stories", "story"):
            return "9:16"
        elif p in ("linkedin", "twitter", "x", "facebook"):
            return "16:9"
        return "1:1"

    @classmethod
    def compile_midjourney(
        cls,
        intent: CreativeIntentJSON,
        visual_style: Optional[Dict[str, Any]] = None,
        seed_key: str = "default_seed",
        platform: str = "instagram",
    ) -> str:
        """Compile intent for Midjourney v6.1 syntax."""
        lexicon = sample_lexicon(seed_key)
        cam = lexicon["camera"]
        lighting = lexicon["lighting"]
        film = lexicon["film"]
        arch = lexicon["architecture"]
        ar = cls.get_aspect_ratio_for_platform(platform, media_type="image")

        colors = ", ".join(intent.color_accents) if intent.color_accents else "curated brand tones"
        neg_space = f"with {intent.negative_space_direction.replace('_', ' ')} for clean negative space" if intent.negative_space_direction != "balanced" else ""

        # Compose photographic Midjourney prompt
        prompt_parts = [
            f"{intent.shot_type} of {intent.subject}, {intent.action_or_state}",
            f"set within {intent.environment_setting or arch}",
            f"atmosphere is {intent.emotional_mood}",
            f"lighting: {intent.lighting_intent or lighting}",
            f"color palette: {colors}, {film}",
            f"shot on {cam['body']} with {cam['lens']} at {cam['aperture']}, {cam['shutter']}",
            f"ultra-detailed tactile micro-textures, authentic skin pores, subsurface scattering, zero artificial smoothing",
            neg_space,
        ]
        clean_prompt = ", ".join([p.strip() for p in prompt_parts if p.strip()])

        # Midjourney parameters
        ar_param = f"--ar {ar}"
        style_param = "--v 6.1 --style raw"
        no_param = f"--no {TARGET_NEGATIVE_PROMPTS['midjourney']}"

        sref_url = (visual_style or {}).get("sref_url")
        sref_param = f"--sref {sref_url}" if sref_url else ""

        return f"{clean_prompt} {ar_param} {no_param} {sref_param} {style_param}".strip()

    @classmethod
    def compile_flux(
        cls,
        intent: CreativeIntentJSON,
        visual_style: Optional[Dict[str, Any]] = None,
        seed_key: str = "default_seed",
        platform: str = "instagram",
    ) -> Dict[str, Any]:
        """Compile intent for FLUX.1 Pro natural language descriptive prose."""
        lexicon = sample_lexicon(seed_key)
        cam = lexicon["camera"]
        lighting = lexicon["lighting"]
        film = lexicon["film"]
        arch = lexicon["architecture"]
        ar = cls.get_aspect_ratio_for_platform(platform, media_type="image")

        colors = ", ".join(intent.color_accents) if intent.color_accents else "cohesive brand color harmony"
        
        # FLUX excels at cohesive narrative prose
        prose_prompt = (
            f"An editorial photograph in {intent.shot_type}. "
            f"The scene captures {intent.subject}, currently {intent.action_or_state}. "
            f"The environment is {intent.environment_setting or arch}, evoking a {intent.emotional_mood} atmosphere. "
            f"Illumination is characterized by {intent.lighting_intent or lighting}. "
            f"Color grading follows {film}, integrating subtle accents of {colors}. "
            f"Captured on {cam['body']} paired with {cam['lens']} at {cam['aperture']}, "
            f"revealing tactile material micro-textures and natural organic detail without digital over-sharpening."
        )

        return {
            "prompt": prose_prompt,
            "aspect_ratio": ar,
            "guidance_scale": 3.5,
            "model": "flux-1-pro",
        }

    @classmethod
    def compile_dalle3(
        cls,
        intent: CreativeIntentJSON,
        visual_style: Optional[Dict[str, Any]] = None,
        seed_key: str = "default_seed",
        platform: str = "instagram",
    ) -> Dict[str, Any]:
        """Compile intent for DALL-E 3 (Positive-only framing, zero negative words)."""
        lexicon = sample_lexicon(seed_key)
        cam = lexicon["camera"]
        lighting = lexicon["lighting"]
        arch = lexicon["architecture"]

        # DALL-E 3 must NEVER have negative words (e.g. "no plastic", "no blur" causes DALL-E to add them)
        # Instead, describe what SHOULD be there with pristine physical reality
        positive_prompt = (
            f"A high-end editorial photograph of {intent.subject}, {intent.action_or_state}. "
            f"The backdrop is {intent.environment_setting or arch}. "
            f"Lighting: {intent.lighting_intent or lighting}. "
            f"The mood is {intent.emotional_mood}. "
            f"Composition: {intent.shot_type} with authentic physical textures, realistic fabric weave, "
            f"subtle natural skin details, and clean commercial aesthetic. "
            f"Camera perspective matches an editorial magazine feature shot on {cam['body']}."
        )

        ar = cls.get_aspect_ratio_for_platform(platform, media_type="image")
        size = "1024x1024" if ar == "1:1" else ("1792x1024" if ar == "16:9" else "1024x1792")

        return {
            "prompt": positive_prompt,
            "size": size,
            "quality": "hd",
            "style": "natural",
        }

    @classmethod
    def compile_imagen(
        cls,
        intent: CreativeIntentJSON,
        visual_style: Optional[Dict[str, Any]] = None,
        seed_key: str = "default_seed",
        platform: str = "instagram",
    ) -> Dict[str, Any]:
        """Compile intent for Google Imagen 3 API."""
        lexicon = sample_lexicon(seed_key)
        cam = lexicon["camera"]
        lighting = lexicon["lighting"]
        ar = cls.get_aspect_ratio_for_platform(platform, media_type="image")

        structured_prompt = (
            f"{intent.shot_type} photograph of {intent.subject}, {intent.action_or_state}, "
            f"setting: {intent.environment_setting}, mood: {intent.emotional_mood}, "
            f"lighting: {intent.lighting_intent or lighting}, "
            f"shot on {cam['body']} with {cam['lens']}, natural textures and colors."
        )

        return {
            "prompt": structured_prompt,
            "aspect_ratio": ar,
            "negative_prompt": TARGET_NEGATIVE_PROMPTS["imagen"],
        }

    @classmethod
    def compile_video_shot_list(
        cls,
        shot_plan: VideoShotPlan,
        seed_key: str = "default_video_seed",
    ) -> Dict[str, Any]:
        """Compile cinematic video prompt for Pika, Veo, Sora, or Runway."""
        lexicon = sample_lexicon(seed_key)
        lighting = lexicon["lighting"]

        motion_prompt = (
            f"Cinematic {shot_plan.aspect_ratio} video sequence, {shot_plan.duration_seconds} seconds. "
            f"Scene: {shot_plan.scene_description}. "
            f"Camera movement: {shot_plan.camera_movement}. "
            f"Subject dynamics: {shot_plan.focal_motion}. "
            f"Lighting & atmosphere: {lighting}, {shot_plan.atmosphere_notes}. "
            f"Frame rate: 24fps cinema standard, seamless temporal coherence, steady motion."
        )

        return {
            "prompt": motion_prompt,
            "duration": shot_plan.duration_seconds,
            "aspect_ratio": shot_plan.aspect_ratio,
            "negative_prompt": TARGET_NEGATIVE_PROMPTS["video"],
        }

    @classmethod
    def compile_for_target(
        cls,
        target_provider: str,
        intent: CreativeIntentJSON,
        visual_style: Optional[Dict[str, Any]] = None,
        seed_key: str = "default_seed",
        platform: str = "instagram",
    ) -> Dict[str, Any]:
        """Universal dispatcher for target compilation."""
        provider = target_provider.lower()
        if "midjourney" in provider:
            return {"provider": "midjourney", "prompt": cls.compile_midjourney(intent, visual_style, seed_key, platform)}
        elif "flux" in provider:
            compiled = cls.compile_flux(intent, visual_style, seed_key, platform)
            return {"provider": "flux", **compiled}
        elif "dalle" in provider or "openai" in provider:
            compiled = cls.compile_dalle3(intent, visual_style, seed_key, platform)
            return {"provider": "openai", **compiled}
        elif "imagen" in provider or "gemini" in provider:
            compiled = cls.compile_imagen(intent, visual_style, seed_key, platform)
            return {"provider": "gemini", **compiled}
        else:
            # Fallback to FLUX style natural language
            compiled = cls.compile_flux(intent, visual_style, seed_key, platform)
            return {"provider": provider, **compiled}
