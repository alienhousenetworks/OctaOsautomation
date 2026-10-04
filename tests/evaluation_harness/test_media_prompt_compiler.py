"""Media Prompt Compiler Test Suite.

Workstream C & Workstream D:
- Verifies target-specific compilation for Midjourney, FLUX, DALL-E 3, Imagen, and Video.
- Asserts that DALL-E 3 contains zero negative phrases.
- Asserts Midjourney contains valid --ar and --no flags.
- Asserts deterministic anti-samey lexicon sampling.
"""
import pytest
from app.services.marketing.compiler.prompt_compiler import (
    MediaPromptCompiler,
    CreativeIntentJSON,
    VideoShotPlan,
)
from app.services.marketing.compiler.lexicon import sample_lexicon


def test_midjourney_compilation_syntax():
    """Verify Midjourney prompt contains photographic framing and valid parameter flags."""
    intent = CreativeIntentJSON(
        subject="enterprise CTO reviewing autonomous deployment pipelines",
        action_or_state="analyzing telemetry data with calm confidence",
        environment_setting="minimalist architectural executive office with frosted glass",
        emotional_mood="authoritative, visionary",
        shot_type="cinematic low-angle medium shot",
        lighting_intent="soft diffused octabox key light with warm golden rim accent",
        negative_space_direction="right_40pct",
        color_accents=["#059669", "#0F172A"],
    )

    mj_prompt = MediaPromptCompiler.compile_midjourney(
        intent=intent,
        seed_key="test_tenant:camp_1:day_1:instagram",
        platform="instagram",
    )

    # Assertions
    assert "--ar 1:1" in mj_prompt
    assert "--v 6.1" in mj_prompt
    assert "--style raw" in mj_prompt
    assert "--no" in mj_prompt
    assert "plastic skin" in mj_prompt  # Included in negative flags
    assert "enterprise CTO" in mj_prompt
    assert "tactile micro-textures" in mj_prompt


def test_flux_compilation_syntax():
    """Verify FLUX prompt compiles into cohesive natural language prose."""
    intent = CreativeIntentJSON(
        subject="modern aerospace data center server rack with tactile aluminum finish",
        action_or_state="pulsing with soft emerald status indicators",
        environment_setting="poured concrete server bay",
        emotional_mood="pristine, high-tech",
        shot_type="macro close-up",
        lighting_intent="indirect cool LED ambient lighting with warm accent",
        color_accents=["#059669"],
    )

    res = MediaPromptCompiler.compile_flux(
        intent=intent,
        seed_key="test_tenant:camp_1:day_1:linkedin",
        platform="linkedin",
    )

    assert "prompt" in res
    assert res["aspect_ratio"] == "16:9"
    assert res["guidance_scale"] == 3.5
    assert res["model"] == "flux-1-pro"
    assert "An editorial photograph in macro close-up" in res["prompt"]
    assert "aerospace data center" in res["prompt"]


def test_dalle3_positive_only_framing():
    """Critical Test: DALL-E 3 must NEVER have negative prompt strings."""
    intent = CreativeIntentJSON(
        subject="corporate product strategy workshop team",
        action_or_state="brainstorming next quarter architecture on digital whiteboards",
        environment_setting="sunlit Scandinavian design studio",
        emotional_mood="collaborative, focused",
        shot_type="eye-level wide shot",
        lighting_intent="diffused natural north-facing window light",
    )

    dalle_res = MediaPromptCompiler.compile_dalle3(
        intent=intent,
        seed_key="test_tenant:camp_1:day_2:linkedin",
        platform="linkedin",
    )

    prompt = dalle_res["prompt"]
    assert dalle_res["quality"] == "hd"
    assert dalle_res["style"] == "natural"
    assert dalle_res["size"] == "1792x1024"  # 16:9 aspect ratio

    # Assert zero negative words (DALL-E 3 inverts negative words)
    assert "--no" not in prompt
    assert "no plastic" not in prompt.lower()
    assert "no blur" not in prompt.lower()
    assert "no distortion" not in prompt.lower()
    assert "authentic physical textures" in prompt


def test_google_imagen_syntax():
    """Verify Imagen 3 returns structured prompt and negative prompt param."""
    intent = CreativeIntentJSON(
        subject="industrial robotics engineer inspecting autonomous arm",
        action_or_state="calibrating optical sensors",
        environment_setting="cleanroom manufacturing facility",
        emotional_mood="precise, rigorous",
        shot_type="medium close-up",
        lighting_intent="clean overhead laboratory lighting",
    )

    res = MediaPromptCompiler.compile_imagen(
        intent=intent,
        seed_key="test_tenant:camp_1:day_3:instagram",
        platform="instagram",
    )

    assert "prompt" in res
    assert res["aspect_ratio"] == "1:1"
    assert "negative_prompt" in res
    assert "blurry" in res["negative_prompt"]


def test_video_shot_planner_syntax():
    """Verify video compilation enforces 24fps cinema standards and temporal coherence."""
    plan = VideoShotPlan(
        scene_description="Autonomous robotics arm positioning optical lens into chassis",
        duration_seconds=6,
        camera_movement="slow cinematic dolly-in at 0.5m/s",
        focal_motion="robotic arm rotates 15 degrees into focus",
        atmosphere_notes="subtle amber rim lighting",
        aspect_ratio="16:9",
    )

    v_res = MediaPromptCompiler.compile_video_shot_list(
        shot_plan=plan,
        seed_key="test_tenant:camp_1:day_2:video",
    )

    assert v_res["duration"] == 6
    assert v_res["aspect_ratio"] == "16:9"
    assert "24fps cinema standard" in v_res["prompt"]
    assert "seamless temporal coherence" in v_res["prompt"]
    assert "jitter" in v_res["negative_prompt"]


def test_anti_samey_lexicon_rotation():
    """Verify that different seed keys deterministically sample varied camera and lighting setups."""
    sample1 = sample_lexicon("tenant_alpha:camp_01:day_1:linkedin")
    sample2 = sample_lexicon("tenant_alpha:camp_01:day_2:linkedin")
    sample3 = sample_lexicon("tenant_alpha:camp_01:day_3:linkedin")

    # Day 1 vs Day 2 vs Day 3 must not be identical
    cameras = [sample1["camera"]["body"], sample2["camera"]["body"], sample3["camera"]["body"]]
    # At least 2 different cameras sampled across 3 days
    assert len(set(cameras)) >= 2
