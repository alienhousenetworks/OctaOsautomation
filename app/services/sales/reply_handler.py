"""Process real prospect replies for active sales leads (email / WhatsApp)."""
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.services.agents.base import BaseAgent
from app.models.verticals import Lead
from app.models.base import APICredential
from app.services.notifications.sales_alerts import send_sales_telegram
from app.services.sales.meeting_booking import book_meeting_for_lead



def _sales_settings(db: Session, tenant_id: str) -> dict:
    cred = (
        db.query(APICredential)
        .filter_by(tenant_id=tenant_id, provider="sales")
        .first()
    )
    base = {
        "sales_auto_reply": True,
        "reply_mode": "review_first",
        "auto_book_meetings": True,
    }
    if cred and cred.settings:
        base.update(cred.settings)
    return base


def sales_auto_reply_enabled(db: Session, tenant_id: str) -> bool:
    return bool(_sales_settings(db, tenant_id).get("sales_auto_reply", True))


def sales_reply_mode(db: Session, tenant_id: str) -> str:
    mode = str(_sales_settings(db, tenant_id).get("reply_mode") or "review_first").lower()
    return mode if mode in ("review_first", "auto_send") else "review_first"


def sales_auto_book_meetings(db: Session, tenant_id: str) -> bool:
    return bool(_sales_settings(db, tenant_id).get("auto_book_meetings", True))


class SalesReplyHandler(BaseAgent):
    def __init__(self, db: Session, tenant_id: str):
        super().__init__(db, tenant_id, "Sales AI")

    def _append_conversation(
        self,
        lead: Lead,
        *,
        direction: str,
        channel: str,
        content: str,
        external_id: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> None:
        data = dict(lead.data or {})
        history = list(data.get("conversation") or [])
        history.append(
            {
                "direction": direction,
                "channel": channel,
                "content": content,
                "subject": subject,
                "external_id": external_id,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        data["conversation"] = history[-50:]
        lead.data = data

    def _already_processed(self, lead: Lead, external_id: Optional[str]) -> bool:
        if not external_id:
            return False
        processed = set((lead.data or {}).get("processed_inbound_ids") or [])
        return external_id in processed

    def _mark_processed(self, lead: Lead, external_id: Optional[str]) -> None:
        if not external_id:
            return
        data = dict(lead.data or {})
        processed = list(data.get("processed_inbound_ids") or [])
        if external_id not in processed:
            processed.append(external_id)
        data["processed_inbound_ids"] = processed[-200:]
        lead.data = data

    def register_inbound(
        self,
        lead: Lead,
        channel: str,
        content: str,
        *,
        subject: Optional[str] = None,
        external_id: Optional[str] = None,
    ) -> bool:
        """Store inbound message; return False if duplicate."""
        if self._already_processed(lead, external_id):
            return False
        self._append_conversation(
            lead,
            direction="inbound",
            channel=channel,
            content=content,
            external_id=external_id,
            subject=subject,
        )
        self._mark_processed(lead, external_id)
        data = dict(lead.data or {})
        data["last_inbound_at"] = datetime.now(timezone.utc).isoformat()
        data["last_inbound_channel"] = channel
        lead.data = data
        if lead.status in ("contacted", "enriched", "captured"):
            lead.status = "replied"
        self.db.commit()
        self.db.refresh(lead)
        return True

    async def process_inbound(
        self,
        lead_id: str,
        channel: str,
        content: str,
        *,
        subject: Optional[str] = None,
        external_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        lead = (
            self.db.query(Lead)
            .filter(Lead.id == lead_id, Lead.tenant_id == self.tenant_id)
            .first()
        )
        if not lead:
            return {"status": "error", "detail": "lead not found"}

        if not self.register_inbound(lead, channel, content, subject=subject, external_id=external_id):
            return {"status": "skipped", "reason": "duplicate"}

        # Telegram: new prospect reply
        preview = (content or "")[:280].replace("\n", " ")
        tg_msg = (
            f"Prospect replied ({channel})\n"
            f"{lead.name} — {lead.company}\n"
            f"{preview}"
        )
        send_sales_telegram(self.db, self.tenant_id, tg_msg)

        parsed = await self._classify_reply(lead, content, subject)
        data = dict(lead.data or {})
        data["prospect_reply"] = content
        data["prospect_interested"] = parsed.get("interested", False)
        data["reply_intent"] = parsed.get("intent", "neutral")
        data["reply_classification"] = parsed
        lead.data = data
        self.db.commit()

        booked = False
        if (
            parsed.get("interested")
            and lead.status != "meeting_scheduled"
            and sales_auto_book_meetings(self.db, self.tenant_id)
        ):
            booked = book_meeting_for_lead(
                self.db,
                self.tenant_id,
                lead,
                tool="google_calendar",
                suggested_time=parsed.get("suggested_time"),
                log_activity=self.log_activity,
            )

        auto_reply = parsed.get("should_auto_reply", True)
        suggested = parsed.get("suggested_reply")
        if sales_auto_reply_enabled(self.db, self.tenant_id) and auto_reply and suggested:
            mode = sales_reply_mode(self.db, self.tenant_id)
            if mode == "review_first":
                # Human must approve draft before send
                from app.services.policy_engine import PolicyEngine
                decision = PolicyEngine(self.db, self.tenant_id).evaluate(
                    action_type="first_touch_email" if channel in ("email", "smtp", "gmail") else "sales_auto_reply",
                    channel=channel,
                    agent_name="Sales AI",
                    confidence=0.7,
                    brand_pass=True,
                    title=f"Sales reply to {lead.name} ({lead.company})",
                    payload={
                        "draft": suggested,
                        "lead_id": lead.id,
                        "channel": channel,
                        "intent": parsed.get("intent"),
                    },
                    resource_type="lead",
                    resource_id=lead.id,
                    requested_by="Sales AI",
                )
                data["pending_review_reply"] = suggested
                data["approval_id"] = decision.get("approval_id")
                lead.data = data
                self.db.commit()
                self.log_activity(
                    "Sales Reply Awaiting Review",
                    f"Draft for {lead.name} queued for human approval ({decision.get('decision')}).",
                    "success",
                )
            else:
                from app.core.celery_app import celery_app

                delay = 120 if channel == "email" else 60
                data["pending_auto_reply_for"] = external_id or data.get("last_inbound_at", "")
                lead.data = data
                self.db.commit()
                celery_app.send_task(
                    "sales_auto_reply_task",
                    args=[
                        self.tenant_id,
                        lead.id,
                        channel,
                        suggested,
                        external_id or data.get("pending_auto_reply_for", ""),
                    ],
                    countdown=delay,
                )
                self.log_activity(
                    "Sales Auto-Reply Queued",
                    f"Queued sales follow-up for {lead.name} in {delay}s.",
                    "success",
                )

        self.log_activity(
            "Prospect Reply Processed",
            f"{lead.name} ({lead.company}) — intent: {parsed.get('intent')}, meeting_booked: {booked}",
            "success",
        )
        return {
            "status": "success",
            "lead_id": lead.id,
            "intent": parsed.get("intent"),
            "meeting_booked": booked,
        }

    async def _classify_reply(
        self, lead: Lead, content: str, subject: Optional[str]
    ) -> Dict[str, Any]:
        outbound = (lead.data or {}).get("outbound_body", "")
        history = (lead.data or {}).get("conversation") or []
        history_text = ""
        for msg in history[-10:]:
            history_text += f"{msg.get('direction', '?').upper()} ({msg.get('channel')}): {msg.get('content', '')}\n"

        prompt = f"""You are a sales assistant analyzing a REAL inbound message from a prospect.

Lead: {lead.name} at {lead.company}
Our last outreach:
{outbound}

Conversation:
{history_text}

New inbound message ({subject or 'no subject'}):
{content}

Classify and respond planning. Output JSON only:
{{
  "intent": "interested" | "question" | "decline" | "neutral",
  "interested": true/false,
  "suggested_time": "meeting time they proposed or null",
  "summary": "one line summary",
  "should_auto_reply": true/false,
  "suggested_reply": "professional reply text to send them (empty if decline and no reply needed)"
}}

Rules:
- interested=true only if they clearly want a call, demo, or meeting.
- should_auto_reply=true for questions and neutral messages; false for clear unsubscribe/decline.
- suggested_reply must sound human, concise, on-brand; do not mention AI.
"""
        response = await self.llm.complete(
            prompt=prompt, provider="anthropic", model="claude-3-haiku-20240307"
        )
        try:
            cleaned = response.strip().strip("```json").strip("```").strip()
            return json.loads(cleaned)
        except Exception:
            lower = content.lower()
            interested = any(
                w in lower
                for w in ("meet", "call", "demo", "schedule", "available", "yes", "interested")
            )
            return {
                "intent": "interested" if interested else "neutral",
                "interested": interested,
                "suggested_time": None,
                "summary": content[:120],
                "should_auto_reply": True,
                "suggested_reply": (
                    "Thanks for getting back to me — happy to find a time that works. "
                    "What does your calendar look like this week?"
                ),
            }

    async def send_sales_reply(self, lead: Lead, channel: str, content: str) -> None:
        from app.services.email.sender import send_email
        from app.services.agents.support import SupportAgent

        if channel == "email":
            subject = (lead.data or {}).get("outbound_subject", "Following up")
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"
            outreach_channel = (lead.data or {}).get("outreach_channel", "smtp")
            result = send_email(
                self.db,
                self.tenant_id,
                lead.email,
                subject,
                content,
                channel=outreach_channel,
            )
            sent = result.get("sent", False) if isinstance(result, dict) else bool(result)
            if sent:
                self._append_conversation(
                    lead, direction="outbound", channel=channel, content=content
                )
                self.db.commit()
                self.log_activity(
                    "Sales Reply Sent",
                    f"Email reply sent to {lead.email}.",
                    "success",
                )
            else:
                reason = result.get("reason", "unknown") if isinstance(result, dict) else "unknown"
                self.log_activity(
                    "Sales Reply Failed",
                    f"Could not send email to {lead.email}. Reason: {reason}",
                    "failed",
                )
        elif channel == "whatsapp":
            support = SupportAgent(self.db, self.tenant_id)
            phone = lead.phone or (lead.data or {}).get("whatsapp_from")
            if phone:
                await support.send_message("whatsapp", phone, content)
                self._append_conversation(
                    lead, direction="outbound", channel=channel, content=content
                )
                self.db.commit()
                self.log_activity(
                    "Sales Reply Sent",
                    f"WhatsApp reply sent to {phone}.",
                    "success",
                )
