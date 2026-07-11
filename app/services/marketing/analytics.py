"""Fetch post insights from Meta (FB/IG) and LinkedIn; store + score performance."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.verticals import ContentPost, MarketingInsightSnapshot, MarketingLearningPattern
from app.models.base import APICredential
from app.core.security import decrypt_api_key
from app.services.social.meta_client import MetaGraphClient, GRAPH_BASE
from app.services.social.linkedin_client import LinkedInClient
from app.services.credentials import get_decrypted_credential

logger = logging.getLogger(__name__)


def _metric_map_from_meta_insights(data: list) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for row in data or []:
        name = (row.get("name") or "").lower()
        values = row.get("values") or []
        val = 0.0
        if values:
            v = values[-1].get("value")
            if isinstance(v, dict):
                # some metrics return breakdowns
                val = float(sum(float(x) for x in v.values() if isinstance(x, (int, float))))
            else:
                try:
                    val = float(v or 0)
                except (TypeError, ValueError):
                    val = 0.0
        out[name] = val
    return out


def compute_performance_score(
    *,
    impressions: float,
    engagement: float,
    clicks: float,
    engagement_rate: float,
    ctr: float,
) -> float:
    """0-100 score blending volume + rates (log-damped impressions)."""
    import math
    vol = min(40.0, math.log10(max(impressions, 1.0) + 1) * 12)
    eng = min(35.0, engagement_rate * 350)  # 10% ER → 35
    click = min(25.0, ctr * 500)  # 5% CTR → 25
    return round(max(0.0, min(100.0, vol + eng + click)), 2)


class MarketingAnalyticsService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def list_published(self, limit: int = 100) -> List[ContentPost]:
        return (
            self.db.query(ContentPost)
            .filter(
                ContentPost.tenant_id == self.tenant_id,
                ContentPost.status == "published",
            )
            .order_by(ContentPost.published_at.desc().nulls_last())
            .limit(limit)
            .all()
        )

    async def sync_post(self, post: ContentPost) -> Dict[str, Any]:
        platform = (post.platform or "").lower()
        if not post.external_post_id:
            return {"status": "skipped", "reason": "no_external_post_id", "post_id": post.id}

        try:
            if platform in ("facebook", "fb", "meta"):
                metrics = await self._fetch_facebook(post.external_post_id)
            elif platform in ("instagram", "ig", "instagram_business"):
                metrics = await self._fetch_instagram(post.external_post_id)
            elif platform in ("linkedin", "li"):
                metrics = await self._fetch_linkedin(post.external_post_id)
            else:
                return {"status": "skipped", "reason": f"unsupported_platform:{platform}", "post_id": post.id}
        except Exception as e:
            logger.warning("Insights fetch failed for %s: %s", post.id, e)
            return {"status": "error", "post_id": post.id, "error": str(e)[:300]}

        self._apply_metrics(post, metrics)
        self.db.commit()
        return {"status": "ok", "post_id": post.id, "metrics": metrics}

    async def sync_all(self, limit: int = 50) -> Dict[str, Any]:
        posts = self.list_published(limit=limit)
        results = []
        for p in posts:
            if p.external_post_id:
                results.append(await self.sync_post(p))
        # Rebuild learning patterns after sync
        patterns = self.rebuild_learning_patterns()
        return {
            "synced": len([r for r in results if r.get("status") == "ok"]),
            "errors": len([r for r in results if r.get("status") == "error"]),
            "skipped": len([r for r in results if r.get("status") == "skipped"]),
            "patterns_updated": patterns,
            "results": results[:20],
        }

    def _apply_metrics(self, post: ContentPost, m: Dict[str, float]) -> None:
        impressions = float(m.get("impressions") or 0)
        reach = float(m.get("reach") or 0)
        likes = float(m.get("likes") or 0)
        comments = float(m.get("comments") or 0)
        shares = float(m.get("shares") or 0)
        clicks = float(m.get("clicks") or 0)
        engagement = float(m.get("engagement") or (likes + comments + shares))
        ctr = (clicks / impressions) if impressions > 0 else 0.0
        er = (engagement / impressions) if impressions > 0 else 0.0
        score = compute_performance_score(
            impressions=impressions,
            engagement=engagement,
            clicks=clicks,
            engagement_rate=er,
            ctr=ctr,
        )

        post.impressions = impressions
        post.reach = reach
        post.likes = likes
        post.comments = comments
        post.shares = shares
        post.clicks = clicks
        post.engagement = engagement
        post.ctr = round(ctr, 6)
        post.engagement_rate = round(er, 6)
        post.performance_score = score
        post.insights_raw = m
        post.insights_synced_at = datetime.now(timezone.utc)
        post.learning_tags = self.extract_content_tags(post.content or "", post)

        snap = MarketingInsightSnapshot(
            tenant_id=self.tenant_id,
            post_id=post.id,
            platform=post.platform,
            impressions=impressions,
            reach=reach,
            engagement=engagement,
            likes=likes,
            comments=comments,
            shares=shares,
            clicks=clicks,
            ctr=post.ctr,
            engagement_rate=post.engagement_rate,
            raw=m,
        )
        self.db.add(snap)

    async def _fetch_facebook(self, external_id: str) -> Dict[str, float]:
        token, settings = get_decrypted_credential(self.db, self.tenant_id, "meta")
        if not token:
            raise RuntimeError("Meta credentials not configured")
        client = MetaGraphClient(token, settings or {})
        # Prefer page token when available
        page_token = (settings or {}).get("page_access_token") or token
        page_client = MetaGraphClient(page_token, settings or {})

        metrics_wanted = [
            "post_impressions",
            "post_impressions_unique",
            "post_engaged_users",
            "post_clicks",
            "post_reactions_by_type_total",
        ]
        try:
            data = await page_client._get(
                f"{external_id}/insights",
                {"metric": ",".join(metrics_wanted), "period": "lifetime"},
            )
            mapped = _metric_map_from_meta_insights(data.get("data") or [])
        except Exception:
            mapped = {}

        # Engagement object
        try:
            eng = await page_client._get(
                external_id,
                {"fields": "shares,likes.summary(true),comments.summary(true)"},
            )
        except Exception:
            eng = {}

        likes = float((eng.get("likes") or {}).get("summary", {}).get("total_count") or 0)
        comments = float((eng.get("comments") or {}).get("summary", {}).get("total_count") or 0)
        shares = float((eng.get("shares") or {}).get("count") or 0)
        impressions = mapped.get("post_impressions") or mapped.get("post_impressions_unique") or 0
        clicks = mapped.get("post_clicks") or 0
        engaged = mapped.get("post_engaged_users") or (likes + comments + shares)

        return {
            "impressions": impressions,
            "reach": mapped.get("post_impressions_unique") or impressions,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "clicks": clicks,
            "engagement": engaged,
            "source": "facebook_insights",
        }

    async def _fetch_instagram(self, external_id: str) -> Dict[str, float]:
        token, settings = get_decrypted_credential(self.db, self.tenant_id, "meta")
        if not token:
            raise RuntimeError("Meta credentials not configured")
        page_token = (settings or {}).get("page_access_token") or token
        client = MetaGraphClient(page_token, settings or {})

        metric_names = [
            "impressions",
            "reach",
            "likes",
            "comments",
            "shares",
            "saved",
            "plays",
            "total_interactions",
        ]
        try:
            data = await client._get(
                f"{external_id}/insights",
                {"metric": ",".join(metric_names)},
            )
            mapped = _metric_map_from_meta_insights(data.get("data") or [])
        except Exception as e:
            # Older media may only support subset
            logger.info("IG insights partial: %s", e)
            mapped = {}

        try:
            basic = await client._get(
                external_id,
                {"fields": "like_count,comments_count,media_type,permalink"},
            )
        except Exception:
            basic = {}

        likes = float(mapped.get("likes") or basic.get("like_count") or 0)
        comments = float(mapped.get("comments") or basic.get("comments_count") or 0)
        shares = float(mapped.get("shares") or 0)
        saves = float(mapped.get("saved") or 0)
        impressions = float(mapped.get("impressions") or mapped.get("plays") or 0)
        reach = float(mapped.get("reach") or impressions)
        engagement = float(mapped.get("total_interactions") or (likes + comments + shares + saves))

        return {
            "impressions": impressions,
            "reach": reach,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "clicks": 0.0,  # IG organic CTR less standardized
            "engagement": engagement,
            "source": "instagram_insights",
            "permalink": basic.get("permalink"),
        }

    async def _fetch_linkedin(self, external_id: str) -> Dict[str, float]:
        token, settings = get_decrypted_credential(self.db, self.tenant_id, "linkedin")
        if not token:
            raise RuntimeError("LinkedIn credentials not configured")

        # external_id may be URN or bare id
        urn = external_id
        if not str(external_id).startswith("urn:"):
            urn = f"urn:li:share:{external_id}"

        headers = {
            "Authorization": f"Bearer {token}",
            "LinkedIn-Version": "202405",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        # Organizational entity share statistics (requires r_organization_social / analytics products)
        encoded = httpx.URL(urn).raw_path.decode() if False else urn.replace(":", "%3A")
        # Use socialActions + shareStatistics when available
        async with httpx.AsyncClient(timeout=60.0) as client:
            impressions = 0.0
            clicks = 0.0
            likes = 0.0
            comments = 0.0
            shares = 0.0

            # Try ugcPosts / shares stats endpoint
            stats_url = (
                "https://api.linkedin.com/rest/organizationalEntityShareStatistics"
                f"?q=organizationalEntity&organizationalEntity={settings.get('organization_urn', '')}"
            )
            try:
                if settings.get("organization_urn"):
                    resp = await client.get(stats_url, headers=headers)
                    if resp.status_code == 200:
                        elements = resp.json().get("elements") or []
                        for el in elements:
                            share = el.get("share") or el.get("ugcPost") or ""
                            if external_id in str(share) or urn in str(share):
                                tot = el.get("totalShareStatistics") or {}
                                impressions = float(tot.get("impressionCount") or 0)
                                clicks = float(tot.get("clickCount") or 0)
                                likes = float(tot.get("likeCount") or 0)
                                comments = float(tot.get("commentCount") or 0)
                                shares = float(tot.get("shareCount") or 0)
                                break
            except Exception as e:
                logger.info("LinkedIn org stats: %s", e)

            # Fallback: socialActions for reactions
            try:
                sa = await client.get(
                    f"https://api.linkedin.com/v2/socialActions/{encoded}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if sa.status_code == 200:
                    body = sa.json()
                    likes = likes or float((body.get("likesSummary") or {}).get("totalLikes") or 0)
                    comments = comments or float((body.get("commentsSummary") or {}).get("totalFirstLevelComments") or 0)
            except Exception:
                pass

        engagement = likes + comments + shares
        return {
            "impressions": impressions,
            "reach": impressions,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "clicks": clicks,
            "engagement": engagement,
            "source": "linkedin_stats",
        }

    @staticmethod
    def extract_content_tags(content: str, post: Optional[ContentPost] = None) -> List[str]:
        tags: List[str] = []
        text = (content or "").strip()
        if not text:
            return tags
        if text.endswith("?"):
            tags.append("question_hook")
        if re.search(r"^(how|why|what|when|who)\b", text.lower()):
            tags.append("question_open")
        if len(text) < 120:
            tags.append("short_copy")
        elif len(text) > 400:
            tags.append("long_copy")
        else:
            tags.append("medium_copy")
        if re.search(r"\b(dm|comment|link|book|call|today|now)\b", text.lower()):
            tags.append("strong_cta")
        if re.search(r"[😀-🙏🚀💡✅🔥]", text):
            tags.append("uses_emoji")
        if text.count("#") >= 2:
            tags.append("hashtags")
        if post:
            if post.image_url and not str(post.image_url).startswith("error:"):
                tags.append("with_image")
            if post.video_url and not str(post.video_url).startswith("error:"):
                tags.append("with_video")
            if post.platform:
                tags.append(f"platform_{(post.platform or '').lower()}")
        return tags

    def rebuild_learning_patterns(self) -> int:
        posts = (
            self.db.query(ContentPost)
            .filter(
                ContentPost.tenant_id == self.tenant_id,
                ContentPost.status == "published",
                ContentPost.impressions > 0,
            )
            .all()
        )
        # aggregate by (platform, tag)
        buckets: Dict[tuple, Dict[str, Any]] = {}
        for p in posts:
            tags = p.learning_tags or self.extract_content_tags(p.content or "", p)
            platform = (p.platform or "all").lower()
            for tag in tags:
                key = (platform, tag)
                b = buckets.setdefault(
                    key,
                    {"ers": [], "ctrs": [], "scores": [], "examples": []},
                )
                b["ers"].append(float(p.engagement_rate or 0))
                b["ctrs"].append(float(p.ctr or 0))
                b["scores"].append(float(p.performance_score or 0))
                if p.content and len(b["examples"]) < 3:
                    b["examples"].append((p.content or "")[:180])

        # baseline overall ER for weight
        all_ers = [float(p.engagement_rate or 0) for p in posts]
        baseline = (sum(all_ers) / len(all_ers)) if all_ers else 0.0

        updated = 0
        for (platform, tag), b in buckets.items():
            n = len(b["ers"])
            if n < 1:
                continue
            avg_er = sum(b["ers"]) / n
            avg_ctr = sum(b["ctrs"]) / n
            avg_score = sum(b["scores"]) / n
            weight = (avg_er - baseline) * 100  # positive = good
            banned = n >= 3 and avg_er < baseline * 0.4 and avg_score < 25

            pattern_type = "hook_style"
            if tag in ("with_image", "with_video", "short_copy", "long_copy", "medium_copy"):
                pattern_type = "format"
            elif tag == "strong_cta":
                pattern_type = "cta"
            elif tag.startswith("platform_"):
                pattern_type = "platform"

            existing = (
                self.db.query(MarketingLearningPattern)
                .filter(
                    MarketingLearningPattern.tenant_id == self.tenant_id,
                    MarketingLearningPattern.platform == platform,
                    MarketingLearningPattern.pattern_key == tag,
                )
                .first()
            )
            if not existing:
                existing = MarketingLearningPattern(
                    tenant_id=self.tenant_id,
                    platform=platform,
                    pattern_type=pattern_type,
                    pattern_key=tag,
                )
                self.db.add(existing)
            existing.sample_count = n
            existing.avg_engagement_rate = avg_er
            existing.avg_ctr = avg_ctr
            existing.avg_performance_score = avg_score
            existing.weight = round(weight, 4)
            existing.examples = b["examples"]
            existing.banned = banned
            existing.pattern_type = pattern_type
            updated += 1

        self.db.commit()
        return updated

    def learning_prompt_block(self, platform: Optional[str] = None) -> str:
        """Text injected into generation prompts so the model favors winners."""
        q = self.db.query(MarketingLearningPattern).filter(
            MarketingLearningPattern.tenant_id == self.tenant_id
        )
        if platform:
            q = q.filter(
                (MarketingLearningPattern.platform == platform.lower())
                | (MarketingLearningPattern.platform == "all")
                | (MarketingLearningPattern.platform.is_(None))
            )
        patterns = q.order_by(MarketingLearningPattern.weight.desc()).limit(40).all()
        if not patterns:
            return (
                "No historical performance data yet. Prefer clear hooks, one strong CTA, "
                "and platform-native length. Avoid generic corporate fluff."
            )

        boosts = [p for p in patterns if p.weight > 0 and not p.banned][:8]
        avoids = [p for p in patterns if p.banned or p.weight < -0.5][:6]

        lines = ["LEARNED PERFORMANCE RULES (from our real published posts):"]
        if boosts:
            lines.append("DO MORE OF:")
            for p in boosts:
                lines.append(
                    f"- {p.pattern_key} (weight {p.weight:.2f}, "
                    f"avg ER {p.avg_engagement_rate*100:.2f}%, n={p.sample_count})"
                )
                if p.examples:
                    lines.append(f"  example: {p.examples[0][:120]}")
        if avoids:
            lines.append("AVOID:")
            for p in avoids:
                lines.append(
                    f"- {p.pattern_key} (underperforming, avg ER {p.avg_engagement_rate*100:.2f}%)"
                )
        lines.append(
            "Write a fresh post that applies the DO MORE patterns and avoids the AVOID patterns."
        )
        return "\n".join(lines)

    def analytics_dashboard(self) -> Dict[str, Any]:
        posts = (
            self.db.query(ContentPost)
            .filter(ContentPost.tenant_id == self.tenant_id)
            .all()
        )
        published = [p for p in posts if p.status == "published"]
        with_metrics = [p for p in published if (p.impressions or 0) > 0]
        total_impr = sum(float(p.impressions or 0) for p in published)
        total_eng = sum(float(p.engagement or 0) for p in published)
        total_clicks = sum(float(p.clicks or 0) for p in published)
        avg_er = (
            sum(float(p.engagement_rate or 0) for p in with_metrics) / len(with_metrics)
            if with_metrics
            else 0.0
        )
        avg_ctr = (
            sum(float(p.ctr or 0) for p in with_metrics) / len(with_metrics)
            if with_metrics
            else 0.0
        )
        top = sorted(published, key=lambda p: float(p.performance_score or 0), reverse=True)[:10]
        patterns = (
            self.db.query(MarketingLearningPattern)
            .filter(MarketingLearningPattern.tenant_id == self.tenant_id)
            .order_by(MarketingLearningPattern.weight.desc())
            .limit(20)
            .all()
        )
        return {
            "totals": {
                "posts": len(posts),
                "published": len(published),
                "with_metrics": len(with_metrics),
                "impressions": total_impr,
                "engagement": total_eng,
                "clicks": total_clicks,
                "avg_engagement_rate": round(avg_er, 6),
                "avg_ctr": round(avg_ctr, 6),
            },
            "top_posts": [
                {
                    "id": p.id,
                    "platform": p.platform,
                    "content": (p.content or "")[:160],
                    "impressions": p.impressions,
                    "engagement": p.engagement,
                    "engagement_rate": p.engagement_rate,
                    "ctr": p.ctr,
                    "performance_score": p.performance_score,
                    "learning_tags": p.learning_tags,
                    "external_post_id": p.external_post_id,
                    "published_at": p.published_at.isoformat() if p.published_at else None,
                }
                for p in top
            ],
            "learning_patterns": [
                {
                    "platform": p.platform,
                    "pattern_type": p.pattern_type,
                    "pattern_key": p.pattern_key,
                    "weight": p.weight,
                    "sample_count": p.sample_count,
                    "avg_engagement_rate": p.avg_engagement_rate,
                    "avg_ctr": p.avg_ctr,
                    "banned": p.banned,
                    "examples": p.examples,
                }
                for p in patterns
            ],
        }
