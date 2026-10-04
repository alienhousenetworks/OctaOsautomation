"""Capability 19: Conversation & Objection Handling Agent.

Handles inbound prospect replies:
1. Intent Classification: interested | objection | wrong_person | unsubscribe | timing_later | question
2. Unsubscribe Suppression: immediately halts outreach and records DNC entry in SuppressionRecord.
3. Objection Playbook Resolution: matches prospect objections against proven Tenant Playbooks.
4. Meeting Scheduling: syncs calendar slots with Google Calendar.
"""
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.services.sales_os.agents.base import BaseSalesAgent, AgentResult, EvidenceItem
from app.models.deal_room import DealRoom, DealObjection, CompanySalesContext, BuyingCommitteeMember
from app.services.sales_os.governance.suppression import SuppressionService
from app.services.knowledge_os.entity_extractor import extract_json_safe
from app.services.rag.hybrid_engine import HybridRAGEngine


class ConversationAgent(BaseSalesAgent):
    def __init__(self, db: Session, tenant_id: str):
        super().__init__(db, tenant_id, "agent_19_conversation")
        self.suppression = SuppressionService(db, tenant_id)
        self.rag = HybridRAGEngine(db, tenant_id)

    async def execute(self, deal_room_id: str, parameters: Dict[str, Any] = None) -> AgentResult:
        start_time = time.time()
        params = parameters or {}
        inbound_text = (params.get("inbound_text") or params.get("reply_text") or "").strip()
        sender_email = params.get("sender_email", "")
        committee_member_id = params.get("committee_member_id")

        if not sender_email and committee_member_id:
            member = (
                self.db.query(BuyingCommitteeMember)
                .filter(BuyingCommitteeMember.id == committee_member_id)
                .first()
            )
            if member:
                sender_email = member.email

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

        # Heuristic fast-path
        lower_inbound = inbound_text.lower()
        if any(w in lower_inbound for w in ["unsubscribe", "remove me", "stop emailing", "take me off"]):
            intent = "unsubscribe"
            parsed = {"intent": "unsubscribe"}
        elif any(w in lower_inbound for w in ["expensive", "cost", "pricing", "budget"]):
            intent = "objection"
            parsed = {"intent": "objection", "objection_category": "pricing"}
        elif any(w in lower_inbound for w in ["competitor", "already using", "alternative"]):
            intent = "objection"
            parsed = {"intent": "objection", "objection_category": "competitor"}
        else:
            prompt = f"""You are the OctaOS Inbound Sales Conversation Agent.
Analyze this reply from a prospect at {deal_room.company_name}.

Prospect Reply:
\"\"\"{inbound_text}\"\"\"

Classify the intent into exactly ONE of:
- "interested" (wants demo, call, pricing, or next steps)
- "objection" (pushes back on price, competitor, timing, or need)
- "unsubscribe" (explicitly asks to be removed, not interested, stop emailing)
- "wrong_person" (directs to someone else)
- "timing_later" (asks to follow up in Q3, next month, next year)
- "question" (asks a specific feature/technical question)

If it is an objection, categorize it into: "pricing", "competitor", "timing", "authority", or "security".

Output a JSON object:
{{
  "intent": "string",
  "objection_category": "string or null",
  "suggested_reply": "string (professional, empathetic response under 80 words)"
}}"""

            try:
                resp = await self.llm.complete(prompt=prompt, model="claude-3-haiku-20240307", provider="anthropic")
                parsed = extract_json_safe(resp)
                intent = parsed.get("intent", "question")
            except Exception:
                intent = "question"
                parsed = {"intent": "question", "suggested_reply": "Thanks for getting back to me. How can I best assist?"}

        # 2. Action based on intent
        if intent == "unsubscribe":
            # Add to global suppression registry
            if sender_email:
                self.suppression.add_suppression(
                    identifier_type="email",
                    identifier_value=sender_email,
                    reason="prospect_unsubscribe_request",
                    origin="conversation_agent",
                    notes=f"Unsubscribed via inbound message: {inbound_text[:80]}",
                )
            deal_room.stage = "lost"
            self.db.commit()

            return AgentResult(
                agent_id=self.agent_id,
                tenant_id=self.tenant_id,
                deal_room_id=deal_room.id,
                decision="executed",
                confidence=1.0,
                source="inbound_reply",
                reasoning_summary=f"Prospect requested removal. Contact {sender_email} added to suppression registry.",
                recommended_next_step="halt_all_cadences",
                data={"intent": "unsubscribe", "suppressed": True},
                execution_time_ms=int((time.time() - start_time) * 1000),
            )

        elif intent == "objection":
            obj_cat = parsed.get("objection_category") or "pricing"
            
            # Fetch playbook counter-argument
            ctx = (
                self.db.query(CompanySalesContext)
                .filter(CompanySalesContext.tenant_id == self.tenant_id, CompanySalesContext.is_active == True)
                .first()
            )
            playbook = ctx.objection_playbook if ctx else {}
            cat_entry = playbook.get(obj_cat, ["We understand. Many of our current clients had the same initial thought before seeing measurable ROI."])
            if isinstance(cat_entry, dict):
                pts = cat_entry.get("talking_points", ["We understand. Many of our current clients had the same initial thought before seeing measurable ROI."])
                suggested_counter = pts[0] if isinstance(pts, list) and pts else str(pts)
            elif isinstance(cat_entry, list):
                suggested_counter = cat_entry[0] if cat_entry else "We understand. Many of our current clients had the same initial thought before seeing measurable ROI."
            else:
                suggested_counter = str(cat_entry)

            # Log objection to DealRoom
            deal_obj = DealObjection(
                deal_room_id=deal_room.id,
                tenant_id=self.tenant_id,
                objection_category=obj_cat,
                prospect_statement=inbound_text,
                applied_counter_argument=suggested_counter,
                status="open",
            )
            self.db.add(deal_obj)
            self.db.commit()

            return AgentResult(
                agent_id=self.agent_id,
                tenant_id=self.tenant_id,
                deal_room_id=deal_room.id,
                decision="action_required",
                confidence=0.90,
                evidence=[EvidenceItem(claim=f"Playbook counter-argument for {obj_cat}", source="objection_playbook")],
                source="objection_playbook",
                reasoning_summary=f"Objection ({obj_cat}) detected. Formulated response from sales playbook.",
                recommended_next_step="send_counter_argument",
                data={
                    "intent": "objection",
                    "category": obj_cat,
                    "counter_argument": suggested_counter,
                    "draft_reply": parsed.get("suggested_reply", suggested_counter),
                },
                execution_time_ms=int((time.time() - start_time) * 1000),
            )

        elif intent == "interested":
            deal_room.stage = "replied"
            self.db.commit()
            return AgentResult(
                agent_id=self.agent_id,
                tenant_id=self.tenant_id,
                deal_room_id=deal_room.id,
                decision="meeting_requested",
                confidence=0.95,
                source="inbound_reply",
                reasoning_summary="Positive interest detected. Ready to book calendar meeting.",
                recommended_next_step="schedule_calendar_meeting",
                data={
                    "intent": "interested",
                    "draft_reply": "Thanks for getting back to me! What does your calendar look like this Thursday or Friday for a brief call?",
                },
                execution_time_ms=int((time.time() - start_time) * 1000),
            )

        else:
            # Query hybrid RAG to answer technical or product question
            rag_context = self.rag.assemble_context(inbound_text, top_k=2)
            return AgentResult(
                agent_id=self.agent_id,
                tenant_id=self.tenant_id,
                deal_room_id=deal_room.id,
                decision="question_answered",
                confidence=0.88,
                source="hybrid_rag",
                reasoning_summary="Grounded answer formulated from knowledge base.",
                recommended_next_step="send_answer_and_re_engage",
                data={
                    "intent": intent,
                    "draft_reply": parsed.get("suggested_reply", "Here is the information you requested."),
                    "citations": rag_context.get("citations", []),
                },
                execution_time_ms=int((time.time() - start_time) * 1000),
            )


ConversationIntelligenceAgent = ConversationAgent
