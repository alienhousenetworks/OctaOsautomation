"""razorpay payment fields and payment_orders

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-11
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_subscriptions", sa.Column("razorpay_customer_id", sa.String(), nullable=True))
    op.add_column("tenant_subscriptions", sa.Column("razorpay_subscription_id", sa.String(), nullable=True))
    op.add_column("tenant_subscriptions", sa.Column("razorpay_last_payment_id", sa.String(), nullable=True))
    op.add_column("tenant_subscriptions", sa.Column("razorpay_last_order_id", sa.String(), nullable=True))

    op.create_table(
        "payment_orders",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("plan_code", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), server_default="razorpay"),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), server_default="INR"),
        sa.Column("status", sa.String(), server_default="created"),
        sa.Column("razorpay_order_id", sa.String(), nullable=True),
        sa.Column("razorpay_payment_id", sa.String(), nullable=True),
        sa.Column("razorpay_signature", sa.String(), nullable=True),
        sa.Column("receipt", sa.String(), nullable=True),
        sa.Column("notes", sa.JSON()),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_payment_orders_tenant_id", "payment_orders", ["tenant_id"])
    op.create_index("ix_payment_orders_razorpay_order_id", "payment_orders", ["razorpay_order_id"], unique=True)
    op.create_index("ix_payment_orders_razorpay_payment_id", "payment_orders", ["razorpay_payment_id"])


def downgrade() -> None:
    op.drop_table("payment_orders")
    op.drop_column("tenant_subscriptions", "razorpay_last_order_id")
    op.drop_column("tenant_subscriptions", "razorpay_last_payment_id")
    op.drop_column("tenant_subscriptions", "razorpay_subscription_id")
    op.drop_column("tenant_subscriptions", "razorpay_customer_id")
