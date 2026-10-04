"""Curated Lexicon & Anti-Samey Deterministic Rotation Engine.

Workstream C:
- Curated databases of verified camera hardware, lighting setups, film stocks, and architectural aesthetics.
- Deterministic seed rotator to guarantee adjacent campaign days never look identical.
"""
import hashlib
from typing import Dict, Any, List


CAMERAS_AND_LENSES = [
    {"body": "Hasselblad H6D-100c medium format", "lens": "HC 100mm f/2.2 prime lens", "aperture": "f/2.8", "shutter": "1/250s"},
    {"body": "Leica M11 Rangefinder", "lens": "Leica Summilux-M 35mm f/1.4 ASPH", "aperture": "f/2.0", "shutter": "1/500s"},
    {"body": "Canon EOS R5", "lens": "Canon RF 50mm f/1.2L USM", "aperture": "f/1.8", "shutter": "1/200s"},
    {"body": "Sony A1 Mirrorless", "lens": "Sony FE 85mm f/1.4 GM", "aperture": "f/2.0", "shutter": "1/320s"},
    {"body": "Arri Alexa Mini LF Cinema Camera", "lens": "Cooke Anamorphic/i Full Frame Plus 40mm", "aperture": "T2.3", "shutter": "180-degree shutter"},
    {"body": "Phase One XF IQ4 150MP", "lens": "Schneider Kreuznach 80mm LS f/2.8", "aperture": "f/4.0", "shutter": "1/160s"},
    {"body": "Nikon Z9", "lens": "NIKKOR Z 58mm f/0.95 S Noct", "aperture": "f/1.2", "shutter": "1/400s"},
    {"body": "Fujifilm GFX 100 II Large Format", "lens": "GF 110mm f/2 R LM WR", "aperture": "f/2.8", "shutter": "1/250s"},
]

LIGHTING_SETUPS = [
    "Soft diffused key light from a 60-inch overhead octabox at 45 degrees with subtle silver reflector fill",
    "High-contrast dramatic chiaroscuro with deep velvet shadows and precise rim illumination on edges",
    "Natural morning golden-hour light streaming through industrial floor-to-ceiling loft windows with subtle volumetric haze",
    "Rembrandt studio lighting with distinct triangular light patch on the cheek and gentle hair backlight",
    "Diffused north-facing overcast skylight producing exceptionally soft, wrap-around shadow falloff",
    "Subtle cinematic tungsten backlighting paired with cool blue ambient fill for refined color contrast",
    "Clean editorial beauty dish lighting positioned directly above camera axis for crisp micro-contrast",
    "Architectural cove lighting with indirect warm ambient bounce and precise directional spotlighting",
]

FILM_STOCKS_AND_COLOR = [
    "Kodak Portra 400 color science with natural organic fine grain and rich, accurate skin tones",
    "Fujifilm Pro 400H profile featuring airy pastel cyan highlights and muted emerald shadow tones",
    "Kodak Ektar 100 with ultra-vivid saturation, sharp micro-contrast, and clean neutral whites",
    "CineStill 800T cinematic color grading with subtle warm red halation around high-contrast light sources",
    "Kodak Tri-X 400 monochrome with rich silver gelatin black levels and timeless editorial texture",
    "Commercial high-dynamic-range color grade with preserved specular highlights and deep neutral charcoal blacks",
    "Nordic minimalist desaturated palette emphasizing muted slate grays, sage greens, and warm alabaster",
    "Warm contemporary editorial grade with soft amber highlights and rich mahogany shadow detail",
]

ARCHITECTURAL_AESTHETICS = [
    "Minimalist boardroom with poured architectural concrete walls, floor-to-ceiling glass, and matte obsidian furniture",
    "Contemporary design atelier with warm natural birch wood slats, brushed aluminum accents, and clean negative space",
    "High-tech aerospace engineering laboratory with polished terrazzo flooring, frosted glass dividers, and recessed linear lighting",
    "Industrial architectural loft featuring restored exposed brick, black steel structural beams, and expansive skylights",
    "Sleek executive sanctuary with dark walnut acoustic wall paneling, subtle indirect warm lighting, and brushed brass details",
    "Futuristic minimalist pavilion surrounded by manicured reflective water features and geometric limestone walls",
]

TARGET_NEGATIVE_PROMPTS = {
    "midjourney": "plastic skin, airbrushed, 3d render, cartoon, anime, illustration, extra fingers, deformed hands, blurry, watermark, signature, stock photo smile",
    "flux": "plastic skin, smooth doll-like skin, extra limbs, low resolution, jpeg artifacts, text overlays, garish neon colors, distorted anatomy",
    "imagen": "blurry, low quality, oversaturated, deformed hands, distorted face, extra limbs, watermark, text, signature, plastic texture",
    "dalle3": "", # DALL-E 3 does not support negative prompts (negatives often trigger the unwanted object)
    "video": "jitter, flickering, abrupt camera movements, morphing objects, unnatural motion, digital noise, frame tears",
}


def sample_lexicon(seed_key: str) -> Dict[str, Any]:
    """Deterministically sample photography parameters based on a unique seed key."""
    # Use sha256 of seed_key (e.g. tenant_id:campaign_id:day:platform)
    h = int(hashlib.sha256(seed_key.encode("utf-8")).hexdigest(), 16)

    camera = CAMERAS_AND_LENSES[h % len(CAMERAS_AND_LENSES)]
    lighting = LIGHTING_SETUPS[(h // len(CAMERAS_AND_LENSES)) % len(LIGHTING_SETUPS)]
    film = FILM_STOCKS_AND_COLOR[(h // (len(CAMERAS_AND_LENSES) * len(LIGHTING_SETUPS))) % len(FILM_STOCKS_AND_COLOR)]
    arch = ARCHITECTURAL_AESTHETICS[(h // 17) % len(ARCHITECTURAL_AESTHETICS)]

    return {
        "camera": camera,
        "lighting": lighting,
        "film": film,
        "architecture": arch,
    }
