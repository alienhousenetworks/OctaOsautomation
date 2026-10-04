"""Knowledge ingestion v2: website sources, document provenance, and vector embeddings

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect_name = bind.dialect.name
    existing_tables = set(inspector.get_table_names())

    # 1. Create knowledge_sources table
    if "knowledge_sources" not in existing_tables:
        op.create_table(
            "knowledge_sources",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("url", sa.String(), nullable=False),
            sa.Column("kind", sa.String(), server_default="web", nullable=False),
            sa.Column("max_pages", sa.Integer(), server_default="50", nullable=True),
            sa.Column("crawl_depth", sa.Integer(), server_default="2", nullable=True),
            sa.Column("include_paths", sa.JSON(), server_default="[]", nullable=True),
            sa.Column("exclude_paths", sa.JSON(), server_default="[]", nullable=True),
            sa.Column("schedule", sa.String(), server_default="manual", nullable=True),
            sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_status", sa.String(), server_default="idle", nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("pages_indexed", sa.Integer(), server_default="0", nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        )

    # 2. Add provenance and web columns to knowledge_documents
    doc_cols = {col["name"] for col in inspector.get_columns("knowledge_documents")}
    with op.batch_alter_table("knowledge_documents") as batch_op:
        if "source_type" not in doc_cols:
            batch_op.add_column(sa.Column("source_type", sa.String(), server_default="text", nullable=True))
        if "source_url" not in doc_cols:
            batch_op.add_column(sa.Column("source_url", sa.String(), nullable=True))
        if "content_hash" not in doc_cols:
            batch_op.add_column(sa.Column("content_hash", sa.String(), nullable=True))
        if "source_id" not in doc_cols:
            batch_op.add_column(sa.Column("source_id", sa.String(), nullable=True))
        if "extraction_method" not in doc_cols:
            batch_op.add_column(sa.Column("extraction_method", sa.String(), nullable=True))
        if "quality_score" not in doc_cols:
            batch_op.add_column(sa.Column("quality_score", sa.Float(), server_default="1.0", nullable=True))
        if "updated_at" not in doc_cols:
            batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True))

    # 3. Add columns and pgvector embeddings to knowledge_chunks
    chunk_cols = {col["name"] for col in inspector.get_columns("knowledge_chunks")}
    with op.batch_alter_table("knowledge_chunks") as batch_op:
        if "page_start" not in chunk_cols:
            batch_op.add_column(sa.Column("page_start", sa.Integer(), nullable=True))
        if "page_end" not in chunk_cols:
            batch_op.add_column(sa.Column("page_end", sa.Integer(), nullable=True))
        if "section_title" not in chunk_cols:
            batch_op.add_column(sa.Column("section_title", sa.String(), nullable=True))
        if "source_url" not in chunk_cols:
            batch_op.add_column(sa.Column("source_url", sa.String(), nullable=True))
        if "content_hash" not in chunk_cols:
            batch_op.add_column(sa.Column("content_hash", sa.String(), nullable=True))

        # Vector column: only for postgres with extension available
        if "embedding" not in chunk_cols and dialect_name == "postgresql":
            try:
                bind.execute(sa.text("SAVEPOINT pgvector_ext_chunk"))
                bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
                bind.execute(sa.text("RELEASE SAVEPOINT pgvector_ext_chunk"))
                batch_op.add_column(sa.Column("embedding", Vector(1536), nullable=True))
            except Exception:
                bind.execute(sa.text("ROLLBACK TO SAVEPOINT pgvector_ext_chunk"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "knowledge_chunks" in existing_tables:
        chunk_cols = {col["name"] for col in inspector.get_columns("knowledge_chunks")}
        with op.batch_alter_table("knowledge_chunks") as batch_op:
            if "embedding" in chunk_cols:
                batch_op.drop_column("embedding")
            if "content_hash" in chunk_cols:
                batch_op.drop_column("content_hash")
            if "source_url" in chunk_cols:
                batch_op.drop_column("source_url")
            if "section_title" in chunk_cols:
                batch_op.drop_column("section_title")
            if "page_end" in chunk_cols:
                batch_op.drop_column("page_end")
            if "page_start" in chunk_cols:
                batch_op.drop_column("page_start")

    if "knowledge_documents" in existing_tables:
        doc_cols = {col["name"] for col in inspector.get_columns("knowledge_documents")}
        with op.batch_alter_table("knowledge_documents") as batch_op:
            if "updated_at" in doc_cols:
                batch_op.drop_column("updated_at")
            if "quality_score" in doc_cols:
                batch_op.drop_column("quality_score")
            if "extraction_method" in doc_cols:
                batch_op.drop_column("extraction_method")
            if "source_id" in doc_cols:
                batch_op.drop_column("source_id")
            if "content_hash" in doc_cols:
                batch_op.drop_column("content_hash")
            if "source_url" in doc_cols:
                batch_op.drop_column("source_url")
            if "source_type" in doc_cols:
                batch_op.drop_column("source_type")

    if "knowledge_sources" in existing_tables:
        op.drop_table("knowledge_sources")
