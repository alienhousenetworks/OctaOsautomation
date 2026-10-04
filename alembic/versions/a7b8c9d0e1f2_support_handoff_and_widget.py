"""Add support handoff, widget fields, and agent presence

Revision ID: a7b8c9d0e1f2
Revises: e5f6a7b8c9d0
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa


revision = "a7b8c9d0e1f2"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add support handoff and widget session columns to tickets
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.add_column(sa.Column("customer_name", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("customer_email", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("customer_phone", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("claimed_by", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("session_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("mode", sa.String(), nullable=True, server_default="ai"))
        batch_op.add_column(sa.Column("extra_data", sa.JSON(), nullable=True, server_default="{}"))
        batch_op.create_index("ix_tickets_session_id", ["session_id"], unique=False)

    # Create support_agent_presences table
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "support_agent_presences" not in inspector.get_table_names():
        op.create_table(
            "support_agent_presences",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("user_name", sa.String(), nullable=True),
            sa.Column("is_online", sa.Boolean(), server_default=sa.true(), nullable=True),
            sa.Column("last_heartbeat", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("support_agent_presences")
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_index("ix_tickets_session_id")
        batch_op.drop_column("extra_data")
        batch_op.drop_column("mode")
        batch_op.drop_column("session_id")
        batch_op.drop_column("resolved_at")
        batch_op.drop_column("claimed_at")
        batch_op.drop_column("claimed_by")
        batch_op.drop_column("customer_phone")
        batch_op.drop_column("customer_email")
        batch_op.drop_column("customer_name")
