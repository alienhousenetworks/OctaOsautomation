"""Outcome labels + learning signals for ROI and strategy performance."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.enterprise import OutcomeEvent, PlaybookSOP
from app.models.learning import DecisionRecord, StrategyPerformance


class OutcomeService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def record(
        self,
        outcome_type: str,
        *,
        agent_name: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        value: float = 1.0,
        metadata: Optional[dict] = None,
    ) -> OutcomeEvent:
        ev = OutcomeEvent(
            tenant_id=self.tenant_id,
            outcome_type=outcome_type,
            agent_name=agent_name,
            resource_type=resource_type,
            resource_id=resource_id,
            decision_id=decision_id,
            value=value,
            metadata_json=metadata or {},
        )
        self.db.add(ev)

        # Feed decision record if present
        if decision_id:
            dec = (
                self.db.query(DecisionRecord)
                .filter(
                    DecisionRecord.id == decision_id,
                    DecisionRecord.tenant_id == self.tenant_id,
                )
                .first()
            )
            if dec:
                signals = dict(dec.behavioral_signals or {})
                signals[outcome_type] = value
                dec.behavioral_signals = signals
                dec.outcome_timestamp = datetime.now(timezone.utc)
                if outcome_type in ("meeting_booked", "conversion", "ticket_csat"):
                    dec.result_status = "success"
                    dec.quality_score = max(dec.quality_score or 0, min(100.0, value * 100 if value <= 1 else value))

                # Update strategy performance EMA-ish
                sp = (
                    self.db.query(StrategyPerformance)
                    .filter(
                        StrategyPerformance.tenant_id == self.tenant_id,
                        StrategyPerformance.agent_name == dec.agent_name,
                        StrategyPerformance.task_type == dec.task_type,
                        StrategyPerformance.strategy_name == dec.strategy_used,
                    )
                    .first()
                )
                if sp:
                    sp.success_count = (sp.success_count or 0) + 1
                    total = (sp.success_count or 0) + (sp.failure_count or 0)
                    sp.rolling_success_rate = (sp.success_count or 0) / max(total, 1)
                    sp.weighted_reward_score = 0.8 * (sp.weighted_reward_score or 0) + 0.2 * float(value)
                    # ban low performers
                    if total >= 20 and sp.rolling_success_rate < 0.25:
                        self._ban_strategy(dec.agent_name, dec.strategy_used)

        self.db.commit()
        self.db.refresh(ev)
        return ev

    def _ban_strategy(self, agent_name: str, strategy: str) -> None:
        # Soft-ban via playbook name match or store as negative via inactive playbook tag
        sops = (
            self.db.query(PlaybookSOP)
            .filter(
                PlaybookSOP.tenant_id == self.tenant_id,
                PlaybookSOP.name == strategy,
            )
            .all()
        )
        for sop in sops:
            sop.banned = True
            sop.performance_score = 0.0

    def summary(self, days: int = 30) -> Dict[str, Any]:
        rows = (
            self.db.query(
                OutcomeEvent.outcome_type,
                func.count(OutcomeEvent.id),
                func.sum(OutcomeEvent.value),
            )
            .filter(OutcomeEvent.tenant_id == self.tenant_id)
            .group_by(OutcomeEvent.outcome_type)
            .all()
        )
        by_type = {
            r[0]: {"count": int(r[1] or 0), "sum_value": float(r[2] or 0)}
            for r in rows
        }
        return {"tenant_id": self.tenant_id, "outcomes": by_type}

    def list_playbooks(self) -> List[PlaybookSOP]:
        return (
            self.db.query(PlaybookSOP)
            .filter(PlaybookSOP.tenant_id == self.tenant_id)
            .order_by(PlaybookSOP.updated_at.desc())
            .all()
        )

    def upsert_playbook(
        self,
        *,
        name: str,
        department: str,
        content: str,
        icp_json: Optional[dict] = None,
        playbook_id: Optional[str] = None,
    ) -> PlaybookSOP:
        if playbook_id:
            pb = (
                self.db.query(PlaybookSOP)
                .filter(PlaybookSOP.id == playbook_id, PlaybookSOP.tenant_id == self.tenant_id)
                .first()
            )
            if not pb:
                raise ValueError("Playbook not found")
            pb.name = name
            pb.department = department
            pb.content = content
            pb.icp_json = icp_json or {}
            pb.version = (pb.version or 1) + 1
        else:
            pb = PlaybookSOP(
                tenant_id=self.tenant_id,
                name=name,
                department=department,
                content=content,
                icp_json=icp_json or {},
            )
            self.db.add(pb)
        self.db.commit()
        self.db.refresh(pb)
        return pb
