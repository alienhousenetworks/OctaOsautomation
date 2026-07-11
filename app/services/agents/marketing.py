from app.services.agents.base import BaseAgent
from app.models.verticals import ContentPost
from app.models.teams import AgentMetric

class MarketingAgent(BaseAgent):
    def __init__(self, db, tenant_id):
        super().__init__(db, tenant_id, "Marketing AI")

    async def execute_task(self, task: dict) -> dict:
        action = task.get("action")
        params = task.get("parameters", {})
        
        if action == "create_posts":
            return await self._create_posts(params)
        elif action == "generate_campaign":
            return await self._generate_campaign(params)
        elif action == "sync_analytics":
            return await self._sync_analytics(params)
        elif action == "learning_report":
            return await self._learning_report(params)
        return {"status": "Unknown action"}

    async def _generate_campaign(self, params: dict):
        from app.worker.tasks import generate_campaign_task
        # Full campaign with media by default (not text-only)
        payload = {
            "topic": params.get("topic", "our company"),
            "days": int(params.get("days", 7)),
            "platforms": params.get("platforms", ["linkedin", "instagram", "facebook"]),
            "text_provider": params.get("text_provider") or params.get("provider") or "gemini",
            "text_model": params.get("text_model") or params.get("model"),
            "image_provider": params.get("image_provider", "openai"),
            "video_provider": params.get("video_provider", "pika"),
            "generate_images": params.get("generate_images", True),
            # In-app video creation disabled until ready (settings.ENABLE_IN_APP_VIDEO)
            "generate_videos": False,
            "generate_remotion": False,
        }
        generate_campaign_task.delay(self.tenant_id, payload)
        days = payload["days"]
        self.log_activity(
            "Campaign Generation",
            f"Queued {days}-day multi-platform campaign with image generation + learning prompts.",
            status="pending",
        )
        return {
            "status": "queued",
            "message": f"{days}-day marketing campaign queued (text + images; learning-aware).",
            "params": payload,
        }

    async def _create_posts(self, params: dict):
        """Learning-aware short batch (uses campaign worker for media quality)."""
        days = int(params.get("days", 3))
        topic = params.get("topic", "our business")
        platforms = params.get("platforms", ["linkedin"])
        # Prefer full campaign pipeline so image gen + learning apply
        return await self._generate_campaign({
            "topic": topic,
            "days": days,
            "platforms": platforms,
            "generate_images": params.get("generate_images", True),
            "generate_videos": params.get("generate_videos", False),
            "text_provider": params.get("provider"),
            "text_model": params.get("model"),
            "image_provider": params.get("image_provider", "openai"),
        })

    async def _sync_analytics(self, params: dict):
        from app.services.marketing.analytics import MarketingAnalyticsService
        from asgiref.sync import async_to_sync
        svc = MarketingAnalyticsService(self.db, self.tenant_id)
        result = async_to_sync(svc.sync_all)(limit=int(params.get("limit", 50)))
        self.log_activity(
            "Analytics Sync",
            f"Synced insights: {result.get('synced')} ok, {result.get('errors')} errors, "
            f"{result.get('patterns_updated')} patterns.",
            status="success",
        )
        return result

    async def _learning_report(self, params: dict):
        from app.services.marketing.analytics import MarketingAnalyticsService
        dash = MarketingAnalyticsService(self.db, self.tenant_id).analytics_dashboard()
        self.log_activity("Learning Report", "Generated marketing performance learning dashboard.", status="success")
        return dash

    async def daily_routine(self):
        self.log_activity("Daily Routine", "Syncing post insights + learning patterns.", status="success")
        try:
            await self._sync_analytics({"limit": 40})
        except Exception as e:
            self.log_activity("Daily Analytics Failed", str(e)[:200], status="failed")
        # Light content generation for pipeline
        await self._create_posts({
            "days": 1,
            "topic": "daily brand awareness",
            "platforms": ["linkedin"],
            "generate_images": True,
        })
