"""Comprehensive Support Chat Service for AI Q&A, Knowledge Base RAG,
Human Handoff, Loop/Out-of-Context Detection, and Ticket Escalation."""

from __future__ import annotations

import difflib
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.base import APICredential, User
from app.models.verticals import Ticket, TicketMessage, SupportAgentPresence
from app.services.kb_rag import KnowledgeRAGService
from app.services.llm_gateway import LLMGateway
from app.services.notifications.telegram import send_telegram_notification
import asyncio


class SupportChatService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.llm = LLMGateway(db, tenant_id)

    def detect_human_handoff_intent(self, message: str) -> bool:
        """Detect explicit user requests to speak with a human support agent."""
        if not message:
            return False
        clean = message.lower().strip()
        patterns = [
            r"\b(talk|speak|connect|chat|transfer)\s+(to|with)?\s*(a\s+)?(human|person|agent|representative|specialist|support|team)\b",
            r"\b(want|need|get)\s+(a\s+)?(human|real\s+person|support\s+agent|live\s+agent|representative)\b",
            r"\b(live\s+(chat|agent|support|person|rep))\b",
            r"\b(human\s+(please|agent|support|help|now))\b",
            r"\b(real\s+(person|human))\b",
            r"\b(customer\s+(service|care|support))\b",
            r"\b(hand\s*off|escalate\s+to\s+human)\b",
            r"\b(agent\s+please)\b",
        ]
        for p in patterns:
            if re.search(p, clean):
                return True
        return False

    def detect_loop(self, recent_messages: List[TicketMessage], current_message: str) -> bool:
        """Detect if conversation is looping, repeating, or user is expressing frustration."""
        clean = current_message.lower().strip()
        frustration_triggers = [
            "stuck",
            "in a loop",
            "looping",
            "you keep repeating",
            "you already said that",
            "already asked that",
            "not helpful",
            "not answering my question",
            "doesn't help",
            "repeat",
            "useless",
            "same answer",
            "don't understand",
        ]
        for trig in frustration_triggers:
            if trig in clean:
                return True

        if not recent_messages:
            return False

        # Compare with recent user messages for high similarity
        user_msgs = [m.content.strip().lower() for m in recent_messages if m.sender == "customer"]
        if len(user_msgs) >= 2:
            # Check similarity with the last 2 user messages
            for prev in user_msgs[-2:]:
                ratio = difflib.SequenceMatcher(None, clean, prev).ratio()
                if ratio > 0.85:
                    return True

        # Check if AI has sent repeating replies
        agent_msgs = [m.content.strip().lower() for m in recent_messages if m.sender == "agent"]
        if len(agent_msgs) >= 2:
            last_agent = agent_msgs[-1]
            prev_agent = agent_msgs[-2]
            if difflib.SequenceMatcher(None, last_agent, prev_agent).ratio() > 0.8:
                return True

        return False

    def check_agent_availability(self) -> Dict[str, Any]:
        """Check if any support agent is currently online and active."""
        # 1. Check support settings toggle
        cred = self.db.query(APICredential).filter(
            APICredential.tenant_id == self.tenant_id,
            APICredential.provider == "support"
        ).first()
        settings = (cred.settings or {}) if cred else {}
        if not settings.get("live_chat_enabled", True):
            return {"available": False, "online_agents_count": 0, "reason": "live_chat_disabled"}

        # 2. Check active agent presence in last 15 minutes
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        active_presences = self.db.query(SupportAgentPresence).filter(
            SupportAgentPresence.tenant_id == self.tenant_id,
            SupportAgentPresence.is_online == True,
            SupportAgentPresence.last_heartbeat >= cutoff
        ).all()

        if active_presences:
            return {
                "available": True,
                "online_agents_count": len(active_presences),
                "agents": [p.user_name for p in active_presences]
            }

        # 3. Fallback: if tenant has any active users and setting force_agents_online is true
        if settings.get("force_agents_online", False):
            return {"available": True, "online_agents_count": 1, "agents": ["Support Team"]}

        return {"available": False, "online_agents_count": 0, "reason": "agents_offline"}

    def update_agent_presence(self, user_id: str, user_name: str, is_online: bool) -> Dict[str, Any]:
        """Heartbeat or presence toggle for a human support agent."""
        presence = self.db.query(SupportAgentPresence).filter(
            SupportAgentPresence.tenant_id == self.tenant_id,
            SupportAgentPresence.user_id == user_id
        ).first()
        now = datetime.now(timezone.utc)
        if not presence:
            presence = SupportAgentPresence(
                tenant_id=self.tenant_id,
                user_id=user_id,
                user_name=user_name,
                is_online=is_online,
                last_heartbeat=now
            )
            self.db.add(presence)
        else:
            presence.is_online = is_online
            presence.user_name = user_name
            presence.last_heartbeat = now

        self.db.commit()
        self.db.refresh(presence)
        return {
            "status": "success",
            "user_id": user_id,
            "is_online": presence.is_online,
            "last_heartbeat": presence.last_heartbeat.isoformat()
        }

    async def handle_visitor_message(
        self,
        session_id: str,
        message: str,
        sender_name: Optional[str] = None,
        sender_email: Optional[str] = None,
        sender_phone: Optional[str] = None,
        action: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Core handler for messages coming from the embeddable chat widget."""
        # 1. Fetch or create Ticket for this visitor session
        ticket = self.db.query(Ticket).filter(
            Ticket.tenant_id == self.tenant_id,
            Ticket.session_id == session_id,
            Ticket.status.in_(["open", "pending_human", "human_handling"])
        ).order_by(Ticket.created_at.desc()).first()

        if not ticket:
            ticket = Ticket(
                tenant_id=self.tenant_id,
                session_id=session_id,
                channel="widget",
                subject=f"Chat: {message[:45]}..." if message else "Website Support Chat",
                description=message or "Chat started",
                status="open",
                mode="ai",
                priority="medium",
                customer_name=sender_name,
                customer_email=sender_email,
                customer_phone=sender_phone,
                customer_contact=sender_email or sender_phone or f"visitor_{session_id[:8]}",
            )
            self.db.add(ticket)
            self.db.commit()
            self.db.refresh(ticket)
        else:
            # Update customer metadata if provided
            if sender_name and not ticket.customer_name:
                ticket.customer_name = sender_name
            if sender_email and not ticket.customer_email:
                ticket.customer_email = sender_email
            if sender_phone and not ticket.customer_phone:
                ticket.customer_phone = sender_phone

        # 2. Add customer message to thread if not empty
        cust_msg = None
        if message and message.strip():
            cust_msg = TicketMessage(
                ticket_id=ticket.id,
                sender="customer",
                content=message.strip(),
            )
            self.db.add(cust_msg)
            self.db.commit()
            self.db.refresh(cust_msg)

        # 3. If ticket is already in live human handling:
        if ticket.status == "human_handling":
            return {
                "status": "waiting_human",
                "reply": None,
                "ticket_id": ticket.id,
                "ticket_status": "human_handling",
                "mode": "human",
                "claimed_by": ticket.claimed_by,
                "message": "Message delivered to live agent."
            }

        # 4. If ticket is waiting in the human queue:
        if ticket.status == "pending_human":
            return {
                "status": "handoff_queued",
                "reply": "You are connected to our live chat queue. An agent will be with you shortly.",
                "ticket_id": ticket.id,
                "ticket_status": "pending_human",
                "mode": "human",
                "live_chat_available": True
            }

        # 5. Check if user requested human handoff (action == 'request_handoff' or explicit text)
        is_handoff_req = (action == "request_handoff") or self.detect_human_handoff_intent(message)
        if is_handoff_req:
            avail = self.check_agent_availability()
            if avail["available"]:
                ticket.status = "pending_human"
                ticket.mode = "human"
                sys_msg = TicketMessage(
                    ticket_id=ticket.id,
                    sender="system",
                    content="[Visitor requested live human support. Waiting for agent claim.]"
                )
                self.db.add(sys_msg)
                self.db.commit()
                self.db.refresh(ticket)

                # Send Telegram notification safely
                msg_alert = f"💬 *Live Chat Requested*\nTicket: #{ticket.id[:8]}\nVisitor: {ticket.customer_name or 'Anonymous'}\nMsg: {message}"
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(send_telegram_notification(self.db, self.tenant_id, msg_alert))
                except RuntimeError:
                    pass

                return {
                    "status": "handoff_queued",
                    "reply": "Connecting you with our live support team now! A human agent will claim your chat momentarily.",
                    "ticket_id": ticket.id,
                    "ticket_status": "pending_human",
                    "mode": "human",
                    "live_chat_available": True
                }
            else:
                # No human agent available -> instruct to raise ticket
                return {
                    "status": "handoff_unavailable",
                    "reply": "Our live support agents are currently offline. Please provide your details below and we will raise a priority support ticket for you.",
                    "action_required": "raise_ticket",
                    "prefill": {
                        "problem": message or ticket.description,
                        "name": ticket.customer_name or "",
                        "email": ticket.customer_email or "",
                        "mobile_no": ticket.customer_phone or "",
                    },
                    "ticket_id": ticket.id,
                    "ticket_status": ticket.status,
                    "mode": "ai",
                    "live_chat_available": False
                }

        # 6. Fetch conversation history for loop and context checks
        history_msgs = self.db.query(TicketMessage).filter(
            TicketMessage.ticket_id == ticket.id
        ).order_by(TicketMessage.created_at.asc()).all()

        # 7. Check for loop / repetition
        is_loop = self.detect_loop(history_msgs[:-1] if cust_msg else history_msgs, message)
        if is_loop:
            avail = self.check_agent_availability()
            return {
                "status": "loop_detected",
                "reply": "It looks like I'm having trouble understanding or resolving this for you. Would you like to connect with a live support agent?",
                "suggest_live_chat": True,
                "reason": "loop_detected",
                "live_chat_available": avail["available"],
                "ticket_id": ticket.id,
                "ticket_status": ticket.status,
                "mode": "ai"
            }

        # 8. Grounded Knowledge Base RAG Search
        rag = KnowledgeRAGService(self.db, self.tenant_id)
        kb_result = rag.answer_context(message, department="Support")

        if not kb_result.get("answer_allowed") or kb_result.get("mode") == "refuse":
            # Out of context / not in KB
            avail = self.check_agent_availability()
            reply_text = (
                "I don't have this specific information in my knowledge base. "
                "Would you like to connect with a live support agent?"
            )
            return {
                "status": "out_of_context",
                "reply": reply_text,
                "suggest_live_chat": True,
                "reason": "not_in_kb",
                "live_chat_available": avail["available"],
                "ticket_id": ticket.id,
                "ticket_status": ticket.status,
                "mode": "ai"
            }

        # 9. Generate AI Response grounded in KB context
        knowledge_context = kb_result.get("context", "")
        citations = kb_result.get("citations", [])

        # Build prompt
        history_str = ""
        for m in history_msgs[-6:]:
            history_str += f"{m.sender.upper()}: {m.content}\n"

        system_prompt = (
            "You are a helpful, professional, and empathetic customer support agent. "
            "Rely strictly on the provided Company Knowledge Base. "
            "Your replies should be clear, concise, and helpful. "
            "Never make up facts not present in the Knowledge Base. "
            "If the information is incomplete, advise the user that they can connect with a live agent."
        )

        prompt = (
            f"Conversation History:\n{history_str}\n\n"
            f"Knowledge Base Context:\n{knowledge_context}\n\n"
            f"User Question: {message}\n"
            "Draft a concise and polite response to the customer."
        )

        ai_reply = await self.llm.complete(
            prompt=prompt,
            model=None,
            provider="gemini",
            system_prompt=system_prompt,
        )

        if not ai_reply or not ai_reply.strip():
            ai_reply = "I'm looking into this for you. If you need immediate assistance, feel free to connect with our live support."

        # Save AI reply to thread
        ai_msg = TicketMessage(
            ticket_id=ticket.id,
            sender="agent",
            content=ai_reply.strip(),
        )
        self.db.add(ai_msg)
        self.db.commit()
        self.db.refresh(ai_msg)

        return {
            "status": "success",
            "reply": ai_reply.strip(),
            "citations": citations[:3] if citations else [],
            "ticket_id": ticket.id,
            "ticket_status": ticket.status,
            "mode": "ai"
        }

    def raise_ticket_from_widget(
        self,
        session_id: str,
        problem: str,
        name: str,
        email: str,
        mobile_no: str,
    ) -> Dict[str, Any]:
        """Create or escalate a formal support ticket from the widget."""
        ticket = self.db.query(Ticket).filter(
            Ticket.tenant_id == self.tenant_id,
            Ticket.session_id == session_id,
        ).order_by(Ticket.created_at.desc()).first()

        subject = f"Support Request from {name}: {problem[:40]}..." if problem else f"Support Request from {name}"
        if not ticket:
            ticket = Ticket(
                tenant_id=self.tenant_id,
                session_id=session_id,
                subject=subject,
                description=problem,
                status="open",
                priority="high",
                channel="widget",
                customer_contact=email or mobile_no,
                customer_name=name,
                customer_email=email,
                customer_phone=mobile_no,
                mode="ai"
            )
            self.db.add(ticket)
        else:
            ticket.subject = subject
            ticket.description = problem
            ticket.customer_name = name
            ticket.customer_email = email
            ticket.customer_phone = mobile_no
            ticket.customer_contact = email or mobile_no
            ticket.status = "open"
            ticket.priority = "high"
            ticket.mode = "ai"

        self.db.commit()
        self.db.refresh(ticket)

        # Record ticket creation message in thread
        content = (
            f"🎫 Formal Support Ticket Raised:\n"
            f"• Name: {name}\n"
            f"• Email: {email}\n"
            f"• Mobile: {mobile_no}\n"
            f"• Problem: {problem}"
        )
        msg = TicketMessage(
            ticket_id=ticket.id,
            sender="system",
            content=content,
        )
        self.db.add(msg)
        self.db.commit()

        # Send alert safely
        alert_text = f"🚨 *New Support Ticket #{ticket.id[:8]}*\nFrom: {name} ({email}, {mobile_no})\nIssue: {problem}"
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(send_telegram_notification(self.db, self.tenant_id, alert_text))
        except RuntimeError:
            pass

        return {
            "status": "success",
            "ticket_id": ticket.id,
            "subject": ticket.subject,
            "message": f"Your ticket #{ticket.id[:8]} has been created! Our support team will contact you at {email or mobile_no}."
        }

    def claim_ticket(self, ticket_id: str, user: User) -> Dict[str, Any]:
        """Support agent claims a waiting ticket to start live chat."""
        ticket = self.db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.tenant_id == self.tenant_id,
        ).first()
        if not ticket:
            raise ValueError("Ticket not found")

        agent_name = user.name or user.email.split("@")[0]
        ticket.status = "human_handling"
        ticket.mode = "human"
        ticket.claimed_by = user.id
        ticket.claimed_at = datetime.now(timezone.utc)

        # Add system message to notify visitor and history
        sys_msg = TicketMessage(
            ticket_id=ticket.id,
            sender="system",
            content=f"[{agent_name} has claimed this ticket and joined the live chat.]"
        )
        self.db.add(sys_msg)
        self.db.commit()
        self.db.refresh(ticket)

        return {
            "status": "claimed",
            "ticket_id": ticket.id,
            "agent_id": user.id,
            "agent_name": agent_name
        }

    def resolve_ticket(self, ticket_id: str, user: User) -> Dict[str, Any]:
        """Support agent resolves ticket and returns control to AI."""
        ticket = self.db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.tenant_id == self.tenant_id,
        ).first()
        if not ticket:
            raise ValueError("Ticket not found")

        agent_name = user.name or user.email.split("@")[0]
        ticket.status = "resolved"
        ticket.mode = "ai"
        ticket.resolved_at = datetime.now(timezone.utc)

        sys_msg = TicketMessage(
            ticket_id=ticket.id,
            sender="system",
            content=f"[{agent_name} marked this ticket as resolved. Conversation returned to AI Support.]"
        )
        self.db.add(sys_msg)
        self.db.commit()
        self.db.refresh(ticket)

        return {
            "status": "resolved",
            "ticket_id": ticket.id,
            "mode": "ai"
        }
