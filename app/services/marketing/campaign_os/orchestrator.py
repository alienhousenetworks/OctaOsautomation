"""Durable Campaign OS DAG Orchestrator.

Workstream E:
- 3-Stage DAG: Strategy Root -> Idempotent Post Fan-Out -> Critic & Dispatch
- Integrates Prompt Compiler, Compliance Rules Engine, and Claim Verifier
- Graceful degradation (circuit breakers, text-only fallback)
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging
from sqlalchemy.orm import Session

from app.models.verticals import ContentPost
from app.models.agents import ActivityLog
from app.models.enterprise import ApprovalRequest
from app.services.knowledge_os.intent_projector import CompanyContextProjectionEngine, IntentType
from app.services.marketing.campaign_os.roles import CampaignRolesEngine
from app.services.marketing.compiler.prompt_compiler import MediaPromptCompiler

logger = logging.getLogger(__name__)


class CampaignOSOrchestrator:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.roles = CampaignRolesEngine(db, tenant_id)
        self.projector = CompanyContextProjectionEngine(db, tenant_id)

    async def execute_campaign_dag(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the durable multi-stage campaign generation DAG."""
        topic = params.get("topic", "Enterprise Automation")
        days = int(params.get("days", 3))
        platforms = params.get("platforms", ["linkedin", "instagram"])
        image_provider = params.get("image_provider", "openai")
        video_provider = params.get("video_provider", "pika")
        generate_images = bool(params.get("generate_images", True))
        generate_videos = bool(params.get("generate_videos", False))
        strategy_provider = params.get("strategy_provider", "anthropic")
        execution_provider = params.get("execution_provider", "gemini")

        # ── Stage 0: Security-Screened Intent Projection ───────────────────
        campaign_projection = await self.projector.get_projection(
            intent=IntentType.CAMPAIGN_MARKETING
        )
        approved_evidence = campaign_projection.get("approved_claims", [])

        # ── Stage 1: Campaign Strategy (DAG Root - Frontier Model) ─────────
        self.log_activity(
            "Campaign Strategy",
            f"Formulating strategic narrative and visual tokens for {days}-day campaign on: {topic}",
            status="pending",
        )

        brand_brief = await self.roles.execute_brand_strategist(
            topic=topic,
            campaign_projection=campaign_projection,
            provider=strategy_provider,
        )

        visual_tokens = await self.roles.execute_visual_director(
            brand_brief=brand_brief,
            campaign_projection=campaign_projection,
            provider=strategy_provider,
        )

        narrative_arc = await self.roles.execute_narrative_architect(
            days=days,
            brand_brief=brand_brief,
            provider=strategy_provider,
        )

        self.log_activity(
            "Campaign Blueprint",
            f"Narrative arc completed: '{narrative_arc.campaign_title}'. Fan-out to {days} days x {len(platforms)} platforms.",
            status="success",
        )

        # ── Stage 2: Post Fan-Out per Day x Platform (Idempotent Tasks) ────
        generated_posts = []
        approved_count = 0
        needs_review_count = 0

        for day_outline in narrative_arc.days_outline:
            for platform in platforms:
                idempotency_key = f"{self.tenant_id}:{narrative_arc.campaign_title[:20]}:{day_outline.day}:{platform}"

                try:
                    # Role 4: Platform Adapter (Copy)
                    draft = await self.roles.execute_platform_adapter(
                        day_outline=day_outline,
                        brand_brief=brand_brief,
                        platform=platform,
                        provider=execution_provider,
                    )

                    # Role 5: Offer/CTA Engineer
                    cta_spec = await self.roles.execute_offer_cta_engineer(
                        draft=draft,
                        brand_brief=brand_brief,
                        provider=execution_provider,
                    )

                    # Media Compilation
                    compiled_image_prompt = None
                    compiled_video_prompt = None

                    if generate_images:
                        # Role 6: Image Concept Director (Structured Intent JSON)
                        image_intent = await self.roles.execute_image_concept_director(
                            draft=draft,
                            visual_tokens=visual_tokens,
                            provider=execution_provider,
                        )
                        # Deterministic Prompt Compiler
                        image_res = MediaPromptCompiler.compile_for_target(
                            target_provider=image_provider,
                            intent=image_intent,
                            visual_style=visual_tokens.model_dump(),
                            seed_key=idempotency_key,
                            platform=platform,
                        )
                        compiled_image_prompt = image_res.get("prompt")

                    if generate_videos and (day_outline.day % 2 == 0):
                        # Role 7: Video Shot Planner (Timed Shot List)
                        video_plan = await self.roles.execute_video_shot_planner(
                            draft=draft,
                            visual_tokens=visual_tokens,
                            platform=platform,
                            provider=execution_provider,
                        )
                        # Deterministic Video Prompt Compiler
                        video_res = MediaPromptCompiler.compile_video_shot_list(
                            shot_plan=video_plan,
                            seed_key=idempotency_key,
                        )
                        compiled_video_prompt = video_res.get("prompt")

                    # Role 9: Critic / Judge (NLI Entailment & Compliance Gate)
                    score_card = await self.roles.execute_critic_judge(
                        post_draft=draft,
                        approved_evidence=approved_evidence,
                        brand_brief=brand_brief,
                        provider=strategy_provider,
                    )

                    # Persist Post Record
                    post = ContentPost(
                        tenant_id=self.tenant_id,
                        platform=platform,
                        content=draft.formatted_full_post,
                        image_prompt=compiled_image_prompt,
                        video_prompt=compiled_video_prompt,
                        media_prompt=compiled_image_prompt or compiled_video_prompt,
                        day=day_outline.day,
                        status="draft",
                        approval_status="approved" if score_card.is_approved else "pending",
                        performance_score=score_card.overall_confidence * 100.0,
                        learning_tags=[day_outline.narrative_focus, cta_spec.action_type],
                    )
                    self.db.add(post)
                    self.db.commit()
                    self.db.refresh(post)

                    # Escalation if Confidence < 0.85
                    if not score_card.is_approved:
                        needs_review_count += 1
                        approval_req = ApprovalRequest(
                            tenant_id=self.tenant_id,
                            action_type="public_post",
                            channel=platform,
                            agent_name="Campaign OS",
                            resource_type="post",
                            resource_id=post.id,
                            title=f"Review Day {day_outline.day} {platform.title()} Post: {draft.hook[:40]}",
                            payload={
                                "content": draft.formatted_full_post,
                                "image_prompt": compiled_image_prompt,
                                "confidence": score_card.overall_confidence,
                                "unsupported_claims": score_card.unsupported_claims,
                                "compliance_issues": score_card.compliance_issues,
                            },
                            confidence=score_card.overall_confidence,
                            status="pending",
                            policy_reason="; ".join(score_card.unsupported_claims + score_card.compliance_issues) or "Confidence below threshold",
                        )
                        self.db.add(approval_req)
                        self.db.commit()
                    else:
                        approved_count += 1

                    generated_posts.append({
                        "post_id": post.id,
                        "day": day_outline.day,
                        "platform": platform,
                        "approved": score_card.is_approved,
                        "confidence": score_card.overall_confidence,
                        "image_prompt": compiled_image_prompt[:120] if compiled_image_prompt else None,
                    })

                except Exception as post_err:
                    logger.error(f"[CampaignOS] Error generating post for Day {day_outline.day} on {platform}: {post_err}")
                    # Graceful degradation: continue to next post without failing entire campaign
                    continue

        self.log_activity(
            "Campaign Generation Completed",
            f"Successfully generated {len(generated_posts)} posts ({approved_count} auto-approved, {needs_review_count} flagged for review).",
            status="success",
        )

        return {
            "status": "success",
            "campaign_title": narrative_arc.campaign_title,
            "total_posts_generated": len(generated_posts),
            "approved_count": approved_count,
            "needs_review_count": needs_review_count,
            "posts": generated_posts,
        }

    def log_activity(self, action: str, description: str, status: str = "success"):
        try:
            log = ActivityLog(
                tenant_id=self.tenant_id,
                agent_name="Campaign OS",
                action=action,
                description=description,
                status=status,
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.debug(f"[CampaignOS] Failed to log activity: {e}")
