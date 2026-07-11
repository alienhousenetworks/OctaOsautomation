"""Subscription plans, entitlements, seats, action quotas (monthly + weekly; refresh each period)."""
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

# Keep all plan definitions in code; only ACTIVE_PLAN_CODE is offered to users.
ACTIVE_PLAN_CODE = "explorer"

DEFAULT_PLANS = [
    {
        "code": "starter",
        "name": "Starter",
        "price_usd_monthly": 399.0,
        "price_inr_monthly": 14999.0,
        "seat_limit": 3,
        "action_quota_monthly": 5000,
        "allowed_agents": ["sales", "support"],
        "is_active": False,  # deactivated — keep code
        "feature_flags": {
            "crm_sync": False,
            "sso": False,
            "roi_pdf": False,
            "mfa": True,
            "approvals": True,
            "weekly_action_quota": 1500,
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
        "is_active": False,
        "feature_flags": {
            "crm_sync": True,
            "sso": False,
            "roi_pdf": True,
            "mfa": True,
            "approvals": True,
            "weekly_action_quota": 8000,
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
        "is_active": False,
        "feature_flags": {
            "crm_sync": True,
            "sso": True,
            "roi_pdf": True,
            "mfa": True,
            "approvals": True,
            "audit_export": True,
            "weekly_action_quota": 30000,
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
        "is_active": False,
        "feature_flags": {
            "crm_sync": True,
            "sso": True,
            "roi_pdf": True,
            "mfa": True,
            "approvals": True,
            "audit_export": True,
            "dedicated_env": True,
            "sla": True,
            "weekly_action_quota": 100000,
        },
    },
    # Single active plan — full product access, high exploratory limits
    # Quotas refresh monthly / weekly (no lifetime total — users renew each month)
    {
        "code": "explorer",
        "name": "OctaOS Full Access",
        "price_usd_monthly": 0.0,
        "price_inr_monthly": 0.0,
        "seat_limit": None,
        "action_quota_monthly": 100000,  # refreshes each calendar month
        "allowed_agents": ["*"],
        "is_active": True,
        "feature_flags": {
            "crm_sync": True,
            "sso": True,
            "roi_pdf": True,
            "mfa": True,
            "approvals": True,
            "audit_export": True,
            "all_access": True,
            "video_studio": False,  # in-app video creation hidden
            "weekly_action_quota": 25000,  # refreshes each ISO week
            "api_rate_limit_per_minute": 300,  # high request rate
        },
    },
]


class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db

    def seed_plans(self) -> List[SubscriptionPlan]:
        plans = []
        for p in DEFAULT_PLANS:
            data = dict(p)
            existing = (
                self.db.query(SubscriptionPlan)
                .filter(SubscriptionPlan.code == data["code"])
                .first()
            )
            if existing:
                # Keep code, refresh active flags / quotas / agents from defaults
                existing.name = data["name"]
                existing.price_usd_monthly = data["price_usd_monthly"]
                existing.price_inr_monthly = data.get("price_inr_monthly")
                existing.seat_limit = data.get("seat_limit")
                existing.action_quota_monthly = data.get("action_quota_monthly")
                existing.allowed_agents = data.get("allowed_agents")
                existing.feature_flags = data.get("feature_flags") or {}
                existing.is_active = bool(data.get("is_active", False))
                plans.append(existing)
                continue
            plan = SubscriptionPlan(**data)
            self.db.add(plan)
            plans.append(plan)
        self.db.commit()

        # Move any tenants still on a deactivated plan onto the active explorer plan
        active = self.get_plan(ACTIVE_PLAN_CODE)
        if active:
            inactive_ids = [
                p.id
                for p in self.db.query(SubscriptionPlan)
                .filter(SubscriptionPlan.is_active == False)  # noqa: E712
                .all()
            ]
            if inactive_ids:
                subs = (
                    self.db.query(TenantSubscription)
                    .filter(TenantSubscription.plan_id.in_(inactive_ids))
                    .all()
                )
                for s in subs:
                    s.plan_id = active.id
                if subs:
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

    def ensure_trial(self, tenant_id: str, plan_code: str = None) -> TenantSubscription:
        plan_code = plan_code or ACTIVE_PLAN_CODE
        existing = self.get_subscription(tenant_id)
        if existing:
            # ensure still on an active plan
            plan = self.db.query(SubscriptionPlan).filter(SubscriptionPlan.id == existing.plan_id).first()
            if plan and not plan.is_active:
                self.seed_plans()
                active = self.get_plan(ACTIVE_PLAN_CODE)
                if active:
                    existing.plan_id = active.id
                    self.db.commit()
                    self.db.refresh(existing)
            return existing
        self.seed_plans()
        plan = self.get_plan(plan_code) or self.get_plan(ACTIVE_PLAN_CODE) or self.get_plan("starter")
        now = datetime.now(timezone.utc)
        sub = TenantSubscription(
            tenant_id=tenant_id,
            plan_id=plan.id,
            status="active",  # full access explorer — no paid gate for now
            trial_ends_at=now + timedelta(days=365),
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            seats_used=1,
            actions_used_period=0,
        )
        self.db.add(sub)
        if not self.db.query(TenantBudgetCap).filter(TenantBudgetCap.tenant_id == tenant_id).first():
            flags = plan.feature_flags or {}
            self.db.add(
                TenantBudgetCap(
                    tenant_id=tenant_id,
                    monthly_spend_usd=float(flags.get("monthly_spend_usd") or 5000.0),
                    monthly_action_cap=plan.action_quota_monthly or 100000,
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
        if not plan.is_active and plan_code != ACTIVE_PLAN_CODE:
            raise ValueError(f"Plan '{plan_code}' is not available. Use '{ACTIVE_PLAN_CODE}'.")
        sub = self.ensure_trial(tenant_id)
        sub.plan_id = plan.id
        sub.status = "active"
        now = datetime.now(timezone.utc)
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=30)
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def _counter(self, tenant_id: str, period_key: str) -> ActionUsageCounter:
        counter = (
            self.db.query(ActionUsageCounter)
            .filter(
                ActionUsageCounter.tenant_id == tenant_id,
                ActionUsageCounter.period_key == period_key,
            )
            .first()
        )
        if not counter:
            counter = ActionUsageCounter(
                tenant_id=tenant_id, period_key=period_key, action_count=0, spend_usd=0.0
            )
            self.db.add(counter)
            self.db.flush()
        return counter

    def _month_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def _week_key(self) -> str:
        # ISO week: 2026-W28
        return datetime.now(timezone.utc).strftime("%Y-W%W")

    def entitlements(self, tenant_id: str) -> Dict[str, Any]:
        sub = self.ensure_trial(tenant_id)
        plan = self.db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.plan_id).first()
        seats = self.db.query(User).filter(User.tenant_id == tenant_id, User.is_active == True).count()  # noqa: E712
        sub.seats_used = seats

        month_c = self._counter(tenant_id, self._month_key())
        week_c = self._counter(tenant_id, self._week_key())
        sub.actions_used_period = month_c.action_count or 0
        self.db.commit()

        flags = dict(plan.feature_flags or {})
        flags.update(sub.feature_overrides or {})
        # Drop legacy lifetime flag if still present in DB feature_flags
        flags.pop("lifetime_action_quota", None)
        weekly_quota = int(flags.get("weekly_action_quota") or 25000)

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
            "actions_used_period": month_c.action_count or 0,
            "actions_used_weekly": week_c.action_count or 0,
            "weekly_action_quota": weekly_quota,
            "allowed_agents": plan.allowed_agents,
            "feature_flags": flags,
            "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "payment": {
                "provider": "razorpay",
                "last_payment_id": getattr(sub, "razorpay_last_payment_id", None),
                "last_order_id": getattr(sub, "razorpay_last_order_id", None),
            },
        }

    def check_action_allowed(self, tenant_id: str, cost_usd: float = 0.0) -> Dict[str, Any]:
        sub = self.ensure_trial(tenant_id)
        plan = self.db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.plan_id).first()
        flags = dict(plan.feature_flags or {})
        cap = (
            self.db.query(TenantBudgetCap)
            .filter(TenantBudgetCap.tenant_id == tenant_id)
            .first()
        )

        month_c = self._counter(tenant_id, self._month_key())
        week_c = self._counter(tenant_id, self._week_key())

        used_m = month_c.action_count or 0
        used_w = week_c.action_count or 0
        spend = month_c.spend_usd or 0.0

        quota_m = plan.action_quota_monthly or 100000
        quota_w = int(flags.get("weekly_action_quota") or 25000)

        hard = True
        spend_cap = 999999.0
        if cap:
            quota_m = min(quota_m, cap.monthly_action_cap or quota_m)
            spend_cap = float(cap.monthly_spend_usd or spend_cap)
            hard = bool(cap.hard_stop)

        # Weekly and monthly counters reset automatically (new period_key each week/month)
        if hard and used_w >= quota_w:
            return {
                "allowed": False,
                "reason": f"Weekly action limit reached ({used_w}/{quota_w}). Resets next week.",
                "used_weekly": used_w,
                "quota_weekly": quota_w,
                "used": used_m,
                "quota": quota_m,
            }
        if hard and used_m >= quota_m:
            return {
                "allowed": False,
                "reason": f"Monthly action limit reached ({used_m}/{quota_m}). Resets next billing month.",
                "used": used_m,
                "quota": quota_m,
                "used_weekly": used_w,
                "quota_weekly": quota_w,
            }
        if hard and spend + cost_usd > spend_cap:
            return {
                "allowed": False,
                "reason": "Monthly spend budget exceeded",
                "spend": spend,
                "cap": spend_cap,
            }
        return {
            "allowed": True,
            "used": used_m,
            "quota": quota_m,
            "used_weekly": used_w,
            "quota_weekly": quota_w,
            "spend": spend,
            "spend_cap": spend_cap,
        }

    def record_action(self, tenant_id: str, cost_usd: float = 0.0, count: int = 1) -> None:
        # Only monthly + weekly (refreshing) counters — no lifetime total
        for pk in (self._month_key(), self._week_key()):
            counter = self._counter(tenant_id, pk)
            counter.action_count = (counter.action_count or 0) + count
            if pk == self._month_key():
                counter.spend_usd = (counter.spend_usd or 0.0) + cost_usd
        sub = self.get_subscription(tenant_id)
        if sub:
            month_c = self._counter(tenant_id, self._month_key())
            sub.actions_used_period = month_c.action_count
        self.db.commit()

    def agent_allowed(self, tenant_id: str, agent_key: str) -> bool:
        ent = self.entitlements(tenant_id)
        allowed = ent.get("allowed_agents") or []
        if "*" in allowed:
            return True
        return agent_key.lower() in [a.lower() for a in allowed]

    def video_features_enabled(self, tenant_id: str) -> bool:
        """In-app video creation is off for explorer plan (and config)."""
        from app.core.config import settings
        if not getattr(settings, "ENABLE_IN_APP_VIDEO", False):
            return False
        ent = self.entitlements(tenant_id)
        return bool((ent.get("feature_flags") or {}).get("video_studio"))
