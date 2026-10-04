import json
import asyncio
import uuid
import datetime
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.models.base import APICredential
from app.models.agents import ActivityLog, KnowledgeDocument
from app.models.verticals import Ticket, TicketMessage, Lead, Candidate, AgentMeeting, Contract, Transaction
from app.models.boardroom_events import MeetingEvent, MeetingEvidence, MeetingAction
from app.services.agents.boardroom_state import (
    transition,
    emit_event,
    classify_action,
    AUTO_APPROVE_CONFIDENCE_THRESHOLD,
)
from app.schemas.boardroom import (
    SpecialistAnalysis,
    AgentCritique,
    CEOSynthesis,
    Finding,
)
from app.services.llm_gateway import LLMGateway
from app.services.notifications.telegram import send_telegram_notification

logger = logging.getLogger(__name__)

class BoardroomService:
    UNIVERSAL_EXPERTS = [
        "Executive Strategy Expert",
        "Finance Expert",
        "Operations Expert",
        "Research Expert",
        "Risk Expert",
    ]

    INDUSTRY_EXPERTS = {
        "technology": ["Software Architecture Expert", "Cybersecurity Expert", "AI Systems Expert", "Cloud Infrastructure Expert", "DevOps Expert"],
        "restaurant": ["Restaurant Operations Expert", "Franchise Expansion Expert", "Food Cost Analysis Expert", "Location Intelligence Expert", "Customer Experience Expert"],
        "retail": ["Inventory Planning Expert", "Merchandising Expert", "Store Expansion Expert", "Supply Chain Expert"],
        "fashion": ["Trend Forecasting Expert", "Merchandising Expert", "Supplier Analysis Expert", "Market Expansion Expert"],
        "healthcare": ["Healthcare Operations Expert", "Compliance Expert", "Clinical Workflow Expert", "Healthcare Finance Expert"],
        "manufacturing": ["Production Planning Expert", "Procurement Expert", "Supply Chain Expert", "Quality Assurance Expert"],
        "real_estate": ["Investment Analysis Expert", "Development Strategy Expert", "Property Operations Expert", "Location Intelligence Expert"],
        "ecommerce": ["Conversion Optimization Expert", "Marketplace Strategy Expert", "Retention Analysis Expert", "Customer Acquisition Expert"],
        "hospitality": ["Occupancy Optimization Expert", "Revenue Management Expert", "Guest Experience Expert"],
        "logistics": ["Fleet Optimization Expert", "Route Intelligence Expert", "Capacity Planning Expert"],
    }

    SIGNAL_EXPERTS = [
        (("salesforce", "hubspot", "zoho", "pipedrive", "crm", "pipeline", "win rate", "sales", "lead", "revenue"), "Sales Intelligence Expert"),
        (("ga4", "mixpanel", "amplitude", "posthog", "campaign", "marketing", "demand", "acquisition", "competitor"), "Marketing Intelligence Expert"),
        (("regulation", "contract", "privacy", "gdpr", "soc2", "governance", "compliance", "legal"), "Legal & Compliance Expert"),
        (("hiring", "headcount", "workforce", "talent", "org design", "compensation", "hr"), "Human Resources Expert"),
    ]

    def __init__(
        self,
        db: Session,
        tenant_id: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.llm = LLMGateway(db, tenant_id)
        self._provider = provider
        self._model = model

    def build_decision_profile(self, title: str, context: str, industry=None, decision_category=None) -> dict:
        text = f"{title} {context}".lower()
        detected_industry = industry or self._detect_industry(text)
        detected_category = decision_category or self._detect_decision_category(text)
        return {
            "objective": title,
            "industry": detected_industry,
            "decision_category": detected_category,
            "constraints": self._extract_constraints(context),
            "success_metrics": self._extract_success_metrics(context),
            "stakeholders": self._extract_stakeholders(context),
            "available_data_sources": self._detect_available_data_sources(text),
        }

    def assemble_boardroom(
        self,
        decision_profile: dict,
        requested_participants=None,
        include_dynamic: bool = True,
    ) -> list[str]:
        participants = ["CEO AI"]
        if include_dynamic:
            participants.extend(self.UNIVERSAL_EXPERTS)
            industry = decision_profile.get("industry")
            participants.extend(self.INDUSTRY_EXPERTS.get(industry, []))
            text = json.dumps(decision_profile).lower()
            for keywords, expert in self.SIGNAL_EXPERTS:
                if any(keyword in text for keyword in keywords):
                    participants.append(expert)
        participants.extend(requested_participants or [])
        return list(dict.fromkeys(participants))

    def format_decision_context(self, topic: str, decision_profile: dict) -> str:
        return (
            f"Custom Topic: {topic}\n"
            f"Decision Profile JSON: {json.dumps(decision_profile, default=str)}"
        )

    async def classify_ticket_inquiry(self, ticket_id: str) -> dict:
        """
        Uses the LLM to classify a support ticket to see if it requires cross-agent boardroom coordination.
        For example, a high-value sales lead, a partner inquiry, or an emergency billing discrepancy.
        """
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return {"needs_meeting": False}

        system_prompt = (
            "You are the OctaOS Triaging System. Classify the customer support ticket to decide if it "
            "requires an evidence-backed boardroom meeting with the CEO AI and other departments "
            "(Sales, Finance, CTO, Legal, Risk, HR, Marketing) to resolve.\n"
            "Requirements for meeting:\n"
            "- Sales Lead: Customer wants to purchase, asking for enterprise plans, bulk discounts, custom pricing, or partnerships.\n"
            "- Financial/Billing Emergency: Severe payment issue, fraud allegation, or invoice dispute.\n"
            "- Critical HR/Job Application: High profile candidates, partnership pitches, or executive job applications.\n"
            "- If it is just a routine support request (e.g. 'how to login', 'where is my password', general product questions), it does NOT need a meeting.\n\n"
            "Respond ONLY with a JSON object in this format:\n"
            "{\n"
            "  \"needs_meeting\": true | false,\n"
            "  \"title\": \"Descriptive Meeting Title (e.g., Enterprise Lead: Custom Pricing for TechCorp)\",\n"
            "  \"participants\": [\"CEO AI\", \"Support AI\", \"Sales AI\", \"Finance AI\", \"Legal AI\", \"Risk AI\"],\n"
            "  \"reason\": \"Brief explanation of why the meeting was called\"\n"
            "}"
        )

        prompt = (
            f"Ticket Subject: {ticket.subject}\n"
            f"Ticket Channel: {ticket.channel}\n"
            f"Sender: {ticket.customer_contact}\n"
            f"Message Content: {ticket.description}\n"
        )

        response_str = await self.llm.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            provider="gemini"
        )

        try:
            # Clean JSON codeblock wrappers if any
            clean_str = response_str.strip().strip("```json").strip("```").strip()
            result = json.loads(clean_str)
            # Ensure participants always contains CEO AI and Support AI at least
            if result.get("needs_meeting"):
                parts = result.get("participants", [])
                if "CEO AI" not in parts:
                    parts.insert(0, "CEO AI")
                if "Support AI" not in parts:
                    parts.append("Support AI")
                if "Sales AI" not in parts and any(w in (ticket.description or "").lower() for w in ["buy", "purchase", "enterprise", "pricing", "licenses"]):
                    parts.append("Sales AI")
                result["participants"] = list(dict.fromkeys(parts)) # unique list
            return result
        except Exception as e:
            print(f"Error parsing classification response: {e}. Raw response: {response_str}")
            # Safe fallback: if "buy", "purchase", "enterprise", "pricing" or "lead" is in content, classify as Sales Lead
            content_lower = (ticket.description or "").lower() or (ticket.subject or "").lower()
            if any(w in content_lower for w in ["buy", "purchase", "enterprise", "custom price", "partnership", "lead", "pricing"]):
                return {
                    "needs_meeting": True,
                    "title": f"Sales Lead escalation from {ticket.customer_contact}",
                    "participants": ["CEO AI", "Support AI", "Sales AI"],
                    "reason": "Customer is requesting commercial information or custom pricing."
                }
            return {"needs_meeting": False}

    async def create_meeting_from_ticket(self, ticket_id: str, classification: dict) -> AgentMeeting:
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        
        meeting = AgentMeeting(
            tenant_id=self.tenant_id,
            title=classification.get("title", f"Boardroom review: Ticket #{ticket_id[:8]}"),
            status="active",
            trigger_type="support_ticket",
            trigger_id=ticket_id,
            context_summary=f"Ticket Channel: {ticket.channel}\nCustomer: {ticket.customer_contact}\nSubject: {ticket.subject}\nInquiry: {ticket.description}",
            participants=classification.get("participants", ["CEO AI", "Support AI", "Sales AI"]),
            transcript=[],
            action_items=[]
        )
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)

        from app.models.agents import ActivityLog
        log = ActivityLog(
            tenant_id=self.tenant_id,
            agent_name="Support AI",
            action="Meeting Summoned",
            description=f"Summoned cross-agent boardroom meeting: '{meeting.title}' to address critical customer inquiry.",
            status="success"
        )
        self.db.add(log)
        self.db.commit()

        # Send Telegram Notification
        msg = f"🔔 *New Boardroom Meeting Summoned*\nTopic: {meeting.title}\nTrigger: {meeting.trigger_type}"
        asyncio.create_task(send_telegram_notification(self.db, self.tenant_id, msg))

        return meeting

    async def run_meeting(self, meeting_id: str):
        """Run an evidence-backed, parallel multi-agent boardroom workflow with strict governance."""
        meeting = self.db.query(AgentMeeting).filter(AgentMeeting.id == meeting_id).first()
        if not meeting:
            return

        meeting.started_at = datetime.datetime.now(datetime.timezone.utc)
        transition(self.db, meeting, "assembly")
        emit_event(
            self.db,
            meeting.id,
            "meeting.started",
            actor="system",
            phase="assembly",
            payload={"title": meeting.title, "trigger_type": meeting.trigger_type}
        )

        participants = list(dict.fromkeys(meeting.participants or []))
        if "CEO AI" not in participants:
            participants.insert(0, "CEO AI")
        decision_profile = self._decision_profile_from_meeting(meeting)
        if meeting.trigger_type == "manual":
            participants = self.assemble_boardroom(decision_profile, participants)
            meeting.participants = participants
        specialists = [p for p in participants if p != "CEO AI"]
        context = meeting.context_summary or ""

        # Phase: Evidence Gathering
        transition(self.db, meeting, "evidence")
        evidence_pack = self._collect_evidence_pack(meeting)
        source_ids = {source["id"] for source in evidence_pack["sources"]}

        # Persist typed evidence in DB
        for src in evidence_pack.get("sources", []):
            existing_ev = self.db.query(MeetingEvidence).filter(
                MeetingEvidence.meeting_id == meeting.id,
                MeetingEvidence.source_ref == src["id"]
            ).first()
            if not existing_ev:
                rel = src.get("reliability", {})
                new_ev = MeetingEvidence(
                    meeting_id=meeting.id,
                    source_ref=src["id"],
                    source_type=src.get("type", "unknown"),
                    trust_score=rel.get("overall_trust_score"),
                    freshness_score=rel.get("freshness_score"),
                    reliability_score=rel.get("reliability_score"),
                    completeness_score=rel.get("completeness_score"),
                    excerpt=src.get("summary", "")[:500],
                )
                self.db.add(new_ev)
        self.db.commit()

        emit_event(
            self.db,
            meeting.id,
            "evidence.added",
            actor="system",
            phase="evidence",
            payload={"sources_count": len(evidence_pack.get("sources", []))}
        )

        transcript = [{
            "sender": "CEO AI",
            "phase": "Decision Understanding / Board Assembly",
            "content": self._format_decision_profile_message(decision_profile, participants, evidence_pack),
            "decision_profile": decision_profile,
            "sources": [source["id"] for source in evidence_pack["sources"]],
            "timestamp": self._timestamp()
        }]
        meeting.transcript = transcript
        self.db.commit()

        # Phase: Specialist Analysis
        transition(self.db, meeting, "analysis")

        async def _timed_specialist_analysis(agent: str) -> dict:
            emit_event(
                self.db,
                meeting.id,
                "agent.thinking",
                actor=agent,
                phase="analysis",
                payload={"agent": agent, "status": "thinking"}
            )
            try:
                res = await asyncio.wait_for(
                    self._run_specialist_analysis(agent, meeting, context, evidence_pack),
                    timeout=50.0
                )
                emit_event(
                    self.db,
                    meeting.id,
                    "agent.completed",
                    actor=agent,
                    phase="analysis",
                    payload={
                        "agent": agent,
                        "findings_count": len(res.get("findings", [])),
                        "confidence": res.get("confidence_score")
                    }
                )
                return res
            except Exception as e:
                logger.warning("Specialist analysis timed out/failed for %s: %s", agent, e)
                emit_event(
                    self.db,
                    meeting.id,
                    "agent.failed",
                    actor=agent,
                    phase="analysis",
                    payload={"agent": agent, "error": str(e)}
                )
                return {
                    "agent": agent,
                    "findings": [f"Specialist analysis encountered an issue: {str(e)}"],
                    "sources": ["meeting_context"],
                    "assumptions": ["Agent execution exceeded timeout or raised exception."],
                    "confidence_score": 0,
                    "confidence_rationale": "Execution timeout or failure during specialist phase",
                    "status": "failed"
                }

        analyses = await asyncio.gather(*[
            _timed_specialist_analysis(agent)
            for agent in specialists
        ])

        successes = [a for a in analyses if a.get("status") != "failed"]
        if specialists and (len(successes) / len(specialists)) < 0.5:
            meeting.failure_reason = f"Quorum failure: only {len(successes)}/{len(specialists)} completed."
            meeting.status = "failed"
            self.db.commit()
            emit_event(
                self.db,
                meeting.id,
                "meeting.failed",
                actor="system",
                phase="analysis",
                payload={"error": meeting.failure_reason}
            )
            return

        analyses_by_agent = {item["agent"]: item for item in analyses}

        for item in analyses:
            transcript.append({
                "sender": item["agent"],
                "phase": "Researching / Analyzing",
                "content": self._format_analysis_message(item),
                "findings": item.get("findings", []),
                "sources": item.get("sources", []),
                "assumptions": item.get("assumptions", []),
                "confidence_score": item.get("confidence_score"),
                "confidence_rationale": item.get("confidence_rationale"),
                "quality_flags": self._quality_flags(item, source_ids),
                "timestamp": self._timestamp()
            })
        meeting.transcript = transcript
        self.db.commit()

        # Phase: Cross-Agent Critique
        transition(self.db, meeting, "critique")

        async def _timed_critique(agent: str) -> dict:
            try:
                res = await asyncio.wait_for(
                    self._run_cross_agent_critique(agent, meeting, context, evidence_pack, analyses_by_agent),
                    timeout=45.0
                )
                emit_event(
                    self.db,
                    meeting.id,
                    "critique.posted",
                    actor=agent,
                    phase="critique",
                    payload={"agent": agent, "agreement_count": len(res.get("agreement_points", []))}
                )
                return res
            except Exception as e:
                logger.warning("Critique timed out/failed for %s: %s", agent, e)
                return {
                    "agent": agent,
                    "agreement_points": [],
                    "objections": [],
                    "missing_information": [f"Critique timed out: {e}"],
                    "risk_factors": [],
                    "sources": ["meeting_context"]
                }

        critiques = await asyncio.gather(*[
            _timed_critique(agent)
            for agent in specialists
        ])

        for critique in critiques:
            for entry in transcript:
                if entry["sender"] == critique["agent"]:
                    entry["phase"] = "Researching / Analyzing / Critiquing"
                    entry["content"] = entry["content"] + "\n\nCritique:\n" + self._format_critique_message(critique)
                    entry["sources"] = list(dict.fromkeys((entry.get("sources") or []) + (critique.get("sources") or [])))
                    entry["quality_flags"] = list(dict.fromkeys((entry.get("quality_flags") or []) + self._quality_flags(critique, source_ids)))
                    break
        meeting.transcript = transcript
        self.db.commit()

        # Phase: Synthesis
        transition(self.db, meeting, "synthesis")
        emit_event(
            self.db,
            meeting.id,
            "agent.thinking",
            actor="CEO AI",
            phase="synthesis",
            payload={"agent": "CEO AI", "status": "synthesizing"}
        )

        synthesis = await self._run_decision_synthesis(meeting, context, evidence_pack, analyses, critiques)
        confidence = self._derive_confidence(synthesis, analyses, critiques, evidence_pack)
        synthesis["confidence_score"] = confidence["score"]
        synthesis["confidence_rationale"] = confidence["rationale"]

        transcript.append({
            "sender": "CEO AI",
            "phase": "Synthesizing",
            "content": self._format_synthesis_message(synthesis),
            "sources": synthesis.get("sources", []),
            "confidence_score": synthesis.get("confidence_score"),
            "confidence_rationale": synthesis.get("confidence_rationale"),
            "quality_flags": self._quality_flags(synthesis, source_ids),
            "timestamp": self._timestamp()
        })
        meeting.transcript = transcript
        self.db.commit()

        emit_event(
            self.db,
            meeting.id,
            "synthesis.posted",
            actor="CEO AI",
            phase="synthesis",
            payload={
                "executive_summary": synthesis.get("executive_summary", "")[:200],
                "confidence_score": synthesis.get("confidence_score"),
                "recommended_action": synthesis.get("recommended_action", "")[:200],
            }
        )

        # Phase: Governed Actions & Approval
        transition(self.db, meeting, "approval")

        raw_action_items = synthesis.get("action_items", [])
        final_actions = []
        action_records = []
        conf_ratio = (confidence.get("score") or 0) / 100.0

        for item in raw_action_items:
            action_desc = item.get("description", "")
            assigned = item.get("assigned_to", "Operations Expert")
            action_type, risk_tier = classify_action(action_desc)
            action_id = str(uuid.uuid4())[:8]
            idempotency_key = f"{meeting.id}:{action_id}"

            action_record = MeetingAction(
                id=action_id,
                meeting_id=meeting.id,
                action_type=action_type,
                assigned_to=assigned,
                description=action_desc,
                risk_tier=risk_tier,
                idempotency_key=idempotency_key,
                evidence_ids=item.get("sources", []),
            )

            # Governance gate
            if risk_tier == "low":
                action_record.status = "executing"
                action_record.approved_by = "auto"
                action_record.approved_at = datetime.datetime.now(datetime.timezone.utc)
            elif risk_tier == "medium" and conf_ratio >= AUTO_APPROVE_CONFIDENCE_THRESHOLD:
                action_record.status = "executing"
                action_record.approved_by = "auto-confidence"
                action_record.approved_at = datetime.datetime.now(datetime.timezone.utc)
            else:
                action_record.status = "awaiting_approval"

            self.db.add(action_record)
            action_records.append(action_record)

        self.db.commit()

        # Emit proposed events and execute auto-approved ones
        any_awaiting = False
        for action_record in action_records:
            if action_record.status == "awaiting_approval":
                any_awaiting = True
                emit_event(
                    self.db,
                    meeting.id,
                    "action.proposed",
                    actor="CEO AI",
                    phase="approval",
                    payload={
                        "action_id": action_record.id,
                        "action_type": action_record.action_type,
                        "assigned_to": action_record.assigned_to,
                        "description": action_record.description,
                        "risk_tier": action_record.risk_tier,
                        "status": "awaiting_approval"
                    }
                )
            elif action_record.status == "executing":
                # Execute auto-approved
                await self._execute_single_action(meeting, action_record)

            final_actions.append({
                "id": action_record.id,
                "assigned_to": action_record.assigned_to,
                "description": action_record.description,
                "risk_tier": action_record.risk_tier,
                "status": action_record.status,
                "approved_by": action_record.approved_by,
                "sources": action_record.evidence_ids or []
            })

        meeting.action_items = final_actions

        if any_awaiting:
            meeting.status = "awaiting_approval"
            meeting.current_phase = "approval"
            self.db.commit()
            log = ActivityLog(
                tenant_id=self.tenant_id,
                agent_name="CEO AI",
                action="Boardroom Awaiting Approval",
                description=f"Boardroom session produced actions requiring human governance. {len(final_actions)} action items.",
                status="pending"
            )
            self.db.add(log)
            self.db.commit()
        else:
            transition(self.db, meeting, "execution")
            transition(self.db, meeting, "completed")
            meeting.status = "completed"
            meeting.finished_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()
            emit_event(
                self.db,
                meeting.id,
                "meeting.completed",
                actor="system",
                phase="completed",
                payload={"total_actions": len(final_actions)}
            )
            log = ActivityLog(
                tenant_id=self.tenant_id,
                agent_name="CEO AI",
                action="Boardroom Concluded",
                description=f"Concluded evidence-backed boardroom session. Assigned {len(final_actions)} action items.",
                status="success"
            )
            self.db.add(log)
            self.db.commit()

    async def _execute_single_action(self, meeting: AgentMeeting, action_record: MeetingAction) -> bool:
        """Executes a single action record and logs output."""
        assigned = (action_record.assigned_to or "").lower()
        desc = (action_record.description or "").lower()
        success = False
        result_payload: dict = {}

        try:
            # 1. Sales AI - Create Lead
            if "sales" in assigned and ("lead" in desc or "create" in desc):
                customer_email = "lead@example.com"
                customer_phone = None
                customer_name = "Interested Prospect"
                company = "Unknown Corp"

                ctx_lines = (meeting.context_summary or "").split("\n")
                for line in ctx_lines:
                    if line.startswith("Customer:"):
                        contact = line.replace("Customer:", "").strip()
                        if "@" in contact:
                            customer_email = contact
                        else:
                            customer_phone = contact
                            customer_email = f"{contact}@whatsapp.com"
                    elif line.startswith("Subject:"):
                        subj = line.replace("Subject:", "").strip()
                        company_match = [w for w in subj.split() if w[0].isupper() and w not in ["New", "WhatsApp", "Email", "Lead", "Ticket"]]
                        if company_match:
                            company = company_match[0]

                new_lead = Lead(
                    tenant_id=self.tenant_id,
                    name=customer_name,
                    email=customer_email,
                    phone=customer_phone,
                    company=company,
                    source=meeting.trigger_type,
                    status="captured"
                )
                self.db.add(new_lead)
                self.db.commit()

                log = ActivityLog(
                    tenant_id=self.tenant_id,
                    agent_name="Sales AI",
                    action="Lead Captured",
                    description=f"Autonomously created lead for '{customer_email}' from boardroom directive.",
                    status="success"
                )
                self.db.add(log)
                self.db.commit()
                result_payload = {"lead_id": new_lead.id, "email": customer_email, "company": company}
                success = True

            # 2. Support AI - Notify Customer / Ticket Reply
            elif "support" in assigned and ("notify" in desc or "send" in desc or "reply" in desc or "ticket" in desc):
                if meeting.trigger_type == "support_ticket" and meeting.trigger_id:
                    ticket_id = meeting.trigger_id
                    ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
                    if ticket:
                        reply_msg = (
                            "Dear customer, thank you for reaching out. We have escalated your inquiry "
                            "directly to our executive board. A meeting was held with our CEO, customer service team, "
                            "and sales department to review your request. We have initiated a priority account file for you, "
                            "and our Sales manager will follow up with you shortly to assist with next steps."
                        )
                        msg = TicketMessage(
                            ticket_id=ticket.id,
                            sender="agent",
                            content=reply_msg
                        )
                        self.db.add(msg)
                        self.db.commit()

                        from app.services.agents.support import SupportAgent
                        support_agent = SupportAgent(self.db, self.tenant_id)
                        await support_agent.send_message(ticket.channel, ticket.customer_contact, reply_msg)
                        result_payload = {"ticket_id": ticket.id, "sent_to": ticket.customer_contact}
                        success = True
                    else:
                        success = True
                        result_payload = {"note": "Ticket not found; customer notification recorded."}
                else:
                    success = True
                    result_payload = {"note": "Customer notification directive recorded for manual outreach."}

            # 3. HR AI - Update Candidate Status
            elif "hr" in assigned and ("candidate" in desc or "offer" in desc or "status" in desc):
                candidate = None
                if meeting.trigger_id and meeting.trigger_type == "candidate_hiring":
                    candidate = self.db.query(Candidate).filter(Candidate.id == meeting.trigger_id).first()
                else:
                    candidate = self.db.query(Candidate).filter(Candidate.tenant_id == self.tenant_id).order_by(Candidate.created_at.desc()).first()

                if candidate:
                    candidate.status = "offered"
                    self.db.commit()

                    log = ActivityLog(
                        tenant_id=self.tenant_id,
                        agent_name="HR AI",
                        action="Candidate Promoted",
                        description=f"Autonomously updated candidate '{candidate.name}' status to 'offered' following budget approval.",
                        status="success"
                    )
                    self.db.add(log)
                    self.db.commit()
                    result_payload = {"candidate_id": candidate.id, "new_status": "offered"}
                    success = True
                else:
                    success = True

            else:
                log = ActivityLog(
                    tenant_id=self.tenant_id,
                    agent_name=action_record.assigned_to,
                    action="Task Recorded",
                    description=f"Boardroom directive recorded for: '{action_record.description}'",
                    status="pending"
                )
                self.db.add(log)
                self.db.commit()
                result_payload = {"note": "Task recorded for manual execution"}
                success = True

        except Exception as ex:
            logger.error("Error executing boardroom action: %s", ex)
            success = False
            result_payload = {"error": str(ex)}

        action_record.status = "completed" if success else "failed"
        action_record.result = result_payload
        self.db.add(action_record)
        self.db.commit()

        # Update JSON action_items on meeting for backward compatibility
        actions_list = list(meeting.action_items or [])
        for act in actions_list:
            if act.get("id") == action_record.id:
                act["status"] = action_record.status
                act["approved_by"] = action_record.approved_by
        meeting.action_items = actions_list
        self.db.commit()

        emit_event(
            self.db,
            meeting.id,
            "action.executed",
            actor=action_record.assigned_to,
            phase=meeting.current_phase,
            payload={
                "action_id": action_record.id,
                "status": action_record.status,
                "result": result_payload
            }
        )
        return success

    async def approve_action(self, action_id: str, approved_by: str = "user") -> MeetingAction:
        """Approve and execute a governed boardroom action."""
        action = self.db.query(MeetingAction).filter(MeetingAction.id == action_id).first()
        if not action:
            raise ValueError(f"Meeting action {action_id} not found")
        if action.status not in ("awaiting_approval", "pending"):
            return action

        meeting = self.db.query(AgentMeeting).filter(AgentMeeting.id == action.meeting_id).first()
        action.status = "executing"
        action.approved_by = approved_by
        action.approved_at = datetime.datetime.now(datetime.timezone.utc)
        self.db.add(action)
        self.db.commit()

        emit_event(
            self.db,
            action.meeting_id,
            "action.approved",
            actor=approved_by,
            phase="approval",
            payload={"action_id": action.id, "approved_by": approved_by}
        )

        if meeting:
            await self._execute_single_action(meeting, action)
            self._check_and_finalize_meeting(meeting)

        return action

    def reject_action(self, action_id: str, rejected_by: str = "user", reason: Optional[str] = None) -> MeetingAction:
        """Reject a proposed boardroom action."""
        action = self.db.query(MeetingAction).filter(MeetingAction.id == action_id).first()
        if not action:
            raise ValueError(f"Meeting action {action_id} not found")

        action.status = "rejected"
        action.rejected_by = rejected_by
        action.rejected_at = datetime.datetime.now(datetime.timezone.utc)
        action.rejection_reason = reason
        self.db.add(action)
        self.db.commit()

        # Update JSON action_items on meeting
        meeting = self.db.query(AgentMeeting).filter(AgentMeeting.id == action.meeting_id).first()
        if meeting:
            actions_list = list(meeting.action_items or [])
            for act in actions_list:
                if act.get("id") == action.id:
                    act["status"] = "rejected"
            meeting.action_items = actions_list
            self.db.commit()

        emit_event(
            self.db,
            action.meeting_id,
            "action.rejected",
            actor=rejected_by,
            phase="approval",
            payload={"action_id": action.id, "rejected_by": rejected_by, "reason": reason}
        )

        if meeting:
            self._check_and_finalize_meeting(meeting)

        return action

    def _check_and_finalize_meeting(self, meeting: AgentMeeting):
        """Check if all actions are completed/rejected and transition to completed if so."""
        pending_count = self.db.query(MeetingAction).filter(
            MeetingAction.meeting_id == meeting.id,
            MeetingAction.status.in_(["pending", "awaiting_approval", "executing"])
        ).count()

        if pending_count == 0:
            meeting.status = "completed"
            meeting.finished_at = datetime.datetime.now(datetime.timezone.utc)
            transition(self.db, meeting, "completed")
            emit_event(
                self.db,
                meeting.id,
                "meeting.completed",
                actor="system",
                phase="completed",
                payload={"meeting_id": meeting.id}
            )

    def cancel_meeting(self, meeting_id: str, cancelled_by: str = "user", reason: Optional[str] = None) -> Optional[AgentMeeting]:
        """Cancel an ongoing or awaiting boardroom meeting."""
        meeting = self.db.query(AgentMeeting).filter(AgentMeeting.id == meeting_id).first()
        if not meeting:
            return None

        meeting.status = "cancelled"
        meeting.failure_reason = reason or "Meeting cancelled by user"
        meeting.finished_at = datetime.datetime.now(datetime.timezone.utc)
        transition(self.db, meeting, "cancelled")
        emit_event(
            self.db,
            meeting.id,
            "meeting.cancelled",
            actor=cancelled_by,
            phase="cancelled",
            payload={"reason": reason or "Cancelled by user"}
        )
        return meeting

    async def execute_action_items(self, meeting_id: str):
        """Legacy compatibility wrapper."""
        actions = self.db.query(MeetingAction).filter(
            MeetingAction.meeting_id == meeting_id,
            MeetingAction.status == "pending"
        ).all()
        meeting = self.db.query(AgentMeeting).filter(AgentMeeting.id == meeting_id).first()
        if not meeting:
            return
        for act in actions:
            if act.risk_tier == "low":
                await self._execute_single_action(meeting, act)

    def _collect_evidence_pack(self, meeting: AgentMeeting) -> dict:
        sources = [{
            "id": "meeting_context",
            "type": "meeting",
            "summary": meeting.context_summary or "No meeting context was provided.",
            "reliability": self._score_source("meeting", meeting.context_summary)
        }]

        if meeting.trigger_type == "support_ticket" and meeting.trigger_id:
            ticket = self.db.query(Ticket).filter(Ticket.id == meeting.trigger_id).first()
            if ticket:
                sources.append({
                    "id": f"ticket:{ticket.id}",
                    "type": "support_ticket",
                    "summary": f"Subject={ticket.subject}; channel={ticket.channel}; customer={ticket.customer_contact}; priority={ticket.priority}; status={ticket.status}; description={ticket.description}",
                    "reliability": self._score_source("support_ticket", ticket.description)
                })

        knowledge_docs = self.db.query(KnowledgeDocument).filter(
            KnowledgeDocument.tenant_id == self.tenant_id
        ).limit(20).all()
        for doc in knowledge_docs:
            sources.append({
                "id": f"knowledge:{doc.id}",
                "type": "knowledge_base",
                "summary": f"department={doc.department}; type={doc.doc_type}; content={doc.content}",
                "reliability": self._score_source("knowledge_base", doc.content)
            })

        lead_count = self.db.query(Lead).filter(Lead.tenant_id == self.tenant_id).count()
        open_ticket_count = self.db.query(Ticket).filter(Ticket.tenant_id == self.tenant_id, Ticket.status == "open").count()
        contract_count = self.db.query(Contract).filter(Contract.tenant_id == self.tenant_id).count()
        anomaly_count = self.db.query(Transaction).filter(Transaction.tenant_id == self.tenant_id, Transaction.is_anomaly == True).count()
        configured_tools = [
            cred.provider for cred in self.db.query(APICredential).filter(APICredential.tenant_id == self.tenant_id).all()
        ]

        sources.append({
            "id": "tenant_operating_metrics",
            "type": "database_query",
            "summary": f"leads={lead_count}; open_support_tickets={open_ticket_count}; contracts={contract_count}; anomalous_transactions={anomaly_count}",
            "reliability": self._score_source("database_query", "tenant metrics")
        })
        sources.append({
            "id": "configured_integrations",
            "type": "credential_inventory",
            "summary": "configured_providers=" + ", ".join(configured_tools) if configured_tools else "configured_providers=none",
            "reliability": self._score_source("credential_inventory", configured_tools)
        })

        return {"sources": sources}

    def _score_source(self, source_type: str, content) -> dict:
        has_content = bool(content)
        source_defaults = {
            "database_query": (95, 90, 90, 95, 85),
            "credential_inventory": (95, 85, 80, 90, 85),
            "support_ticket": (90, 75, 70, 70, 65),
            "knowledge_base": (70, 70, 65, 60, 60),
            "meeting": (85, 65, 60, 55, 55),
        }
        freshness, reliability, completeness, verification, bias = source_defaults.get(source_type, (60, 60, 50, 50, 50))
        if not has_content:
            completeness = min(completeness, 20)
            verification = min(verification, 30)
        overall = round((freshness + reliability + completeness + verification + bias) / 5)
        return {
            "freshness_score": freshness,
            "reliability_score": reliability,
            "completeness_score": completeness,
            "verification_score": verification,
            "bias_score": bias,
            "overall_trust_score": overall,
        }

    async def _run_specialist_analysis(self, agent: str, meeting: AgentMeeting, context: str, evidence_pack: dict) -> dict:
        system_prompt = self._structured_agent_prompt(agent, "analysis")
        prompt = (
            f"Boardroom topic: {meeting.title}\n"
            f"Context: {context}\n"
            f"Evidence pack JSON: {json.dumps(evidence_pack, default=str)}\n"
            "Return JSON with keys: agent, findings, calculations, sources, assumptions, confidence_rationale, recommended_actions, data_quality_assessment. "
            "Every source must be one of the evidence pack source ids. Use calculations when the supplied data supports them. "
            "If evidence is insufficient, say so explicitly instead of filling gaps with assumptions."
        )
        raw = await self._safe_complete(prompt, system_prompt)
        parsed = self._parse_json_object(raw)
        if not parsed:
            parsed = {
                "agent": agent,
                "findings": [raw.strip()] if raw else ["No analyzable model output was returned."],
                "sources": ["meeting_context"],
                "assumptions": ["Output was not valid JSON and was retained as an unstructured finding."],
                "confidence_score": 0,
                "confidence_rationale": "No structured confidence could be derived from invalid JSON output.",
                "recommended_actions": []
            }
        parsed["agent"] = agent
        return parsed

    async def _run_cross_agent_critique(self, agent: str, meeting: AgentMeeting, context: str, evidence_pack: dict, analyses: dict) -> dict:
        system_prompt = self._structured_agent_prompt(agent, "critique")
        prompt = (
            f"Boardroom topic: {meeting.title}\n"
            f"Context: {context}\n"
            f"Evidence pack JSON: {json.dumps(evidence_pack, default=str)}\n"
            f"Agent analyses JSON: {json.dumps(analyses, default=str)}\n"
            "Return JSON with keys: agent, agreement_points, objections, missing_information, risk_factors, sources. "
            "Critique only claims made by other agents and cite only evidence pack source ids."
        )
        raw = await self._safe_complete(prompt, system_prompt)
        parsed = self._parse_json_object(raw)
        if not parsed:
            parsed = {
                "agent": agent,
                "agreement_points": [],
                "objections": [raw.strip()] if raw else ["No analyzable critique was returned."],
                "missing_information": ["Critique output was not valid JSON."],
                "risk_factors": [],
                "sources": ["meeting_context"]
            }
        parsed["agent"] = agent
        return parsed

    async def _run_decision_synthesis(self, meeting: AgentMeeting, context: str, evidence_pack: dict, analyses: list, critiques: list) -> dict:
        system_prompt = (
            "You are CEO AI and Orchestrator AI for an enterprise decision-intelligence boardroom. "
            "Produce a final recommendation using only the provided evidence, specialist analyses, and critiques. "
            "Do not invent statistics, sources, fake tool results, random scores, or placeholder work. "
            "If evidence is insufficient, recommend a gated next step instead of pretending certainty."
        )
        prompt = (
            f"Boardroom topic: {meeting.title}\n"
            f"Context: {context}\n"
            f"Evidence pack JSON: {json.dumps(evidence_pack, default=str)}\n"
            f"Analyses JSON: {json.dumps(analyses, default=str)}\n"
            f"Critiques JSON: {json.dumps(critiques, default=str)}\n"
            "Return JSON with keys: executive_summary, key_findings, evidence, sources, financial_impact, operational_impact, "
            "risk_matrix, alternative_options, expert_disagreements, data_gaps, recommended_action, audit_trail, action_items. "
            "action_items must be objects with assigned_to, description, sources. Do not include invented confidence scores; "
            "the platform will derive confidence from evidence quality and expert agreement."
        )
        raw = await self._safe_complete(prompt, system_prompt)
        parsed = self._parse_json_object(raw)
        if not parsed:
            parsed = self._deterministic_synthesis(meeting, analyses, critiques)
        elif "action_items" not in parsed:
            fallback = self._deterministic_synthesis(meeting, analyses, critiques)
            parsed = {
                **fallback,
                **parsed,
                "action_items": fallback["action_items"]
            }
        return parsed

    async def _safe_complete(
        self,
        prompt: str,
        system_prompt: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        try:
            return await self.llm.complete(
                prompt=prompt,
                system_prompt=system_prompt,
                provider=provider or self._provider or "gemini",
                model=model or self._model,
            )
        except Exception as exc:
            return json.dumps({
                "findings": [f"LLM call failed: {exc}"],
                "sources": ["meeting_context"],
                "assumptions": ["The model provider did not return a usable response."],
                "confidence_score": 0,
                "recommended_actions": []
            })

    def _parse_json_object(self, raw: str):
        if not raw:
            return None
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.strip("`").replace("json\n", "", 1).strip()
        if "[MESSAGE]" in clean and "[ACTIONS]" in clean:
            message, actions = clean.split("[ACTIONS]", 1)
            return {
                "executive_summary": message.replace("[MESSAGE]", "").strip(),
                "key_findings": [],
                "risks": [],
                "opportunities": [],
                "recommended_action": message.replace("[MESSAGE]", "").strip(),
                "confidence_score": 50,
                "sources": ["meeting_context"],
                "action_items": json.loads(actions.strip())
            }
        try:
            return json.loads(clean)
        except Exception:
            return None

    def _quality_flags(self, payload: dict, allowed_sources: set) -> list:
        flags = []
        sources = payload.get("sources", []) or []
        unknown_sources = [source for source in sources if source not in allowed_sources]
        if unknown_sources:
            flags.append(f"Rejected unknown sources: {', '.join(unknown_sources)}")
        if not sources:
            flags.append("No sources cited.")
        if payload.get("confidence_score") is None and "confidence_score" in payload:
            flags.append("Missing confidence score.")
        return flags

    def _derive_confidence(self, synthesis: dict, analyses: list, critiques: list, evidence_pack: dict) -> dict:
        cited = set(synthesis.get("sources", []) or [])
        for item in analyses + critiques:
            cited.update(item.get("sources", []) or [])
        source_lookup = {source["id"]: source for source in evidence_pack.get("sources", [])}
        trusted_scores = [
            source_lookup[source_id].get("reliability", {}).get("overall_trust_score", 0)
            for source_id in cited
            if source_id in source_lookup
        ]
        evidence_quality = round(sum(trusted_scores) / len(trusted_scores)) if trusted_scores else 0
        evidence_quantity = min(len(trusted_scores) * 10, 30)
        objections = sum(len(item.get("objections", []) or []) for item in critiques)
        agreement = sum(len(item.get("agreement_points", []) or []) for item in critiques)
        agreement_score = 20 if agreement >= objections else 10 if agreement else 0
        missing_info = sum(len(item.get("missing_information", []) or []) for item in critiques)
        gap_penalty = min(missing_info * 4, 25)
        score = max(0, min(100, round((evidence_quality * 0.5) + evidence_quantity + agreement_score - gap_penalty)))
        rationale = (
            f"Derived from {len(trusted_scores)} cited evidence sources, average source trust {evidence_quality}, "
            f"{agreement} agreement signals, {objections} objections, and {missing_info} missing-information flags."
        )
        return {"score": score, "rationale": rationale}

    def _deterministic_synthesis(self, meeting: AgentMeeting, analyses: list, critiques: list) -> dict:
        action_items = []
        if meeting.trigger_type == "support_ticket":
            if "Sales AI" in (meeting.participants or []):
                action_items.append({
                    "assigned_to": "Sales AI",
                    "description": "Create a CRM lead from the support ticket contact and meeting context.",
                    "sources": ["meeting_context"]
                })
            if "Support AI" in (meeting.participants or []):
                action_items.append({
                    "assigned_to": "Support AI",
                    "description": "Send a customer response that states the request is under review and avoids unverified pricing or commitments.",
                    "sources": ["meeting_context"]
                })
        return {
            "executive_summary": "The boardroom completed with limited structured model output. Proceed only with actions directly supported by tenant records.",
            "key_findings": [item.get("findings", []) for item in analyses],
            "risks": [item.get("risk_factors", []) for item in critiques],
            "opportunities": [],
            "recommended_action": "Use the cited tenant context to execute only verifiable next steps and gather missing data before strategic commitments.",
            "confidence_score": 0,
            "confidence_rationale": "Fallback confidence is zero because the synthesis model did not return structured evidence-backed output.",
            "sources": ["meeting_context"],
            "action_items": action_items
        }

    def _decision_profile_from_meeting(self, meeting: AgentMeeting) -> dict:
        marker = "Decision Profile JSON:"
        context = meeting.context_summary or ""
        if marker in context:
            raw = context.split(marker, 1)[1].strip()
            try:
                return json.loads(raw)
            except Exception:
                pass
        return self.build_decision_profile(meeting.title, context)

    def _detect_industry(self, text: str) -> str:
        industry_keywords = {
            "healthcare": ("healthcare", "clinic", "hospital", "patient", "clinical"),
            "restaurant": ("restaurant", "menu", "food", "franchise", "kitchen", "dining"),
            "real_estate": ("real estate", "property", "development", "lease", "occupancy"),
            "manufacturing": ("manufacturing", "factory", "production", "procurement", "quality"),
            "logistics": ("logistics", "fleet", "route", "warehouse", "shipping"),
            "technology": ("software", "saas", "cloud", "ai", "cyber", "devops", "app", "platform"),
            "retail": ("retail", "store", "inventory", "merchandising", "pos"),
            "fashion": ("fashion", "apparel", "garment", "trend", "supplier"),
            "ecommerce": ("ecommerce", "e-commerce", "marketplace", "cart", "conversion", "retention"),
            "hospitality": ("hotel", "hospitality", "guest", "occupancy", "room rate"),
        }
        scores = {
            industry: sum(1 for keyword in keywords if keyword in text)
            for industry, keywords in industry_keywords.items()
        }
        best_industry, best_score = max(scores.items(), key=lambda item: item[1])
        if best_score:
            return best_industry
        return "general_business"

    def _detect_decision_category(self, text: str) -> str:
        categories = {
            "growth": ("growth", "expand", "market", "launch", "acquisition", "revenue"),
            "investment": ("invest", "roi", "payback", "dcf", "capex", "budget"),
            "operations": ("capacity", "process", "operations", "staffing", "supply", "execution"),
            "risk_compliance": ("risk", "compliance", "privacy", "security", "contract", "regulation"),
            "customer": ("customer", "support", "retention", "churn", "experience"),
            "workforce": ("hiring", "workforce", "headcount", "talent", "org"),
        }
        for category, keywords in categories.items():
            if any(keyword in text for keyword in keywords):
                return category
        return "strategic_decision"

    def _detect_available_data_sources(self, text: str) -> list:
        known_sources = [
            "salesforce", "hubspot", "zoho", "pipedrive", "dynamics", "quickbooks", "xero",
            "netsuite", "sap", "oracle", "mixpanel", "amplitude", "posthog", "ga4",
            "postgresql", "mysql", "mongodb", "snowflake", "bigquery", "redshift",
            "notion", "confluence", "sharepoint", "google drive", "slack", "teams",
            "zendesk", "intercom", "freshdesk", "jira", "linear", "asana", "clickup",
            "github", "gitlab", "aws", "azure", "gcp", "kubernetes",
        ]
        return [source for source in known_sources if source in text]

    def _extract_constraints(self, context: str) -> list:
        constraints = []
        for line in (context or "").splitlines():
            lower = line.lower()
            if any(token in lower for token in ["constraint", "must", "cannot", "deadline", "budget", "limit"]):
                constraints.append(line.strip())
        return constraints[:6]

    def _extract_success_metrics(self, context: str) -> list:
        metrics = []
        for line in (context or "").splitlines():
            lower = line.lower()
            if any(token in lower for token in ["metric", "kpi", "success", "roi", "revenue", "margin", "conversion", "retention"]):
                metrics.append(line.strip())
        return metrics[:6]

    def _extract_stakeholders(self, context: str) -> list:
        stakeholders = []
        for label in ["CEO", "CFO", "COO", "CTO", "Legal", "Sales", "Marketing", "HR", "Customer", "Operations"]:
            if label.lower() in (context or "").lower():
                stakeholders.append(label)
        return stakeholders

    def _structured_agent_prompt(self, agent: str, phase: str) -> str:
        return (
            f"You are {agent}. Focus: {self._get_agent_role_description(agent)} "
            f"Phase: {phase}. Use only supplied evidence and real tool/database results. "
            "Do not invent statistics, percentages, sources, action completion, or placeholder findings. "
            "Return valid JSON only."
        )

    def _format_analysis_message(self, item: dict) -> str:
        return (
            f"Findings: {self._join_list(item.get('findings'))}\n"
            f"Calculations: {self._join_list(item.get('calculations'))}\n"
            f"Assumptions: {self._join_list(item.get('assumptions'))}\n"
            f"Data quality: {self._join_list(item.get('data_quality_assessment'))}\n"
            f"Confidence rationale: {item.get('confidence_rationale', 'Not provided.')}\n"
            f"Recommended actions: {self._join_list(item.get('recommended_actions'))}"
        )

    def _format_critique_message(self, item: dict) -> str:
        return (
            f"Agreement: {self._join_list(item.get('agreement_points'))}\n"
            f"Objections: {self._join_list(item.get('objections'))}\n"
            f"Missing information: {self._join_list(item.get('missing_information'))}\n"
            f"Risk factors: {self._join_list(item.get('risk_factors'))}"
        )

    def _format_synthesis_message(self, item: dict) -> str:
        return (
            f"Executive summary: {item.get('executive_summary', '')}\n"
            f"Key findings: {self._join_list(item.get('key_findings'))}\n"
            f"Risks: {self._join_list(item.get('risks'))}\n"
            f"Opportunities: {self._join_list(item.get('opportunities'))}\n"
            f"Financial impact: {self._join_list(item.get('financial_impact'))}\n"
            f"Operational impact: {self._join_list(item.get('operational_impact'))}\n"
            f"Alternative options: {self._join_list(item.get('alternative_options'))}\n"
            f"Data gaps: {self._join_list(item.get('data_gaps'))}\n"
            f"Recommended action: {item.get('recommended_action', '')}\n"
            f"Confidence rationale: {item.get('confidence_rationale', 'Not calculated.')}"
        )

    def _format_decision_profile_message(self, decision_profile: dict, participants: list, evidence_pack: dict) -> str:
        source_lines = []
        for source in evidence_pack.get("sources", []):
            trust = source.get("reliability", {}).get("overall_trust_score")
            source_lines.append(f"{source.get('id')} ({source.get('type')}, trust {trust})")
        return (
            f"Objective: {decision_profile.get('objective')}\n"
            f"Industry: {decision_profile.get('industry')}\n"
            f"Decision category: {decision_profile.get('decision_category')}\n"
            f"Assembled experts: {', '.join(participants)}\n"
            f"Available data sources: {self._join_list(decision_profile.get('available_data_sources'))}\n"
            f"Evidence sources: {self._join_list(source_lines)}"
        )

    def _join_list(self, value) -> str:
        if not value:
            return "None cited."
        if isinstance(value, list):
            return "; ".join(json.dumps(v) if isinstance(v, (dict, list)) else str(v) for v in value)
        return str(value)

    def _timestamp(self) -> str:
        return datetime.datetime.now().strftime("%I:%M:%S %p")

    def _get_agent_role_description(self, agent_name: str) -> str:
        roles = {
            "CEO AI": "Executive leadership, strategic decisions, financial approvals, team resource coordination.",
            "Support AI": "Customer experience, ticket triaging, immediate response, onboarding issues, customer escalations.",
            "Sales AI": "B2B client sourcing, client calls, enterprise quotes, conversion rate optimization, outbound campaigns.",
            "Finance AI": "Budgets, pricing models, payment anomalies, fraud flags, operational expenses.",
            "CFO AI": "Cost analysis, ROI modeling, financial risk, budget forecasting, and revenue forecast validation.",
            "CTO AI": "Architecture, scalability, security, technical feasibility, code and infrastructure risk.",
            "Legal AI": "Compliance, regulatory risk, contract review, policy obligations, and legal constraints.",
            "Marketing AI": "Brand identity, copy writing, social media outreach, campaigns, platform specific templates.",
            "HR AI": "Candidate recruitment, resume scanning, applicant outreach, onboarding sequences, payroll budget requests.",
            "Risk AI": "Operational risk, security risk, market risk, execution risk, controls, and mitigations."
        }
        roles.update({
            "Executive Strategy Expert": "Business growth, competitive advantage, expansion opportunities, and strategic alignment.",
            "Finance Expert": "ROI, cash flow impact, revenue forecasting, cost analysis, profitability, and financial calculations.",
            "Operations Expert": "Execution feasibility, capacity, resources, process impact, and operational constraints.",
            "Research Expert": "Data collection, market intelligence, trend analysis, and source verification.",
            "Risk Expert": "Operational, financial, strategic, market, and execution risk assessment.",
            "Sales Intelligence Expert": "Pipeline analysis, win-rate forecasting, revenue prediction, and sales bottleneck analysis.",
            "Marketing Intelligence Expert": "Demand forecasting, customer acquisition, competitor positioning, and campaign effectiveness.",
            "Legal & Compliance Expert": "Compliance review, regulatory impact, contract risk, privacy, and data governance.",
            "Human Resources Expert": "Hiring plans, organizational design, workforce cost, and talent availability.",
        })
        return roles.get(agent_name, "Business specialist AI.")
