import os
os.environ["TESTING"] = "1"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone

from app.main import app
from app.api.deps import get_db, get_current_tenant_id, get_current_user
from app.models.base import Base, Tenant, User, APICredential
from app.models.verticals import Ticket, TicketMessage, SupportAgentPresence
from app.models.agents import KnowledgeDocument
from app.models.enterprise import KnowledgeChunk

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_support_handoff.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

test_tenant_id = "test-support-tenant-123"
test_user_id = "test-agent-user-456"


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    # Create dummy tenant & user
    tenant = Tenant(id=test_tenant_id, name="Acme Support Corp", subdomain="acme", is_active=True)
    user = User(
        id=test_user_id,
        tenant_id=test_tenant_id,
        email="agent@acme.com",
        name="Agent Smith",
        hashed_password="hashed_pw_test",
        is_active=True,
        is_verified=True,
        role="admin"
    )
    session.add_all([tenant, user])
    session.commit()

    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_get_current_tenant_id():
        return test_tenant_id

    def override_get_current_user():
        return db.query(User).filter(User.id == test_user_id).first()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_tenant_id] = override_get_current_tenant_id
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_widget_config(client, db):
    response = client.get(f"/api/v1/support/widget/config/{test_tenant_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == test_tenant_id
    assert "Acme Support Corp" in data["title"]
    assert data["ai_enabled"] is True


def test_widget_embed_js(client):
    response = client.get("/api/v1/support/widget/embed.js")
    assert response.status_code == 200
    assert "application/javascript" in response.headers["content-type"]
    assert "OctaSupport" in response.text or "octaos-widget-root" in response.text


@pytest.mark.asyncio
@patch("app.services.llm_gateway.LLMGateway.complete")
async def test_widget_message_kb_grounded_answer(mock_complete, client, db):
    mock_complete.return_value = "You can update custom domains in Project Settings under Domains."

    # Add a Knowledge Chunk
    chunk = KnowledgeChunk(
        tenant_id=test_tenant_id,
        document_id="doc1",
        title="Custom Domains FAQ",
        content="To configure custom domains, navigate to Project Settings -> Domains and add your CNAME record.",
        embedding_hint="custom domains cname dns project settings",
        department="Support",
        is_active=True,
        version=1
    )
    db.add(chunk)
    db.commit()

    response = client.post(
        f"/api/v1/support/widget/message/{test_tenant_id}",
        json={
            "session_id": "session_test_1",
            "message": "How do I configure custom domains?",
            "sender_name": "Alice Visitor"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Domains" in data["reply"]
    assert len(data["citations"]) > 0


@pytest.mark.asyncio
async def test_out_of_context_suggests_live_chat(client, db):
    response = client.post(
        f"/api/v1/support/widget/message/{test_tenant_id}",
        json={
            "session_id": "session_test_2",
            "message": "What is the secret recipe for quantum cold fusion?",
            "sender_name": "Curious Cat"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "out_of_context"
    assert data["suggest_live_chat"] is True
    assert data["reason"] == "not_in_kb"


@pytest.mark.asyncio
async def test_loop_detected_suggests_live_chat(client, db):
    # Send user frustration trigger
    response = client.post(
        f"/api/v1/support/widget/message/{test_tenant_id}",
        json={
            "session_id": "session_test_3",
            "message": "You keep repeating yourself, this doesn't help and I am stuck!",
            "sender_name": "Frustrated User"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "loop_detected"
    assert data["suggest_live_chat"] is True
    assert data["reason"] == "loop_detected"


@pytest.mark.asyncio
async def test_human_handoff_with_agent_online(client, db):
    # Set agent presence to online
    presence = SupportAgentPresence(
        tenant_id=test_tenant_id,
        user_id=test_user_id,
        user_name="Agent Smith",
        is_online=True,
        last_heartbeat=datetime.now(timezone.utc)
    )
    db.add(presence)
    db.commit()

    # Visitor asks explicitly for human
    response = client.post(
        f"/api/v1/support/widget/message/{test_tenant_id}",
        json={
            "session_id": "session_test_handoff",
            "message": "I want to talk to human please",
            "sender_name": "Bob Client"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "handoff_queued"
    assert data["mode"] == "human"
    assert data["live_chat_available"] is True

    # Check ticket status in database
    ticket = db.query(Ticket).filter(Ticket.id == data["ticket_id"]).first()
    assert ticket.status == "pending_human"

    # Agent claims ticket
    claim_resp = client.post(f"/api/v1/support/tickets/{ticket.id}/claim")
    assert claim_resp.status_code == 200
    assert claim_resp.json()["status"] == "claimed"

    db.refresh(ticket)
    assert ticket.status == "human_handling"
    assert ticket.claimed_by == test_user_id

    # Agent sends reply to visitor
    reply_resp = client.post(
        f"/api/v1/support/tickets/{ticket.id}/reply",
        json={"content": "Hello Bob! I am Agent Smith. How can I help you today?"}
    )
    assert reply_resp.status_code == 200

    # Visitor polls and receives agent message
    poll_resp = client.get(f"/api/v1/support/widget/poll/{test_tenant_id}/{ticket.session_id}")
    assert poll_resp.status_code == 200
    poll_data = poll_resp.json()
    assert poll_data["ticket"]["status"] == "human_handling"
    assert any("Agent Smith" in m["content"] for m in poll_data["messages"])

    # Agent resolves ticket
    resolve_resp = client.post(f"/api/v1/support/tickets/{ticket.id}/resolve")
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "resolved"

    db.refresh(ticket)
    assert ticket.status == "resolved"
    assert ticket.mode == "ai"


def test_offline_agents_raises_ticket(client, db):
    # No presence records in DB -> agents offline
    response = client.post(
        f"/api/v1/support/widget/raise-ticket/{test_tenant_id}",
        json={
            "session_id": "session_offline_ticket",
            "problem": "Payment failed via Razorpay but card was debited",
            "name": "Sarah Connor",
            "email": "sarah@skynet.com",
            "mobile_no": "+1-555-0199"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    ticket_id = data["ticket_id"]

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    assert ticket is not None
    assert ticket.customer_name == "Sarah Connor"
    assert ticket.customer_email == "sarah@skynet.com"
    assert ticket.customer_phone == "+1-555-0199"
    assert ticket.priority == "high"
    assert ticket.channel == "widget"
    assert "Razorpay" in ticket.description


def test_list_tickets_and_messages_serializable(client, db):
    client.post(
        f"/api/v1/support/widget/raise-ticket/{test_tenant_id}",
        json={
            "session_id": "session_list_test",
            "problem": "Cannot log in",
            "name": "Neo",
            "email": "neo@matrix.io",
            "mobile_no": "+1-555-0100",
        },
    )

    resp = client.get("/api/v1/support/tickets")
    assert resp.status_code == 200
    tickets = resp.json()
    assert len(tickets) == 1
    assert tickets[0]["customer_name"] == "Neo"
    assert tickets[0]["customer_phone"] == "+1-555-0100"

    msgs = client.get(f"/api/v1/support/tickets/{tickets[0]['id']}/messages")
    assert msgs.status_code == 200
    assert any("Neo" in m["content"] for m in msgs.json())
