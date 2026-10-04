import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, DateTime,
    ForeignKey, JSON, Numeric, Float, Text, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base

class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    workflow_id = Column(String, ForeignKey("workflows.id", ondelete="RESTRICT"), nullable=False, index=True)
    execution_id = Column(String, nullable=False)
    sequence_num = Column(BigInteger, nullable=False)
    event_type = Column(String(64), nullable=False)
    event_version = Column(String(16), nullable=False, default="1.0")
    actor_type = Column(String(32), nullable=False) # 'SYSTEM', 'AGENT', 'USER', 'POLICY_KERNEL'
    actor_id = Column(String(64), nullable=False)
    task_id = Column(String(64), nullable=True)
    correlation_id = Column(String(64), nullable=False, index=True)
    causation_id = Column(String(64), nullable=True)
    canonical_payload = Column(Text, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    previous_hash = Column(String(64), nullable=False)
    event_hash = Column(String(64), nullable=False)
    timestamp_iso = Column(String(36), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("workflow_id", "sequence_num", name="uq_wf_events_seq"),
    )


class CapabilityRegistry(Base):
    __tablename__ = "capability_registry"

    id = Column(String(128), primary_key=True)
    version = Column(String(16), primary_key=True)
    department = Column(String(32), nullable=False)
    description = Column(Text, nullable=False)
    side_effect_class = Column(String(32), nullable=False) # 'R0_INFORMATIONAL', 'R1_INTERNAL_REVERSIBLE', 'R2_EXTERNAL_REVERSIBLE', 'R3_EXTERNAL_IRREVERSIBLE', 'R4_FINANCIAL_CRITICAL'
    input_schema = Column(JSON, nullable=False)
    output_schema = Column(JSON, nullable=False)
    required_permissions = Column(JSON, nullable=False, default=list)
    cost_model = Column(JSON, nullable=False)
    default_autonomy = Column(String(8), nullable=False, default="L1")
    max_autonomy = Column(String(8), nullable=False, default="L2")
    dry_run_supported = Column(Boolean, nullable=False, default=True)
    idempotent = Column(Boolean, nullable=False, default=True)
    is_compensable = Column(Boolean, nullable=False, default=False)
    compensation_capability_id = Column(String(128), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BudgetEnvelope(Base):
    __tablename__ = "budget_envelopes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    department = Column(String(32), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    authorized_limit = Column(Numeric(12, 2), nullable=False)
    reserved_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    consumed_amount = Column(Numeric(12, 2), nullable=False, default=0.00)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("reserved_amount + consumed_amount <= authorized_limit", name="chk_budget_ceiling"),
        CheckConstraint("reserved_amount >= 0 AND consumed_amount >= 0", name="chk_budget_non_negative"),
    )


class BudgetReservation(Base):
    __tablename__ = "budget_reservations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    envelope_id = Column(String, ForeignKey("budget_envelopes.id", ondelete="RESTRICT"), nullable=False)
    workflow_id = Column(String, nullable=False)
    task_id = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(32), nullable=False, default="RESERVED") # 'RESERVED', 'COMMITTED', 'RELEASED', 'EXPIRED'
    idempotency_key = Column(String(128), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class KillSwitch(Base):
    __tablename__ = "kill_switches"

    id = Column(String(128), primary_key=True) # e.g. 'GLOBAL', 'sales.send_sequence', 'tenant:123'
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    engaged = Column(Boolean, nullable=False, default=True)
    engaged_by = Column(String(64), nullable=False)
    reason = Column(Text, nullable=False)
    engaged_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    released_at = Column(DateTime(timezone=True), nullable=True)


class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id = Column(String(64), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    condition_expr = Column(JSON, nullable=False)
    enforcement_action = Column(String(32), nullable=False) # 'DENY', 'QUARANTINE', 'REQUIRE_APPROVAL', 'ALLOW'
    required_roles = Column(JSON, default=lambda: ["CEO"])
    priority = Column(Integer, nullable=False, default=100) # Lower number = higher priority
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SuppressionList(Base):
    __tablename__ = "suppression_list"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type = Column(String(32), nullable=False) # 'EMAIL', 'DOMAIN', 'PHONE'
    target_value = Column(String(255), nullable=False, index=True)
    reason = Column(String(64), nullable=False) # 'OPTOUT', 'BOUNCE', 'LEGAL_HOLD', 'COMPLIANCE'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "target_type", "target_value", name="uq_suppression_target"),
    )


class PlanVersion(Base):
    __tablename__ = "plan_versions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    workflow_id = Column(String, ForeignKey("workflows.id", ondelete="RESTRICT"), nullable=False, index=True)
    version_num = Column(Integer, nullable=False)
    strategy_variant = Column(String(32), nullable=False) # 'AGGRESSIVE', 'BALANCED', 'CONSERVATIVE', 'CUSTOM'
    status = Column(String(32), nullable=False, default="DRAFT")
    plan_content_hash = Column(String(64), nullable=False)
    objective = Column(Text, nullable=False)
    executive_summary = Column(Text, nullable=False)
    estimated_budget = Column(Numeric(12, 2), nullable=False)
    max_budget_envelope = Column(Numeric(12, 2), nullable=False)
    quant_forecast = Column(JSON, nullable=False)
    red_team_critique = Column(JSON, nullable=False, default=list)
    compliance_scorecard = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    nodes = relationship("PlanNode", back_populates="plan_version", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("workflow_id", "version_num", "strategy_variant", name="uq_plan_version_variant"),
    )


class PlanNode(Base):
    __tablename__ = "plan_nodes"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_version_id = Column(String, ForeignKey("plan_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    department = Column(String(64), nullable=False, default="EXECUTION")
    capability_id = Column(String(128), nullable=False)
    capability_version = Column(String(16), nullable=False, default="1.0.0")
    parameters = Column(JSON, nullable=False, default=dict)
    depends_on = Column(JSON, nullable=False, default=list) # List of node IDs
    estimated_duration_seconds = Column(Integer, nullable=False, default=60)
    is_compensable = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plan_version = relationship("PlanVersion", back_populates="nodes")


class ExecutiveApprovalRequest(Base):
    __tablename__ = "executive_approval_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    workflow_id = Column(String, ForeignKey("workflows.id", ondelete="RESTRICT"), nullable=False, index=True)
    plan_version_id = Column(String, ForeignKey("plan_versions.id", ondelete="RESTRICT"), nullable=False)
    task_id = Column(String(64), nullable=False)
    capability_id = Column(String(128), nullable=False)
    capability_version = Column(String(16), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    risk_class = Column(String(32), nullable=False)
    required_keys = Column(Integer, nullable=False, default=1) # R4 requires 2
    status = Column(String(32), nullable=False, default="PENDING") # 'PENDING', 'APPROVED', 'REJECTED', 'EXPIRED'
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    financial_impact = Column(Numeric(12, 2), default=0.00)
    requester_user_id = Column(String(64), nullable=True) # Used for anti-self-approval
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    decisions = relationship("ApprovalDecision", back_populates="request", cascade="all, delete-orphan")


# Alias for backward compatibility within Executive OS
ApprovalRequest = ExecutiveApprovalRequest


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    approval_request_id = Column(String, ForeignKey("executive_approval_requests.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    user_role = Column(String(32), nullable=False)
    decision = Column(String(32), nullable=False) # 'APPROVE', 'REJECT'
    rationale = Column(Text, nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    request = relationship("ExecutiveApprovalRequest", back_populates="decisions")

    __table_args__ = (
        UniqueConstraint("approval_request_id", "user_id", name="uq_request_user_decision"),
    )


class SideEffectOutbox(Base):
    __tablename__ = "side_effect_outbox"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    workflow_id = Column(String, ForeignKey("workflows.id", ondelete="RESTRICT"), nullable=False, index=True)
    task_id = Column(String(64), nullable=False)
    capability_id = Column(String(128), nullable=False)
    capability_version = Column(String(16), nullable=False)
    idempotency_key = Column(String(128), nullable=False, unique=True)
    payload_hash = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(32), nullable=False, default="STAGED") # 'STAGED', 'DISPATCHED_UNKNOWN', 'ACKNOWLEDGED', 'FAILED', 'DEAD_LETTER'
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    lease_owner = Column(String(64), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    staged_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    url = Column(Text, nullable=False)
    domain = Column(String(255), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    content_hash = Column(String(64), nullable=False) # SHA-256 of raw_content
    raw_content = Column(Text, nullable=False)
    domain_reputation_score = Column(Float, nullable=False, default=0.7)
    is_quarantined = Column(Boolean, nullable=False, default=False)
    taint_flags = Column(JSON, nullable=False, default=list) # e.g. ["PROMPT_INJECTION_SUSPECT"]
    retrieved_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    claims = relationship("ClaimSupport", back_populates="source", cascade="all, delete-orphan")


class ClaimCluster(Base):
    __tablename__ = "claim_clusters"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    normalized_statement = Column(Text, nullable=False)
    entity_id = Column(String(128), nullable=True, index=True) # e.g. "competitor:salesforce", "market:tam:us_crm"
    numeric_consensus = Column(Numeric(14, 4), nullable=True)
    consensus_unit = Column(String(32), nullable=True)
    verification_status = Column(String(32), nullable=False, default="UNVERIFIED") # 'VERIFIED', 'SINGLE_SOURCE', 'CONTRADICTED', 'QUARANTINED', 'UNVERIFIED'
    confidence_score = Column(Numeric(3, 2), nullable=False, default=0.00)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    supports = relationship("ClaimSupport", back_populates="cluster", cascade="all, delete-orphan")


class ClaimSupport(Base):
    __tablename__ = "claim_support"

    cluster_id = Column(String, ForeignKey("claim_clusters.id", ondelete="CASCADE"), primary_key=True)
    source_id = Column(String, ForeignKey("evidence_sources.id", ondelete="CASCADE"), primary_key=True)
    raw_statement = Column(Text, nullable=False)
    extracted_value = Column(Numeric(14, 4), nullable=True)
    as_of_date = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    retrieved_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    supports_consensus = Column(Boolean, nullable=False, default=True)

    cluster = relationship("ClaimCluster", back_populates="supports")
    source = relationship("EvidenceSource", back_populates="claims")


class PlaybookPostMortem(Base):
    __tablename__ = "playbook_post_mortems"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(String, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_version_id = Column(String, ForeignKey("plan_versions.id", ondelete="CASCADE"), nullable=False)
    objective = Column(Text, nullable=False)
    strategy_variant = Column(String(32), nullable=False)
    forecast_p50_cost = Column(Float, nullable=False, default=0.0)
    actual_cost = Column(Float, nullable=False, default=0.0)
    forecast_duration_seconds = Column(Integer, nullable=False, default=0)
    actual_duration_seconds = Column(Integer, nullable=False, default=0)
    tasks_completed = Column(Integer, nullable=False, default=0)
    tasks_failed = Column(Integer, nullable=False, default=0)
    variance_analysis = Column(JSON, nullable=False, default=dict)
    executive_brief_markdown = Column(Text, nullable=False)
    key_learnings = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

