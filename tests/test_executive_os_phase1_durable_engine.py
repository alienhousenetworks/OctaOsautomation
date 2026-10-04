import pytest
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models.base import Base, Tenant, User
from app.models.workflows import Workflow
from app.models.executive import (
    WorkflowEvent, CapabilityRegistry, BudgetEnvelope,
    BudgetReservation, KillSwitch, PolicyRule, SuppressionList,
    ApprovalRequest, ApprovalDecision, SideEffectOutbox, PlanVersion, PlanNode
)
from app.core.governance import DeterministicGovernanceKernel
from app.core.event_ledger import EventLedger
from app.core.approval_service import ApprovalService
from app.core.capabilities import (
    register_capability, SendSalesSequenceCapability, TagContactCapability
)
from app.services.executive_os.execution_engine import DurableExecutionEngine
from app.services.executive_os.state_machine import WorkflowState, TaskState
from app.services.executive_os.sse_manager import SSEManager
from app.services.agents.executive.execution_supervisor import ExecutionSupervisorAgent

TEST_DB_URL = "sqlite:///./test_executive_phase1.db"
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

    tenant = Tenant(id="tenant-beta", name="Beta Corp", subdomain="beta", company_email="admin@beta.com")
    db.add(tenant)
    db.flush()

    user_ceo = User(id="user-ceo", tenant_id=tenant.id, email="ceo@beta.com", hashed_password="pw", role="CEO")
    user_coo = User(id="user-coo", tenant_id=tenant.id, email="coo@beta.com", hashed_password="pw", role="COO")
    db.add_all([user_ceo, user_coo])

    wf = Workflow(id="wf-exec-1", tenant_id=tenant.id, name="Executive Growth DAG", vertical="CEO", department="CEO", status="COMPILED")
    db.add(wf)

    # Register capabilities
    cap_sales = SendSalesSequenceCapability()
    cap_tag = TagContactCapability()
    register_capability(cap_sales)
    register_capability(cap_tag)

    for cap in [cap_sales, cap_tag]:
        cdef = cap.definition
        row = CapabilityRegistry(
            id=cdef.id,
            version=cdef.version,
            department=cdef.department,
            description=cdef.description,
            side_effect_class=cdef.side_effect_class,
            input_schema=cdef.input_schema,
            output_schema=cdef.output_schema,
            required_permissions=cdef.required_permissions,
            cost_model=cdef.cost_model.model_dump(),
            is_compensable=cdef.is_compensable
        )
        db.merge(row)

    # Seed budget envelope
    now = datetime.now(timezone.utc)
    env = BudgetEnvelope(
        id="env-beta-q4",
        tenant_id=tenant.id,
        department="CEO",
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=30),
        authorized_limit=10000.00,
        reserved_amount=0.00,
        consumed_amount=0.00
    )
    db.add(env)
    db.commit()

    try:
        yield db
    finally:
        db.close()
        engine.dispose()
        Base.metadata.drop_all(bind=engine)


def create_test_plan(db, tenant_id: str, workflow_id: str, plan_id: str) -> PlanVersion:
    pv = PlanVersion(
        id=plan_id,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        version_num=1,
        strategy_variant="BALANCED",
        status="ACTIVE",
        plan_content_hash="test-plan-hash",
        objective="Scale qualified leads by 25%",
        executive_summary="Targeted outreach with CRM sync",
        estimated_budget=500.0,
        max_budget_envelope=1000.0,
        quant_forecast={"target_conversion": 0.04}
    )
    db.add(pv)
    db.commit()
    return pv


@pytest.mark.asyncio
async def test_workflow_start_and_projection(db_session):
    tenant_id = "tenant-beta"
    wf_id = "wf-exec-1"
    plan_id = "plan-v1"
    create_test_plan(db_session, tenant_id, wf_id, plan_id)

    node1 = PlanNode(
        id="node-1",
        plan_version_id=plan_id,
        name="Tag High Value Lead",
        capability_id="crm.tag_contact",
        capability_version="1.0.0",
        parameters={"contact_id": "c-100", "tag": "VIP_PROSPECT"},
        depends_on=[]
    )
    db_session.add(node1)
    db_session.commit()

    engine = DurableExecutionEngine(db_session, tenant_id)
    wf = engine.start_workflow(wf_id, plan_id)

    assert wf.status == "RUNNING"

    # Reconstruct from event ledger
    proj = engine.get_workflow_projection(wf_id)
    assert proj["workflow_status"] == "RUNNING"
    assert proj["plan_version_id"] == plan_id

    # Cryptographic integrity check
    assert EventLedger.verify_ledger_integrity(db_session, wf_id) is True


@pytest.mark.asyncio
async def test_diamond_dag_execution_across_ticks(db_session):
    r"""
    Tests dependency resolution across multiple atomic ticks:
             Node 1 (Root)
             /          \
      Node 2A            Node 2B
             \          /
             Node 3 (Join)
    """
    tenant_id = "tenant-beta"
    wf_id = "wf-exec-1"
    plan_id = "plan-diamond"
    create_test_plan(db_session, tenant_id, wf_id, plan_id)

    n1 = PlanNode(id="n1", plan_version_id=plan_id, name="Root Task", capability_id="crm.tag_contact",
                  parameters={"contact_id": "c1", "tag": "root"}, depends_on=[])
    n2a = PlanNode(id="n2a", plan_version_id=plan_id, name="Branch A", capability_id="crm.tag_contact",
                   parameters={"contact_id": "c2a", "tag": "branch_a"}, depends_on=["n1"])
    n2b = PlanNode(id="n2b", plan_version_id=plan_id, name="Branch B", capability_id="crm.tag_contact",
                   parameters={"contact_id": "c2b", "tag": "branch_b"}, depends_on=["n1"])
    n3 = PlanNode(id="n3", plan_version_id=plan_id, name="Join Task", capability_id="crm.tag_contact",
                  parameters={"contact_id": "c3", "tag": "join"}, depends_on=["n2a", "n2b"])

    db_session.add_all([n1, n2a, n2b, n3])
    db_session.commit()

    engine = DurableExecutionEngine(db_session, tenant_id)
    engine.start_workflow(wf_id, plan_id)

    # Tick 1: Only n1 is ready
    res1 = await engine.execute_tick(wf_id, plan_id)
    assert res1["status"] == "TICK_PROCESSED"
    assert res1["executed_nodes"] == ["n1"]

    # Tick 2: n2a and n2b are ready (n1 completed)
    res2 = await engine.execute_tick(wf_id, plan_id)
    assert res2["status"] == "TICK_PROCESSED"
    assert set(res2["executed_nodes"]) == {"n2a", "n2b"}

    # Tick 3: n3 is ready (both n2a and n2b completed)
    res3 = await engine.execute_tick(wf_id, plan_id)
    assert res3["status"] == "TICK_PROCESSED"
    assert res3["executed_nodes"] == ["n3"]

    # Tick 4: Entire DAG finished -> transitions to COMPLETED
    res4 = await engine.execute_tick(wf_id, plan_id)
    assert res4["status"] == "COMPLETED"
    assert res4["completed_count"] == 4

    proj = engine.get_workflow_projection(wf_id)
    assert proj["workflow_status"] == "COMPLETED"
    assert len(proj["task_results"]) == 4

    assert EventLedger.verify_ledger_integrity(db_session, wf_id) is True


@pytest.mark.asyncio
async def test_approval_block_and_dual_key_resolution(db_session):
    """
    Tests that R3 capability is halted by Governance Kernel, creates ApprovalRequest,
    resumes only after approval, and completes cleanly.
    """
    tenant_id = "tenant-beta"
    wf_id = "wf-exec-1"
    plan_id = "plan-approval"
    create_test_plan(db_session, tenant_id, wf_id, plan_id)

    node_outreach = PlanNode(
        id="node-email",
        plan_version_id=plan_id,
        name="Dispatch Enterprise Cold Outreach",
        capability_id="sales.send_sequence",
        capability_version="1.0.0",
        parameters={"lead_ids": ["lead-1", "lead-2"], "template_id": "tpl-ent-1", "channel": "smtp"},
        depends_on=[]
    )
    db_session.add(node_outreach)
    db_session.commit()

    engine = DurableExecutionEngine(db_session, tenant_id)
    engine.start_workflow(wf_id, plan_id)

    # First tick: Governance Kernel encounters R3 -> creates ApprovalRequest
    res1 = await engine.execute_tick(wf_id, plan_id)
    assert res1["status"] == "TICK_PROCESSED"
    assert res1["executed_nodes"] == [] # Did not execute yet

    proj = engine.get_workflow_projection(wf_id)
    assert proj["task_states"]["node-email"] == TaskState.WAITING_APPROVAL.value

    # Verify ApprovalRequest in DB
    req = db_session.query(ApprovalRequest).filter_by(workflow_id=wf_id, task_id="node-email").first()
    assert req is not None
    assert req.status == "PENDING"
    assert req.risk_class == "R3_EXTERNAL_IRREVERSIBLE"

    # Subsequent tick without approval remains waiting
    res2 = await engine.execute_tick(wf_id, plan_id)
    assert res2["executed_nodes"] == []

    # Operator approves
    approval_svc = ApprovalService(db_session, tenant_id)
    dec_res = approval_svc.record_decision(
        request_id=req.id,
        user_id="user-ceo",
        user_role="CEO",
        decision="APPROVE",
        rationale="Approved high priority enterprise sequence.",
        payload=node_outreach.parameters,
        idempotency_key=f"appr-{node_outreach.id}"
    )
    assert dec_res["status"] == "APPROVED"

    # Now tick should succeed
    res3 = await engine.execute_tick(wf_id, plan_id)
    assert res3["executed_nodes"] == ["node-email"]

    proj_after = engine.get_workflow_projection(wf_id)
    assert proj_after["task_states"]["node-email"] == TaskState.COMPLETED.value
    assert EventLedger.verify_ledger_integrity(db_session, wf_id) is True


@pytest.mark.asyncio
async def test_pause_resume_and_cancel_signals(db_session):
    tenant_id = "tenant-beta"
    wf_id = "wf-exec-1"
    plan_id = "plan-signals"
    create_test_plan(db_session, tenant_id, wf_id, plan_id)

    node = PlanNode(id="node-sig", plan_version_id=plan_id, name="Signal Test",
                    capability_id="crm.tag_contact", parameters={"contact_id": "c1", "tag": "test"}, depends_on=[])
    db_session.add(node)
    db_session.commit()

    engine = DurableExecutionEngine(db_session, tenant_id)
    engine.start_workflow(wf_id, plan_id)

    # Pause
    assert engine.pause_workflow(wf_id) is True
    proj = engine.get_workflow_projection(wf_id)
    assert proj["workflow_status"] == "PAUSED"

    # Tick while paused is rejected
    tick_res = await engine.execute_tick(wf_id, plan_id)
    assert tick_res["status"] == "PAUSED"

    # Resume
    assert engine.resume_workflow(wf_id) is True
    proj = engine.get_workflow_projection(wf_id)
    assert proj["workflow_status"] == "RUNNING"

    # Cancel
    assert engine.cancel_workflow(wf_id) is True
    proj = engine.get_workflow_projection(wf_id)
    assert proj["workflow_status"] == "CANCELLED"

    tick_res2 = await engine.execute_tick(wf_id, plan_id)
    assert tick_res2["status"] == "CANCELLED"

    assert EventLedger.verify_ledger_integrity(db_session, wf_id) is True


@pytest.mark.asyncio
async def test_failure_and_reverse_order_compensation(db_session):
    """
    Tests compensation order and irreversible handling:
    Task 1 (Tag - compensable) -> Task 2 (Email - irreversible) -> Task 3 (Policy DENY)
    Rollback should compensate in reverse:
    - Task 2: compensation_unsupported (emails cannot be un-sent)
    - Task 1: task_compensated (tag removed)
    """
    tenant_id = "tenant-beta"
    wf_id = "wf-exec-1"
    plan_id = "plan-comp"
    create_test_plan(db_session, tenant_id, wf_id, plan_id)

    # Policy rule to DENY task 3
    rule = PolicyRule(
        id="deny-rule-test",
        tenant_id=tenant_id,
        name="Block Malicious Contact",
        condition_expr={
            "op": "and",
            "clauses": [
                {"op": "eq", "field": "capability_id", "value": "crm.tag_contact"},
                {"op": "eq", "field": "input.tag", "value": "MALICIOUS"}
            ]
        },
        enforcement_action="DENY",
        priority=10
    )
    db_session.add(rule)

    t1 = PlanNode(id="t1", plan_version_id=plan_id, name="Step 1 Tag", capability_id="crm.tag_contact",
                  parameters={"contact_id": "c1", "tag": "step1"}, depends_on=[])
    t2 = PlanNode(id="t2", plan_version_id=plan_id, name="Step 2 Email", capability_id="sales.send_sequence",
                  parameters={"lead_ids": ["c1"], "template_id": "t1", "channel": "smtp"}, depends_on=["t1"])
    t3 = PlanNode(id="t3", plan_version_id=plan_id, name="Step 3 Denied", capability_id="crm.tag_contact",
                  parameters={"contact_id": "c1", "tag": "MALICIOUS"}, depends_on=["t2"])

    db_session.add_all([t1, t2, t3])
    db_session.commit()

    engine = DurableExecutionEngine(db_session, tenant_id)
    engine.start_workflow(wf_id, plan_id)

    # Tick 1: t1 executes
    await engine.execute_tick(wf_id, plan_id)

    # Approve t2 so it can execute
    appr = ApprovalService(db_session, tenant_id)
    await engine.execute_tick(wf_id, plan_id) # creates approval request
    req = db_session.query(ApprovalRequest).filter_by(workflow_id=wf_id, task_id="t2").first()
    appr.record_decision(
        request_id=req.id,
        user_id="user-ceo",
        user_role="CEO",
        decision="APPROVE",
        rationale="Approved t2",
        payload=t2.parameters,
        idempotency_key="appr-t2"
    )
    await engine.execute_tick(wf_id, plan_id) # executes t2

    proj_pre = engine.get_workflow_projection(wf_id)
    assert proj_pre["task_states"]["t1"] == "COMPLETED"
    assert proj_pre["task_states"]["t2"] == "COMPLETED"

    # Tick 4: t3 evaluated -> Policy Kernel returns DENY -> triggers task_failed
    res_fail = await engine.execute_tick(wf_id, plan_id)
    assert res_fail["status"] == "TASK_DENIED"

    # Next tick catches failed task and triggers compensation rollback
    res_comp = await engine.execute_tick(wf_id, plan_id)
    assert res_comp["status"] == "FAILED"

    # Verify event ledger reflects compensation
    events = db_session.query(WorkflowEvent).filter_by(workflow_id=wf_id).order_by(WorkflowEvent.sequence_num.asc()).all()
    event_types = [e.event_type for e in events]

    assert "workflow_failed" in event_types
    assert "compensation_unsupported" in event_types # for t2 (irreversible)
    assert "task_compensated" in event_types         # for t1 (reversible)

    assert EventLedger.verify_ledger_integrity(db_session, wf_id) is True


@pytest.mark.asyncio
async def test_manual_skip_and_retry(db_session):
    tenant_id = "tenant-beta"
    wf_id = "wf-exec-1"
    plan_id = "plan-skip"
    create_test_plan(db_session, tenant_id, wf_id, plan_id)

    t1 = PlanNode(id="t1", plan_version_id=plan_id, name="Optional Survey", capability_id="crm.tag_contact",
                  parameters={"contact_id": "c1", "tag": "survey"}, depends_on=[])
    t2 = PlanNode(id="t2", plan_version_id=plan_id, name="Downstream Task", capability_id="crm.tag_contact",
                  parameters={"contact_id": "c1", "tag": "next"}, depends_on=["t1"])

    db_session.add_all([t1, t2])
    db_session.commit()

    engine = DurableExecutionEngine(db_session, tenant_id)
    engine.start_workflow(wf_id, plan_id)

    # Operator manually skips t1
    engine.skip_task(wf_id, "t1")

    proj = engine.get_workflow_projection(wf_id)
    assert proj["task_states"]["t1"] == TaskState.SKIPPED.value

    # Tick should now execute t2 because skipped dependency is considered satisfied
    res = await engine.execute_tick(wf_id, plan_id)
    assert res["executed_nodes"] == ["t2"]

    assert EventLedger.verify_ledger_integrity(db_session, wf_id) is True


@pytest.mark.asyncio
async def test_sse_event_streaming_and_resume(db_session):
    """
    Tests SSE stream generator with Last-Event-ID replay.
    """
    tenant_id = "tenant-beta"
    wf_id = "wf-exec-1"
    plan_id = "plan-sse"
    create_test_plan(db_session, tenant_id, wf_id, plan_id)

    engine = DurableExecutionEngine(db_session, tenant_id)
    engine.start_workflow(wf_id, plan_id)

    # Append 3 additional events
    for i in range(1, 4):
        engine.skip_task(wf_id, f"test-task-{i}")

    all_events = db_session.query(WorkflowEvent).filter_by(workflow_id=wf_id).order_by(WorkflowEvent.sequence_num.asc()).all()
    assert len(all_events) == 4 # 1 workflow_started + 3 task_skipped

    # Replay starting after sequence_num 2
    generator = SSEManager.event_generator(
        db_factory=TestingSessionLocal,
        tenant_id=tenant_id,
        workflow_id=wf_id,
        last_event_id=2,
        poll_interval=0.1,
        heartbeat_interval=0.5
    )

    # Collect the two backlog events (seq 3 and 4)
    msg1 = await anext(generator)
    assert "id: 3" in msg1
    assert "task_skipped" in msg1

    msg2 = await anext(generator)
    assert "id: 4" in msg2
    assert "task_skipped" in msg2

    # Verify keep-alive ping when idle
    msg_ping = await anext(generator)
    assert msg_ping == ": ping\n\n"

    # Close generator
    await generator.aclose()


@pytest.mark.asyncio
async def test_execution_supervisor_drift_detection(db_session):
    """
    Tests Agent #9 (Execution Supervisor) detecting execution drift >= 1.5x.
    """
    tenant_id = "tenant-beta"
    wf_id = "wf-exec-1"
    plan_id = "plan-drift"
    create_test_plan(db_session, tenant_id, wf_id, plan_id)

    node = PlanNode(
        id="node-slow",
        plan_version_id=plan_id,
        name="Long Running Quantitative Model",
        capability_id="crm.tag_contact",
        parameters={"contact_id": "c1", "tag": "quant"},
        depends_on=[],
        estimated_duration_seconds=10 # estimated: 10s
    )
    db_session.add(node)
    db_session.commit()

    engine = DurableExecutionEngine(db_session, tenant_id)
    engine.start_workflow(wf_id, plan_id)

    # Record task_in_progress at T0
    t0 = datetime.now(timezone.utc) - timedelta(seconds=25) # 25s elapsed (2.5x estimated)
    EventLedger.append_event(
        db=db_session,
        tenant_id=tenant_id,
        workflow_id=wf_id,
        execution_id="exec-drift-1",
        event_type="task_in_progress",
        actor_type="SYSTEM",
        actor_id="DurableExecutionEngine",
        task_id="node-slow",
        payload={"capability_id": "crm.tag_contact"},
        correlation_id="exec-drift-1"
    )
    db_session.commit()

    # Backdate created_at of this event to simulate elapsed time
    ev = db_session.query(WorkflowEvent).filter_by(task_id="node-slow", event_type="task_in_progress").first()
    ev.created_at = t0
    db_session.commit()

    supervisor = ExecutionSupervisorAgent(db_session, tenant_id)
    report = supervisor.inspect_workflow(wf_id, plan_id)

    assert report["status"] == "DRIFT_DETECTED"
    assert len(report["drifting_tasks"]) == 1
    drift = report["drifting_tasks"][0]
    assert drift["task_id"] == "node-slow"
    assert drift["drift_ratio"] >= 1.5
    assert report["recommendation"] == "INVESTIGATE_LATENCY_OR_SCALE"

    # Verify supervisor alert recorded in ledger
    alert_event = db_session.query(WorkflowEvent).filter_by(event_type="supervisor_drift_detected").first()
    assert alert_event is not None
    assert alert_event.actor_id == ExecutionSupervisorAgent.AGENT_ID
    assert EventLedger.verify_ledger_integrity(db_session, wf_id) is True


def test_ceo_v5_api_endpoints_integration(db_session):
    """
    Tests CEO Workspace v5 REST endpoints through FastAPI router:
    - start, tick, projection, pause, resume, telemetry, cancel
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api import deps

    tenant_id = "tenant-beta"
    wf_id = "wf-exec-1"
    plan_id = "plan-api-test"
    create_test_plan(db_session, tenant_id, wf_id, plan_id)

    node = PlanNode(
        id="node-api",
        plan_version_id=plan_id,
        name="API Test Task",
        capability_id="crm.tag_contact",
        parameters={"contact_id": "c-api", "tag": "test_api"},
        depends_on=[],
        estimated_duration_seconds=30
    )
    db_session.add(node)
    db_session.commit()

    # Configure dependency overrides
    app.dependency_overrides[deps.get_db] = lambda: db_session
    app.dependency_overrides[deps.get_current_tenant_id] = lambda: tenant_id

    client = TestClient(app)

    try:
        # 1. Start workflow
        res_start = client.post(f"/api/v1/ceo/workflows/{wf_id}/start", json={"plan_version_id": plan_id})
        assert res_start.status_code == 200
        data_start = res_start.json()
        assert data_start["status"] == "STARTED"
        assert data_start["workflow_status"] == "RUNNING"

        # 2. Tick workflow
        res_tick = client.post(f"/api/v1/ceo/workflows/{wf_id}/tick", json={"plan_version_id": plan_id})
        assert res_tick.status_code == 200
        data_tick = res_tick.json()
        assert data_tick["status"] == "TICK_PROCESSED"
        assert data_tick["executed_nodes"] == ["node-api"]

        # 3. Get projection
        res_proj = client.get(f"/api/v1/ceo/workflows/{wf_id}/projection")
        assert res_proj.status_code == 200
        data_proj = res_proj.json()
        assert data_proj["task_states"]["node-api"] == "COMPLETED"

        # 4. Telemetry audit
        res_telemetry = client.get(f"/api/v1/ceo/workflows/{wf_id}/telemetry?plan_version_id={plan_id}")
        assert res_telemetry.status_code == 200
        data_tel = res_telemetry.json()
        assert data_tel["status"] == "HEALTHY"

        # 5. Pause
        res_pause = client.post(f"/api/v1/ceo/workflows/{wf_id}/pause")
        assert res_pause.status_code == 200
        assert res_pause.json()["status"] == "PAUSED"

        # 6. Resume
        res_resume = client.post(f"/api/v1/ceo/workflows/{wf_id}/resume")
        assert res_resume.status_code == 200
        assert res_resume.json()["status"] == "RESUMED"

        # 7. Cancel
        res_cancel = client.post(f"/api/v1/ceo/workflows/{wf_id}/cancel")
        assert res_cancel.status_code == 200
        assert res_cancel.json()["status"] == "CANCELLED"

        # 8. Skip & Retry endpoints
        res_skip = client.post(f"/api/v1/ceo/workflows/{wf_id}/tasks/node-api/skip")
        assert res_skip.status_code == 200
        assert res_skip.json()["status"] == "SKIPPED"

        res_retry = client.post(f"/api/v1/ceo/workflows/{wf_id}/tasks/node-api/retry")
        assert res_retry.status_code == 200
        assert res_retry.json()["status"] == "RETRIED"

    finally:
        app.dependency_overrides.clear()
