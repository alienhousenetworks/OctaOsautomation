"""Pydantic Contracts for the 9-Role Campaign Creative Operating System.

Workstream B:
- Typed input/output contracts between all pipeline stages
- Guaranteed schema validation and serializability
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.services.marketing.compiler.prompt_compiler import CreativeIntentJSON, VideoShotPlan


class BrandStrategyBrief(BaseModel):
    """Output from Role 1: Brand Strategist."""
    core_narrative: str = Field(..., description="Central thematic narrative for the campaign")
    tone_keywords: List[str] = Field(default_factory=list, description="Authoritative tone adjectives")
    target_persona: str = Field(..., description="Target buyer or audience segment")
    key_differentiators: List[str] = Field(default_factory=list, description="Defensible product advantages")
    approved_evidence_ids: List[str] = Field(default_factory=list, description="Referenced evidence records")
    prohibited_topics: List[str] = Field(default_factory=list, description="Taboos or non-approved claims")


class VisualIdentityTokens(BaseModel):
    """Output from Role 2: Visual Director."""
    primary_color: str = "#059669"
    secondary_color: str = "#0F172A"
    accent_color: str = "#38BDF8"
    aesthetic_mood: str = "Cinematic architectural minimalism, high-contrast authentic textures"
    photography_archetype: str = "35mm corporate editorial lookbook"
    sref_url: Optional[str] = None


class CampaignDayOutline(BaseModel):
    """Single-day narrative step in the campaign arc."""
    day: int
    theme: str
    narrative_focus: str  # e.g., "Problem Agitation", "Case Study Proof", "Product Teardown", "Executive Vision"
    suggested_hook_angle: str
    target_cta_intent: str


class CampaignNarrativeArc(BaseModel):
    """Output from Role 3: Narrative Architect."""
    campaign_title: str
    total_days: int
    days_outline: List[CampaignDayOutline]


class PlatformPostDraft(BaseModel):
    """Output from Role 4: Platform Adapter."""
    platform: str
    day: int
    hook: str
    body_content: str
    cta_sentence: str
    hashtags: List[str] = Field(default_factory=list)
    formatted_full_post: str


class CallToActionSpec(BaseModel):
    """Output from Role 5: Offer/CTA Engineer."""
    cta_copy: str
    action_type: str = "demo_request"  # demo_request, audit_signup, resource_download, comment_dialogue
    friction_level: str = "low"


class CritiqueScoreCard(BaseModel):
    """Output from Role 9: Critic / Judge."""
    groundedness_score: float = Field(..., ge=0.0, le=1.0)
    unsupported_claims: List[str] = Field(default_factory=list)
    platform_fit_score: float = Field(..., ge=0.0, le=1.0)
    brand_voice_score: float = Field(..., ge=0.0, le=1.0)
    compliance_passed: bool = True
    compliance_issues: List[str] = Field(default_factory=list)
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    is_approved: bool = True
    critique_notes: str = ""
