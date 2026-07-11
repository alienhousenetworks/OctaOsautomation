"""Finance AI — invoices, expense categorization, AR follow-up, ROI tracking."""
from datetime import datetime, timezone
from app.services.agents.base import BaseAgent
from app.models.teams import AgentMetric
from app.models.enterprise import FinanceRecord
from app.services.policy_engine import PolicyEngine


class FinanceAgent(BaseAgent):
    def __init__(self, db, tenant_id):
        super().__init__(db, tenant_id, "Finance AI", department="finance")

    async def execute_task(self, task: dict) -> dict:
        action = task.get("action")
        params = task.get("parameters", {})

        if action == "track_roi":
            return await self._track_roi(params)
        if action == "create_invoice":
            return await self._create_invoice(params)
        if action == "categorize_expense":
            return await self._categorize_expense(params)
        if action == "ar_followup":
            return await self._ar_followup(params)
        if action == "list_overdue":
            return await self._list_overdue(params)
        return {"status": "error", "message": f"Unknown finance action: {action}"}

    async def _track_roi(self, params: dict):
        amount = float(params.get("amount", 0) or 0)
        self.log_activity("Track ROI", f"Updating revenue impact by ${amount}")

        metric = self.db.query(AgentMetric).filter(
            AgentMetric.tenant_id == self.tenant_id,
            AgentMetric.metric_name == "revenue_impact",
        ).first()

        if not metric:
            metric = AgentMetric(tenant_id=self.tenant_id, metric_name="revenue_impact", value=0.0)
            self.db.add(metric)

        metric.value = (metric.value or 0) + amount
        self.db.commit()
        return {"status": "success", "revenue_added": amount, "total": metric.value}

    async def _create_invoice(self, params: dict):
        amount = float(params.get("amount", 0) or 0)
        rec = FinanceRecord(
            tenant_id=self.tenant_id,
            record_type="invoice",
            counterparty=params.get("counterparty") or params.get("customer"),
            amount=amount,
            currency=params.get("currency", "USD"),
            category=params.get("category", "sales"),
            status="open",
            description=params.get("description"),
            metadata_json=params.get("metadata") or {},
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        self.log_activity("Create Invoice", f"Invoice {rec.id} for {amount} {rec.currency}")
        return {"status": "success", "record_id": rec.id, "amount": amount}

    async def _categorize_expense(self, params: dict):
        amount = float(params.get("amount", 0) or 0)
        description = params.get("description") or ""
        # Simple rule-based categorization + optional LLM later
        category = params.get("category")
        if not category:
            text = description.lower()
            if any(w in text for w in ("ads", "meta", "google ads", "linkedin ads")):
                category = "advertising"
            elif any(w in text for w in ("salary", "payroll", "contractor")):
                category = "payroll"
            elif any(w in text for w in ("aws", "cloud", "openai", "anthropic", "api")):
                category = "software_infrastructure"
            elif any(w in text for w in ("travel", "flight", "hotel", "uber")):
                category = "travel"
            else:
                category = "general_expense"

        rec = FinanceRecord(
            tenant_id=self.tenant_id,
            record_type="expense",
            counterparty=params.get("vendor"),
            amount=amount,
            currency=params.get("currency", "USD"),
            category=category,
            status="recorded",
            description=description,
            metadata_json={"auto_categorized": not bool(params.get("category"))},
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        self.log_activity("Categorize Expense", f"{category}: {amount}")
        return {"status": "success", "record_id": rec.id, "category": category}

    async def _ar_followup(self, params: dict):
        """Draft AR follow-up; always goes through policy (price/money sensitive)."""
        amount = float(params.get("amount", 0) or 0)
        counterparty = params.get("counterparty") or "customer"
        record_id = params.get("record_id")
        draft = (
            f"Hello {counterparty},\n\n"
            f"This is a friendly reminder that invoice "
            f"{record_id or ''} for {amount} remains outstanding. "
            f"Please let us know if you need a copy of the invoice or have any questions.\n\n"
            f"Thank you."
        )
        policy = PolicyEngine(self.db, self.tenant_id)
        decision = policy.evaluate(
            action_type="price_quote",  # money-related → approval
            channel="email",
            agent_name="Finance AI",
            confidence=0.9,
            amount=amount,
            brand_pass=True,
            title=f"AR follow-up for {counterparty} (${amount})",
            payload={"draft": draft, "record_id": record_id, "counterparty": counterparty},
            resource_type="finance_record",
            resource_id=record_id,
            requested_by="Finance AI",
        )
        if record_id:
            rec = (
                self.db.query(FinanceRecord)
                .filter(FinanceRecord.id == record_id, FinanceRecord.tenant_id == self.tenant_id)
                .first()
            )
            if rec:
                meta = dict(rec.metadata_json or {})
                meta["last_ar_followup"] = {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "decision": decision,
                }
                rec.metadata_json = meta
                if rec.status == "open":
                    rec.status = "overdue"
                self.db.commit()

        self.log_activity("AR Follow-up", f"Queued for {counterparty}: {decision.get('decision')}")
        return {"status": "success", "policy": decision, "draft": draft}

    async def _list_overdue(self, params: dict):
        rows = (
            self.db.query(FinanceRecord)
            .filter(
                FinanceRecord.tenant_id == self.tenant_id,
                FinanceRecord.record_type == "invoice",
                FinanceRecord.status.in_(["open", "overdue"]),
            )
            .all()
        )
        return {
            "status": "success",
            "count": len(rows),
            "records": [
                {"id": r.id, "counterparty": r.counterparty, "amount": r.amount, "status": r.status}
                for r in rows
            ],
        }

    async def daily_routine(self):
        overdue = await self._list_overdue({})
        self.log_activity(
            "Daily Routine",
            f"Finance check: {overdue.get('count', 0)} open/overdue invoices.",
            status="success",
        )
