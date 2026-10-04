from typing import Dict, Any, List, Protocol
from sqlalchemy.orm import Session
from app.models.verticals import Lead, Ticket, TicketMessage, ContentPost, Candidate, Transaction
import uuid


class EntityAdapter(Protocol):
    def get_supported_actions(self) -> List[str]:
        ...

    async def execute_action(
        self, action: str, tenant_id: str, payload: Dict[str, Any], db: Session
    ) -> Dict[str, Any]:
        ...


class SalesSectionAdapter:
    def get_supported_actions(self) -> List[str]:
        return ["lead.create", "lead.update", "lead.score"]

    async def execute_action(
        self, action: str, tenant_id: str, payload: Dict[str, Any], db: Session
    ) -> Dict[str, Any]:
        if action == "lead.create":
            name = payload.get("name", "Inbound Prospect")
            email = payload.get("email")
            company = payload.get("company", "Unknown")
            source = payload.get("source", "Autonomous Flow")
            score = int(payload.get("score", 0))

            lead = Lead(
                tenant_id=tenant_id,
                name=name,
                email=email,
                company=company,
                source=source,
                score=score,
                status="captured",
                data=payload.get("data", {}),
            )
            db.add(lead)
            db.commit()
            db.refresh(lead)
            return {"success": True, "lead_id": lead.id, "name": lead.name, "score": lead.score}

        elif action == "lead.update":
            lead_id = payload.get("lead_id")
            if not lead_id:
                # Find most recent lead if not supplied
                lead = db.query(Lead).filter_by(tenant_id=tenant_id).order_by(Lead.created_at.desc()).first()
            else:
                lead = db.query(Lead).filter_by(tenant_id=tenant_id, id=lead_id).first()

            if not lead:
                raise ValueError(f"Lead not found for update (ID: {lead_id})")

            if "score" in payload:
                lead.score = int(payload["score"])
            if "status" in payload:
                lead.status = payload["status"]
            if "notes" in payload:
                current_data = dict(lead.data or {})
                current_data["agent_notes"] = payload["notes"]
                lead.data = current_data
            if "data" in payload and isinstance(payload["data"], dict):
                current_data = dict(lead.data or {})
                current_data.update(payload["data"])
                lead.data = current_data

            db.commit()
            db.refresh(lead)
            return {"success": True, "lead_id": lead.id, "status": lead.status, "score": lead.score}

        elif action == "lead.score":
            lead_id = payload.get("lead_id")
            score = int(payload.get("score", 50))
            lead = db.query(Lead).filter_by(tenant_id=tenant_id, id=lead_id).first()
            if lead:
                lead.score = score
                if score >= 70 and lead.status == "captured":
                    lead.status = "qualified"
                db.commit()
                return {"success": True, "lead_id": lead.id, "score": lead.score, "status": lead.status}
            return {"success": False, "message": "Lead not found"}

        raise NotImplementedError(f"Action '{action}' is not supported by SalesSectionAdapter.")


class SupportSectionAdapter:
    def get_supported_actions(self) -> List[str]:
        return ["ticket.create", "ticket.reply", "ticket.close"]

    async def execute_action(
        self, action: str, tenant_id: str, payload: Dict[str, Any], db: Session
    ) -> Dict[str, Any]:
        if action == "ticket.create":
            ticket = Ticket(
                tenant_id=tenant_id,
                subject=payload.get("subject", "Customer Inquiry"),
                description=payload.get("description", ""),
                status="open",
                customer_email=payload.get("customer_email"),
                customer_name=payload.get("customer_name"),
                priority=payload.get("priority", "medium"),
            )
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            return {"success": True, "ticket_id": ticket.id}

        elif action == "ticket.reply":
            ticket_id = payload.get("ticket_id")
            message = payload.get("message")
            ticket = db.query(Ticket).filter_by(tenant_id=tenant_id, id=ticket_id).first()
            if not ticket:
                # Find latest open ticket as fallback
                ticket = db.query(Ticket).filter_by(tenant_id=tenant_id).order_by(Ticket.created_at.desc()).first()

            if not ticket:
                return {"success": False, "message": "No ticket available to reply."}

            msg = TicketMessage(ticket_id=ticket.id, sender="agent", content=message)
            db.add(msg)
            if payload.get("status"):
                ticket.status = payload["status"]
            db.commit()
            return {"success": True, "ticket_id": ticket.id, "reply_length": len(message or "")}

        elif action == "ticket.close":
            ticket_id = payload.get("ticket_id")
            ticket = db.query(Ticket).filter_by(tenant_id=tenant_id, id=ticket_id).first()
            if ticket:
                ticket.status = "closed"
                db.commit()
                return {"success": True, "ticket_id": ticket.id, "status": "closed"}
            return {"success": False, "message": "Ticket not found"}

        raise NotImplementedError(f"Action '{action}' not supported by SupportSectionAdapter.")


class MarketingSectionAdapter:
    def get_supported_actions(self) -> List[str]:
        return ["post.create", "post.publish"]

    async def execute_action(
        self, action: str, tenant_id: str, payload: Dict[str, Any], db: Session
    ) -> Dict[str, Any]:
        if action in ("post.create", "post.publish"):
            content = payload.get("content", "")
            platform = payload.get("platform", "linkedin")
            post = ContentPost(
                tenant_id=tenant_id,
                platform=platform,
                content=content,
                status="draft" if action == "post.create" else "published",
                approval_status="pending" if action == "post.create" else "approved",
            )
            db.add(post)
            db.commit()
            db.refresh(post)
            return {"success": True, "post_id": post.id, "platform": post.platform}

        raise NotImplementedError(f"Action '{action}' not supported by MarketingSectionAdapter.")


class HRSectionAdapter:
    def get_supported_actions(self) -> List[str]:
        return ["applicant.create", "applicant.score"]

    async def execute_action(
        self, action: str, tenant_id: str, payload: Dict[str, Any], db: Session
    ) -> Dict[str, Any]:
        if action == "applicant.create":
            candidate = Candidate(
                tenant_id=tenant_id,
                name=payload.get("name", "Applicant"),
                email=payload.get("email"),
                role=payload.get("role", "General"),
                status="sourced",
                scorecard=payload.get("scorecard", {}),
            )
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
            return {"success": True, "candidate_id": candidate.id}

        elif action == "applicant.score":
            candidate_id = payload.get("candidate_id")
            candidate = db.query(Candidate).filter_by(tenant_id=tenant_id, id=candidate_id).first()
            if candidate:
                scorecard = dict(candidate.scorecard or {})
                scorecard.update(payload.get("scorecard", {}))
                candidate.scorecard = scorecard
                if payload.get("status"):
                    candidate.status = payload["status"]
                db.commit()
                return {"success": True, "candidate_id": candidate.id, "status": candidate.status}
            return {"success": False, "message": "Candidate not found"}

        raise NotImplementedError(f"Action '{action}' not supported by HRSectionAdapter.")


class SectionRegistry:
    def __init__(self):
        self._adapters: Dict[str, Any] = {
            "sales": SalesSectionAdapter(),
            "support": SupportSectionAdapter(),
            "marketing": MarketingSectionAdapter(),
            "hr": HRSectionAdapter(),
        }

    def register_adapter(self, section: str, adapter: Any):
        self._adapters[section] = adapter

    def get_adapter(self, section: str) -> Any:
        return self._adapters.get(section)

    async def execute_action(
        self, section: str, action: str, tenant_id: str, payload: Dict[str, Any], db: Session
    ) -> Dict[str, Any]:
        adapter = self.get_adapter(section)
        if not adapter:
            # Fallback search all adapters
            for sec, ad in self._adapters.items():
                if action in ad.get_supported_actions():
                    return await ad.execute_action(action, tenant_id, payload, db)
            raise ValueError(f"No section adapter registered for action '{action}' (section: {section})")

        return await adapter.execute_action(action, tenant_id, payload, db)


section_registry = SectionRegistry()
