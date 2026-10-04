from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base
import uuid


# ─────────────────────────────────────────────────────────────────────────────
# 1. DESIGN LAYER (Immutable definitions & versioning)
# ─────────────────────────────────────────────────────────────────────────────

class AgentDefinition(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True, index=True)  # Null = Platform Default
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, index=True)
    department = Column(String, nullable=False, default="general")  # sales, marketing, support, hr, finance, operations, custom
    role = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    avatar_icon = Column(String, default="Bot")
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    versions = relationship("AgentVersion", back_populates="agent", cascade="all, delete-orphan", order_by="desc(AgentVersion.version)")


class AgentVersion(Base):
    __tablename__ = "agent_versions"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    system_prompt = Column(Text, nullable=False)
    provider = Column(String, nullable=False, default="anthropic")
    model = Column(String, nullable=False, default="claude-sonnet-4-6")
    fallback_models = Column(JSON, default=list)  # e.g. ["gpt-4o", "gemini-2.5-flash"]
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=4096)
    tool_grants = Column(JSON, default=list)  # e.g. ["web_search", "lead.update", "email.send"]
    knowledge_access = Column(JSON, default=list)  # Department truth tags
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    agent = relationship("AgentDefinition", back_populates="versions")


class FlowDefinition(Base):
    __tablename__ = "flows"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, index=True)
    section = Column(String, nullable=False, default="sales")  # sales, marketing, support, hr, finance, executive
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    package_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    versions = relationship("FlowVersion", back_populates="flow", cascade="all, delete-orphan", order_by="desc(FlowVersion.version)")
    runs = relationship("FlowRun", back_populates="flow", cascade="all, delete-orphan")


class FlowVersion(Base):
    __tablename__ = "flow_versions"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    flow_id = Column(String, ForeignKey("flows.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    definition = Column(JSON, nullable=False, default=list)  # DAG of steps
    trigger_type = Column(String, default="manual")  # manual, schedule, event, webhook
    trigger_config = Column(JSON, default=dict)  # cron, event_topic, webhook_secret
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    flow = relationship("FlowDefinition", back_populates="versions")
    runs = relationship("FlowRun", back_populates="flow_version")


class PackageDefinition(Base):
    __tablename__ = "packages"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True, index=True)  # Null = Platform-wide
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, index=True)
    section = Column(String, nullable=False, default="sales")
    category = Column(String, nullable=False, default="General")
    desc = Column(Text, nullable=False)
    icon = Column(String, default="📦")
    complexity = Column(String, default="Intermediate")  # Beginner, Intermediate, Advanced
    time_saved = Column(String, default="15h/week")
    is_system = Column(Boolean, default=False)
    is_community = Column(Boolean, default=False)
    review_status = Column(String, default="published")  # draft, pending, published, suspended
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    versions = relationship("PackageVersion", back_populates="package", cascade="all, delete-orphan")
    installations = relationship("Installation", back_populates="package")


class PackageVersion(Base):
    __tablename__ = "package_versions"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    package_id = Column(String, ForeignKey("packages.id"), nullable=False, index=True)
    version = Column(String, nullable=False, default="1.0.0")  # Semver
    manifest = Column(JSON, nullable=False, default=dict)  # Complete package blueprint
    config_schema = Column(JSON, default=dict)  # Input parameters requested on install
    required_tools = Column(JSON, default=list)
    required_scopes = Column(JSON, default=list)
    eval_scores = Column(JSON, default=dict)  # Benchmark quality results
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    package = relationship("PackageDefinition", back_populates="versions")
    installations = relationship("Installation", back_populates="package_version")


class EvaluationSuite(Base):
    __tablename__ = "evaluation_suites"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True)
    target_type = Column(String, nullable=False)  # agent or package
    target_id = Column(String, nullable=False, index=True)
    test_cases = Column(JSON, default=list)
    latest_results = Column(JSON, default=dict)  # success_rate, tool_accuracy, latency, cost
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# 2. INSTALLATION LAYER (Tenant bindings & lifecycle)
# ─────────────────────────────────────────────────────────────────────────────

class Installation(Base):
    __tablename__ = "installations"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    package_id = Column(String, ForeignKey("packages.id"), nullable=False, index=True)
    package_version_id = Column(String, ForeignKey("package_versions.id"), nullable=False)
    status = Column(String, default="active")  # active, paused, failed
    config = Column(JSON, default=dict)
    secret_refs = Column(JSON, default=dict)
    created_resource_ids = Column(JSON, default=dict)  # {"agent_ids": [...], "flow_ids": [...]}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    package = relationship("PackageDefinition", back_populates="installations")
    package_version = relationship("PackageVersion", back_populates="installations")


# ─────────────────────────────────────────────────────────────────────────────
# 3. RUN LAYER (Durable Execution & Real Telemetry)
# ─────────────────────────────────────────────────────────────────────────────

class FlowRun(Base):
    __tablename__ = "flow_runs"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    flow_id = Column(String, ForeignKey("flows.id"), nullable=False, index=True)
    flow_version_id = Column(String, ForeignKey("flow_versions.id"), nullable=False)
    status = Column(String, default="pending", index=True)  # pending, running, waiting_approval, succeeded, failed, cancelled
    trigger_type = Column(String, default="manual")
    trigger_context = Column(JSON, default=dict)
    inputs = Column(JSON, default=dict)
    outputs = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    total_duration_ms = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)
    total_tokens = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    flow = relationship("FlowDefinition", back_populates="runs")
    flow_version = relationship("FlowVersion", back_populates="runs")
    step_runs = relationship("StepRun", back_populates="flow_run", cascade="all, delete-orphan", order_by="StepRun.created_at")
    approval_requests = relationship("ApprovalRequest", back_populates="flow_run", cascade="all, delete-orphan")


class StepRun(Base):
    __tablename__ = "step_runs"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    flow_run_id = Column(String, ForeignKey("flow_runs.id"), nullable=False, index=True)
    step_id = Column(String, nullable=False)
    step_type = Column(String, nullable=False)  # agent, tool, condition, approval, loop, entity_action, webhook
    status = Column(String, default="pending", index=True)  # pending, running, waiting_approval, succeeded, failed, skipped
    attempt = Column(Integer, default=1)
    idempotency_key = Column(String, index=True, nullable=True)
    inputs = Column(JSON, default=dict)
    outputs = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    duration_ms = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    flow_run = relationship("FlowRun", back_populates="step_runs")
    approval_requests = relationship("ApprovalRequest", back_populates="step_run", cascade="all, delete-orphan")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    flow_run_id = Column(String, ForeignKey("flow_runs.id"), nullable=False, index=True)
    step_run_id = Column(String, ForeignKey("step_runs.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    risk_level = Column(String, default="medium")  # low, medium, high
    status = Column(String, default="pending", index=True)  # pending, approved, rejected
    payload = Column(JSON, default=dict)  # Editable review content
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    flow_run = relationship("FlowRun", back_populates="approval_requests")
    step_run = relationship("StepRun", back_populates="approval_requests")


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    flow_run_id = Column(String, nullable=True, index=True)
    step_run_id = Column(String, nullable=True)
    agent_id = Column(String, nullable=True, index=True)
    agent_version_id = Column(String, nullable=True)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Float, default=0.0)
    task_type = Column(String, default="general")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ExecutionEvent(Base):
    __tablename__ = "execution_events"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    flow_run_id = Column(String, nullable=False, index=True)
    step_run_id = Column(String, nullable=True)
    event_type = Column(String, nullable=False)  # flow.started, step.completed, approval.requested, tool.invoked
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
