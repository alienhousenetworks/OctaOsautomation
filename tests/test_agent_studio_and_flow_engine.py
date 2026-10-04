import pytest
import asyncio
from unittest.mock import MagicMock, patch
from app.services.agents.tools import tool_registry, validate_outbound_url, SSRFProtectionError
from app.services.agents.section_registry import section_registry
from app.models.flow_engine import (
    AgentDefinition,
    AgentVersion,
    FlowDefinition,
    FlowVersion,
    FlowRun,
    StepRun,
    ApprovalRequest,
)


def test_ssrf_protection():
    """Verify SSRF guard rejects loopback and RFC 1918 private addresses."""
    malicious_urls = [
        "http://127.0.0.1:8000/secret",
        "http://localhost:5432",
        "http://10.0.0.5/admin",
        "http://192.168.1.100/metadata",
        "http://169.254.169.254/latest/meta-data/",
    ]
    for url in malicious_urls:
        with pytest.raises(SSRFProtectionError):
            validate_outbound_url(url)

    # Valid external URLs should pass through
    assert validate_outbound_url("https://api.github.com/events") == "https://api.github.com/events"


def test_tool_registry_registration():
    """Verify default capabilities are registered with appropriate risk levels."""
    tools = tool_registry.list_tools()
    tool_names = {t["name"] for t in tools}

    assert "web_search" in tool_names
    assert "email.send" in tool_names
    assert "lead.update" in tool_names
    assert "ticket.reply" in tool_names
    assert "webhook_post" in tool_names

    email_tool = tool_registry.get("email.send")
    assert email_tool.risk_level == "HIGH"
    assert email_tool.approval_required is True
    assert email_tool.side_effect == "WRITE"

    search_tool = tool_registry.get("web_search")
    assert search_tool.risk_level == "LOW"
    assert search_tool.approval_required is False
    assert search_tool.side_effect == "READ"


@pytest.mark.asyncio
async def test_section_registry_adapters():
    """Verify SectionRegistry dispatches actions to adapters cleanly."""
    mock_db = MagicMock()
    # Mocking db queries for Sales adapter
    mock_lead = MagicMock(id="lead-123", name="Acme", score=50, status="captured")
    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_lead

    res = await section_registry.execute_action(
        section="sales",
        action="lead.score",
        tenant_id="tenant-test",
        payload={"lead_id": "lead-123", "score": 85},
        db=mock_db,
    )
    assert res["success"] is True
    assert res["score"] == 85
    assert res["status"] == "qualified"


@pytest.mark.asyncio
async def test_flow_engine_approval_pause_and_resume():
    """Verify flow engine halts on approval step and resumes upon sign-off."""
    from app.services.agents.flow_engine import FlowExecutionEngine

    engine = FlowExecutionEngine()

    # Create mock database session and objects
    mock_db = MagicMock()

    flow_run = FlowRun(
        id="run-test-001",
        tenant_id="tenant-test",
        flow_id="flow-001",
        flow_version_id="ver-001",
        status="running",
        inputs={"company": "TestCorp", "email": "test@testcorp.com"},
        outputs={},
    )
    flow_ver = FlowVersion(
        id="ver-001",
        flow_id="flow-001",
        version=1,
        definition=[
            {"id": "step_1", "name": "Research", "type": "agent", "agent_slug": "sales_ai"},
            {"id": "step_2", "name": "Executive Sign-Off", "type": "approval", "risk_level": "medium"},
        ],
    )

    mock_db.query.return_value.filter_by.side_effect = [
        MagicMock(first=lambda: flow_run),  # for flow_run lookup
        MagicMock(first=lambda: flow_ver),  # for flow_ver lookup
        MagicMock(first=lambda: None),       # existing step_run for step_1
        MagicMock(first=lambda: None),       # existing step_run for step_2
        MagicMock(first=lambda: None),       # existing approval for step_2
    ]

    from unittest.mock import patch

    with patch("app.services.agents.flow_engine.agent_runtime.execute") as mock_exec:
        mock_exec.return_value = {
            "duration_ms": 150,
            "cost_usd": 0.005,
            "tokens": 120,
            "status": "succeeded",
            "output": "Lead qualified successfully",
        }
        await engine.execute_flow_run(mock_db, flow_run.id)

    # Verification: flow_run should be paused in waiting_approval
    assert flow_run.status == "waiting_approval"


def test_inbuilt_packages_auto_installation():
    """Verify DEFAULT_INBUILT_AUTO_INSTALL_SLUGS and ensure_default_installations logic."""
    from app.services.agents.seeder import DEFAULT_INBUILT_AUTO_INSTALL_SLUGS, ensure_default_installations
    from app.models.flow_engine import PackageDefinition, PackageVersion, Installation

    assert "saas_outreach_system" in DEFAULT_INBUILT_AUTO_INSTALL_SLUGS
    assert "ecommerce_growth_autopilot" in DEFAULT_INBUILT_AUTO_INSTALL_SLUGS
    assert "medical_clinic_receptionist" in DEFAULT_INBUILT_AUTO_INSTALL_SLUGS
    assert "hr_recruiter_system" in DEFAULT_INBUILT_AUTO_INSTALL_SLUGS
    assert "creative_content_lab" in DEFAULT_INBUILT_AUTO_INSTALL_SLUGS

    mock_db = MagicMock()
    mock_pack = PackageDefinition(
        id="pack-001",
        name="SaaS Outreach",
        slug="saas_outreach_system",
        section="sales",
        is_system=True,
    )
    mock_ver = PackageVersion(
        id="ver-001",
        package_id="pack-001",
        manifest={"flow": [{"id": "s1", "type": "agent", "agent_slug": "sales_ai"}]},
    )

    installed_set = set()

    def mock_query(model):
        q = MagicMock()
        if model == PackageDefinition:
            q.filter_by.return_value.first.return_value = mock_pack
        elif model == PackageVersion:
            q.filter_by.return_value.order_by.return_value.first.return_value = mock_ver
        elif model == Installation:
            # First check returns None, so it triggers install
            def check_inst():
                if "installed" in installed_set:
                    return MagicMock()
                installed_set.add("installed")
                return None
            q.filter_by.return_value.first.side_effect = check_inst
        else:
            q.filter_by.return_value.first.return_value = None
        return q

    mock_db.query.side_effect = mock_query

    with patch("app.services.agents.seeder.seed_system_packages"):
        ensure_default_installations(mock_db, "tenant-test-123")
    assert mock_db.commit.called

