"""Sales OS Deal Room and Evidence Architecture

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. suppression_records
    op.create_table(
        "suppression_records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("identifier_type", sa.String(), nullable=False),
        sa.Column("identifier_value", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("origin", sa.String(), server_default="system"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "identifier_type", "identifier_value", name="uq_tenant_suppression"),
    )
    op.create_index("ix_suppression_tenant", "suppression_records", ["tenant_id"])
    op.create_index("ix_suppression_type", "suppression_records", ["identifier_type"])
    op.create_index("ix_suppression_value", "suppression_records", ["identifier_value"])

    # 2. deal_rooms
    op.create_table(
        "deal_rooms",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=True),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("website", sa.String(), nullable=True),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("annual_revenue_usd", sa.Float(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("tech_stack", sa.JSON(), nullable=True),
        sa.Column("stage", sa.String(), server_default="discovered"),
        sa.Column("icp_fit_score", sa.Float(), server_default="0.0"),
        sa.Column("timing_score", sa.Float(), server_default="0.0"),
        sa.Column("evidence_score", sa.Float(), server_default="0.0"),
        sa.Column("accessibility_score", sa.Float(), server_default="0.0"),
        sa.Column("priority_index", sa.Float(), server_default="0.0"),
        sa.Column("calibrated_win_prob", sa.Float(), server_default="0.0"),
        sa.Column("is_multi_threaded", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("committee_coverage", sa.Float(), server_default="0.0"),
        sa.Column("risk_flags", sa.JSON(), nullable=True),
        sa.Column("next_best_action", sa.JSON(), nullable=True),
        sa.Column("assigned_human_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("account_brief", sa.JSON(), nullable=True),
        sa.Column("pain_hypotheses", sa.JSON(), nullable=True),
        sa.Column("solution_matches", sa.JSON(), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "domain", name="uq_tenant_deal_room_domain"),
    )
    op.create_index("ix_deal_rooms_tenant", "deal_rooms", ["tenant_id"])
    op.create_index("ix_deal_rooms_domain", "deal_rooms", ["domain"])
    op.create_index("ix_deal_rooms_company_name", "deal_rooms", ["company_name"])
    op.create_index("ix_deal_rooms_stage", "deal_rooms", ["stage"])
    op.create_index("ix_deal_rooms_org", "deal_rooms", ["organization_id"])

    # 3. buying_committee_members
    op.create_table(
        "buying_committee_members",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("deal_room_id", sa.String(), sa.ForeignKey("deal_rooms.id"), nullable=False),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("role_type", sa.String(), server_default="influencer"),
        sa.Column("department", sa.String(), nullable=True),
        sa.Column("linkedin_url", sa.String(), nullable=True),
        sa.Column("engagement_state", sa.String(), server_default="uncontacted"),
        sa.Column("provenance", sa.JSON(), nullable=True),
        sa.Column("messaging_angle", sa.String(), nullable=True),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("deal_room_id", "email", name="uq_deal_room_member_email"),
    )
    op.create_index("ix_bcm_deal_room", "buying_committee_members", ["deal_room_id"])
    op.create_index("ix_bcm_tenant", "buying_committee_members", ["tenant_id"])
    op.create_index("ix_bcm_email", "buying_committee_members", ["email"])

    # 4. account_signals
    op.create_table(
        "account_signals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("deal_room_id", sa.String(), sa.ForeignKey("deal_rooms.id"), nullable=False),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("signal_type", sa.String(), nullable=False),
        sa.Column("headline", sa.String(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("evidence_url", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="1.0"),
        sa.Column("decay_half_life_days", sa.Integer(), server_default="14"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_account_signals_deal_room", "account_signals", ["deal_room_id"])
    op.create_index("ix_account_signals_tenant", "account_signals", ["tenant_id"])
    op.create_index("ix_account_signals_type", "account_signals", ["signal_type"])

    # 5. deal_objections
    op.create_table(
        "deal_objections",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("deal_room_id", sa.String(), sa.ForeignKey("deal_rooms.id"), nullable=False),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("committee_member_id", sa.String(), sa.ForeignKey("buying_committee_members.id"), nullable=True),
        sa.Column("objection_category", sa.String(), nullable=False),
        sa.Column("prospect_statement", sa.Text(), nullable=False),
        sa.Column("applied_counter_argument", sa.Text(), nullable=True),
        sa.Column("provenance_playbook_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_deal_objections_deal_room", "deal_objections", ["deal_room_id"])
    op.create_index("ix_deal_objections_tenant", "deal_objections", ["tenant_id"])

    # 6. deal_activities
    op.create_table(
        "deal_activities",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("deal_room_id", sa.String(), sa.ForeignKey("deal_rooms.id"), nullable=False),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("committee_member_id", sa.String(), sa.ForeignKey("buying_committee_members.id"), nullable=True),
        sa.Column("activity_type", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=True),
        sa.Column("direction", sa.String(), server_default="outbound"),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_deal_activities_deal_room", "deal_activities", ["deal_room_id"])
    op.create_index("ix_deal_activities_tenant", "deal_activities", ["tenant_id"])
    op.create_index("ix_deal_activities_type", "deal_activities", ["activity_type"])

    # 7. evidence_records
    op.create_table(
        "evidence_records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("location_reference", sa.String(), nullable=True),
        sa.Column("raw_snippet", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0"),
        sa.Column("authority_score", sa.Float(), server_default="1.0"),
        sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_valid", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_evidence_records_tenant", "evidence_records", ["tenant_id"])

    # 8. company_sales_contexts
    op.create_table(
        "company_sales_contexts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("company_overview", sa.JSON(), nullable=True),
        sa.Column("products_catalog", sa.JSON(), nullable=True),
        sa.Column("services_catalog", sa.JSON(), nullable=True),
        sa.Column("icp_definitions", sa.JSON(), nullable=True),
        sa.Column("buyer_personas", sa.JSON(), nullable=True),
        sa.Column("proof_points", sa.JSON(), nullable=True),
        sa.Column("competitor_battlecards", sa.JSON(), nullable=True),
        sa.Column("objection_playbook", sa.JSON(), nullable=True),
        sa.Column("policies", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_csc_tenant", "company_sales_contexts", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("company_sales_contexts")
    op.drop_table("evidence_records")
    op.drop_table("deal_activities")
    op.drop_table("deal_objections")
    op.drop_table("account_signals")
    op.drop_table("buying_committee_members")
    op.drop_table("deal_rooms")
    op.drop_table("suppression_records")
