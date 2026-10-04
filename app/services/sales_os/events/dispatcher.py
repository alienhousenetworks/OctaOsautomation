"""Event-Driven Sales Engine Dispatcher.

Handles asynchronous domain events:
- LeadDiscovered -> creates DealRoom
- AccountEnriched -> runs Qualifier (Fit x Timing)
- SignalDetected -> computes temporal decay score, updates PriorityIndex
- CommitteeMemberAdded -> updates multi-threading coverage
- ReplyReceived -> routes to Conversation Agent & objection playbook
- MeetingBooked -> advances stage to meeting_booked
- DealStalled -> flags risk and triggers Next Best Action
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.deal_room import DealRoom, AccountSignal, BuyingCommitteeMember, DealActivity


class SalesEventDispatcher:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    async def dispatch_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch domain event to corresponding handlers."""
        handlers = {
            "LeadDiscovered": self._handle_lead_discovered,
            "SignalDetected": self._handle_signal_detected,
            "CommitteeMemberAdded": self._handle_committee_added,
            "ReplyReceived": self._handle_reply_received,
            "MeetingBooked": self._handle_meeting_booked,
            "DealStalled": self._handle_deal_stalled,
        }

        handler = handlers.get(event_type)
        if not handler:
            return {"status": "unhandled_event", "event_type": event_type}

        return await handler(payload)

    async def _handle_lead_discovered(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        domain = payload.get("domain", "").strip().lower().replace("www.", "")
        company_name = payload.get("company_name") or domain.split(".")[0].capitalize()

        deal_room = (
            self.db.query(DealRoom)
            .filter(DealRoom.tenant_id == self.tenant_id, DealRoom.domain == domain)
            .first()
        )
        if not deal_room:
            deal_room = DealRoom(
                tenant_id=self.tenant_id,
                domain=domain,
                company_name=company_name,
                industry=payload.get("industry"),
                employee_count=payload.get("employee_count"),
                website=payload.get("website", f"https://{domain}"),
                stage="discovered",
                last_activity_at=datetime.now(timezone.utc),
            )
            self.db.add(deal_room)
            self.db.commit()
            self.db.refresh(deal_room)

        # Log activity
        activity = DealActivity(
            deal_room_id=deal_room.id,
            tenant_id=self.tenant_id,
            activity_type="account_discovered",
            direction="internal",
            subject=f"Account discovered: {company_name}",
            metadata_json=payload,
        )
        self.db.add(activity)
        self.db.commit()

        return {"status": "success", "deal_room_id": deal_room.id}

    async def _handle_signal_detected(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        deal_room_id = payload.get("deal_room_id")
        deal_room = self.db.query(DealRoom).filter(
            DealRoom.id == deal_room_id, DealRoom.tenant_id == self.tenant_id
        ).first()

        if not deal_room:
            return {"status": "error", "message": "DealRoom not found"}

        signal = AccountSignal(
            deal_room_id=deal_room_id,
            tenant_id=self.tenant_id,
            signal_type=payload.get("signal_type", "hiring"),
            headline=payload.get("headline", "New market signal detected"),
            details=payload.get("details"),
            evidence_url=payload.get("evidence_url"),
            confidence=float(payload.get("confidence", 0.9)),
            decay_half_life_days=int(payload.get("decay_days", 14)),
        )
        self.db.add(signal)

        # Recompute timing score
        deal_room.timing_score = min(1.0, deal_room.timing_score + 0.35)
        deal_room.priority_index = round(deal_room.icp_fit_score * deal_room.timing_score, 3)
        deal_room.last_activity_at = datetime.now(timezone.utc)
        
        self.db.commit()
        return {"status": "success", "signal_id": signal.id, "new_timing_score": deal_room.timing_score}

    async def _handle_committee_added(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        deal_room_id = payload.get("deal_room_id")
        deal_room = self.db.query(DealRoom).filter(
            DealRoom.id == deal_room_id, DealRoom.tenant_id == self.tenant_id
        ).first()

        if not deal_room:
            return {"status": "error", "message": "DealRoom not found"}

        email = payload.get("email", "").strip().lower()
        exists = (
            self.db.query(BuyingCommitteeMember)
            .filter(
                BuyingCommitteeMember.deal_room_id == deal_room_id,
                BuyingCommitteeMember.email == email,
            )
            .first()
        )
        if not exists:
            member = BuyingCommitteeMember(
                deal_room_id=deal_room_id,
                tenant_id=self.tenant_id,
                name=payload.get("name", "Contact"),
                email=email,
                phone=payload.get("phone"),
                title=payload.get("title", "Stakeholder"),
                role_type=payload.get("role_type", "influencer"),
                department=payload.get("department"),
                provenance=payload.get("provenance", {"source": "manual", "confidence": 1.0}),
            )
            self.db.add(member)
            self.db.flush()

        # Update multi-threading metrics
        committee_count = (
            self.db.query(BuyingCommitteeMember)
            .filter(BuyingCommitteeMember.deal_room_id == deal_room_id)
            .count()
        )
        deal_room.is_multi_threaded = committee_count >= 2
        deal_room.committee_coverage = min(1.0, round(committee_count / 4.0, 2))
        self.db.commit()

        return {
            "status": "success",
            "committee_count": committee_count,
            "is_multi_threaded": deal_room.is_multi_threaded,
        }

    async def _handle_reply_received(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        deal_room_id = payload.get("deal_room_id")
        deal_room = self.db.query(DealRoom).filter(
            DealRoom.id == deal_room_id, DealRoom.tenant_id == self.tenant_id
        ).first()

        if not deal_room:
            return {"status": "error", "message": "DealRoom not found"}

        deal_room.stage = "replied"
        deal_room.last_activity_at = datetime.now(timezone.utc)
        self.db.commit()
        return {"status": "success", "new_stage": "replied"}

    async def _handle_meeting_booked(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        deal_room_id = payload.get("deal_room_id")
        deal_room = self.db.query(DealRoom).filter(
            DealRoom.id == deal_room_id, DealRoom.tenant_id == self.tenant_id
        ).first()

        if not deal_room:
            return {"status": "error", "message": "DealRoom not found"}

        deal_room.stage = "meeting_booked"
        deal_room.calibrated_win_prob = max(0.40, deal_room.calibrated_win_prob)
        deal_room.last_activity_at = datetime.now(timezone.utc)
        self.db.commit()
        return {"status": "success", "new_stage": "meeting_booked"}

    async def _handle_deal_stalled(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        deal_room_id = payload.get("deal_room_id")
        deal_room = self.db.query(DealRoom).filter(
            DealRoom.id == deal_room_id, DealRoom.tenant_id == self.tenant_id
        ).first()

        if not deal_room:
            return {"status": "error", "message": "DealRoom not found"}

        flags = list(deal_room.risk_flags or [])
        if "stalled_7_days" not in flags:
            flags.append("stalled_7_days")
        deal_room.risk_flags = flags
        deal_room.next_best_action = {
            "action": "re_engage_alternate_stakeholder",
            "reason": "Primary contact unresponsive for 7 days. Multi-thread to next committee member.",
        }
        self.db.commit()
        return {"status": "success", "risk_flags": deal_room.risk_flags}


DealRoomEventDispatcher = SalesEventDispatcher
