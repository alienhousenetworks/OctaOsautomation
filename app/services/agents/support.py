import os
import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.services.agents.base import BaseAgent
from app.models.verticals import Ticket, TicketMessage
from app.models.base import APICredential
from app.core.security import decrypt_api_key
from app.services.credentials import get_decrypted_credential
from app.core.celery_app import celery_app
from app.services.notifications.telegram import send_telegram_notification
import asyncio
from app.core.http_utils import with_retry


class SupportAgent(BaseAgent):
    def __init__(self, db, tenant_id):
        super().__init__(db, tenant_id, "Support AI")

    async def execute_task(self, task: dict) -> dict:
        action = task.get("action")
        params = task.get("parameters", {})
        
        if action == "onboard_users":
            return await self._onboard_users(params)
        return {"status": "Unknown action"}

    async def _onboard_users(self, params: dict):
        count = params.get("count", 2)
        self.log_activity("Onboard Users", f"Drafting onboarding messages for {count} users.")
        
        for i in range(count):
            ticket = Ticket(
                tenant_id=self.tenant_id,
                subject=f"Welcome to our service User {i+1}",
                description="Auto-generated onboarding sequence.",
                status="open",
                customer_contact=f"user{i+1}@example.com",
                channel="email",
                approval_status="pending"
            )
            self.db.add(ticket)
        self.db.commit()
        return {"status": "success", "tickets_created": count}

    async def daily_routine(self):
        self.log_activity("Daily Routine", "Checking for new unhandled tickets.", status="success")

    def is_auto_reply_enabled(self, channel: str) -> bool:
        cred = self.db.query(APICredential).filter(
            APICredential.tenant_id == self.tenant_id,
            APICredential.provider == "support"
        ).first()
        if cred and cred.settings:
            if channel == "whatsapp":
                return cred.settings.get("whatsapp_auto_reply", True)
            elif channel == "email":
                return cred.settings.get("email_auto_reply", True)
        return True # Default to True

    def validate_credentials(self, channel: str):
        if channel == "whatsapp":
            cred = self.db.query(APICredential).filter(
                APICredential.tenant_id == self.tenant_id,
                APICredential.provider == "meta"
            ).first()
            if not cred or not cred.encrypted_key or not cred.settings or not cred.settings.get("phone_number_id"):
                raise ValueError("WhatsApp Meta API credentials (Access Token and Phone Number ID) are required but not configured.")
        elif channel == "email":
            cred = self.db.query(APICredential).filter(
                APICredential.tenant_id == self.tenant_id,
                APICredential.provider == "smtp"
            ).first()
            if not cred or not cred.encrypted_key or not cred.settings or not cred.settings.get("smtp_server"):
                raise ValueError("SMTP/Email credentials (Server, Port, Username, Password) are required but not configured.")

    async def handle_incoming_message(
        self,
        channel: str,
        sender: str,
        content: str,
        subject: Optional[str] = None,
        external_id: Optional[str] = None,
    ) -> dict:
        # 0. Active sales lead? Route to Sales AI (real replies, booking, auto-reply)
        from app.services.sales.inbound_router import route_incoming_to_sales

        sales_route = await route_incoming_to_sales(
            self.db,
            self.tenant_id,
            channel,
            sender,
            content,
            subject=subject,
            external_id=external_id,
        )
        if sales_route.get("handled"):
            return {
                "status": "success",
                "routed_to": "sales",
                "lead_id": sales_route.get("lead_id"),
            }

        # 1. Validation check for credentials
        self.validate_credentials(channel)

        # 2. Look for existing open ticket for sender on this channel
        ticket = self.db.query(Ticket).filter(
            Ticket.tenant_id == self.tenant_id,
            Ticket.channel == channel,
            Ticket.customer_contact == sender,
            Ticket.status == "open"
        ).order_by(Ticket.created_at.desc()).first()

        if not ticket:
            # Create a new ticket
            ticket = Ticket(
                tenant_id=self.tenant_id,
                subject=subject or f"New {channel.capitalize()} support request from {sender}",
                description=content,
                status="open",
                priority="medium",
                channel=channel,
                customer_contact=sender,
                approval_status="pending"
            )
            self.db.add(ticket)
            self.db.commit()
            self.db.refresh(ticket)
            self.log_activity("Ticket Created", f"New ticket #{ticket.id[:8]} opened for {sender} via {channel}.")
            
            # Send Telegram Notification
            msg = f"🎫 *New Support Ticket*\nFrom: {sender}\nSubject: {ticket.subject}\nChannel: {channel}"
            asyncio.create_task(send_telegram_notification(self.db, self.tenant_id, msg))

            # Context Engineering Check: determine if boardroom meeting is needed
            try:
                celery_app.send_task("check_ticket_coordination_task", args=[self.tenant_id, ticket.id])
            except Exception as e:
                print(f"Failed to queue ticket check task: {e}")

        # 3. Create TicketMessage
        message = TicketMessage(
            ticket_id=ticket.id,
            sender="customer",
            content=content
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)

        # 4. If auto-reply is enabled, queue celery task with human-like delay
        if self.is_auto_reply_enabled(channel):
            # WhatsApp ~4–5 min; Email ~20 min (product SLA)
            delay_seconds = 270 if channel == "whatsapp" else 1200 if channel == "email" else 180
            if ticket.status == "human_handling":
                self.log_activity("Auto-Reply Skipped", f"Ticket #{ticket.id[:8]} under human takeover.")
            else:
                celery_app.send_task(
                    "auto_reply_task",
                    args=[self.tenant_id, ticket.id, message.id, channel],
                    countdown=delay_seconds,
                )
                self.log_activity(
                    "Auto-Reply Queued",
                    f"Queued support response for ticket #{ticket.id[:8]} in {delay_seconds}s.",
                )

        return {
            "status": "success",
            "ticket_id": ticket.id,
            "message_id": message.id
        }

    async def process_auto_reply(self, ticket_id: str, trigger_msg_id: str, channel: str):
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return

        if ticket.status in ("resolved", "closed", "human_handling"):
            self.log_activity("Auto-Reply Cancelled", f"Ticket #{ticket.id[:8]} status is {ticket.status}.")
            return

        trigger_msg = self.db.query(TicketMessage).filter(TicketMessage.id == trigger_msg_id).first()
        if not trigger_msg:
            return

        # Check if an agent replied after trigger message
        later_agent_messages = self.db.query(TicketMessage).filter(
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.sender == "agent",
            TicketMessage.created_at > trigger_msg.created_at
        ).count()

        if later_agent_messages > 0:
            self.log_activity("Auto-Reply Cancelled", f"A reply has already been sent by agent for ticket #{ticket.id[:8]}.")
            return

        # KB-gated answer with citations / refuse mode
        from app.services.kb_rag import KnowledgeRAGService
        from app.services.policy_engine import PolicyEngine
        from app.services.subscription_service import SubscriptionService

        budget = SubscriptionService(self.db).check_action_allowed(self.tenant_id)
        if not budget.get("allowed"):
            self.log_activity("Auto-Reply Blocked", f"Budget/quota: {budget.get('reason')}")
            return

        last_customer = trigger_msg.content or ""
        kb = KnowledgeRAGService(self.db, self.tenant_id).answer_context(
            last_customer, department="Support"
        )
        if not kb.get("answer_allowed"):
            reply_content = kb.get("message") or (
                "Thank you for reaching out. I'm escalating this to a specialist who can help."
            )
            citations = []
        else:
            knowledge = kb.get("context") or self.get_knowledge_context("Support")
            citations = kb.get("citations") or []
            messages = self.db.query(TicketMessage).filter(
                TicketMessage.ticket_id == ticket_id
            ).order_by(TicketMessage.created_at.asc()).all()

            history_str = ""
            for m in messages:
                history_str += f"{m.sender.upper()}: {m.content}\n"

            system_prompt = (
                "You are a helpful, professional, and empathetic customer support agent. "
                "Your replies should be concise, human-like, and natural. Do not mention that you are an AI or bot. "
                "Rely strictly on the provided Company Guidelines & Knowledge Base. "
                "If the information is not in the knowledge base, say you will escalate to a specialist. "
                "When you use knowledge, you may cite sources by their citation tags."
            )
            prompt = (
                f"Customer Conversation History:\n{history_str}\n"
                f"Knowledge Base (with citations):\n{knowledge}\n"
                "Draft the final response from the agent to the customer."
            )

            reply_content = await self.llm.complete(
                prompt=prompt,
                model=None,
                provider="gemini",
                system_prompt=system_prompt,
            )
            if citations:
                reply_content = f"{reply_content}\n\nSources: " + "; ".join(citations[:3])

        # Policy: support replies go through HITL unless auto_with_rules
        decision = PolicyEngine(self.db, self.tenant_id).evaluate(
            action_type="support_auto_reply",
            channel=channel,
            agent_name="Support AI",
            confidence=0.9 if kb.get("mode") == "grounded" else 0.5,
            brand_pass=True,
            title=f"Support reply ticket {ticket.id[:8]}",
            payload={"draft": reply_content, "ticket_id": ticket.id, "channel": channel},
            resource_type="ticket",
            resource_id=ticket.id,
            requested_by="Support AI",
        )
        if decision.get("decision") == "block":
            self.log_activity("Auto-Reply Blocked", decision.get("reason", "policy"))
            return
        if decision.get("decision") == "queue_approval":
            # Save draft as internal note without sending
            draft_msg = TicketMessage(
                ticket_id=ticket.id,
                sender="agent",
                content=f"[PENDING APPROVAL {decision.get('approval_id')}]\n{reply_content}",
            )
            self.db.add(draft_msg)
            self.db.commit()
            self.log_activity("Auto-Reply Queued for Approval", f"Ticket #{ticket.id[:8]}")
            return

        # Save + send
        reply_message = TicketMessage(
            ticket_id=ticket.id,
            sender="agent",
            content=reply_content,
        )
        self.db.add(reply_message)
        self.db.commit()
        self.db.refresh(reply_message)

        await self.send_message(channel, ticket.customer_contact, reply_content)
        SubscriptionService(self.db).record_action(self.tenant_id, cost_usd=0.0, count=1)
        self.log_activity("Auto-Reply Sent", f"Auto-reply sent for ticket #{ticket.id[:8]} via {channel}.")

    @with_retry
    async def send_message(self, channel: str, recipient: str, content: str):
        if channel == "whatsapp":
            cred = self.db.query(APICredential).filter_by(tenant_id=self.tenant_id, provider="meta").first()
            token, _ = get_decrypted_credential(self.db, self.tenant_id, "meta")
            if not cred or not token or not cred.settings or not cred.settings.get("phone_number_id"):
                raise ValueError("WhatsApp Meta API credentials are not configured.")

            phone_number_id = cred.settings.get("phone_number_id")

            async with httpx.AsyncClient() as client:
                url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": recipient,
                    "type": "text",
                    "text": {"preview_url": False, "body": content},
                }
                response = await client.post(url, json=payload, headers=headers, timeout=20.0)
                if response.status_code not in (200, 201):
                    raise Exception(f"Failed to send WhatsApp message via Meta API: {response.text}")
                self.log_activity("WhatsApp Sent (Official)", f"Successfully sent WhatsApp message to {recipient}.")

        elif channel == "email":
            cred = self.db.query(APICredential).filter(
                APICredential.tenant_id == self.tenant_id,
                APICredential.provider == "smtp"
            ).first()
            
            if not cred or not cred.encrypted_key or not cred.settings or not cred.settings.get("smtp_server"):
                raise ValueError("SMTP/Email credentials are not configured.")
            
            smtp_server = cred.settings.get("smtp_server")
            smtp_port = int(cred.settings.get("smtp_port", 587))
            smtp_user = cred.settings.get("smtp_username")
            smtp_pass = decrypt_api_key(cred.encrypted_key)
            from_email = cred.settings.get("from_email", smtp_user)
            
            msg = MIMEMultipart()
            msg["From"] = from_email
            msg["To"] = recipient
            msg["Subject"] = f"Re: OctaOS Customer Support Inquiry"
            msg.attach(MIMEText(content, "plain"))
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, recipient, msg.as_string())
            server.quit()
            self.log_activity("Email Sent (Official)", f"Successfully sent email to {recipient}.")
