import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.models.base import Base, Tenant, User
from app.models.workflows import Workflow
from app.models.verticals import AgentMeeting
from app.models.executive import (
    PlanVersion, PlanNode, BudgetEnvelope, ExecutiveApprovalRequest,
    WorkflowEvent, PlaybookPostMortem, CapabilityRegistry
)
from app.core.event_ledger import EventLedger
from app.main import app
from app.api import deps

TEST_DB_URL = "sqlite:///./test_executive_phase4.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False, "timeout": 30})

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    tenant = Tenant(id="tenant-epsilon", name="Epsilon Holdings", subdomain="epsilon", company_email="admin@epsilon.com")
    db.add(tenant)
    db.flush()

    wf = Workflow(id="wf-cockpit-1", tenant_id=tenant.id, name="Enterprise Expansion Campaign", vertical="CEO", department="CEO", status="RUNNING")
    db.add(wf)

    # Add active budget envelope
    now = datetime.now(timezone.utc)
    env = BudgetEnvelope(
        id="env-cockpit-1",
        tenant_id=tenant.id,
        department="CEO",
        period_start=now - timedelta(days=30),
        period_end=now + timedelta(days=60),
        authorized_limit=50000.0,
        consumed_amount=12400.0,
        currency="USD",
        is_active=True
    )
    db.add(env)

    # Seed capability registry
    cap1 = CapabilityRegistry(
        id="sales.send_sequence",
        version="1.0.0",
        department="SALES",
        description="Dispatches email sequence to prospective enterprise leads.",
        side_effect_class="R3_EXTERNAL_IRREVERSIBLE",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        cost_model={"base_cost": 0.05}
    )
    cap2 = CapabilityRegistry(
        id="sales.tag_contact",
        version="1.0.0",
        department="SALES",
        description="Internal CRM tag assignment.",
        side_effect_class="R1_INTERNAL_REVERSIBLE",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        cost_model={"base_cost": 0.01}
    )
    cap3 = CapabilityRegistry(
        id="finance.allocate_capital",
        version="1.0.0",
        department="FINANCE",
        description="Transfers financial capital between business divisions.",
        side_effect_class="R4_FINANCIAL_CRITICAL",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        cost_model={"base_cost": 0.10}
    )
    db.add_all([cap1, cap2, cap3])

    # Seed active PlanVersion & PlanNodes
    plan = PlanVersion(
        id="plan-cockpit-v1",
        tenant_id=tenant.id,
        workflow_id=wf.id,
        version_num=1,
        strategy_variant="BALANCED",
        status="ACTIVE",
        plan_content_hash="abc123canonicalhash",
        objective="Execute enterprise SaaS customer acquisition pipeline",
        executive_summary="Milestone-gated expansion targeting 50 new B2B accounts",
        estimated_budget=15000.0,
        max_budget_envelope=20000.0,
        quant_forecast={
            "p10_outcome": 11000.0,
            "p50_outcome": 15000.0,
            "p90_outcome": 19500.0,
            "p_target_attainment": 0.88
        },
        red_team_critique={
            "fragility_score": 0.24,
            "unmitigated_risks": ["Email domain reputation throttle under high outbound volume"]
        },
        compliance_scorecard={
            "is_compliant": True,
            "compliance_status": "COMPLIANT"
        }
    )
    db.add(plan)
    db.flush()

    node1 = PlanNode(
        id="node-p4-1",
        plan_version_id=plan.id,
        name="Tag Prospect Profiles",
        department="SALES",
        capability_id="sales.tag_contact",
        capability_version="1.0.0",
        parameters={"contact_id": "c-101", "tag": "enterprise_target"},
        depends_on=[],
        estimated_duration_seconds=30
    )
    node2 = PlanNode(
        id="node-p4-2",
        plan_version_id=plan.id,
        name="Dispatch Outbound Outreach",
        department="SALES",
        capability_id="sales.send_sequence",
        capability_version="1.0.0",
        parameters={"lead_ids": ["lead-1", "lead-2"]},
        depends_on=["node-p4-1"],
        estimated_duration_seconds=120
    )
    node3 = PlanNode(
        id="node-p4-3",
        plan_version_id=plan.id,
        name="Capital Treasury Allocation",
        department="FINANCE",
        capability_id="finance.allocate_capital",
        capability_version="1.0.0",
        parameters={"amount": 7500.0, "destination": "outreach_campaign"},
        depends_on=["node-p4-2"],
        estimated_duration_seconds=60
    )
    db.add_all([node1, node2, node3])

    db.commit()

    try:
        yield db
    finally:
        db.close()
        engine.dispose()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    tenant_id = "tenant-epsilon"
    app.dependency_overrides[deps.get_db] = lambda: db_session
    app.dependency_overrides[deps.get_current_tenant_id] = lambda: tenant_id
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


def test_cockpit_vitals_aggregation(client, db_session):
    """
    Test 1: Cockpit vitals endpoint aggregates active pipelines, budget allocation vs spent,
    and flags pending dual-key approvals.
    """
    tenant_id = "tenant-epsilon"

    # Add a pending approval request
    req = ExecutiveApprovalRequest(
        id="app-vital-1",
        tenant_id=tenant_id,
        workflow_id="wf-cockpit-1",
        plan_version_id="plan-cockpit-v1",
        task_id="node-p4-3",
        capability_id="finance.allocate_capital",
        capability_version="1.0.0",
        payload_hash="testhash123",
        risk_class="R4_FINANCIAL_CRITICAL",
        title="Approve Capital Transfer",
        description="Allocate 7500 USD to outreach campaign",
        required_keys=2,
        status="PENDING",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
    )
    db_session.add(req)
    db_session.commit()

    res = client.get("/api/v1/ceo/cockpit/vitals")
    assert res.status_code == 200
    data = res.json()

    assert data["active_pipelines"] >= 1
    assert data["pending_approvals_count"] == 1
    assert data["total_budget_allocated"] == 50000.0
    assert data["total_budget_spent"] == 12400.0
    assert data["budget_utilization_pct"] == 24.8
    assert data["system_status"] == "ATTENTION_REQUIRED"
    assert len(data["attention_items"]) == 1
    assert data["attention_items"][0]["urgency"] == "HIGH"


def test_plan_pre_execution_dry_run(client, db_session):
    """
    Test 2: Pre-Execution Dry Run simulates DAG execution, calculates token/cost estimates,
    and identifies required R3 single-key and R4 dual-key approval gates.
    """
    res = client.post("/api/v1/ceo/plans/wf-cockpit-1/plan-cockpit-v1/dry-run")
    assert res.status_code == 200
    sim = res.json()

    assert sim["simulation_status"] == "PASSED"
    assert sim["total_nodes"] == 3
    assert sim["total_estimated_duration_seconds"] == 210
    assert sim["total_estimated_cost_usd"] > 0
    assert sim["budget_sufficient"] is True

    # Verify identified approval gates (sales.send_sequence R3 and finance.allocate_capital R4)
    checkpoints = sim["approval_checkpoints"]
    assert len(checkpoints) >= 1
    cap_ids = {c["capability_id"] for c in checkpoints}
    assert "sales.send_sequence" in cap_ids

    # Verify per-node simulation breakdown
    nodes = sim["node_simulations"]
    assert len(nodes) == 3
    tag_node = next(n for n in nodes if n["capability_id"] == "sales.tag_contact")
    assert tag_node["verdict"] == "ALLOW"
    assert tag_node["requires_human_approval"] is False


def test_plan_dry_run_blocked_by_compliance(client, db_session):
    """
    Test 3: Dry run detects compliance suppression list collisions and blocks execution simulation.
    """
    from app.models.executive import SuppressionList

    tenant_id = "tenant-epsilon"
    # Suppress the lead recipient email
    supp = SuppressionList(
        tenant_id=tenant_id,
        target_type="EMAIL",
        target_value="blocked@competitor.com",
        reason="COMPLIANCE"
    )
    db_session.add(supp)

    # Point node parameter to the suppressed recipient
    node2 = db_session.query(PlanNode).filter_by(id="node-p4-2").first()
    node2.parameters = {"email": "blocked@competitor.com"}
    db_session.commit()

    res = client.post("/api/v1/ceo/plans/wf-cockpit-1/plan-cockpit-v1/dry-run")
    assert res.status_code == 200
    sim = res.json()

    assert sim["simulation_status"] == "BLOCKED"
    send_sim = next(n for n in sim["node_simulations"] if n["capability_id"] == "sales.send_sequence")
    assert send_sim["verdict"] == "DENY"


def test_boardroom_escalation_bridge(client, db_session):
    """
    Test 4: Strategic plan escalation transfers risk factors, Red Team critique, and budget
    into the Agent Boardroom for multi-agent executive deliberation.
    """
    res = client.post("/api/v1/ceo/plans/wf-cockpit-1/plan-cockpit-v1/escalate-to-boardroom")
    assert res.status_code == 200
    esc = res.json()

    assert esc["status"] == "ESCALATED"
    meeting_id = esc["meeting_id"]
    assert "Boardroom Executive Strategic Review" in esc["title"]
    assert "CEO AI" in esc["participants"]
    assert "Red Team Critic" in esc["participants"]
    assert "Strategist" in esc["participants"]

    # Verify AgentMeeting created in DB
    meeting = db_session.query(AgentMeeting).filter_by(id=meeting_id).first()
    assert meeting is not None
    assert meeting.trigger_type == "ceo_strategy_escalation"
    assert meeting.trigger_id == "plan-cockpit-v1"

    # Verify audit event on EventLedger
    events = db_session.query(WorkflowEvent).filter_by(event_type="boardroom_escalated").all()
    assert len(events) == 1
    assert events[0].correlation_id == "plan-cockpit-v1"


def test_workflow_post_mortem_and_strategic_brief(client, db_session):
    """
    Test 5: Workflow Post-Mortem generates a Board-ready executive brief comparing
    Quant Forecast vs Actuals, analyzes Red Team predictions, and saves to Playbook memory.
    """
    tenant_id = "tenant-epsilon"
    # Seed completed task events on EventLedger
    EventLedger.append_event(
        db=db_session,
        tenant_id=tenant_id,
        workflow_id="wf-cockpit-1",
        execution_id="plan-cockpit-v1",
        event_type="task_completed",
        actor_type="AGENT",
        actor_id="SalesAgent",
        payload={"task_id": "node-p4-1", "result": "tagged"},
        correlation_id="wf-cockpit-1"
    )
    EventLedger.append_event(
        db=db_session,
        tenant_id=tenant_id,
        workflow_id="wf-cockpit-1",
        execution_id="plan-cockpit-v1",
        event_type="task_completed",
        actor_type="AGENT",
        actor_id="SalesAgent",
        payload={"task_id": "node-p4-2", "result": "dispatched"},
        correlation_id="wf-cockpit-1"
    )
    db_session.commit()

    # Generate post-mortem via API
    res_gen = client.post("/api/v1/ceo/workflows/wf-cockpit-1/generate-post-mortem")
    assert res_gen.status_code == 200
    pm = res_gen.json()

    assert pm["workflow_id"] == "wf-cockpit-1"
    assert pm["plan_version_id"] == "plan-cockpit-v1"
    assert pm["strategy_variant"] == "BALANCED"
    assert pm["actual_cost"] > 0
    assert "cost_variance_pct" in pm["variance_analysis"]
    assert "# Executive Strategic Brief" in pm["executive_brief_markdown"]
    assert len(pm["key_learnings"]) >= 3

    # Verify persistent DB record
    pm_row = db_session.query(PlaybookPostMortem).filter_by(workflow_id="wf-cockpit-1").first()
    assert pm_row is not None
    assert pm_row.tasks_completed == 2

    # Fetch post-mortem via GET API
    res_get = client.get("/api/v1/ceo/workflows/wf-cockpit-1/post-mortem")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == pm["id"]
