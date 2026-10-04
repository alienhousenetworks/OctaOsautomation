import os
os.environ["TESTING"] = "1"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, AsyncMock
import json

from app.main import app
from app.api.deps import get_db, get_current_tenant_id
from app.models.base import Base
from app.models.verticals import Ticket, Lead, AgentMeeting
from app.models.boardroom_events import MeetingEvent, MeetingEvidence, MeetingAction
from app.services.agents.boardroom import BoardroomService
from app.services.agents.boardroom_state import classify_action

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_boardroom.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

tenant_id_override_store = {"tenant_id": None}

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_get_current_tenant_id():
        return tenant_id_override_store["tenant_id"] or "test-tenant-id"

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_tenant_id] = override_get_current_tenant_id
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_risk_tier_classification():
    assert classify_action("Create internal note regarding billing") == ("create_internal_note", "low")
    assert classify_action("Tag lead with priority-enterprise") == ("tag_lead", "low")
    assert classify_action("Create lead for new prospective buyer") == ("create_lead", "medium")
    assert classify_action("Update ticket status to closed") == ("update_ticket_status", "medium")
    assert classify_action("Send customer email with quote") == ("send_customer_reply", "high")
    assert classify_action("Promote candidate to next interview stage") == ("promote_candidate", "high")

@pytest.mark.asyncio
@patch("app.services.llm_gateway.LLMGateway.complete")
async def test_boardroom_inquiry_classification(mock_complete, db):
    mock_complete.return_value = '{"needs_meeting": true, "title": "Enterprise Sales Escalation", "participants": ["CEO AI", "Support AI", "Sales AI"], "reason": "Customer inquiry regarding bulk pricing"}'

    tenant_id = "test-tenant-id"
    service = BoardroomService(db, tenant_id)

    ticket = Ticket(
        tenant_id=tenant_id,
        subject="Enterprise Inquiry",
        description="We want to buy 500 licenses, please send pricing info.",
        status="open",
        channel="whatsapp",
        customer_contact="+123456789",
        approval_status="pending"
    )
    db.add(ticket)
    db.commit()

    res = await service.classify_ticket_inquiry(ticket.id)
    assert res["needs_meeting"] is True
    assert res["title"] == "Enterprise Sales Escalation"
    assert "Sales AI" in res["participants"]

@pytest.mark.asyncio
@patch("app.services.llm_gateway.LLMGateway.complete")
@patch("app.services.agents.support.SupportAgent.send_message", new_callable=AsyncMock)
async def test_run_meeting_governance_and_approval(mock_send_message, mock_complete, db):
    support_analysis = json.dumps({
        "agent": "Support AI",
        "findings": ["Customer wants custom enterprise pricing"],
        "sources": ["meeting_context"],
        "confidence_score": 85,
        "recommended_actions": ["Review discount schedule"]
    })
    sales_analysis = json.dumps({
        "agent": "Sales AI",
        "findings": ["High value account with 500 potential seats"],
        "sources": ["meeting_context"],
        "confidence_score": 90,
        "recommended_actions": ["Create lead in CRM"]
    })
    support_critique = json.dumps({
        "agent": "Support AI",
        "agreement_points": ["Agree on creating lead"],
        "objections": [],
        "sources": ["meeting_context"]
    })
    sales_critique = json.dumps({
        "agent": "Sales AI",
        "agreement_points": ["Agree on urgent response"],
        "objections": [],
        "sources": ["meeting_context"]
    })
    ceo_synthesis = json.dumps({
        "executive_summary": "Approved enterprise track with lead capture and managed response.",
        "key_findings": ["500 seats request"],
        "sources": ["meeting_context"],
        "confidence_score": 88,
        "recommended_action": "Capture lead and prepare executive response",
        "action_items": [
            {"assigned_to": "Sales AI", "description": "Create internal note regarding customer pricing query", "sources": ["meeting_context"]},
            {"assigned_to": "Sales AI", "description": "Create lead for prospect in CRM", "sources": ["meeting_context"]},
            {"assigned_to": "Support AI", "description": "Send customer notification regarding review", "sources": ["meeting_context"]}
        ]
    })

    mock_complete.side_effect = [
        support_analysis,
        sales_analysis,
        support_critique,
        sales_critique,
        ceo_synthesis,
    ]

    tenant_id = "test-tenant-id"
    service = BoardroomService(db, tenant_id)

    ticket = Ticket(
        tenant_id=tenant_id,
        subject="Enterprise pricing quote",
        description="Hello, can we purchase an enterprise package?",
        status="open",
        channel="email",
        customer_contact="prospect@company.com",
        approval_status="pending"
    )
    db.add(ticket)
    db.commit()

    classification = {
        "needs_meeting": True,
        "title": "Escalated Lead: prospect@company.com",
        "participants": ["CEO AI", "Support AI", "Sales AI"]
    }

    meeting = await service.create_meeting_from_ticket(ticket.id, classification)
    assert meeting is not None
    assert meeting.status == "active"

    # Run meeting
    await service.run_meeting(meeting.id)
    db.refresh(meeting)

    # Held action triggers human governance gate!
    assert meeting.status == "awaiting_approval"
    assert meeting.current_phase == "approval"

    # Check MeetingEvidence table
    evidence_rows = db.query(MeetingEvidence).filter(MeetingEvidence.meeting_id == meeting.id).all()
    assert len(evidence_rows) > 0

    # Check MeetingEvent table
    event_rows = db.query(MeetingEvent).filter(MeetingEvent.meeting_id == meeting.id).all()
    assert len(event_rows) > 0
    event_types = [e.event_type for e in event_rows]
    assert "meeting.started" in event_types
    assert "evidence.added" in event_types
    assert "agent.completed" in event_types
    assert "action.proposed" in event_types

    actions = db.query(MeetingAction).filter(MeetingAction.meeting_id == meeting.id).all()
    assert len(actions) == 3

    # Low-risk action auto-approved
    note_action = next(a for a in actions if "internal note" in a.description.lower())
    assert note_action.risk_tier == "low"
    assert note_action.status == "completed"

    # High-risk action awaiting approval
    high_risk_action = next(a for a in actions if "notification" in a.description.lower())
    assert high_risk_action.risk_tier == "high"
    assert high_risk_action.status == "awaiting_approval"

    # Lead action awaiting approval (medium risk with <75% confidence)
    lead_action = next(a for a in actions if "create lead" in a.description.lower())
    assert lead_action.risk_tier == "medium"
    assert lead_action.status == "awaiting_approval"

    # Human manager approves the lead action and customer reply action
    await service.approve_action(lead_action.id, approved_by="sales-manager")
    db.refresh(lead_action)
    assert lead_action.status == "completed"

    # Verify that a lead was indeed created
    lead = db.query(Lead).filter(Lead.tenant_id == tenant_id).first()
    assert lead is not None
    assert lead.email == "prospect@company.com"

    await service.approve_action(high_risk_action.id, approved_by="manager-jane")
    db.refresh(high_risk_action)
    assert high_risk_action.status == "completed"
    assert high_risk_action.approved_by == "manager-jane"

    # All actions resolved -> meeting transitions to completed!
    db.refresh(meeting)
    assert meeting.status == "completed"
    assert meeting.current_phase == "completed"

def test_action_rejection(db):
    tenant_id = "test-tenant-id"
    service = BoardroomService(db, tenant_id)

    meeting = AgentMeeting(
        tenant_id=tenant_id,
        title="Test Action Rejection",
        status="awaiting_approval",
        current_phase="approval",
        trigger_type="manual",
        participants=["CEO AI"]
    )
    db.add(meeting)
    db.commit()

    action = MeetingAction(
        id="act-test-1",
        meeting_id=meeting.id,
        action_type="send_customer_reply",
        assigned_to="Support AI",
        description="Send customer notification",
        risk_tier="high",
        status="awaiting_approval"
    )
    db.add(action)
    db.commit()

    rejected = service.reject_action(action.id, rejected_by="admin", reason="Incorrect discount offered")
    assert rejected.status == "rejected"
    assert rejected.rejection_reason == "Incorrect discount offered"

    db.refresh(meeting)
    assert meeting.status == "completed"

def test_cancel_meeting(db):
    tenant_id = "test-tenant-id"
    service = BoardroomService(db, tenant_id)

    meeting = AgentMeeting(
        tenant_id=tenant_id,
        title="Meeting to Cancel",
        status="active",
        current_phase="analysis",
        trigger_type="manual",
        participants=["CEO AI"]
    )
    db.add(meeting)
    db.commit()

    service.cancel_meeting(meeting.id, cancelled_by="user", reason="Duplicate inquiry")
    db.refresh(meeting)
    assert meeting.status == "cancelled"
    assert meeting.failure_reason == "Duplicate inquiry"

def test_dynamic_boardroom_assembly_selects_relevant_experts(db):
    service = BoardroomService(db, "test-tenant-id")

    profile = service.build_decision_profile(
        title="Evaluate healthcare AI expansion",
        context=(
            "We need to decide whether to launch a clinical workflow SaaS product. "
            "Use HubSpot pipeline data, GA4 acquisition metrics, privacy constraints, "
            "ROI, and hiring capacity as success inputs."
        ),
    )
    participants = service.assemble_boardroom(profile)

    assert profile["industry"] == "healthcare"
    assert "Finance Expert" in participants
    assert "Risk Expert" in participants
    assert "Healthcare Operations Expert" in participants
    assert "Sales Intelligence Expert" in participants
    assert "Marketing Intelligence Expert" in participants
    assert "Legal & Compliance Expert" in participants
    assert "Human Resources Expert" in participants

def test_coordination_api_endpoints(client, db):
    tenant_id = "test-tenant-id"
    meeting = AgentMeeting(
        id="m-api-test",
        tenant_id=tenant_id,
        title="API Test Meeting",
        status="awaiting_approval",
        current_phase="approval",
        trigger_type="manual",
        participants=["CEO AI", "Finance Expert"]
    )
    db.add(meeting)
    ev = MeetingEvidence(
        id="ev-1",
        meeting_id=meeting.id,
        source_ref="ticket:123",
        source_type="support_ticket",
        trust_score=90,
        excerpt="Enterprise pricing requested"
    )
    db.add(ev)
    act = MeetingAction(
        id="act-1",
        meeting_id=meeting.id,
        action_type="send_customer_reply",
        assigned_to="Support AI",
        description="Send customer notification",
        risk_tier="high",
        status="awaiting_approval"
    )
    db.add(act)
    db.commit()

    # GET evidence
    res_ev = client.get(f"/api/v1/coordination/meetings/{meeting.id}/evidence")
    assert res_ev.status_code == 200
    assert len(res_ev.json()) == 1
    assert res_ev.json()[0]["source_ref"] == "ticket:123"

    # GET actions
    res_act = client.get(f"/api/v1/coordination/meetings/{meeting.id}/actions")
    assert res_act.status_code == 200
    assert len(res_act.json()) == 1
    assert res_act.json()[0]["risk_tier"] == "high"

    # POST approve action
    res_app = client.post(
        f"/api/v1/coordination/meetings/{meeting.id}/actions/{act.id}/approve",
        json={"approved_by": "lead-manager"}
    )
    assert res_app.status_code == 200
    assert res_app.json()["status"] == "completed"

    # GET export
    res_export = client.get(f"/api/v1/coordination/meetings/{meeting.id}/export?format=json")
    assert res_export.status_code == 200
    assert res_export.json()["title"] == "API Test Meeting"

    # GET analytics
    res_ana = client.get("/api/v1/coordination/analytics")
    assert res_ana.status_code == 200
    assert res_ana.json()["total_meetings"] >= 1
