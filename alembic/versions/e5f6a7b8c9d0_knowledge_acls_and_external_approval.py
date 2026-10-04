"""Knowledge ACLs and external approval fields

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa


revision = "e5f6a7b8c9d0"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add classification and access control fields to knowledge_documents
    with op.batch_alter_table("knowledge_documents") as batch_op:
        batch_op.add_column(
            sa.Column("classification", sa.String(), nullable=False, server_default="internal")
        )
        batch_op.add_column(
            sa.Column("approved_for_external_use", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("source_authority", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.add_column(
            sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("metadata_json", sa.JSON(), nullable=True, server_default="{}")
        )
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )


def downgrade() -> None:
    with op.batch_alter_table("knowledge_documents") as batch_op:
        batch_op.drop_column("is_active")
        batch_op.drop_column("metadata_json")
        batch_op.drop_column("valid_until")
        batch_op.drop_column("source_authority")
        batch_op.drop_column("approved_for_external_use")
        batch_op.drop_column("classification")
