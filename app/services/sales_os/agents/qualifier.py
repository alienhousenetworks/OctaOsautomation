"""Capability 10: Multi-Factor Lead & Account Qualifier.

Evaluates:
- Firmographic Fit (Industry, Employee Count, Revenue Band)
- Budget Capacity Fit
- Timing Score (Recency and velocity of buying signals)
- Evidence Coverage
Produces an explainable qualification decision without artificial leniency.
"""
import time
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.services.sales_os.agents.base import BaseSalesAgent, AgentResult, EvidenceItem
from app.models.deal_room import DealRoom, CompanySalesContext


class QualifierAgent(BaseSalesAgent):
    def __init__(self, db: Session, tenant_id: str):
        super().__init__(db, tenant_id, "agent_10_qualifier")

    async def execute(self, deal_room_id: str, parameters: Dict[str, Any] = None) -> AgentResult:
        start_time = time.time()
        deal_room = (
            self.db.query(DealRoom)
            .filter(DealRoom.id == deal_room_id, DealRoom.tenant_id == self.tenant_id)
            .first()
        )
        if not deal_room:
            return AgentResult(
                agent_id=self.agent_id,
                tenant_id=self.tenant_id,
                decision="error",
                confidence=0.0,
                reasoning_summary="DealRoom not found",
                recommended_next_step="discover_account",
            )

        # Fetch active Company Sales Context
        ctx = (
            self.db.query(CompanySalesContext)
            .filter(
                CompanySalesContext.tenant_id == self.tenant_id,
                CompanySalesContext.is_active == True,  # noqa: E712
            )
            .first()
        )
        icp = ctx.icp_definitions if ctx else {}
        target_industries = [i.lower() for i in icp.get("industries", ["saas", "technology", "manufacturing", "healthcare"])]

        missing_info = []
        scores = {}

        # 1. Industry Fit
        if deal_room.industry:
            ind_lower = deal_room.industry.lower()
            if any(ti in ind_lower or ind_lower in ti for ti in target_industries):
                scores["industry_fit"] = 1.0
            else:
                scores["industry_fit"] = 0.4
        else:
            missing_info.append("industry_unknown")
            scores["industry_fit"] = 0.2

        # 2. Company Size Fit
        if deal_room.employee_count:
            if 20 <= deal_room.employee_count <= 2000:
                scores["size_fit"] = 1.0
            elif 5 <= deal_room.employee_count < 20:
                scores["size_fit"] = 0.6
            else:
                scores["size_fit"] = 0.5
        else:
            missing_info.append("employee_count_unknown")
            scores["size_fit"] = 0.3

        # 3. Budget Fit
        if deal_room.annual_revenue_usd:
            if deal_room.annual_revenue_usd >= 1_000_000:
                scores["budget_fit"] = 1.0
            else:
                scores["budget_fit"] = 0.6
        else:
            missing_info.append("revenue_unknown")
            scores["budget_fit"] = 0.5

        # Weighted ICP Fit (0.0 to 1.0)
        icp_fit = (
            scores["industry_fit"] * 0.40
            + scores["size_fit"] * 0.35
            + scores["budget_fit"] * 0.25
        )

        timing = deal_room.timing_score or 0.5
        evidence_cov = 1.0 - (len(missing_info) * 0.25)
        evidence_cov = max(0.2, evidence_cov)

        priority = round(icp_fit * timing * evidence_cov, 3)
        deal_room.icp_fit_score = round(icp_fit, 3)
        deal_room.priority_index = priority

        is_qualified = icp_fit >= 0.55
        deal_room.stage = "qualified" if is_qualified else "nurtured"
        self.db.commit()

        decision = "qualified" if is_qualified else "disqualified"
        reasoning = (
            f"Evaluated against ICP: Industry fit={scores['industry_fit']:.1f}, "
            f"Size fit={scores['size_fit']:.1f}, Budget fit={scores['budget_fit']:.1f}. "
            f"Composite ICP Score: {icp_fit:.2f}, Priority Index: {priority:.2f}."
        )

        elapsed = int((time.time() - start_time) * 1000)
        return AgentResult(
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            deal_room_id=deal_room.id,
            decision=decision,
            confidence=round(evidence_cov, 2),
            evidence=[
                EvidenceItem(
                    claim=f"Company {deal_room.company_name} matches ICP criteria with score {icp_fit:.2f}",
                    source="icp_evaluator",
                    confidence=evidence_cov,
                )
            ],
            source="deal_room_evaluator",
            reasoning_summary=reasoning,
            missing_information=missing_info,
            recommended_next_step="account_research" if is_qualified else "enrich_further",
            data={
                "icp_fit_score": round(icp_fit, 3),
                "timing_score": round(timing, 3),
                "priority_index": priority,
                "dimension_scores": scores,
            },
            execution_time_ms=elapsed,
        )
