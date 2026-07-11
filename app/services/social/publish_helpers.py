"""Synchronous helpers for Celery tasks."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from asgiref.sync import async_to_sync

from app.models.verticals import ContentPost
from app.models.teams import AgentMetric
from app.models.agents import ActivityLog
from app.services.social.publisher import publish_content_post


def apply_publish_result(db: Session, post: ContentPost, result, now: datetime) -> None:
    if result.success:
        log = ActivityLog(
            tenant_id=post.tenant_id,
            agent_name="Marketing AI",
            action="Publish Post",
            description=(
                f"Published to {post.platform.upper()} (Day {post.day}): "
                f"'{(post.content or '')[:60]}...' [id={result.external_id}]"
            ),
            status="success",
        )
        db.add(log)

        metric = (
            db.query(AgentMetric)
            .filter(
                AgentMetric.tenant_id == post.tenant_id,
                AgentMetric.metric_name == "posts_published",
            )
            .first()
        )
        if not metric:
            metric = AgentMetric(
                tenant_id=post.tenant_id, metric_name="posts_published", value=0.0
            )
            db.add(metric)
        metric.value += 1.0

        post.approval_status = "published"
        post.published_at = now
        post.status = "published"
        if getattr(result, "external_id", None):
            post.external_post_id = result.external_id
        # Seed learning tags at publish time
        try:
            from app.services.marketing.analytics import MarketingAnalyticsService
            post.learning_tags = MarketingAnalyticsService.extract_content_tags(
                post.content or "", post
            )
        except Exception:
            pass
    else:
        log = ActivityLog(
            tenant_id=post.tenant_id,
            agent_name="Marketing AI",
            action="Publish Post Failed",
            description=f"Failed posting to {post.platform.upper()}: {result.error[:300]}",
            status="failed",
        )
        db.add(log)
        post.status = "failed"


def publish_post_sync(db: Session, post: ContentPost) -> bool:
    now = datetime.now(timezone.utc)
    result = async_to_sync(publish_content_post)(db, post)
    apply_publish_result(db, post, result, now)
    db.commit()
    return result.success
