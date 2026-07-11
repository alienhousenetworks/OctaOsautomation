"""Human-in-the-loop policy engine for outbound / autonomous actions."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.enterprise import ApprovalRequest, TenantPolicy
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

DEFAULT_ALWAYS_APPROVE = [
    "first_touch_email",
    "public_post",
    "price_quote",
    "refund",
    "linkedin_dm",
]


class PolicyEngine:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def get_or_create_policy(self) -> TenantPolicy:
        policy = (
            self.db.query(TenantPolicy)
            .filter(TenantPolicy.tenant_id == self.tenant_id)
            .first()
        )
        if not policy:
            policy = TenantPolicy(
                tenant_id=self.tenant_id,
                default_mode="draft_only",
                min_confidence=0.85,
                max_auto_amount=0.0,
                always_approve=list(DEFAULT_ALWAYS_APPROVE),
                support_refuse_if_not_in_kb=True,
            )
            self.db.add(policy)
            self.db.commit()
            self.db.refresh(policy)
        return policy

    def update_policy(self, updates: Dict[str, Any]) -> TenantPolicy:
        policy = self.get_or_create_policy()
        for key, value in updates.items():
            if hasattr(policy, key) and value is not None:
                setattr(policy, key, value)
        self.db.commit()
        self.db.refresh(policy)
        AuditService.log_event(
            self.db,
            action="policy.updated",
            tenant_id=self.tenant_id,
            resource="policy",
            details=updates,
        )
        return policy

    def evaluate(
        self,
        *,
        action_type: str,
        channel: Optional[str] = None,
        agent_name: Optional[str] = None,
        confidence: Optional[float] = None,
        amount: Optional[float] = None,
        brand_pass: bool = True,
        title: str = "",
        payload: Optional[Dict[str, Any]] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        requested_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns decision:
          allow_auto | queue_approval | block
        """
        policy = self.get_or_create_policy()
        payload = payload or {}

        # Kill switches
        channel_ks = policy.channel_kill_switches or {}
        agent_ks = policy.agent_kill_switches or {}
        if channel and channel_ks.get(channel):
            return self._block(f"Channel kill-switch active: {channel}")
        if agent_name and agent_ks.get(agent_name.lower().replace(" ", "_").replace(" ai", "")):
            return self._block(f"Agent kill-switch active: {agent_name}")
        # also check raw agent name
        if agent_name and agent_ks.get(agent_name):
            return self._block(f"Agent kill-switch active: {agent_name}")

        allowed = policy.allowed_channels or []
        if channel and allowed and channel not in allowed:
            return self._block(f"Channel not allowed: {channel}")

        always = policy.always_approve or DEFAULT_ALWAYS_APPROVE
        needs_approval = action_type in always or policy.default_mode == "draft_only"

        conf = confidence if confidence is not None else 0.0
        if policy.require_brand_pass and not brand_pass:
            needs_approval = True
            reason = "Brand language check failed"
        elif conf < (policy.min_confidence or 0.85):
            needs_approval = True
            reason = f"Confidence {conf:.2f} below min {policy.min_confidence}"
        elif amount is not None and amount > (policy.max_auto_amount or 0):
            needs_approval = True
            reason = f"Amount {amount} exceeds max auto {policy.max_auto_amount}"
        else:
            reason = "Within auto-send rules"

        if policy.default_mode == "auto_with_rules" and not needs_approval and action_type not in always:
            return {
                "decision": "allow_auto",
                "reason": reason,
                "approval_id": None,
            }

        approval = ApprovalRequest(
            tenant_id=self.tenant_id,
            action_type=action_type,
            channel=channel,
            agent_name=agent_name,
            resource_type=resource_type,
            resource_id=resource_id,
            title=title or f"Approve {action_type}",
            payload=payload,
            confidence=confidence,
            status="pending",
            policy_reason=reason if needs_approval else "Always requires approval",
            requested_by=requested_by,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        self.db.add(approval)
        self.db.commit()
        self.db.refresh(approval)

        AuditService.log_event(
            self.db,
            action="approval.queued",
            tenant_id=self.tenant_id,
            resource="approval",
            resource_id=approval.id,
            details={
                "action_type": action_type,
                "channel": channel,
            },
        )

        return {
            "decision": "queue_approval",
            "reason": approval.policy_reason,
            "approval_id": approval.id,
            "status": "pending",
        }

    def _block(self, reason: str) -> Dict[str, Any]:
        return {"decision": "block", "reason": reason, "approval_id": None}

    def review(
        self,
        approval_id: str,
        *,
        approve: bool,
        reviewer_id: str,
        note: Optional[str] = None,
    ) -> ApprovalRequest:
        approval = (
            self.db.query(ApprovalRequest)
            .filter(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.tenant_id == self.tenant_id,
            )
            .first()
        )
        if not approval:
            raise ValueError("Approval not found")
        if approval.status != "pending":
            raise ValueError(f"Approval already {approval.status}")

        approval.status = "approved" if approve else "rejected"
        approval.reviewed_by = reviewer_id
        approval.review_note = note
        approval.reviewed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(approval)

        AuditService.log_event(
            self.db,
            action="approval.reviewed",
            tenant_id=self.tenant_id,
            user_id=reviewer_id,
            resource="approval",
            resource_id=approval_id,
            details={
                "status": approval.status,
                "note": note,
            },
        )
        return approval

    def list_pending(self, limit: int = 50):
        return (
            self.db.query(ApprovalRequest)
            .filter(
                ApprovalRequest.tenant_id == self.tenant_id,
                ApprovalRequest.status == "pending",
            )
            .order_by(ApprovalRequest.created_at.desc())
            .limit(limit)
            .all()
        )
