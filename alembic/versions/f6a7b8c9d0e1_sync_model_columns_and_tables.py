"""Add columns and tables that the models expect but migrations never created.

Revision ID: f6a7b8c9d0e1
Revises: d4e5f6a7b8c9
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

NEW_TABLES = [
    "global_failure_patterns",
    "global_skill_packages",
    "global_strategy_registry",
    "cross_agent_context",
    "decision_records",
    "global_memory",
    "manager_feedback",
    "negative_pattern_memory",
    "strategy_performance",
    "video_projects",
    "video_assets",
    "video_renders",
    "episodic_memory",
]


def upgrade() -> None:
    op.add_column("api_credentials", sa.Column("is_main", sa.Boolean(), nullable=True))
    op.add_column("business_profiles", sa.Column("extra_context", sa.Text(), nullable=True))
    op.add_column("content_posts", sa.Column("remotion_prompt", sa.Text(), nullable=True))
    op.add_column("content_posts", sa.Column("remotion_prompt_enabled", sa.Boolean(), nullable=True))
    op.add_column("content_posts", sa.Column("remotion_provider", sa.String(), nullable=True))
    op.add_column("content_posts", sa.Column("remotion_model", sa.String(), nullable=True))

    from app.models.base import Base
    import app.models.learning  # noqa: F401
    import app.models.memory  # noqa: F401
    import app.models.video  # noqa: F401

    bind = op.get_bind()
    names = list(NEW_TABLES)
    # episodic_memory stores embeddings with pgvector. Skip it when the extension
    # is not installed so the rest of the schema can still be created.
    try:
        bind.execute(sa.text("SAVEPOINT pgvector_ext"))
        bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        bind.execute(sa.text("RELEASE SAVEPOINT pgvector_ext"))
    except Exception:
        bind.execute(sa.text("ROLLBACK TO SAVEPOINT pgvector_ext"))
        names = [name for name in names if name != "episodic_memory"]

    tables = [Base.metadata.tables[name] for name in names if name in Base.metadata.tables]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for name in reversed(NEW_TABLES):
        if name in existing:
            op.drop_table(name)
    op.drop_column("content_posts", "remotion_model")
    op.drop_column("content_posts", "remotion_provider")
    op.drop_column("content_posts", "remotion_prompt_enabled")
    op.drop_column("content_posts", "remotion_prompt")
    op.drop_column("business_profiles", "extra_context")
    op.drop_column("api_credentials", "is_main")
