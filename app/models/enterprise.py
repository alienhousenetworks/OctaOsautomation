"""Enterprise platform models: policy, billing, DLQ, CRM sync, AI employees, compliance."""
import uuid
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, JSON, Float, Integer, Text, UniqueConstraint
)
from sqlalchemy.sql import func
from app.models.base import Base


class TenantPolicy(Base):
    """Per-tenant HITL / outbound policy configuration."""
    __tablename__ = "tenant_policies"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, unique=True, index=True)
    # Default: AI drafts only unless rules allow auto-send
    default_mode = Column(String, default="draft_only")  # draft_only | auto_with_rules
    min_confidence = Column(Float, default=0.85)
    max_auto_amount = Column(Float, default=0.0)  # for refunds/quotes
    allowed_channels = Column(JSON, default=lambda: ["email", "whatsapp", "linkedin", "meta"])
    require_brand_pass = Column(Boolean, default=True)
    # Kill switches per channel / agent
    channel_kill_switches = Column(JSON, default=dict)  # {"whatsapp": true} = killed
    agent_kill_switches = Column(JSON, default=dict)  # {"sales": true}
    # Which action types always need human approval
    always_approve = Column(
        JSON,
        default=lambda: [
            "first_touch_email",
            "public_post",
            "price_quote",
            "refund",
            "linkedin_dm",
        ],
    )
    support_refuse_if_not_in_kb = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ApprovalRequest(Base):
    """Human-in-the-loop approval queue."""
    __tablename__ = "approval_requests"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    organization_id = Column(String, nullable=True, index=True)
    action_type = Column(String, nullable=False, index=True)  # first_touch_email, public_post, ...
    channel = Column(String, nullable=True)
    agent_name = Column(String, nullable=True)
    resource_type = Column(String, nullable=True)  # lead, post, ticket
    resource_id = Column(String, nullable=True, index=True)
    title = Column(String, nullable=False)
    payload = Column(JSON, default=dict)  # draft content, recipient, metadata
    confidence = Column(Float, nullable=True)
    status = Column(String, default="pending", index=True)  # pending, approved, rejected, expired, auto_sent
    policy_reason = Column(String, nullable=True)
    requested_by = Column(String, nullable=True)  # agent or user id
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    review_note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)


class MFASecret(Base):
    __tablename__ = "mfa_secrets"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    secret_encrypted = Column(String, nullable=False)
    enabled = Column(Boolean, default=False)
    backup_codes_hashed = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String, unique=True, nullable=False)  # starter, growth, business, enterprise
    name = Column(String, nullable=False)
    price_usd_monthly = Column(Float, nullable=False)
    price_inr_monthly = Column(Float, nullable=True)
    seat_limit = Column(Integer, nullable=True)  # null = unlimited
    action_quota_monthly = Column(Integer, default=10000)
    allowed_agents = Column(JSON, default=list)
    feature_flags = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, unique=True, index=True)
    plan_id = Column(String, ForeignKey("subscription_plans.id"), nullable=False)
    status = Column(String, default="trialing")  # trialing, active, past_due, canceled, expired
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    seats_used = Column(Integer, default=1)
    actions_used_period = Column(Integer, default=0)
    feature_overrides = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ActionUsageCounter(Base):
    """Monthly action counters for quotas / budget caps."""
    __tablename__ = "action_usage_counters"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    period_key = Column(String, nullable=False)  # YYYY-MM
    action_count = Column(Integer, default=0)
    spend_usd = Column(Float, default=0.0)
    __table_args__ = (UniqueConstraint("tenant_id", "period_key", name="uq_tenant_period"),)


class DeadLetterJob(Base):
    __tablename__ = "dead_letter_jobs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=True, index=True)
    task_name = Column(String, nullable=False, index=True)
    task_id = Column(String, nullable=True, index=True)
    args = Column(JSON, default=list)
    kwargs = Column(JSON, default=dict)
    error_message = Column(Text, nullable=True)
    traceback = Column(Text, nullable=True)
    status = Column(String, default="failed")  # failed, replaying, resolved, discarded
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class WorkflowCheckpoint(Base):
    """Checkpointed multi-step agent runs."""
    __tablename__ = "workflow_checkpoints"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    workflow_name = Column(String, nullable=False, index=True)
    run_id = Column(String, nullable=False, index=True)
    step_index = Column(Integer, default=0)
    step_name = Column(String, nullable=True)
    state = Column(JSON, default=dict)
    status = Column(String, default="running")  # running, waiting, completed, failed
    idempotency_key = Column(String, nullable=True, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WebhookEvent(Base):
    """Idempotency store for inbound webhooks."""
    __tablename__ = "webhook_events"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)
    event_id = Column(String, nullable=False)
    payload_hash = Column(String, nullable=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("tenant_id", "provider", "event_id", name="uq_webhook_event"),)


class CRMConnection(Base):
    __tablename__ = "crm_connections"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    provider = Column(String, nullable=False)  # hubspot, salesforce, zendesk, freshdesk
    encrypted_credentials = Column(Text, nullable=False)
    settings = Column(JSON, default=dict)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    sync_status = Column(String, default="idle")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CRMSyncRecord(Base):
    __tablename__ = "crm_sync_records"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    provider = Column(String, nullable=False)
    local_type = Column(String, nullable=False)  # lead, ticket
    local_id = Column(String, nullable=False)
    remote_id = Column(String, nullable=False)
    last_synced_at = Column(DateTime(timezone=True), server_default=func.now())
    direction = Column(String, default="bidirectional")
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "local_type", "local_id", name="uq_crm_local"),
    )


class OutcomeEvent(Base):
    """Labeled outcomes for learning / ROI (reply, meeting, CSAT, engagement)."""
    __tablename__ = "outcome_events"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    outcome_type = Column(String, nullable=False, index=True)
    # reply_received, meeting_booked, ticket_csat, post_engagement, conversion
    agent_name = Column(String, nullable=True, index=True)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True, index=True)
    decision_id = Column(String, nullable=True, index=True)
    value = Column(Float, default=1.0)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PlaybookSOP(Base):
    """First-class SOPs / ICP playbooks per tenant."""
    __tablename__ = "playbook_sops"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    department = Column(String, nullable=False)  # sales, marketing, support
    version = Column(Integer, default=1)
    content = Column(Text, nullable=False)
    icp_json = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    banned = Column(Boolean, default=False)  # low performer ban
    performance_score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class KnowledgeChunk(Base):
    """Versioned KB chunks for RAG + citations."""
    __tablename__ = "knowledge_chunks"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("knowledge_documents.id"), nullable=True, index=True)
    department = Column(String, nullable=False, default="General")
    version = Column(Integer, default=1)
    title = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    embedding_hint = Column(String, nullable=True)  # keyword fingerprint for simple retrieval
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AIEmployee(Base):
    """AI Employee operating model entity."""
    __tablename__ = "ai_employees"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)  # Sales AI, Support AI
    role_key = Column(String, nullable=False)  # sales, marketing, support, hr
    manager_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    quota_daily = Column(Integer, default=100)
    used_today = Column(Integer, default=0)
    sop_id = Column(String, ForeignKey("playbook_sops.id"), nullable=True)
    kpis = Column(JSON, default=dict)  # targets
    schedule = Column(JSON, default=dict)  # shift windows
    escalation_path = Column(JSON, default=list)  # user ids / roles
    is_active = Column(Boolean, default=True)
    status = Column(String, default="idle")  # idle, working, waiting_approval, error
    last_standup = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DataRetentionPolicy(Base):
    __tablename__ = "data_retention_policies"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, unique=True)
    leads_days = Column(Integer, default=730)
    tickets_days = Column(Integer, default=365)
    audit_days = Column(Integer, default=2555)  # ~7 years
    messages_days = Column(Integer, default=365)
    auto_purge_enabled = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GDPRRequest(Base):
    __tablename__ = "gdpr_requests"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    request_type = Column(String, nullable=False)  # export, delete
    subject_email = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    result_payload = Column(JSON, default=dict)
    requested_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class TenantBudgetCap(Base):
    __tablename__ = "tenant_budget_caps"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, unique=True)
    monthly_spend_usd = Column(Float, default=500.0)
    monthly_action_cap = Column(Integer, default=10000)
    hard_stop = Column(Boolean, default=True)
    alert_at_pct = Column(Float, default=0.8)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TenantSLOMetric(Base):
    __tablename__ = "tenant_slo_metrics"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    metric_name = Column(String, nullable=False)
    # ticket_first_response_seconds, post_publish_success_rate, outreach_error_rate
    value = Column(Float, nullable=False)
    period_key = Column(String, nullable=False)  # YYYY-MM-DD
    sample_count = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("tenant_id", "metric_name", "period_key", name="uq_slo_day"),
    )


class FinanceRecord(Base):
    """Real finance vertical: invoices / expenses / AR follow-ups."""
    __tablename__ = "finance_records"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    record_type = Column(String, nullable=False)  # invoice, expense, ar_followup
    counterparty = Column(String, nullable=True)
    amount = Column(Float, nullable=False, default=0.0)
    currency = Column(String, default="USD")
    category = Column(String, nullable=True)
    status = Column(String, default="open")  # open, paid, overdue, canceled
    due_date = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
