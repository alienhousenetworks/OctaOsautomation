from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from asgiref.sync import async_to_sync

from app.api import deps
from app.core.rbac import Action, Resource, require_permission
from app.models.base import User
from app.schemas import verticals as schemas
from app.models import verticals as models

router = APIRouter()


class GenerateMediaRequest(BaseModel):
    media_type: str  # "image" or "video"
    prompt: str
    provider: Optional[str] = None
    sub_model: Optional[str] = None


class ApproveOptions(BaseModel):
    publish_now: bool = False


@router.post("/generate", response_model=schemas.ContentPost)
async def generate_content(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.EXECUTE)),
    topic: str,
    platform: str = "linkedin",
) -> Any:
    from app.services.verticals.marketing import MarketingService

    service = MarketingService(db, tenant_id)
    post = await service.generate_post(topic, platform)
    return post


@router.get("/", response_model=List[schemas.ContentPost])
def read_posts(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.READ)),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    posts = (
        db.query(models.ContentPost)
        .filter(models.ContentPost.tenant_id == tenant_id)
        .order_by(models.ContentPost.day.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return posts


@router.post("/campaign")
def trigger_campaign(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.CREATE)),
    campaign_in: schemas.CampaignCreate,
) -> Any:
    from app.worker.tasks import generate_campaign_task

    generate_campaign_task.delay(tenant_id, campaign_in.dict())
    return {"status": "queued", "message": "Campaign generation has been queued in the background."}


@router.put("/posts/{post_id}", response_model=schemas.ContentPost)
def update_post(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.UPDATE)),
    post_id: str,
    post_in: schemas.ContentPostBase,
) -> Any:
    post = (
        db.query(models.ContentPost)
        .filter(models.ContentPost.id == post_id, models.ContentPost.tenant_id == tenant_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.content = post_in.content
    post.platform = post_in.platform
    if post_in.image_url is not None:
        post.image_url = post_in.image_url
    if post_in.video_url is not None:
        post.video_url = post_in.video_url
    if post_in.scheduled_at is not None:
        post.scheduled_at = post_in.scheduled_at
    if post_in.media_prompt is not None:
        post.media_prompt = post_in.media_prompt
    if post_in.media_prompt_enabled is not None:
        post.media_prompt_enabled = post_in.media_prompt_enabled
    if post_in.image_prompt is not None:
        post.image_prompt = post_in.image_prompt
    if post_in.image_prompt_enabled is not None:
        post.image_prompt_enabled = post_in.image_prompt_enabled
    if post_in.video_prompt is not None:
        post.video_prompt = post_in.video_prompt
    if post_in.video_prompt_enabled is not None:
        post.video_prompt_enabled = post_in.video_prompt_enabled
    if post_in.remotion_prompt is not None:
        post.remotion_prompt = post_in.remotion_prompt
    if post_in.remotion_prompt_enabled is not None:
        post.remotion_prompt_enabled = post_in.remotion_prompt_enabled
    if hasattr(post_in, 'remotion_provider') and post_in.remotion_provider is not None:
        post.remotion_provider = post_in.remotion_provider
    if hasattr(post_in, 'remotion_model') and post_in.remotion_model is not None:
        post.remotion_model = post_in.remotion_model
    if post_in.is_manual_media is not None:
        post.is_manual_media = post_in.is_manual_media

    db.commit()
    db.refresh(post)
    return post


@router.post("/posts/create", response_model=schemas.ContentPost)
def create_manual_post(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.CREATE)),
    post_in: schemas.ContentPostCreate,
) -> Any:
    post = models.ContentPost(
        tenant_id=tenant_id,
        platform=post_in.platform,
        content=post_in.content,
        image_url=post_in.image_url,
        video_url=post_in.video_url,
        media_prompt=post_in.media_prompt,
        media_prompt_enabled=post_in.media_prompt_enabled,
        image_prompt=post_in.image_prompt,
        image_prompt_enabled=post_in.image_prompt_enabled,
        video_prompt=post_in.video_prompt,
        video_prompt_enabled=post_in.video_prompt_enabled,
        remotion_prompt=post_in.remotion_prompt,
        remotion_prompt_enabled=post_in.remotion_prompt_enabled,
        remotion_provider=getattr(post_in, 'remotion_provider', 'gemini'),
        remotion_model=getattr(post_in, 'remotion_model', 'gemini-2.5-flash'),
        is_manual_media=post_in.is_manual_media,
        day=post_in.day or 1,
        status="draft",
        approval_status="pending",
        scheduled_at=post_in.scheduled_at,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.post("/upload-media")
async def upload_media(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.CREATE)),
    file: UploadFile = File(...),
) -> Any:
    from app.services.media.storage import _write_bytes
    content = await file.read()
    url = _write_bytes(content, file.content_type, prefix="upload")
    return {"url": url}


@router.post("/posts/{post_id}/generate-media", response_model=schemas.ContentPost)
async def generate_media_for_post(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.CREATE)),
    post_id: str,
    req: GenerateMediaRequest,
) -> Any:
    post = (
        db.query(models.ContentPost)
        .filter(models.ContentPost.id == post_id, models.ContentPost.tenant_id == tenant_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    from app.services.llm_gateway import LLMGateway
    gateway = LLMGateway(db, tenant_id)

    if req.media_type == "video":
        provider = req.provider or "pika"
        video_url = await gateway.generate_video(req.prompt, provider=provider)
        if video_url.startswith("error:"):
            raise HTTPException(status_code=400, detail=video_url.replace("error:", ""))
        post.video_url = video_url
        post.image_url = None
        post.is_manual_media = False
        post.video_prompt = req.prompt
        post.video_prompt_enabled = True
    elif req.media_type == "remotion":
        from app.services.agents.video import VideoAgent
        import httpx
        from app.services.media.storage import ensure_public_url
        import os
        from app.models.video import VideoProject
        
        agent = VideoAgent(db, tenant_id)
        project = VideoProject(
            tenant_id=tenant_id,
            title=f"Post Video {post.id}",
            prompt=req.prompt,
            duration_seconds=15,
            llm_provider=req.provider or post.remotion_provider or "gemini",
            llm_model=req.sub_model or post.remotion_model or "gemini-2.5-flash"
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        res = await agent.plan_video(project.id)
        if res.get("status") == "success":
            blueprint = res.get("blueprint")
            with httpx.Client(timeout=300.0) as client:
                try:
                    resp = client.post("http://localhost:8002/render", json=blueprint)
                    if resp.status_code == 200:
                        data = resp.json()
                        local_file = data.get("file")
                        if local_file and os.path.exists(local_file):
                            with open(local_file, "rb") as f:
                                content = f.read()
                            from app.services.media.storage import _write_bytes
                            public_url = _write_bytes(content, "video/mp4", prefix="remotion")
                            post.video_url = public_url
                            post.image_url = None
                            post.is_manual_media = False
                            post.video_prompt = req.prompt
                            post.video_prompt_enabled = True
                        else:
                            raise HTTPException(status_code=500, detail="Failed to render remotion video")
                    else:
                        raise HTTPException(status_code=500, detail="Failed to communicate with renderer")
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Renderer error: {str(e)}")
        else:
            raise HTTPException(status_code=500, detail="Failed to plan video blueprint")
    else:
        provider = req.provider or "openai"
        image_url = await gateway.generate_image(req.prompt, provider=provider)
        if image_url.startswith("error:"):
            raise HTTPException(status_code=400, detail=image_url.replace("error:", ""))
        post.image_url = image_url
        post.video_url = None
        post.is_manual_media = False
        post.image_prompt = req.prompt
        post.image_prompt_enabled = True
    db.commit()
    db.refresh(post)
    return post


class SuggestPromptRequest(BaseModel):
    content: str
    media_type: str  # "image" or "video"


@router.post("/suggest-prompt")
async def suggest_prompt(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.CREATE)),
    req: SuggestPromptRequest,
) -> Any:
    from app.services.llm_gateway import LLMGateway
    gateway = LLMGateway(db, tenant_id)

    if req.media_type == "video":
        prompt = (
            f"Based on the following social media post text, write a detailed, highly descriptive prompt to generate a 5-second video loop/cinemagraph (e.g. for Pika, Runway, or Sora). "
            f"The video should match the tone and subject of the post. Keep the prompt descriptive, focused on visual actions, movement, lighting, and style. Do not write any introduction or explanation, only output the final prompt text itself.\n\n"
            f"Post Text:\n{req.content}"
        )
    else:
        prompt = (
            f"Based on the following social media post text, write a detailed, highly descriptive prompt to generate a high-quality illustration/photo/graphic (e.g. for Midjourney or DALL-E). "
            f"The image should visually represent the theme of the post. Describe the subject, composition, background, color palette, lighting, and style (e.g., modern photography, warm corporate style, minimalist illustration). Do not write any introduction or explanation, only output the final prompt text itself.\n\n"
            f"Post Text:\n{req.content}"
        )

    suggestion = await gateway.complete(
        prompt=prompt,
        provider="gemini",
        system_prompt="You are an expert AI prompt engineer specializing in generating highly effective prompts for Text-to-Image (DALL-E, Midjourney) and Text-to-Video (Pika, Runway, Sora) models based on social media content. Respond with only the prompt itself, clean of markdown formatting, quotes, intro, or wrap-up."
    )
    clean_suggestion = suggestion.strip().strip('"\'')
    return {"prompt": clean_suggestion}


def _schedule_post(post: models.ContentPost, publish_now: bool = False) -> None:
    now = datetime.now(timezone.utc)
    post.approval_status = "approved"
    if publish_now:
        post.scheduled_at = now
        post.status = "scheduled"
    else:
        if post.scheduled_at is None:
            day = post.day or 1
            scheduled = (now + timedelta(days=day)).replace(hour=9, minute=0, second=0, microsecond=0)
            if scheduled.tzinfo is None:
                scheduled = scheduled.replace(tzinfo=timezone.utc)
            post.scheduled_at = scheduled
        post.status = "approved"


@router.post("/posts/{post_id}/approve", response_model=schemas.ContentPost)
def approve_post(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.EXECUTE)),
    post_id: str,
    options: ApproveOptions = ApproveOptions(),
) -> Any:
    post = (
        db.query(models.ContentPost)
        .filter(models.ContentPost.id == post_id, models.ContentPost.tenant_id == tenant_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    _schedule_post(post, publish_now=options.publish_now)
    db.commit()
    db.refresh(post)

    if options.publish_now:
        from app.worker.tasks import publish_post_by_id

        publish_post_by_id.delay(post.id)

    return post


@router.post("/posts/{post_id}/publish-now")
def publish_post_now(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.EXECUTE)),
    post_id: str,
) -> Any:
    post = (
        db.query(models.ContentPost)
        .filter(models.ContentPost.id == post_id, models.ContentPost.tenant_id == tenant_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.approval_status = "approved"
    post.scheduled_at = datetime.now(timezone.utc)
    db.commit()

    from app.services.social.publish_helpers import publish_post_sync

    success = publish_post_sync(db, post)
    if not success:
        raise HTTPException(status_code=502, detail="Publishing failed. Check activity logs for details.")
    db.refresh(post)
    return {"status": "published", "post": schemas.ContentPost.model_validate(post)}


@router.post("/posts/{post_id}/reject", response_model=schemas.ContentPost)
def reject_post(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.EXECUTE)),
    post_id: str,
) -> Any:
    post = (
        db.query(models.ContentPost)
        .filter(models.ContentPost.id == post_id, models.ContentPost.tenant_id == tenant_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post_data = schemas.ContentPost.model_validate(post)
    db.delete(post)
    db.commit()
    return post_data


@router.post("/posts/approve-all")
def approve_all_posts(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.EXECUTE)),
    options: ApproveOptions = ApproveOptions(),
) -> Any:
    posts = (
        db.query(models.ContentPost)
        .filter(
            models.ContentPost.tenant_id == tenant_id,
            models.ContentPost.approval_status == "pending",
        )
        .all()
    )

    for post in posts:
        _schedule_post(post, publish_now=options.publish_now)

    db.commit()

    if options.publish_now:
        from app.worker.tasks import publish_scheduled_posts

        publish_scheduled_posts.delay()

    return {"message": f"Successfully approved and scheduled {len(posts)} posts."}


class BulkScheduleRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    posting_time: str


@router.post("/posts/bulk-schedule")
def bulk_schedule_posts(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.CREATE)),
    req: BulkScheduleRequest,
) -> Any:
    if req.end_date < req.start_date:
        raise HTTPException(status_code=400, detail="End date must be on or after start date")

    # Get all posts that are not published
    posts = (
        db.query(models.ContentPost)
        .filter(
            models.ContentPost.tenant_id == tenant_id,
            models.ContentPost.approval_status != "published",
            models.ContentPost.status != "published",
        )
        .order_by(models.ContentPost.day.asc(), models.ContentPost.created_at.asc())
        .all()
    )

    if not posts:
        return {"message": "No pending or draft posts found to schedule."}

    try:
        hour, minute = map(int, req.posting_time.split(":"))
    except Exception:
        hour, minute = 9, 0

    n = len(posts)
    if n == 1:
        scheduled_time = req.start_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled_time.tzinfo is None:
            scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)
        posts[0].scheduled_at = scheduled_time
        posts[0].approval_status = "approved"
        posts[0].status = "approved"
    else:
        duration = req.end_date - req.start_date
        total_seconds = duration.total_seconds()
        step_seconds = total_seconds / (n - 1)
        for i, post in enumerate(posts):
            current_dt = req.start_date + timedelta(seconds=i * step_seconds)
            scheduled_time = current_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if scheduled_time.tzinfo is None:
                scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)
            post.scheduled_at = scheduled_time
            post.approval_status = "approved"
            post.status = "approved"

    db.commit()
    return {"message": f"Successfully bulk scheduled {n} posts."}


# ── Analytics + learning loop ────────────────────────────────────────────────

@router.get("/analytics/dashboard")
def marketing_analytics_dashboard(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.READ)),
) -> Any:
    from app.services.marketing.analytics import MarketingAnalyticsService
    return MarketingAnalyticsService(db, tenant_id).analytics_dashboard()


@router.post("/analytics/sync")
async def sync_marketing_analytics(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.EXECUTE)),
    limit: int = 50,
    background: bool = True,
) -> Any:
    """Pull impressions/engagement from Meta & LinkedIn and update learning patterns."""
    if background:
        from app.worker.tasks import sync_marketing_insights_task
        sync_marketing_insights_task.delay(tenant_id, limit)
        return {"status": "queued", "message": "Analytics sync started in background"}
    from app.services.marketing.analytics import MarketingAnalyticsService
    return await MarketingAnalyticsService(db, tenant_id).sync_all(limit=limit)


@router.post("/analytics/sync/{post_id}")
async def sync_single_post_analytics(
    post_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.EXECUTE)),
) -> Any:
    post = (
        db.query(models.ContentPost)
        .filter(models.ContentPost.id == post_id, models.ContentPost.tenant_id == tenant_id)
        .first()
    )
    if not post:
        raise HTTPException(404, "Post not found")
    from app.services.marketing.analytics import MarketingAnalyticsService
    return await MarketingAnalyticsService(db, tenant_id).sync_post(post)


@router.post("/analytics/rebuild-learning")
def rebuild_marketing_learning(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.EXECUTE)),
) -> Any:
    from app.services.marketing.analytics import MarketingAnalyticsService
    n = MarketingAnalyticsService(db, tenant_id).rebuild_learning_patterns()
    return {"status": "ok", "patterns_updated": n}


@router.get("/analytics/learning-prompt")
def get_learning_prompt(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.READ)),
    platform: Optional[str] = None,
) -> Any:
    from app.services.marketing.analytics import MarketingAnalyticsService
    block = MarketingAnalyticsService(db, tenant_id).learning_prompt_block(platform)
    return {"platform": platform, "learning_prompt": block}


@router.get("/posts/{post_id}/insights")
def get_post_insights(
    post_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.READ)),
) -> Any:
    post = (
        db.query(models.ContentPost)
        .filter(models.ContentPost.id == post_id, models.ContentPost.tenant_id == tenant_id)
        .first()
    )
    if not post:
        raise HTTPException(404, "Post not found")
    from app.models.verticals import MarketingInsightSnapshot
    snaps = (
        db.query(MarketingInsightSnapshot)
        .filter(
            MarketingInsightSnapshot.post_id == post_id,
            MarketingInsightSnapshot.tenant_id == tenant_id,
        )
        .order_by(MarketingInsightSnapshot.captured_at.desc())
        .limit(30)
        .all()
    )
    return {
        "post_id": post.id,
        "platform": post.platform,
        "external_post_id": post.external_post_id,
        "current": {
            "impressions": post.impressions,
            "reach": post.reach,
            "engagement": post.engagement,
            "likes": post.likes,
            "comments": post.comments,
            "shares": post.shares,
            "clicks": post.clicks,
            "ctr": post.ctr,
            "engagement_rate": post.engagement_rate,
            "performance_score": post.performance_score,
            "learning_tags": post.learning_tags,
            "synced_at": post.insights_synced_at,
        },
        "history": [
            {
                "impressions": s.impressions,
                "engagement": s.engagement,
                "ctr": s.ctr,
                "engagement_rate": s.engagement_rate,
                "captured_at": s.captured_at,
            }
            for s in snaps
        ],
    }
