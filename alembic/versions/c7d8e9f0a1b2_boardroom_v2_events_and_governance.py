"""Boardroom v2 events, evidence, governance actions and meeting metrics

Revision ID: c7d8e9f0a1b2
Revises: b8c9d0e1f2a3
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa


revision = "c7d8e9f0a1b2"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Add new columns to agent_meetings
    if "agent_meetings" in existing_tables:
        existing_cols = {col["name"] for col in inspector.get_columns("agent_meetings")}
        with op.batch_alter_table("agent_meetings") as batch_op:
            if "current_phase" not in existing_cols:
                batch_op.add_column(sa.Column("current_phase", sa.String(), nullable=True))
            if "started_at" not in existing_cols:
                batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
            if "finished_at" not in existing_cols:
                batch_op.add_column(sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
            if "total_tokens" not in existing_cols:
                batch_op.add_column(sa.Column("total_tokens", sa.Integer(), nullable=True, server_default="0"))
            if "total_cost_usd" not in existing_cols:
                batch_op.add_column(sa.Column("total_cost_usd", sa.Float(), nullable=True, server_default="0.0"))
            if "failure_reason" not in existing_cols:
                batch_op.add_column(sa.Column("failure_reason", sa.Text(), nullable=True))

    # 2. Create meeting_events
    if "meeting_events" not in existing_tables:
        op.create_table(
            "meeting_events",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("meeting_id", sa.String(), sa.ForeignKey("agent_meetings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("phase", sa.String(), nullable=True),
            sa.Column("actor", sa.String(), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_meeting_events_meeting_id", "meeting_events", ["meeting_id"])

    # 3. Create meeting_evidence
    if "meeting_evidence" not in existing_tables:
        op.create_table(
            "meeting_evidence",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("meeting_id", sa.String(), sa.ForeignKey("agent_meetings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_ref", sa.String(), nullable=False),
            sa.Column("source_type", sa.String(), nullable=False),
            sa.Column("trust_score", sa.Integer(), nullable=True),
            sa.Column("freshness_score", sa.Integer(), nullable=True),
            sa.Column("reliability_score", sa.Integer(), nullable=True),
            sa.Column("completeness_score", sa.Integer(), nullable=True),
            sa.Column("excerpt", sa.Text(), nullable=True),
            sa.Column("redacted", sa.Boolean(), default=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_meeting_evidence_meeting_id", "meeting_evidence", ["meeting_id"])

    # 4. Create meeting_actions
    if "meeting_actions" not in existing_tables:
        op.create_table(
            "meeting_actions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("meeting_id", sa.String(), sa.ForeignKey("agent_meetings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("action_type", sa.String(), nullable=False),
            sa.Column("assigned_to", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("risk_tier", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("idempotency_key", sa.String(), nullable=True, unique=True),
            sa.Column("approved_by", sa.String(), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejected_by", sa.String(), nullable=True),
            sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("evidence_ids", sa.JSON(), nullable=True, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index("ix_meeting_actions_meeting_id", "meeting_actions", ["meeting_id"])


def downgrade() -> None:
    op.drop_table("meeting_actions")
    op.drop_table("meeting_evidence")
    op.drop_table("meeting_events")
    with op.batch_alter_table("agent_meetings") as batch_op:
        batch_op.drop_column("failure_reason")
        batch_op.drop_column("total_cost_usd")
        batch_op.drop_column("total_tokens")
        batch_op.drop_column("finished_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("current_phase")
