"""enterprise platform tables

Revision ID: a1b2c3d4e5f6
Revises: 9a1b2c3d4e5f
Create Date: 2026-07-11
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "9a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_policies",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False, unique=True),
        sa.Column("default_mode", sa.String(), server_default="draft_only"),
        sa.Column("min_confidence", sa.Float(), server_default="0.85"),
        sa.Column("max_auto_amount", sa.Float(), server_default="0"),
        sa.Column("allowed_channels", sa.JSON()),
        sa.Column("require_brand_pass", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("channel_kill_switches", sa.JSON()),
        sa.Column("agent_kill_switches", sa.JSON()),
        sa.Column("always_approve", sa.JSON()),
        sa.Column("support_refuse_if_not_in_kb", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_tenant_policies_tenant_id", "tenant_policies", ["tenant_id"])

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=True),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=True),
        sa.Column("agent_name", sa.String(), nullable=True),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON()),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), server_default="pending"),
        sa.Column("policy_reason", sa.String(), nullable=True),
        sa.Column("requested_by", sa.String(), nullable=True),
        sa.Column("reviewed_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_approval_requests_tenant_id", "approval_requests", ["tenant_id"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
    )

    op.create_table(
        "mfa_secrets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("secret_encrypted", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("backup_codes_hashed", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("code", sa.String(), unique=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("price_usd_monthly", sa.Float(), nullable=False),
        sa.Column("price_inr_monthly", sa.Float(), nullable=True),
        sa.Column("seat_limit", sa.Integer(), nullable=True),
        sa.Column("action_quota_monthly", sa.Integer(), server_default="10000"),
        sa.Column("allowed_agents", sa.JSON()),
        sa.Column("feature_flags", sa.JSON()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "tenant_subscriptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False, unique=True),
        sa.Column("plan_id", sa.String(), sa.ForeignKey("subscription_plans.id"), nullable=False),
        sa.Column("status", sa.String(), server_default="trialing"),
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seats_used", sa.Integer(), server_default="1"),
        sa.Column("actions_used_period", sa.Integer(), server_default="0"),
        sa.Column("feature_overrides", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "action_usage_counters",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("period_key", sa.String(), nullable=False),
        sa.Column("action_count", sa.Integer(), server_default="0"),
        sa.Column("spend_usd", sa.Float(), server_default="0"),
        sa.UniqueConstraint("tenant_id", "period_key", name="uq_tenant_period"),
    )

    op.create_table(
        "dead_letter_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("task_name", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("args", sa.JSON()),
        sa.Column("kwargs", sa.JSON()),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), server_default="failed"),
        sa.Column("attempts", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "workflow_checkpoints",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("workflow_name", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("step_index", sa.Integer(), server_default="0"),
        sa.Column("step_name", sa.String(), nullable=True),
        sa.Column("state", sa.JSON()),
        sa.Column("status", sa.String(), server_default="running"),
        sa.Column("idempotency_key", sa.String(), unique=True, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("payload_hash", sa.String(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "provider", "event_id", name="uq_webhook_event"),
    )

    op.create_table(
        "crm_connections",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("settings", sa.JSON()),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_status", sa.String(), server_default="idle"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "crm_sync_records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("local_type", sa.String(), nullable=False),
        sa.Column("local_id", sa.String(), nullable=False),
        sa.Column("remote_id", sa.String(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("direction", sa.String(), server_default="bidirectional"),
        sa.UniqueConstraint("tenant_id", "provider", "local_type", "local_id", name="uq_crm_local"),
    )

    op.create_table(
        "outcome_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("outcome_type", sa.String(), nullable=False),
        sa.Column("agent_name", sa.String(), nullable=True),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("decision_id", sa.String(), nullable=True),
        sa.Column("value", sa.Float(), server_default="1"),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "playbook_sops",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("department", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("icp_json", sa.JSON()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("banned", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("performance_score", sa.Float(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("document_id", sa.String(), sa.ForeignKey("knowledge_documents.id"), nullable=True),
        sa.Column("department", sa.String(), nullable=False, server_default="General"),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding_hint", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "ai_employees",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role_key", sa.String(), nullable=False),
        sa.Column("manager_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("quota_daily", sa.Integer(), server_default="100"),
        sa.Column("used_today", sa.Integer(), server_default="0"),
        sa.Column("sop_id", sa.String(), sa.ForeignKey("playbook_sops.id"), nullable=True),
        sa.Column("kpis", sa.JSON()),
        sa.Column("schedule", sa.JSON()),
        sa.Column("escalation_path", sa.JSON()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("status", sa.String(), server_default="idle"),
        sa.Column("last_standup", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "data_retention_policies",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False, unique=True),
        sa.Column("leads_days", sa.Integer(), server_default="730"),
        sa.Column("tickets_days", sa.Integer(), server_default="365"),
        sa.Column("audit_days", sa.Integer(), server_default="2555"),
        sa.Column("messages_days", sa.Integer(), server_default="365"),
        sa.Column("auto_purge_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "gdpr_requests",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("request_type", sa.String(), nullable=False),
        sa.Column("subject_email", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="pending"),
        sa.Column("result_payload", sa.JSON()),
        sa.Column("requested_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "tenant_budget_caps",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False, unique=True),
        sa.Column("monthly_spend_usd", sa.Float(), server_default="500"),
        sa.Column("monthly_action_cap", sa.Integer(), server_default="10000"),
        sa.Column("hard_stop", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("alert_at_pct", sa.Float(), server_default="0.8"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "tenant_slo_metrics",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("metric_name", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("period_key", sa.String(), nullable=False),
        sa.Column("sample_count", sa.Integer(), server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "metric_name", "period_key", name="uq_slo_day"),
    )

    op.create_table(
        "finance_records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("record_type", sa.String(), nullable=False),
        sa.Column("counterparty", sa.String(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(), server_default="USD"),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="open"),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    for t in [
        "finance_records",
        "tenant_slo_metrics",
        "tenant_budget_caps",
        "gdpr_requests",
        "data_retention_policies",
        "ai_employees",
        "knowledge_chunks",
        "playbook_sops",
        "outcome_events",
        "crm_sync_records",
        "crm_connections",
        "webhook_events",
        "workflow_checkpoints",
        "dead_letter_jobs",
        "action_usage_counters",
        "tenant_subscriptions",
        "subscription_plans",
        "mfa_secrets",
        "refresh_tokens",
        "approval_requests",
        "tenant_policies",
    ]:
        op.drop_table(t)
