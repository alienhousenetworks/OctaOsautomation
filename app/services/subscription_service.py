"""Subscription plans, entitlements, seats, action quotas."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.base import User
from app.models.enterprise import (
    ActionUsageCounter,
    SubscriptionPlan,
    TenantBudgetCap,
    TenantSubscription,
)

DEFAULT_PLANS = [
    {
        "code": "starter",
        "name": "Starter",
        "price_usd_monthly": 399.0,
        "price_inr_monthly": 14999.0,
        "seat_limit": 3,
        "action_quota_monthly": 5000,
        "allowed_agents": ["sales", "support"],
        "feature_flags": {
            "crm_sync": False,
            "sso": False,
            "roi_pdf": False,
            "mfa": True,
            "approvals": True,
        },
    },
    {
        "code": "growth",
        "name": "Growth",
        "price_usd_monthly": 1499.0,
        "price_inr_monthly": 49999.0,
        "seat_limit": 15,
        "action_quota_monthly": 25000,
        "allowed_agents": ["sales", "marketing", "support", "hr"],
        "feature_flags": {
            "crm_sync": True,
            "sso": False,
            "roi_pdf": True,
            "mfa": True,
            "approvals": True,
        },
    },
    {
        "code": "business",
        "name": "Business",
        "price_usd_monthly": 3999.0,
        "price_inr_monthly": 149999.0,
        "seat_limit": 50,
        "action_quota_monthly": 100000,
        "allowed_agents": ["sales", "marketing", "support", "hr", "ceo", "finance"],
        "feature_flags": {
            "crm_sync": True,
            "sso": True,
            "roi_pdf": True,
            "mfa": True,
            "approvals": True,
            "audit_export": True,
        },
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "price_usd_monthly": 12000.0,
        "price_inr_monthly": 999999.0,
        "seat_limit": None,
        "action_quota_monthly": 500000,
        "allowed_agents": ["*"],
        "feature_flags": {
            "crm_sync": True,
            "sso": True,
            "roi_pdf": True,
            "mfa": True,
            "approvals": True,
            "audit_export": True,
            "dedicated_env": True,
            "sla": True,
        },
    },
]


class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db

    def seed_plans(self) -> List[SubscriptionPlan]:
        plans = []
        for p in DEFAULT_PLANS:
            existing = (
                self.db.query(SubscriptionPlan)
                .filter(SubscriptionPlan.code == p["code"])
                .first()
            )
            if existing:
                plans.append(existing)
                continue
            plan = SubscriptionPlan(**p)
            self.db.add(plan)
            plans.append(plan)
        self.db.commit()
        return plans

    def get_plan(self, code: str) -> Optional[SubscriptionPlan]:
        return self.db.query(SubscriptionPlan).filter(SubscriptionPlan.code == code).first()

    def list_plans(self) -> List[SubscriptionPlan]:
        self.seed_plans()
        return (
            self.db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.is_active == True)  # noqa: E712
            .all()
        )

    def get_subscription(self, tenant_id: str) -> Optional[TenantSubscription]:
        return (
            self.db.query(TenantSubscription)
            .filter(TenantSubscription.tenant_id == tenant_id)
            .first()
        )

    def ensure_trial(self, tenant_id: str, plan_code: str = "starter") -> TenantSubscription:
        existing = self.get_subscription(tenant_id)
        if existing:
            return existing
        self.seed_plans()
        plan = self.get_plan(plan_code) or self.get_plan("starter")
        now = datetime.now(timezone.utc)
        sub = TenantSubscription(
            tenant_id=tenant_id,
            plan_id=plan.id,
            status="trialing",
            trial_ends_at=now + timedelta(days=14),
            current_period_start=now,
            current_period_end=now + timedelta(days=14),
            seats_used=1,
            actions_used_period=0,
        )
        self.db.add(sub)
        # default budget cap
        if not self.db.query(TenantBudgetCap).filter(TenantBudgetCap.tenant_id == tenant_id).first():
            self.db.add(
                TenantBudgetCap(
                    tenant_id=tenant_id,
                    monthly_spend_usd=500.0,
                    monthly_action_cap=plan.action_quota_monthly or 10000,
                    hard_stop=True,
                )
            )
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def change_plan(self, tenant_id: str, plan_code: str) -> TenantSubscription:
        self.seed_plans()
        plan = self.get_plan(plan_code)
        if not plan:
            raise ValueError(f"Unknown plan: {plan_code}")
        sub = self.ensure_trial(tenant_id)
        sub.plan_id = plan.id
        sub.status = "active"
        now = datetime.now(timezone.utc)
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=30)
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def entitlements(self, tenant_id: str) -> Dict[str, Any]:
        sub = self.ensure_trial(tenant_id)
        plan = self.db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.plan_id).first()
        seats = self.db.query(User).filter(User.tenant_id == tenant_id, User.is_active == True).count()  # noqa: E712
        sub.seats_used = seats
        self.db.commit()

        flags = dict(plan.feature_flags or {})
        flags.update(sub.feature_overrides or {})
        return {
            "tenant_id": tenant_id,
            "status": sub.status,
            "plan": {
                "code": plan.code,
                "name": plan.name,
                "price_usd_monthly": plan.price_usd_monthly,
                "price_inr_monthly": plan.price_inr_monthly,
            },
            "seat_limit": plan.seat_limit,
            "seats_used": seats,
            "action_quota_monthly": plan.action_quota_monthly,
            "actions_used_period": sub.actions_used_period,
            "allowed_agents": plan.allowed_agents,
            "feature_flags": flags,
            "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        }

    def _period_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def check_action_allowed(self, tenant_id: str, cost_usd: float = 0.0) -> Dict[str, Any]:
        sub = self.ensure_trial(tenant_id)
        plan = self.db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.plan_id).first()
        cap = (
            self.db.query(TenantBudgetCap)
            .filter(TenantBudgetCap.tenant_id == tenant_id)
            .first()
        )
        counter = (
            self.db.query(ActionUsageCounter)
            .filter(
                ActionUsageCounter.tenant_id == tenant_id,
                ActionUsageCounter.period_key == self._period_key(),
            )
            .first()
        )
        used = counter.action_count if counter else 0
        spend = counter.spend_usd if counter else 0.0
        quota = plan.action_quota_monthly or 10000
        if cap:
            quota = min(quota, cap.monthly_action_cap or quota)
            spend_cap = cap.monthly_spend_usd
            hard = cap.hard_stop
        else:
            spend_cap = 999999.0
            hard = False

        if used >= quota and hard:
            return {"allowed": False, "reason": "Action quota exceeded", "used": used, "quota": quota}
        if spend + cost_usd > spend_cap and hard:
            return {
                "allowed": False,
                "reason": "Monthly spend budget exceeded",
                "spend": spend,
                "cap": spend_cap,
            }
        return {"allowed": True, "used": used, "quota": quota, "spend": spend, "spend_cap": spend_cap}

    def record_action(self, tenant_id: str, cost_usd: float = 0.0, count: int = 1) -> None:
        pk = self._period_key()
        counter = (
            self.db.query(ActionUsageCounter)
            .filter(
                ActionUsageCounter.tenant_id == tenant_id,
                ActionUsageCounter.period_key == pk,
            )
            .first()
        )
        if not counter:
            counter = ActionUsageCounter(tenant_id=tenant_id, period_key=pk, action_count=0, spend_usd=0.0)
            self.db.add(counter)
        counter.action_count = (counter.action_count or 0) + count
        counter.spend_usd = (counter.spend_usd or 0.0) + cost_usd
        sub = self.get_subscription(tenant_id)
        if sub:
            sub.actions_used_period = counter.action_count
        self.db.commit()

    def agent_allowed(self, tenant_id: str, agent_key: str) -> bool:
        ent = self.entitlements(tenant_id)
        allowed = ent.get("allowed_agents") or []
        if "*" in allowed:
            return True
        return agent_key.lower() in [a.lower() for a in allowed]
