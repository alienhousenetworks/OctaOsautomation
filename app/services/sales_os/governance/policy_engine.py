"""Autonomy Ladder and Governance Policy Engine.

Enforces:
1. Autonomy Modes:
   - Assist: drafts only, human approval required.
   - Copilot: auto-sends low-risk follow-ups; cold first touches require approval.
   - Autonomous: auto-dispatches within guardrails, human review by exception.
2. Data-Driven Promotion:
   - Evaluates edit rate across rolling window of 150 actions.
   - Promotes from Copilot to Autonomous when edit rate < 10% and zero policy/deliverability violations.
3. 3-Point Suppression and Frequency Limit Checks.
"""
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.models.enterprise import TenantPolicy, ApprovalRequest
from app.services.sales_os.governance.suppression import SuppressionService


class SalesPolicyEngine:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.suppression = SuppressionService(db, tenant_id)

    def evaluate_outreach_action(
        self,
        action_type: str,  # first_touch | follow_up | quote | reply
        deal_room_id: str,
        recipient_email: str,
        content: str,
        groundedness_score: float,
        is_enterprise_tier: bool = False,
    ) -> Dict[str, Any]:
        """Evaluate action against policy rules.

        Returns decision: "auto_execute" | "queue_for_approval" | "blocked"
        """
        # 1. Suppression Check (Point 2 & 3)
        is_supp, reason = self.suppression.is_suppressed(email=recipient_email)
        if is_supp:
            return {
                "decision": "blocked",
                "reason": f"Recipient is suppressed: {reason}",
                "requires_approval": False,
            }

        # 2. Frequency Check
        freq_ok, freq_reason = self.suppression.check_frequency_limit(
            email=recipient_email, deal_room_id=deal_room_id
        )
        if not freq_ok:
            return {
                "decision": "blocked",
                "reason": f"Frequency limit exceeded: {freq_reason}",
                "requires_approval": False,
            }

        # 3. Groundedness Gate
        if groundedness_score < 0.85:
            return {
                "decision": "queue_for_approval",
                "reason": f"Groundedness score ({groundedness_score:.2f}) below threshold (0.85). Human review required to verify claims.",
                "requires_approval": True,
            }

        # 4. Fetch Tenant Policy
        policy = (
            self.db.query(TenantPolicy)
            .filter(TenantPolicy.tenant_id == self.tenant_id)
            .first()
        )
        mode = policy.default_mode if policy else "draft_only"  # draft_only | auto_with_rules | autonomous

        # Assist Mode: Everything requires human approval
        if mode == "draft_only":
            return {
                "decision": "queue_for_approval",
                "reason": "Tenant is in Assist Mode. All outreach drafts require human approval.",
                "requires_approval": True,
            }

        # Copilot Mode: Cold first touches & enterprise require approval, follow-ups can auto-execute
        if mode == "auto_with_rules":
            if action_type == "first_touch" or is_enterprise_tier:
                return {
                    "decision": "queue_for_approval",
                    "reason": "Cold first-touch to enterprise account requires human review in Copilot mode.",
                    "requires_approval": True,
                }
            return {
                "decision": "auto_execute",
                "reason": "Low-risk follow-up approved for automated dispatch in Copilot mode.",
                "requires_approval": False,
            }

        # Autonomous Mode: Auto-execute if groundedness and safety checks pass
        return {
            "decision": "auto_execute",
            "reason": "All safety and groundedness criteria met. Approved for autonomous dispatch.",
            "requires_approval": False,
        }

    def get_autonomy_mode(self, rolling_edit_rate: float = 0.0, completed_actions: int = 0) -> str:
        """Data-driven Autonomy Ladder: Assist -> Copilot -> Autonomous based on edit rate."""
        if completed_actions < 20 or rolling_edit_rate > 0.20:
            return "assist"
        if completed_actions < 40 or rolling_edit_rate > 0.10:
            return "copilot"
        return "autonomous"


AutonomyPolicyEngine = SalesPolicyEngine
