import pytest
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base, Tenant, User
from app.models.workflows import Workflow, WorkflowTask
from app.models.executive import (
    WorkflowEvent, CapabilityRegistry, BudgetEnvelope,
    BudgetReservation, KillSwitch, PolicyRule, SuppressionList,
    ApprovalRequest, ApprovalDecision, SideEffectOutbox, PlanVersion
)
from app.core.governance import DeterministicGovernanceKernel
from app.core.event_ledger import EventLedger
from app.core.approval_service import ApprovalService
from app.workers.outbox_worker import OutboxWorker
from app.core.capabilities import register_capability, SendSalesSequenceCapability

TEST_DB_URL = "sqlite:///./test_executive_os.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Seed test tenant and users
    tenant = Tenant(id="tenant-alpha", name="Alpha Corp", subdomain="alpha", company_email="admin@alpha.com")
    db.add(tenant)
    db.flush()

    user_a = User(id="user-a", tenant_id=tenant.id, email="ceo@alpha.com", hashed_password="pw", role="CEO")
    user_b = User(id="user-b", tenant_id=tenant.id, email="cfo@alpha.com", hashed_password="pw", role="CFO")
    user_c = User(id="user-c", tenant_id=tenant.id, email="coo@alpha.com", hashed_password="pw", role="COO")
    db.add_all([user_a, user_b, user_c])

    # Seed test workflow
    wf = Workflow(id="wf-test-1", tenant_id=tenant.id, name="Q4 Pipeline Surge", vertical="CEO", department="CEO")
    db.add(wf)

    # Seed capability registry
    cap = SendSalesSequenceCapability()
    register_capability(cap)
    cap_def = cap.definition
    cap_row = CapabilityRegistry(
        id=cap_def.id,
        version=cap_def.version,
        department=cap_def.department,
        description=cap_def.description,
        side_effect_class=cap_def.side_effect_class,
        input_schema=cap_def.input_schema,
        output_schema=cap_def.output_schema,
        required_permissions=cap_def.required_permissions,
        cost_model=cap_def.cost_model.model_dump(),
        is_compensable=cap_def.is_compensable
    )
    db.merge(cap_row)

    # Seed budget envelope: $100.00 authorized
    now = datetime.now(timezone.utc)
    env = BudgetEnvelope(
        id="env-sales-q4",
        tenant_id=tenant.id,
        department="Sales",
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=30),
        authorized_limit=100.00,
        reserved_amount=0.00,
        consumed_amount=0.00
    )
    db.add(env)
    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def test_ledger_cryptographic_tamper_detection(db_session):
    """
    Test 1: Appends 5 chained events and verifies that modifying 1 character
    in canonical_payload or event_hash is mathematically caught by verify_ledger_integrity.
    """
    tenant_id = "tenant-alpha"
    workflow_id = "wf-test-1"

    for i in range(1, 6):
        EventLedger.append_event(
            db=db_session,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            execution_id=f"exec-{i}",
            event_type=f"task_step_{i}",
            actor_type="AGENT",
            actor_id="RevenueOperator",
            payload={"step": i, "details": f"Prospect cluster {i} evaluated"},
            correlation_id=f"corr-{i}"
        )
    db_session.commit()

    # 1. Chain must be valid initially
    assert EventLedger.verify_ledger_integrity(db_session, workflow_id) is True

    # 2. Tamper with payload of step 3
    ev3 = db_session.query(WorkflowEvent).filter_by(workflow_id=workflow_id, sequence_num=3).first()
    ev3.canonical_payload = '{"details":"TAMPERED_INJECTED_STRING","step":3}'
    db_session.commit()

    # 3. Verification must fail
    assert EventLedger.verify_ledger_integrity(db_session, workflow_id) is False

    # 4. Restore payload, but tamper with event_hash
    ev3.canonical_payload = '{"details":"Prospect cluster 3 evaluated","step":3}'
    ev3.event_hash = "deadbeef" * 8
    db_session.commit()

    assert EventLedger.verify_ledger_integrity(db_session, workflow_id) is False


def test_fail_closed_policy_fuzzer(db_session):
    """
    Test 2: Verifies that unknown AST operators, missing fields, or malformed ASTs
    fail closed to DENY.
    """
    kernel = DeterministicGovernanceKernel(db_session, tenant_id="tenant-alpha")
    inputs = {"lead_ids": ["lead-1", "lead-2"], "template_id": "tpl-1", "channel": "smtp"}

    # Base capability evaluation without custom policies
    res = kernel.evaluate("sales.send_sequence", "1.0.0", inputs)
    # R3 requires approval by default
    assert res["decision"] == "REQUIRE_APPROVAL"

    # Add a malformed policy with an unknown operator
    bad_policy = PolicyRule(
        id="pol-fuzz-1",
        tenant_id="tenant-alpha",
        name="Malicious Fuzz Policy",
        condition_expr={"op": "arbitrary_eval_exploit", "field": "capability_id", "value": "sales.send_sequence"},
        enforcement_action="ALLOW",
        priority=10
    )
    db_session.add(bad_policy)
    db_session.commit()

    # Kernel must catch PolicyEvaluationError and fail closed to DENY
    res_fuzzed = kernel.evaluate("sales.send_sequence", "1.0.0", inputs)
    assert res_fuzzed["decision"] == "DENY"

    # Clean bad policy and test suppression list
    db_session.delete(bad_policy)
    supp = SuppressionList(
        tenant_id="tenant-alpha",
        target_type="DOMAIN",
        target_value="blocked-competitor.com",
        reason="LEGAL_HOLD"
    )
    db_session.add(supp)
    db_session.commit()

    supp_inputs = {"lead_ids": ["lead-1"], "email": "ceo@blocked-competitor.com", "template_id": "tpl-1", "channel": "smtp"}
    res_supp = kernel.evaluate("sales.send_sequence", "1.0.0", supp_inputs)
    assert res_supp["decision"] == "DENY"
    assert "suppression list" in res_supp["reason"]


def test_atomic_budget_reservation_and_ceiling(db_session):
    """
    Test 3: Budget envelope has $100.00 authorized limit.
    Verifies atomic reservations, ceiling enforcement, and release.
    """
    kernel = DeterministicGovernanceKernel(db_session, tenant_id="tenant-alpha")

    # Reserve $30.00 x 3 = $90.00
    res1 = kernel.reserve_budget("Sales", "wf-test-1", "task-1", 30.00, "idemp-b1")
    res2 = kernel.reserve_budget("Sales", "wf-test-1", "task-2", 30.00, "idemp-b2")
    res3 = kernel.reserve_budget("Sales", "wf-test-1", "task-3", 30.00, "idemp-b3")
    assert res1 is not None and res2 is not None and res3 is not None

    # Current reserved: $90.00. Remaining: $10.00.
    # Attempting to reserve $20.00 must return None (exceeds authorized limit)
    res4 = kernel.reserve_budget("Sales", "wf-test-1", "task-4", 20.00, "idemp-b4")
    assert res4 is None

    # Release reservation 1 ($30.00)
    released = kernel.release_budget("idemp-b1")
    assert released is True

    # Now reserving $20.00 succeeds ($60 + $20 = $80 <= $100)
    res5 = kernel.reserve_budget("Sales", "wf-test-1", "task-5", 20.00, "idemp-b5")
    assert res5 is not None


def test_dual_key_approval_and_anti_self_approval(db_session):
    """
    Test 4: Verifies dual-key approval for R4 actions, anti-self-approval enforcement,
    and automatic staging in Outbox upon final key.
    """
    app_svc = ApprovalService(db_session, tenant_id="tenant-alpha")
    payload = {"lead_ids": ["L1", "L2"], "template_id": "tpl-intro", "channel": "smtp"}

    # Seed plan version
    pv = PlanVersion(
        id="pv-test-1",
        tenant_id="tenant-alpha",
        workflow_id="wf-test-1",
        version_num=1,
        strategy_variant="BALANCED",
        status="VALIDATED",
        plan_content_hash="hash-12345",
        objective="Surge leads",
        executive_summary="Executive plan",
        estimated_budget=5000.0,
        max_budget_envelope=10000.0,
        quant_forecast={"p50": 80000}
    )
    db_session.add(pv)
    db_session.commit()

    # Create R4 request with requester = user-a (CEO)
    req = app_svc.create_request(
        workflow_id="wf-test-1",
        plan_version_id="pv-test-1",
        task_id="task-high-spend",
        capability_id="sales.send_sequence",
        capability_version="1.0.0",
        payload=payload,
        risk_class="R4_FINANCIAL_CRITICAL",
        title="High Volume Outreach",
        description="Outreach to enterprise accounts",
        financial_impact=5000.0,
        requester_user_id="user-a" # Requester
    )
    db_session.commit()
    assert req.required_keys == 2

    # 1. user-a (requester) attempts to approve their own R4 request -> Anti-self-approval blocks!
    with pytest.raises(PermissionError) as exc_info:
        app_svc.record_decision(
            request_id=req.id,
            user_id="user-a",
            user_role="CEO",
            decision="APPROVE",
            rationale="I approve my own proposal",
            payload=payload,
            idempotency_key="outbox-idemp-1"
        )
    assert "Anti-self-approval" in str(exc_info.value)

    # 2. user-b (CFO) provides first key -> status remains PENDING
    dec1 = app_svc.record_decision(
        request_id=req.id,
        user_id="user-b",
        user_role="CFO",
        decision="APPROVE",
        rationale="Budget envelope verified by finance",
        payload=payload,
        idempotency_key="outbox-idemp-1"
    )
    assert dec1["status"] == "PENDING"

    # 3. user-c (COO) provides second key -> status becomes APPROVED and staged in Outbox!
    dec2 = app_svc.record_decision(
        request_id=req.id,
        user_id="user-c",
        user_role="COO",
        decision="APPROVE",
        rationale="Operational readiness verified",
        payload=payload,
        idempotency_key="outbox-idemp-1"
    )
    assert dec2["status"] == "APPROVED"
    db_session.commit()

    # Verify row staged in SideEffectOutbox
    staged = db_session.query(SideEffectOutbox).filter_by(idempotency_key="outbox-idemp-1").first()
    assert staged is not None
    assert staged.status == "STAGED"
    assert staged.capability_id == "sales.send_sequence"


def test_payload_tampering_detection_on_approval(db_session):
    """
    Test 5: Verifies that if a payload is modified between request creation and approval,
    the payload hash mismatch immediately blocks approval.
    """
    app_svc = ApprovalService(db_session, tenant_id="tenant-alpha")
    original_payload = {"lead_ids": ["L1", "L2"], "template_id": "tpl-intro", "channel": "smtp"}

    req = app_svc.create_request(
        workflow_id="wf-test-1",
        plan_version_id="pv-test-1",
        task_id="task-tamper-check",
        capability_id="sales.send_sequence",
        capability_version="1.0.0",
        payload=original_payload,
        risk_class="R3_EXTERNAL_IRREVERSIBLE",
        title="Outreach Task",
        description="Send emails",
        requester_user_id="user-a"
    )
    db_session.commit()

    # Attempt to approve with an injected lead
    tampered_payload = {"lead_ids": ["L1", "L2", "INJECTED_UNAUTHORIZED_LEAD"], "template_id": "tpl-intro", "channel": "smtp"}
    with pytest.raises(ValueError) as exc_info:
        app_svc.record_decision(
            request_id=req.id,
            user_id="user-b",
            user_role="CFO",
            decision="APPROVE",
            rationale="Approved",
            payload=tampered_payload,
            idempotency_key="idemp-tamper"
        )
    assert "Payload tampering detected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_outbox_worker_execution_and_killswitch(db_session):
    """
    Test 6: Tests leased outbox processing, kill-switch abort, and atomic event ledger recording.
    """
    worker = OutboxWorker(db_session, worker_id="worker-node-1")
    idemp_key = f"outbox-test-{uuid.uuid4().hex[:8]}"
    payload = {"lead_ids": ["lead-101", "lead-102"], "template_id": "tpl-welcome", "channel": "smtp"}

    import json, hashlib
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # 1. Stage an outbox row
    outbox_entry = SideEffectOutbox(
        tenant_id="tenant-alpha",
        workflow_id="wf-test-1",
        task_id="task-dispatch-1",
        capability_id="sales.send_sequence",
        capability_version="1.0.0",
        idempotency_key=idemp_key,
        payload_hash=payload_hash,
        payload=payload,
        status="STAGED"
    )
    db_session.add(outbox_entry)
    db_session.commit()

    # 2. Engage kill-switch for capability
    ks = KillSwitch(
        id="sales.send_sequence",
        tenant_id="tenant-alpha",
        engaged=True,
        engaged_by="user-a",
        reason="Security audit in progress"
    )
    db_session.merge(ks)
    db_session.commit()

    # Process batch -> must abort dispatch due to kill-switch
    processed = await worker.process_batch(batch_size=10)
    db_session.expire_all()
    item = db_session.query(SideEffectOutbox).filter_by(idempotency_key=idemp_key).first()
    assert item.status == "FAILED"
    assert "kill-switch engaged" in item.last_error

    # 3. Release kill-switch and reset status to STAGED
    ks = db_session.query(KillSwitch).filter_by(id="sales.send_sequence").first()
    ks.engaged = False

    item = db_session.query(SideEffectOutbox).filter_by(idempotency_key=idemp_key).first()
    item.status = "STAGED"
    item.retry_count = 0
    item.lease_expires_at = None
    item.lease_owner = None
    db_session.commit()

    # Process batch -> must succeed and record event atomically
    processed = await worker.process_batch(batch_size=10)
    assert processed == 1

    db_session.expire_all()
    item = db_session.query(SideEffectOutbox).filter_by(idempotency_key=idemp_key).first()
    assert item.status == "ACKNOWLEDGED"
    assert item.acknowledged_at is not None

    # 4. Verify event was appended in event ledger and ledger chain is valid
    events = db_session.query(WorkflowEvent).filter_by(workflow_id="wf-test-1").all()
    assert len(events) >= 1
    assert EventLedger.verify_ledger_integrity(db_session, "wf-test-1") is True
