"""AI Employee operating model: manager, quota, SOP, KPIs, standup, takeover."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.agents import ActivityLog
from app.models.enterprise import AIEmployee, ApprovalRequest, PlaybookSOP
from app.models.verticals import Ticket


DEFAULT_EMPLOYEES = [
    {"name": "Sales AI", "role_key": "sales", "quota_daily": 150, "kpis": {"meetings": 5, "replies": 20}},
    {"name": "Marketing AI", "role_key": "marketing", "quota_daily": 30, "kpis": {"posts": 7, "campaigns": 2}},
    {"name": "Support AI", "role_key": "support", "quota_daily": 200, "kpis": {"tickets_resolved": 40, "csat": 4.5}},
]


class AIEmployeeService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def ensure_defaults(self) -> List[AIEmployee]:
        existing = (
            self.db.query(AIEmployee)
            .filter(AIEmployee.tenant_id == self.tenant_id)
            .all()
        )
        if existing:
            return existing
        created = []
        for d in DEFAULT_EMPLOYEES:
            emp = AIEmployee(
                tenant_id=self.tenant_id,
                name=d["name"],
                role_key=d["role_key"],
                quota_daily=d["quota_daily"],
                kpis=d["kpis"],
                schedule={"timezone": "UTC", "hours": "09:00-18:00"},
                escalation_path=["manager", "admin"],
                is_active=True,
                status="idle",
            )
            self.db.add(emp)
            created.append(emp)
        self.db.commit()
        for e in created:
            self.db.refresh(e)
        return created

    def list_employees(self) -> List[AIEmployee]:
        return self.ensure_defaults()

    def update_employee(self, employee_id: str, updates: Dict[str, Any]) -> AIEmployee:
        emp = (
            self.db.query(AIEmployee)
            .filter(AIEmployee.id == employee_id, AIEmployee.tenant_id == self.tenant_id)
            .first()
        )
        if not emp:
            raise ValueError("AI employee not found")
        for k, v in updates.items():
            if hasattr(emp, k) and v is not None and k not in ("id", "tenant_id"):
                setattr(emp, k, v)
        self.db.commit()
        self.db.refresh(emp)
        return emp

    def generate_standup(self, employee_id: Optional[str] = None) -> Dict[str, Any]:
        employees = self.list_employees()
        if employee_id:
            employees = [e for e in employees if e.id == employee_id]

        reports = []
        pending_approvals = (
            self.db.query(ApprovalRequest)
            .filter(
                ApprovalRequest.tenant_id == self.tenant_id,
                ApprovalRequest.status == "pending",
            )
            .count()
        )
        for emp in employees:
            logs = (
                self.db.query(ActivityLog)
                .filter(
                    ActivityLog.tenant_id == self.tenant_id,
                    ActivityLog.agent_name == emp.name,
                )
                .order_by(ActivityLog.created_at.desc())
                .limit(20)
                .all()
            )
            failed = [l for l in logs if l.status == "failed"]
            done = [l for l in logs if l.status == "success"]
            standup = {
                "employee_id": emp.id,
                "name": emp.name,
                "role_key": emp.role_key,
                "status": emp.status,
                "quota_daily": emp.quota_daily,
                "used_today": emp.used_today,
                "did": [{"action": l.action, "description": l.description} for l in done[:10]],
                "needs_approval": pending_approvals if emp.role_key in ("sales", "marketing", "support") else 0,
                "failed": [{"action": l.action, "description": l.description} for l in failed[:5]],
                "kpis": emp.kpis,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            emp.last_standup = standup
            reports.append(standup)
        self.db.commit()
        return {"tenant_id": self.tenant_id, "standups": reports}

    def takeover_ticket(self, ticket_id: str, user_id: str) -> Dict[str, Any]:
        """Human takes over a support conversation — disable AI auto-reply for ticket."""
        ticket = (
            self.db.query(Ticket)
            .filter(Ticket.id == ticket_id, Ticket.tenant_id == self.tenant_id)
            .first()
        )
        if not ticket:
            raise ValueError("Ticket not found")
        ticket.status = "human_handling"
        ticket.approval_status = f"takeover:{user_id}"
        note = f"\n[HUMAN TAKEOVER by {user_id} at {datetime.now(timezone.utc).isoformat()}]"
        ticket.description = (ticket.description or "") + note
        self.db.commit()
        return {"ticket_id": ticket_id, "status": "human_takeover", "by": user_id}
