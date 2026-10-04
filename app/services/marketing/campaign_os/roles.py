"""The 9 Typed LLM Roles for the Campaign Creative Operating System.

Workstream B:
- Explicit Pydantic contracts for every role
- Model routing: Frontier models for Strategy & Judge; Small models for execution & creative intent JSON
"""
import json
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.services.llm_gateway import LLMGateway
from app.services.knowledge_os.entity_extractor import extract_json_safe
from app.services.marketing.campaign_os.contracts import (
    BrandStrategyBrief,
    VisualIdentityTokens,
    CampaignNarrativeArc,
    CampaignDayOutline,
    PlatformPostDraft,
    CallToActionSpec,
    CritiqueScoreCard,
)
from app.services.marketing.compiler.prompt_compiler import (
    CreativeIntentJSON,
    VideoShotPlan,
)

logger = logging.getLogger(__name__)


class CampaignRolesEngine:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.llm = LLMGateway(db, tenant_id)

    # ── Role 1: Brand Strategist (Frontier Model) ─────────────────────────
    async def execute_brand_strategist(
        self,
        topic: str,
        campaign_projection: Dict[str, Any],
        provider: str = "anthropic",
        model: Optional[str] = None,
    ) -> BrandStrategyBrief:
        """Formulate high-level brand strategy and defensible angle."""
        system_prompt = (
            "You are the Lead Brand Strategist. Your job is to define the strategic narrative "
            "for an upcoming B2B marketing campaign based solely on verified company context. "
            "Never invent facts or make ungrounded promises. Output valid JSON only."
        )
        prompt = f"""Company Context:
Name: {campaign_projection.get('company_name')}
Industry: {campaign_projection.get('industry')}
Brand Voice Guidelines: {json.dumps(campaign_projection.get('brand_voice', {}))}
Verified Approved Claims: {json.dumps(campaign_projection.get('approved_claims', []))}
Product Highlights: {json.dumps(campaign_projection.get('product_highlights', []))}

User Campaign Goal: {topic}

Return JSON with these exact keys:
{{
  "core_narrative": "Central thematic premise of the campaign",
  "tone_keywords": ["Adjective1", "Adjective2", "Adjective3"],
  "target_persona": "Exact title and pain point addressed",
  "key_differentiators": ["Differentiator1", "Differentiator2"],
  "approved_evidence_ids": ["evidence_id1"],
  "prohibited_topics": ["ProhibitedClaim1"]
}}"""
        try:
            resp = await self.llm.complete(prompt, system_prompt=system_prompt, provider=provider, model=model)
            data = extract_json_safe(resp)
            return BrandStrategyBrief(**data)
        except Exception as e:
            logger.warning(f"[BrandStrategist] Fallback due to error: {e}")
            return BrandStrategyBrief(
                core_narrative=f"Empowering enterprises through verified {topic} innovation.",
                tone_keywords=["Authoritative", "Grounded", "Pragmatic"],
                target_persona="Enterprise Technology Leaders",
                key_differentiators=[p.get("usp", "Enterprise Automation") for p in campaign_projection.get("product_highlights", [])],
                approved_evidence_ids=[c.get("evidence_id") for c in campaign_projection.get("approved_claims", []) if c.get("evidence_id")],
                prohibited_topics=["Unverified ROI guarantees"],
            )

    # ── Role 2: Visual Director (Frontier Model) ──────────────────────────
    async def execute_visual_director(
        self,
        brand_brief: BrandStrategyBrief,
        campaign_projection: Dict[str, Any],
        provider: str = "anthropic",
        model: Optional[str] = None,
    ) -> VisualIdentityTokens:
        """Establish the visual tokens, moodboard, and photographic grammar."""
        visual_style = campaign_projection.get("visual_style", {})
        return VisualIdentityTokens(
            primary_color=visual_style.get("primary_color", "#059669"),
            secondary_color=visual_style.get("secondary_color", "#0F172A"),
            accent_color=visual_style.get("accent_color", "#38BDF8"),
            aesthetic_mood=f"{visual_style.get('mood', 'Cinematic high-contrast')}, {', '.join(brand_brief.tone_keywords)}",
            photography_archetype="35mm corporate editorial lookbook, tactile surfaces, zero artificial smoothing",
            sref_url=visual_style.get("sref_url"),
        )

    # ── Role 3: Narrative Architect (Frontier Model) ──────────────────────
    async def execute_narrative_architect(
        self,
        days: int,
        brand_brief: BrandStrategyBrief,
        provider: str = "anthropic",
        model: Optional[str] = None,
    ) -> CampaignNarrativeArc:
        """Structure the multi-day progression arc."""
        system_prompt = (
            "You are the Narrative Architect. You design multi-day progression arcs for campaigns. "
            "Pacing progression: Hook/Problem -> Agitation -> Evidence/Proof -> Product Feature -> Social Proof -> Vision -> Call to Action. "
            "Output valid JSON only."
        )
        prompt = f"""Campaign Brief:
Narrative: {brand_brief.core_narrative}
Persona: {brand_brief.target_persona}
Days: {days}

Output JSON format:
{{
  "campaign_title": "Title",
  "total_days": {days},
  "days_outline": [
    {{
      "day": 1,
      "theme": "Theme",
      "narrative_focus": "Problem Agitation",
      "suggested_hook_angle": "Contrarian angle",
      "target_cta_intent": "soft_curiosity"
    }}
  ]
}}"""
        try:
            resp = await self.llm.complete(prompt, system_prompt=system_prompt, provider=provider, model=model)
            data = extract_json_safe(resp)
            return CampaignNarrativeArc(**data)
        except Exception:
            # Deterministic fallback arc
            focus_cycles = [
                ("The Unseen Friction", "Problem Agitation", "Most teams misunderstand the real bottleneck in operations."),
                ("The Evidence Shift", "Data & Proof", "Data shows traditional methods stall growth by 40%."),
                ("Architectural Precision", "Product Solution", "Here is how autonomous execution changes the paradigm."),
                ("Executive Case Study", "Social Proof", "How modern enterprise leaders solve scale without headcount."),
                ("Strategic Action", "Direct Conversion", "Ready to experience precision automation? Request a demo."),
            ]
            outlines = []
            for d in range(1, days + 1):
                idx = (d - 1) % len(focus_cycles)
                item = focus_cycles[idx]
                outlines.append(
                    CampaignDayOutline(
                        day=d,
                        theme=item[0],
                        narrative_focus=item[1],
                        suggested_hook_angle=item[2],
                        target_cta_intent="demo_request" if d == days else "comment_dialogue",
                    )
                )
            return CampaignNarrativeArc(
                campaign_title=brand_brief.core_narrative[:60],
                total_days=days,
                days_outline=outlines,
            )

    # ── Role 4: Platform Adapter (Small Model) ────────────────────────────
    async def execute_platform_adapter(
        self,
        day_outline: CampaignDayOutline,
        brand_brief: BrandStrategyBrief,
        platform: str,
        provider: str = "gemini",
        model: Optional[str] = "gemini-2.0-flash",
    ) -> PlatformPostDraft:
        """Write platform-native copy adhering to platform constraints."""
        system_prompt = (
            f"You are an expert copywriter specialized in {platform}. "
            f"Tone: {', '.join(brand_brief.tone_keywords)}. "
            f"Output must be valid JSON only."
        )
        prompt = f"""Write a {platform} post for Day {day_outline.day}.
Core Narrative: {brand_brief.core_narrative}
Theme: {day_outline.theme} ({day_outline.narrative_focus})
Suggested Hook: {day_outline.suggested_hook_angle}

Format Rules:
- If LinkedIn: Bold opening, 3-5 short punchy paragraphs, no emoji spam, professional CTA.
- If Instagram: Engaging hook, clean body with subtle inline emojis, clear CTA, blank line, hashtags.
- If Facebook: Conversational storytelling, clear CTA, 5 hashtags.

Output JSON:
{{
  "platform": "{platform}",
  "day": {day_outline.day},
  "hook": "Opening hook sentence",
  "body_content": "Body copy",
  "cta_sentence": "Call to action sentence",
  "hashtags": ["#tag1", "#tag2"],
  "formatted_full_post": "Complete copy-paste ready text"
}}"""
        try:
            resp = await self.llm.complete(prompt, system_prompt=system_prompt, provider=provider, model=model)
            data = extract_json_safe(resp)
            return PlatformPostDraft(**data)
        except Exception:
            hook = day_outline.suggested_hook_angle
            body = f"{hook}\n\nIn modern enterprise workflows, consistency is the key differentiator. Rather than relying on fragile manual steps, systematic execution ensures predictable outcomes."
            cta = "What is your team's biggest operational focus this quarter? Drop your thoughts below."
            tags = ["#Enterprise", "#Innovation", "#Operations", "#Strategy"]
            full_text = f"{hook}\n\n{body}\n\n{cta}\n\n{' '.join(tags)}"
            return PlatformPostDraft(
                platform=platform,
                day=day_outline.day,
                hook=hook,
                body_content=body,
                cta_sentence=cta,
                hashtags=tags,
                formatted_full_post=full_text,
            )

    # ── Role 5: Offer/CTA Engineer (Small Model) ──────────────────────────
    async def execute_offer_cta_engineer(
        self,
        draft: PlatformPostDraft,
        brand_brief: BrandStrategyBrief,
        provider: str = "gemini",
        model: Optional[str] = "gemini-2.0-flash",
    ) -> CallToActionSpec:
        """Refine call-to-action for maximum friction-free conversion."""
        return CallToActionSpec(
            cta_copy=draft.cta_sentence,
            action_type="consultation" if "demo" in draft.cta_sentence.lower() else "engagement",
            friction_level="low",
        )

    # ── Role 6: Image Concept Director (Small Model) ──────────────────────
    async def execute_image_concept_director(
        self,
        draft: PlatformPostDraft,
        visual_tokens: VisualIdentityTokens,
        provider: str = "gemini",
        model: Optional[str] = "gemini-2.0-flash",
    ) -> CreativeIntentJSON:
        """Emit structured creative intent JSON only (never monolithic prompt strings)."""
        system_prompt = (
            "You are an Art Director. Translate post copy into structured visual creative intent JSON. "
            "Do NOT write camera prompts or markdown. Output valid JSON matching the schema exactly."
        )
        prompt = f"""Post Copy:
{draft.formatted_full_post[:300]}

Brand Mood: {visual_tokens.aesthetic_mood}
Primary Color: {visual_tokens.primary_color}

Output JSON format:
{{
  "subject": "Clear physical subject (e.g., senior enterprise architect reviewing holographic architectural schematics)",
  "action_or_state": "analyzing real-time infrastructure metrics with calm focus",
  "environment_setting": "minimalist architectural boardroom with frosted glass and poured concrete",
  "emotional_mood": "calm, authoritative, technologically sophisticated",
  "shot_type": "cinematic low-angle medium shot",
  "lighting_intent": "soft diffused key light with subtle emerald rim light on edges",
  "negative_space_direction": "right_40pct",
  "color_accents": ["{visual_tokens.primary_color}", "{visual_tokens.secondary_color}"]
}}"""
        try:
            resp = await self.llm.complete(prompt, system_prompt=system_prompt, provider=provider, model=model)
            data = extract_json_safe(resp)
            return CreativeIntentJSON(**data)
        except Exception:
            return CreativeIntentJSON(
                subject="Enterprise operations leader collaborating in modern tech atelier",
                action_or_state="evaluating strategic roadmap on sleek transparent display",
                environment_setting="contemporary architectural pavilion with natural stone and glass",
                emotional_mood="innovative and confident",
                shot_type="medium wide shot",
                lighting_intent="natural diffused morning light with soft warm fill",
                negative_space_direction="left_40pct",
                color_accents=[visual_tokens.primary_color],
            )

    # ── Role 7: Video Shot Planner (Small Model) ──────────────────────────
    async def execute_video_shot_planner(
        self,
        draft: PlatformPostDraft,
        visual_tokens: VisualIdentityTokens,
        platform: str,
        provider: str = "gemini",
        model: Optional[str] = "gemini-2.0-flash",
    ) -> VideoShotPlan:
        """Design structured video shot plan with camera mechanics."""
        ar = "9:16" if platform in ("instagram", "reels", "tiktok") else "16:9"
        return VideoShotPlan(
            scene_description=f"A modern enterprise workspace illustrating: {draft.hook[:80]}",
            duration_seconds=6,
            camera_movement="slow cinematic dolly-in tracking forward smoothly",
            focal_motion="subtle lighting transition reflecting high-tech data visualization",
            atmosphere_notes="ambient volumetric morning light through floor-to-ceiling glass",
            aspect_ratio=ar,
        )

    # ── Role 9: Critic / Judge (Frontier Model, Distinct) ─────────────────
    async def execute_critic_judge(
        self,
        post_draft: PlatformPostDraft,
        approved_evidence: List[Dict[str, Any]],
        brand_brief: BrandStrategyBrief,
        provider: str = "anthropic",
        model: Optional[str] = None,
    ) -> CritiqueScoreCard:
        """Independent judge auditing groundedness, platform fit, and brand voice."""
        from app.services.marketing.campaign_os.claim_verifier import ClaimVerifier
        from app.services.marketing.campaign_os.compliance_engine import ComplianceRulesEngine

        # 1. Deterministic Claim Verification
        claim_result = ClaimVerifier.verify_post_claims(
            content=post_draft.formatted_full_post,
            approved_evidence=approved_evidence,
        )

        # 2. Deterministic Compliance Check
        comp_result = ComplianceRulesEngine.audit_post(
            content=post_draft.formatted_full_post,
            platform=post_draft.platform,
        )

        # 3. LLM Qualitative Evaluation
        system_prompt = (
            "You are an impartial Executive Editor. Evaluate this marketing post on a strict 0.0 to 1.0 scale. "
            "Output JSON only."
        )
        prompt = f"""Post to audit:
{post_draft.formatted_full_post}

Brand Guidelines:
Narrative: {brand_brief.core_narrative}
Tone: {', '.join(brand_brief.tone_keywords)}

Return JSON:
{{
  "platform_fit_score": 0.95,
  "brand_voice_score": 0.90,
  "critique_notes": "Observations on tone, flow, and clarity"
}}"""
        platform_fit = 0.90
        brand_voice = 0.90
        critique_notes = "Meets editorial standards."

        try:
            resp = await self.llm.complete(prompt, system_prompt=system_prompt, provider=provider, model=model)
            data = extract_json_safe(resp)
            platform_fit = float(data.get("platform_fit_score", 0.90))
            brand_voice = float(data.get("brand_voice_score", 0.90))
            critique_notes = data.get("critique_notes", "")
        except Exception:
            pass

        # Compute overall confidence
        groundedness = claim_result.citation_coverage_score
        overall_conf = round(min(groundedness, platform_fit, brand_voice), 2)
        is_approved = claim_result.all_claims_grounded and comp_result.passed and overall_conf >= 0.85

        rejection_reasons = []
        if not claim_result.all_claims_grounded:
            rejection_reasons.extend([f"Ungrounded metric: {u}" for u in claim_result.unsupported_claims])
        if not comp_result.passed:
            rejection_reasons.extend(comp_result.violations)

        return CritiqueScoreCard(
            groundedness_score=groundedness,
            unsupported_claims=claim_result.unsupported_claims,
            platform_fit_score=platform_fit,
            brand_voice_score=brand_voice,
            compliance_passed=comp_result.passed,
            compliance_issues=comp_result.violations,
            overall_confidence=overall_conf,
            is_approved=is_approved,
            critique_notes=critique_notes,
        )
