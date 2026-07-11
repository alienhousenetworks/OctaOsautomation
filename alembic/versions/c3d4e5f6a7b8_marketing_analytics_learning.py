"""marketing analytics + learning tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content_posts", sa.Column("external_post_id", sa.String(), nullable=True))
    op.add_column("content_posts", sa.Column("external_url", sa.String(), nullable=True))
    op.add_column("content_posts", sa.Column("impressions", sa.Float(), server_default="0"))
    op.add_column("content_posts", sa.Column("reach", sa.Float(), server_default="0"))
    op.add_column("content_posts", sa.Column("engagement", sa.Float(), server_default="0"))
    op.add_column("content_posts", sa.Column("likes", sa.Float(), server_default="0"))
    op.add_column("content_posts", sa.Column("comments", sa.Float(), server_default="0"))
    op.add_column("content_posts", sa.Column("shares", sa.Float(), server_default="0"))
    op.add_column("content_posts", sa.Column("clicks", sa.Float(), server_default="0"))
    op.add_column("content_posts", sa.Column("ctr", sa.Float(), server_default="0"))
    op.add_column("content_posts", sa.Column("engagement_rate", sa.Float(), server_default="0"))
    op.add_column("content_posts", sa.Column("performance_score", sa.Float(), server_default="0"))
    op.add_column("content_posts", sa.Column("insights_raw", sa.JSON(), nullable=True))
    op.add_column("content_posts", sa.Column("insights_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("content_posts", sa.Column("learning_tags", sa.JSON(), nullable=True))
    op.create_index("ix_content_posts_external_post_id", "content_posts", ["external_post_id"])

    op.create_table(
        "marketing_insight_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("post_id", sa.String(), sa.ForeignKey("content_posts.id"), nullable=False),
        sa.Column("platform", sa.String(), nullable=True),
        sa.Column("impressions", sa.Float(), server_default="0"),
        sa.Column("reach", sa.Float(), server_default="0"),
        sa.Column("engagement", sa.Float(), server_default="0"),
        sa.Column("likes", sa.Float(), server_default="0"),
        sa.Column("comments", sa.Float(), server_default="0"),
        sa.Column("shares", sa.Float(), server_default="0"),
        sa.Column("clicks", sa.Float(), server_default="0"),
        sa.Column("ctr", sa.Float(), server_default="0"),
        sa.Column("engagement_rate", sa.Float(), server_default="0"),
        sa.Column("raw", sa.JSON()),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_mkt_snap_tenant", "marketing_insight_snapshots", ["tenant_id"])
    op.create_index("ix_mkt_snap_post", "marketing_insight_snapshots", ["post_id"])

    op.create_table(
        "marketing_learning_patterns",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("platform", sa.String(), nullable=True),
        sa.Column("pattern_type", sa.String(), nullable=False),
        sa.Column("pattern_key", sa.String(), nullable=False),
        sa.Column("sample_count", sa.Integer(), server_default="0"),
        sa.Column("avg_engagement_rate", sa.Float(), server_default="0"),
        sa.Column("avg_ctr", sa.Float(), server_default="0"),
        sa.Column("avg_performance_score", sa.Float(), server_default="0"),
        sa.Column("weight", sa.Float(), server_default="0"),
        sa.Column("examples", sa.JSON()),
        sa.Column("banned", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_mkt_learn_tenant", "marketing_learning_patterns", ["tenant_id"])
    op.create_index("ix_mkt_learn_platform", "marketing_learning_patterns", ["platform"])


def downgrade() -> None:
    op.drop_table("marketing_learning_patterns")
    op.drop_table("marketing_insight_snapshots")
    for col in [
        "learning_tags",
        "insights_synced_at",
        "insights_raw",
        "performance_score",
        "engagement_rate",
        "ctr",
        "clicks",
        "shares",
        "comments",
        "likes",
        "engagement",
        "reach",
        "impressions",
        "external_url",
        "external_post_id",
    ]:
        op.drop_column("content_posts", col)
