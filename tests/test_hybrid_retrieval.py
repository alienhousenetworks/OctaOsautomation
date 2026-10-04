"""Tests for Hybrid RAG Engine, RRF scoring, and non-dumping prompt injection."""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base, Tenant
from app.models.agents import KnowledgeDocument
from app.models.enterprise import KnowledgeChunk
from app.services.rag.hybrid_engine import HybridRAGEngine
from app.services.agents.base import BaseAgent
from app.services.llm_gateway import LLMGateway


@pytest.fixture
def hybrid_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    tenant = Tenant(id="tenant-hybrid-1", name="Acme Corp", company_website="https://acme.com")
    session.add(tenant)
    session.commit()

    yield session
    session.close()


def test_sparse_keyword_retrieval_and_citations(hybrid_db):
    tenant_id = "tenant-hybrid-1"
    engine = HybridRAGEngine(hybrid_db, tenant_id)

    # Seed knowledge chunks
    c1 = KnowledgeChunk(
        id="chunk-11111111",
        tenant_id=tenant_id,
        document_id="doc-1",
        title="Enterprise Pricing Guide",
        content="Our enterprise tier costs $999 per month with unlimited API calls and dedicated support.",
        page_start=4,
        page_end=4,
        source_url="https://acme.com/pricing",
        embedding_hint="pricing cost subscription plans tiers",
        is_active=True,
        version=1,
    )
    c2 = KnowledgeChunk(
        id="chunk-22222222",
        tenant_id=tenant_id,
        document_id="doc-2",
        title="Security & Compliance",
        content="We are SOC2 Type II certified and adhere to GDPR data protection standards.",
        page_start=12,
        page_end=14,
        source_url="https://acme.com/security",
        embedding_hint="security compliance soc2 gdpr audits",
        is_active=True,
        version=1,
    )
    c3 = KnowledgeChunk(
        id="chunk-33333333",
        tenant_id=tenant_id,
        document_id="doc-3",
        title="Inactive Document",
        content="Old pricing $500 per month.",
        is_active=False,
        version=1,
    )
    hybrid_db.add_all([c1, c2, c3])
    hybrid_db.commit()

    # Query for pricing
    results = engine.retrieve("What does the enterprise tier cost?", top_k=5)
    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk-11111111"
    assert "Enterprise Pricing Guide" in results[0]["citation"]
    assert "p.4" in results[0]["citation"]
    assert "https://acme.com/pricing" in results[0]["citation"]
    assert results[0]["score"] > 0

    # Query for security
    sec_results = engine.retrieve("Tell me about GDPR and SOC2 compliance", top_k=5)
    assert len(sec_results) == 1
    assert sec_results[0]["chunk_id"] == "chunk-22222222"
    assert "p.12" in sec_results[0]["citation"]


def test_reciprocal_rank_fusion_scoring(hybrid_db):
    tenant_id = "tenant-hybrid-1"
    engine = HybridRAGEngine(hybrid_db, tenant_id)

    # Add two chunks
    c1 = KnowledgeChunk(
        id="chunk-alpha",
        tenant_id=tenant_id,
        document_id="doc-a",
        title="Alpha Product",
        content="Alpha provides fast automated outbound prospecting campaigns.",
        is_active=True,
        version=1,
    )
    c2 = KnowledgeChunk(
        id="chunk-beta",
        tenant_id=tenant_id,
        document_id="doc-b",
        title="Beta Analytics",
        content="Beta provides detailed sales analytics and revenue forecasting.",
        is_active=True,
        version=1,
    )
    hybrid_db.add_all([c1, c2])
    hybrid_db.commit()

    # Sparse query matching both, but alpha higher
    results = engine.retrieve("automated outbound prospecting campaigns", top_k=2)
    assert len(results) >= 1
    assert results[0]["chunk_id"] == "chunk-alpha"
    # RRF formula: 1 / (60 + 1) = 0.01639... -> 0.0164
    assert results[0]["score"] == 0.0164


def test_assemble_context(hybrid_db):
    tenant_id = "tenant-hybrid-1"
    engine = HybridRAGEngine(hybrid_db, tenant_id)

    c = KnowledgeChunk(
        id="chunk-refund",
        tenant_id=tenant_id,
        document_id="doc-refund",
        title="Refund Policy",
        content="Customers can request a full refund within 30 days of purchase.",
        page_start=1,
        source_url="https://acme.com/refund",
        is_active=True,
        version=1,
    )
    hybrid_db.add(c)
    hybrid_db.commit()

    ctx = engine.assemble_context("What is the refund policy?")
    assert ctx["mode"] == "grounded"
    assert ctx["hits"] == 1
    assert "Refund Policy" in ctx["context"]
    assert len(ctx["citations"]) == 1

    # Empty query fallback
    empty_ctx = engine.assemble_context("Unrelated topic that definitely has no hits xyz123")
    assert empty_ctx["mode"] == "empty"
    assert empty_ctx["hits"] == 0


def test_pinned_directives_vs_selective_retrieval_in_agent(hybrid_db):
    tenant_id = "tenant-hybrid-1"

    # Seed 1 pinned directive
    pinned = KnowledgeDocument(
        id="pinned-1",
        tenant_id=tenant_id,
        doc_type="Prompt Directives",
        department="General",
        content="Always speak in a professional, polite, and confident tone. Never disclose competitor names.",
        is_active=True,
    )

    # Seed 1 regular document that should NOT be dumped entirely unless retrieved via chunks
    regular_doc = KnowledgeDocument(
        id="regular-1",
        tenant_id=tenant_id,
        doc_type="Internal Policy",
        department="HR",
        content="Office hours are from 9 AM to 5 PM Monday through Friday. Lunch break is 1 hour.",
        is_active=True,
    )

    # Seed a relevant knowledge chunk for sales
    chunk = KnowledgeChunk(
        id="sales-chunk-1",
        tenant_id=tenant_id,
        document_id="sales-doc",
        title="Sales Playbook",
        department="Sales",
        content="Highlight our 99.99% uptime guarantee and fast 24/7 onboarding.",
        is_active=True,
        version=1,
    )

    hybrid_db.add_all([pinned, regular_doc, chunk])
    hybrid_db.commit()

    agent = BaseAgent(hybrid_db, tenant_id, "SalesBot", department="Sales")
    context = agent.get_knowledge_context("sales onboarding guarantee", department="Sales")

    # 1. Pinned directive MUST be present
    assert "Always speak in a professional, polite, and confident tone" in context
    assert "[Prompt Directives]" in context

    # 2. Retrieved sales chunk MUST be present
    assert "Sales Playbook" in context
    assert "99.99% uptime guarantee" in context

    # 3. Irrelevant HR handbook MUST NOT be dumped into the context
    assert "Office hours are from 9 AM to 5 PM" not in context
    assert "Lunch break is 1 hour" not in context
