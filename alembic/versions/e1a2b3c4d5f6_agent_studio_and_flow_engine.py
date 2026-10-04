"""agent studio, flow engine, capability registry and safe marketplace

Revision ID: e1a2b3c4d5f6
Revises: c7d8e9f0a1b2
Create Date: 2026-10-04
"""
from alembic import op
import sqlalchemy as sa


revision = "e1a2b3c4d5f6"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. agents
    if "agents" not in existing_tables:
        op.create_table(
            "agents",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=True, index=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False, index=True),
            sa.Column("department", sa.String(), nullable=False, server_default="general"),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("avatar_icon", sa.String(), server_default="Bot"),
            sa.Column("is_system", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # 2. agent_versions
    if "agent_versions" not in existing_tables:
        op.create_table(
            "agent_versions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("agent_id", sa.String(), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("system_prompt", sa.Text(), nullable=False),
            sa.Column("provider", sa.String(), nullable=False, server_default="anthropic"),
            sa.Column("model", sa.String(), nullable=False, server_default="claude-sonnet-4-6"),
            sa.Column("fallback_models", sa.JSON(), nullable=True),
            sa.Column("temperature", sa.Float(), server_default="0.7"),
            sa.Column("max_tokens", sa.Integer(), server_default="4096"),
            sa.Column("tool_grants", sa.JSON(), nullable=True),
            sa.Column("knowledge_access", sa.JSON(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # 3. flows
    if "flows" not in existing_tables:
        op.create_table(
            "flows",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False, index=True),
            sa.Column("section", sa.String(), nullable=False, server_default="sales"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
            sa.Column("package_id", sa.String(), nullable=True, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # 4. flow_versions
    if "flow_versions" not in existing_tables:
        op.create_table(
            "flow_versions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("flow_id", sa.String(), sa.ForeignKey("flows.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("definition", sa.JSON(), nullable=False),
            sa.Column("trigger_type", sa.String(), server_default="manual"),
            sa.Column("trigger_config", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # 5. packages
    if "packages" not in existing_tables:
        op.create_table(
            "packages",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=True, index=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False, index=True),
            sa.Column("section", sa.String(), nullable=False, server_default="sales"),
            sa.Column("category", sa.String(), nullable=False, server_default="General"),
            sa.Column("desc", sa.Text(), nullable=False),
            sa.Column("icon", sa.String(), server_default="📦"),
            sa.Column("complexity", sa.String(), server_default="Intermediate"),
            sa.Column("time_saved", sa.String(), server_default="15h/week"),
            sa.Column("is_system", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("is_community", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("review_status", sa.String(), server_default="published"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # 6. package_versions
    if "package_versions" not in existing_tables:
        op.create_table(
            "package_versions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("package_id", sa.String(), sa.ForeignKey("packages.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("version", sa.String(), nullable=False, server_default="1.0.0"),
            sa.Column("manifest", sa.JSON(), nullable=False),
            sa.Column("config_schema", sa.JSON(), nullable=True),
            sa.Column("required_tools", sa.JSON(), nullable=True),
            sa.Column("required_scopes", sa.JSON(), nullable=True),
            sa.Column("eval_scores", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # 7. evaluation_suites
    if "evaluation_suites" not in existing_tables:
        op.create_table(
            "evaluation_suites",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=True),
            sa.Column("target_type", sa.String(), nullable=False),
            sa.Column("target_id", sa.String(), nullable=False, index=True),
            sa.Column("test_cases", sa.JSON(), nullable=True),
            sa.Column("latest_results", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # 8. installations
    if "installations" not in existing_tables:
        op.create_table(
            "installations",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("package_id", sa.String(), sa.ForeignKey("packages.id"), nullable=False, index=True),
            sa.Column("package_version_id", sa.String(), sa.ForeignKey("package_versions.id"), nullable=False),
            sa.Column("status", sa.String(), server_default="active"),
            sa.Column("config", sa.JSON(), nullable=True),
            sa.Column("secret_refs", sa.JSON(), nullable=True),
            sa.Column("created_resource_ids", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # 9. flow_runs
    if "flow_runs" not in existing_tables:
        op.create_table(
            "flow_runs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("flow_id", sa.String(), sa.ForeignKey("flows.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("flow_version_id", sa.String(), sa.ForeignKey("flow_versions.id"), nullable=False),
            sa.Column("status", sa.String(), server_default="pending", index=True),
            sa.Column("trigger_type", sa.String(), server_default="manual"),
            sa.Column("trigger_context", sa.JSON(), nullable=True),
            sa.Column("inputs", sa.JSON(), nullable=True),
            sa.Column("outputs", sa.JSON(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("total_duration_ms", sa.Integer(), server_default="0"),
            sa.Column("total_cost_usd", sa.Float(), server_default="0.0"),
            sa.Column("total_tokens", sa.Integer(), server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # 10. step_runs
    if "step_runs" not in existing_tables:
        op.create_table(
            "step_runs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("flow_run_id", sa.String(), sa.ForeignKey("flow_runs.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("step_id", sa.String(), nullable=False),
            sa.Column("step_type", sa.String(), nullable=False),
            sa.Column("status", sa.String(), server_default="pending", index=True),
            sa.Column("attempt", sa.Integer(), server_default="1"),
            sa.Column("idempotency_key", sa.String(), nullable=True, index=True),
            sa.Column("inputs", sa.JSON(), nullable=True),
            sa.Column("outputs", sa.JSON(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), server_default="0"),
            sa.Column("cost_usd", sa.Float(), server_default="0.0"),
            sa.Column("tokens_used", sa.Integer(), server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # 11. approval_requests
    if "approval_requests" not in existing_tables:
        op.create_table(
            "approval_requests",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("flow_run_id", sa.String(), sa.ForeignKey("flow_runs.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("step_run_id", sa.String(), sa.ForeignKey("step_runs.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("risk_level", sa.String(), server_default="medium"),
            sa.Column("status", sa.String(), server_default="pending", index=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("approved_by", sa.String(), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # 12. usage_events
    if "usage_events" not in existing_tables:
        op.create_table(
            "usage_events",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("flow_run_id", sa.String(), nullable=True, index=True),
            sa.Column("step_run_id", sa.String(), nullable=True),
            sa.Column("agent_id", sa.String(), nullable=True, index=True),
            sa.Column("agent_version_id", sa.String(), nullable=True),
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("model", sa.String(), nullable=False),
            sa.Column("input_tokens", sa.Integer(), server_default="0"),
            sa.Column("output_tokens", sa.Integer(), server_default="0"),
            sa.Column("cost_usd", sa.Float(), server_default="0.0"),
            sa.Column("latency_ms", sa.Float(), server_default="0.0"),
            sa.Column("task_type", sa.String(), server_default="general"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        )

    # 13. execution_events
    if "execution_events" not in existing_tables:
        op.create_table(
            "execution_events",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("flow_run_id", sa.String(), nullable=False, index=True),
            sa.Column("step_run_id", sa.String(), nullable=True),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade() -> None:
    tables = [
        "execution_events",
        "usage_events",
        "approval_requests",
        "step_runs",
        "flow_runs",
        "installations",
        "evaluation_suites",
        "package_versions",
        "packages",
        "flow_versions",
        "flows",
        "agent_versions",
        "agents",
    ]
    for table in tables:
        op.drop_table(table)
