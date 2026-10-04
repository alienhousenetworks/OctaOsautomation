import pytest
import uuid
import hashlib
from datetime import datetime, timezone
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models.base import Base, Tenant, User
from app.models.workflows import Workflow
from app.models.executive import (
    PlanVersion, PlanNode, ClaimCluster, SuppressionList, KillSwitch, WorkflowEvent
)
from app.services.agents.executive.chief_of_staff import ChiefOfStaffAgent
from app.services.agents.executive.quant_analyst import QuantAnalystEngine
from app.services.agents.executive.red_team import RedTeamCriticAgent
from app.services.agents.executive.compliance_sentinel import ComplianceSentinelAgent
from app.services.executive_os.strategy_compiler import StrategyCompiler
from app.core.event_ledger import EventLedger

TEST_DB_URL = "sqlite:///./test_executive_phase3.db"
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

    tenant = Tenant(id="tenant-delta", name="Delta Corp", subdomain="delta", company_email="admin@delta.com")
    db.add(tenant)
    db.flush()

    wf = Workflow(id="wf-compiler-1", tenant_id=tenant.id, name="Q4 Strategic Planning", vertical="CEO", department="CEO")
    db.add(wf)
    db.commit()

    try:
        yield db
    finally:
        db.close()
        engine.dispose()
        Base.metadata.drop_all(bind=engine)


def test_chief_of_staff_intent_parsing(db_session):
    """
    Test 1: Chief of Staff Agent parses unstructured CEO directives into IntentAST.
    """
    cos = ChiefOfStaffAgent(db_session, "tenant-delta")
    prompt = "Accelerate outbound pipeline to reach $50,000 in Q4 without hiring new reps within 45 days"

    res = cos.parse_intent(prompt)
    ast = res["intent_ast"]

    assert ast["strategic_pillar"] == "REVENUE"
    assert ast["budget_envelope_cap"] == 50000.0
    assert ast["timeline_days"] == 45
    assert len(ast["explicit_constraints"]) > 0
    assert res["routing_plan"]["requires_market_scout"] is True


def test_kahns_algorithm_acyclicity_validation():
    """
    Test 2: Kahn's Algorithm validates acyclic DAGs and rejects circular dependencies.
    """
    # 1. Valid Acyclic DAG (Diamond)
    valid_nodes = [
        {"id": "A", "depends_on": []},
        {"id": "B1", "depends_on": ["A"]},
        {"id": "B2", "depends_on": ["A"]},
        {"id": "C", "depends_on": ["B1", "B2"]}
    ]
    order = StrategyCompiler.validate_acyclicity(valid_nodes)
    assert order[0] == "A"
    assert order[-1] == "C"

    # 2. Cyclic DAG (A -> B -> C -> A)
    cyclic_nodes = [
        {"id": "node-A", "depends_on": ["node-C"]},
        {"id": "node-B", "depends_on": ["node-A"]},
        {"id": "node-C", "depends_on": ["node-B"]}
    ]
    with pytest.raises(ValueError, match="Cycle detected in plan DAG"):
        StrategyCompiler.validate_acyclicity(cyclic_nodes)


def test_evidence_admission_gate_filtering(db_session):
    """
    Test 3: Only evidence claims with confidence >= 0.70 are admitted to compiler.
    Single-source claims (< 0.70) are strictly excluded from plan synthesis.
    """
    tenant_id = "tenant-delta"

    # Sub-threshold claim (confidence = 0.55, unverified single source)
    c1 = ClaimCluster(
        id="c-unverified",
        tenant_id=tenant_id,
        normalized_statement="Conversion benchmark is 8.0%",
        numeric_consensus=8.0,
        consensus_unit="%",
        verification_status="SINGLE_SOURCE",
        confidence_score=0.55
    )
    # Admissible claim (confidence = 0.90, multi-source verified)
    c2 = ClaimCluster(
        id="c-verified",
        tenant_id=tenant_id,
        normalized_statement="Conversion benchmark is 3.5%",
        numeric_consensus=3.5,
        consensus_unit="%",
        verification_status="VERIFIED",
        confidence_score=0.90
    )
    db_session.add_all([c1, c2])
    db_session.commit()

    compiler = StrategyCompiler(db_session, tenant_id)
    plans = compiler.compile_plans("wf-compiler-1", "Scale pipeline by $20,000")

    assert len(plans) == 3
    # Check that quant forecast calibrated using the verified claim (3.5%), not the unverified one
    bal_plan = next(p for p in plans if p.strategy_variant == "BALANCED")
    conv_forecast = bal_plan.quant_forecast["metric_forecasts"]["conversion_rate"]["p50"]
    # 3.5% should be the median calibration
    assert 2.5 <= conv_forecast <= 4.5


def test_seeded_deterministic_quant_engine():
    """
    Test 4: Quant Analyst Monte Carlo simulation is bitwise reproducible for the same seed,
    satisfying P10 <= P50 <= P90.
    """
    quant = QuantAnalystEngine()
    evidence = [{"numeric_consensus": 4.0, "consensus_unit": "%"}]

    res1 = quant.run_monte_carlo("BALANCED", 10000.0, evidence, seed=42)
    res2 = quant.run_monte_carlo("BALANCED", 10000.0, evidence, seed=42)

    # Deterministic equality assertion
    assert res1["metric_forecasts"] == res2["metric_forecasts"]

    pipe = res1["metric_forecasts"]["qualified_pipeline"]
    assert pipe["p10"] <= pipe["p50"] <= pipe["p90"]

    assert len(res1["sensitivity_ranking"]) > 0


def test_red_team_critic_adversarial_inspection():
    """
    Test 5: Red Team Critic detects unrooted irreversible actions and calculates fragility.
    """
    critic = RedTeamCriticAgent()

    # Flawed DAG: Unrooted irreversible external sequence
    flawed_nodes = [
        {
            "id": "node-unrooted-send",
            "name": "Direct Cold Outreach",
            "capability_id": "sales.send_sequence",
            "parameters": {"lead_ids": ["l1", "l2"]},
            "depends_on": [],
            "is_compensable": False
        }
    ]

    critique = critic.critique_plan("AGGRESSIVE", flawed_nodes, [])
    assert len(critique["attack_vectors"]) > 0
    assert any(v["severity"] == "CRITICAL" for v in critique["attack_vectors"])
    assert critique["fragility_score"] > 0.40


def test_compliance_sentinel_preflight_audit(db_session):
    """
    Test 6: Compliance Sentinel catches suppressed emails and kill switches before execution.
    """
    tenant_id = "tenant-delta"

    # Seed suppression
    supp = SuppressionList(
        tenant_id=tenant_id,
        target_type="EMAIL",
        target_value="blocked@competitor.com",
        reason="LEGAL_HOLD"
    )
    db_session.add(supp)
    db_session.commit()

    sentinel = ComplianceSentinelAgent(db_session, tenant_id)

    # 1. Non-compliant nodes
    bad_nodes = [
        {
            "id": "n-bad",
            "capability_id": "sales.send_sequence",
            "parameters": {"lead_ids": ["blocked@competitor.com"]}
        }
    ]
    report_bad = sentinel.inspect_dag_compliance(bad_nodes)
    assert report_bad["is_compliant"] is False
    assert report_bad["violations_count"] == 1

    # 2. Compliant nodes
    good_nodes = [
        {
            "id": "n-good",
            "capability_id": "sales.send_sequence",
            "parameters": {"lead_ids": ["clean@customer.com"]}
        }
    ]
    report_good = sentinel.inspect_dag_compliance(good_nodes)
    assert report_good["is_compliant"] is True


def test_strategy_compiler_full_generation(db_session):
    """
    Test 7: Strategy Compiler emits AGGRESSIVE, BALANCED, and CONSERVATIVE PlanVersions,
    populates PlanNodes, and logs plan_compiled events.
    """
    tenant_id = "tenant-delta"
    compiler = StrategyCompiler(db_session, tenant_id)

    plans = compiler.compile_plans(
        workflow_id="wf-compiler-1",
        prompt="Launch outbound pipeline acceleration with $15,000 budget cap"
    )

    assert len(plans) == 3
    variants = {p.strategy_variant for p in plans}
    assert variants == {"AGGRESSIVE", "BALANCED", "CONSERVATIVE"}

    # Verify budgets follow variant tiers
    agg = next(p for p in plans if p.strategy_variant == "AGGRESSIVE")
    bal = next(p for p in plans if p.strategy_variant == "BALANCED")
    con = next(p for p in plans if p.strategy_variant == "CONSERVATIVE")

    assert float(agg.estimated_budget) > float(bal.estimated_budget) > float(con.estimated_budget)

    # Verify PlanNodes created in DB
    nodes_count = db_session.query(PlanNode).filter_by(plan_version_id=bal.id).count()
    assert nodes_count >= 2

    # Verify EventLedger has plan_compiled records
    events = db_session.query(WorkflowEvent).filter_by(event_type="plan_compiled").all()
    assert len(events) == 3


def test_plan_content_hash_tamper_detection():
    """
    Test 8: Changing 1 byte in plan node parameters mutates the cryptographic content hash.
    """
    nodes_v1 = [
        {
            "id": "n1",
            "capability_id": "sales.send_sequence",
            "depends_on": [],
            "parameters": {"leads": ["l1", "l2"]}
        }
    ]
    nodes_v2 = [
        {
            "id": "n1",
            "capability_id": "sales.send_sequence",
            "depends_on": [],
            "parameters": {"leads": ["l1", "l3"]} # 1 character changed
        }
    ]

    hash1 = StrategyCompiler.compute_plan_content_hash("wf-1", 1, "BALANCED", nodes_v1)
    hash2 = StrategyCompiler.compute_plan_content_hash("wf-1", 1, "BALANCED", nodes_v2)

    assert hash1 != hash2


def test_compiler_and_plan_api_endpoints(db_session):
    """
    Test 9: FastAPI REST endpoints for Strategy Compiler:
    - POST /compiler/compile
    - GET /plans/{workflow_id}
    - GET /plans/{workflow_id}/{plan_version_id}
    - POST /plans/{workflow_id}/{plan_version_id}/activate
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api import deps

    tenant_id = "tenant-delta"
    app.dependency_overrides[deps.get_db] = lambda: db_session
    app.dependency_overrides[deps.get_current_tenant_id] = lambda: tenant_id

    client = TestClient(app)

    try:
        # 1. Compile plans via API
        res_compile = client.post(
            "/api/v1/ceo/compiler/compile",
            json={
                "workflow_id": "wf-compiler-1",
                "prompt": "Scale customer acquisition with $20,000 budget cap in 30 days"
            }
        )
        assert res_compile.status_code == 200
        compiled_list = res_compile.json()
        assert len(compiled_list) == 3

        selected_plan = compiled_list[0]
        plan_id = selected_plan["id"]

        # 2. List plans for workflow
        res_list = client.get("/api/v1/ceo/plans/wf-compiler-1")
        assert res_list.status_code == 200
        assert len(res_list.json()) >= 3

        # 3. Get plan details
        res_detail = client.get(f"/api/v1/ceo/plans/wf-compiler-1/{plan_id}")
        assert res_detail.status_code == 200
        detail_data = res_detail.json()
        assert detail_data["id"] == plan_id
        assert len(detail_data["nodes"]) >= 2
        assert "quant_forecast" in detail_data
        assert "red_team_critique" in detail_data

        # 4. Activate plan
        res_activate = client.post(f"/api/v1/ceo/plans/wf-compiler-1/{plan_id}/activate")
        assert res_activate.status_code == 200
        assert res_activate.json()["status"] == "ACTIVATED"

    finally:
        app.dependency_overrides.clear()
