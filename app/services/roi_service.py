"""ROI dashboards: cost per meeting, cost per ticket, hours saved, quality samples."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.base import ProviderUsage
from app.models.enterprise import OutcomeEvent
from app.models.learning import DecisionRecord
from app.models.verticals import Lead, ContentPost


class ROIService:
    # Conservative hours-saved assumptions for automation
    HOURS_PER = {
        "meeting_booked": 1.5,
        "reply_received": 0.25,
        "ticket_csat": 0.35,
        "post_engagement": 0.75,
        "conversion": 2.0,
        "first_touch_sent": 0.2,
    }
    HOURLY_COST_USD = 25.0  # default blended

    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def dashboard(self) -> Dict[str, Any]:
        spend = (
            self.db.query(func.coalesce(func.sum(ProviderUsage.cost), 0.0))
            .filter(ProviderUsage.tenant_id == self.tenant_id)
            .scalar()
        ) or 0.0

        outcomes = (
            self.db.query(
                OutcomeEvent.outcome_type,
                func.count(OutcomeEvent.id),
                func.coalesce(func.sum(OutcomeEvent.value), 0.0),
            )
            .filter(OutcomeEvent.tenant_id == self.tenant_id)
            .group_by(OutcomeEvent.outcome_type)
            .all()
        )
        by_type = {r[0]: {"count": int(r[1]), "value_sum": float(r[2])} for r in outcomes}

        meetings = by_type.get("meeting_booked", {}).get("count", 0)
        tickets = by_type.get("ticket_csat", {}).get("count", 0) or by_type.get(
            "ticket_resolved", {}
        ).get("count", 0)

        cost_per_meeting = (float(spend) / meetings) if meetings else None
        cost_per_ticket = (float(spend) / tickets) if tickets else None

        hours_saved = 0.0
        for otype, data in by_type.items():
            hours_saved += data["count"] * self.HOURS_PER.get(otype, 0.1)

        labor_value = hours_saved * self.HOURLY_COST_USD
        net_roi = labor_value - float(spend)
        roi_multiple = (labor_value / float(spend)) if spend else None

        # quality samples: recent decisions with outcomes
        samples = (
            self.db.query(DecisionRecord)
            .filter(DecisionRecord.tenant_id == self.tenant_id)
            .order_by(DecisionRecord.timestamp.desc())
            .limit(10)
            .all()
        )
        quality_samples = [
            {
                "id": s.id,
                "agent": s.agent_name,
                "task_type": s.task_type,
                "strategy": s.strategy_used,
                "confidence": s.confidence_score,
                "quality_score": s.quality_score,
                "result_status": s.result_status,
                "signals": s.behavioral_signals,
            }
            for s in samples
        ]

        leads_count = (
            self.db.query(func.count(Lead.id))
            .filter(Lead.tenant_id == self.tenant_id)
            .scalar()
            or 0
        )
        posts_count = (
            self.db.query(func.count(ContentPost.id))
            .filter(ContentPost.tenant_id == self.tenant_id)
            .scalar()
            or 0
        )

        return {
            "tenant_id": self.tenant_id,
            "ai_spend_usd": float(spend),
            "outcomes": by_type,
            "cost_per_meeting_usd": cost_per_meeting,
            "cost_per_resolved_ticket_usd": cost_per_ticket,
            "hours_saved": round(hours_saved, 2),
            "labor_value_usd": round(labor_value, 2),
            "net_roi_usd": round(net_roi, 2),
            "roi_multiple": round(roi_multiple, 2) if roi_multiple else None,
            "volume": {"leads": leads_count, "posts": posts_count},
            "quality_samples": quality_samples,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def monthly_pdf_payload(self) -> Dict[str, Any]:
        """Structured payload for CFO monthly ROI report (render client-side or PDF later)."""
        dash = self.dashboard()
        return {
            "title": "OctaOS Monthly ROI Report",
            "period": datetime.now(timezone.utc).strftime("%Y-%m"),
            "summary": {
                "ai_spend_usd": dash["ai_spend_usd"],
                "hours_saved": dash["hours_saved"],
                "labor_value_usd": dash["labor_value_usd"],
                "net_roi_usd": dash["net_roi_usd"],
                "roi_multiple": dash["roi_multiple"],
            },
            "unit_economics": {
                "cost_per_meeting_usd": dash["cost_per_meeting_usd"],
                "cost_per_ticket_usd": dash["cost_per_resolved_ticket_usd"],
            },
            "outcomes": dash["outcomes"],
            "quality_samples": dash["quality_samples"][:5],
            "notes": [
                "Hours saved use conservative automation assumptions.",
                "Labor value assumes blended fully-loaded cost of $25/hr (override per tenant later).",
                "AI spend is BYO provider usage tracked on-platform.",
            ],
        }
