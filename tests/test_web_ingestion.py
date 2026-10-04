"""Tests for Firecrawl web client, SSRF protection, and website synchronization."""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base, Tenant
from app.models.agents import KnowledgeDocument, KnowledgeSource
from app.models.enterprise import KnowledgeChunk
from app.services.web_ingestion.firecrawl_client import validate_target_url, FirecrawlClient
from app.services.web_ingestion.website_sync import WebsiteSyncService


def test_ssrf_protection():
    # Loopback targets
    with pytest.raises(ValueError, match="internal loopback"):
        validate_target_url("http://localhost:8000/secret")
    with pytest.raises(ValueError, match="internal loopback"):
        validate_target_url("http://127.0.0.1:5432")

    # AWS metadata service
    with pytest.raises(ValueError, match="metadata"):
        validate_target_url("http://169.254.169.254/latest/meta-data/")

    # Invalid URL scheme
    with pytest.raises(ValueError):
        validate_target_url("file:///etc/passwd")

    # Valid external URL
    safe = validate_target_url("https://docs.github.com/en")
    assert safe == "https://docs.github.com/en"

    # Adds https if missing
    safe_added = validate_target_url("github.com/pricing")
    assert safe_added == "https://github.com/pricing"


@pytest.fixture
def test_db(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-dummy-key")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed test tenant
    tenant = Tenant(id="test-tenant-1", name="Acme Corp", company_website="https://acme.com")
    session.add(tenant)
    session.commit()

    yield session
    session.close()


@pytest.mark.asyncio
async def test_website_sync_change_detection(test_db):
    tenant_id = "test-tenant-1"

    # Create KnowledgeSource
    source = KnowledgeSource(
        id="src-1",
        tenant_id=tenant_id,
        url="https://acme.com",
        kind="web",
        schedule="manual",
    )
    test_db.add(source)
    test_db.commit()

    service = WebsiteSyncService(test_db, tenant_id)

    # Mock FirecrawlClient.crawl_website
    mock_pages_v1 = [
        {"url": "https://acme.com", "title": "Acme Home", "markdown": "# Welcome to Acme Corp\nEnterprise automation."},
        {"url": "https://acme.com/pricing", "title": "Acme Pricing", "markdown": "# Pricing\nStarter is $49/mo."},
    ]

    with patch.object(FirecrawlClient, "crawl_website", return_value=mock_pages_v1):
        res1 = await service.sync_knowledge_source("src-1")
        assert res1["created"] == 2
        assert res1["updated"] == 0
        assert res1["skipped"] == 0
        assert res1["active_pages"] == 2

    # Verify documents and chunks in DB
    docs = test_db.query(KnowledgeDocument).filter(KnowledgeDocument.tenant_id == tenant_id).all()
    assert len(docs) == 2
    chunks = test_db.query(KnowledgeChunk).filter(KnowledgeChunk.tenant_id == tenant_id, KnowledgeChunk.is_active == True).all()
    assert len(chunks) >= 2

    # Second crawl: identical content -> should skip all pages
    with patch.object(FirecrawlClient, "crawl_website", return_value=mock_pages_v1):
        res2 = await service.sync_knowledge_source("src-1")
        assert res2["skipped"] == 2
        assert res2["updated"] == 0
        assert res2["created"] == 0

    # Third crawl: pricing page updated ($49 -> $79), home page unchanged
    mock_pages_v2 = [
        {"url": "https://acme.com", "title": "Acme Home", "markdown": "# Welcome to Acme Corp\nEnterprise automation."},
        {"url": "https://acme.com/pricing", "title": "Acme Pricing", "markdown": "# Pricing\nStarter is now $79/mo with premium SLAs."},
    ]

    with patch.object(FirecrawlClient, "crawl_website", return_value=mock_pages_v2):
        res3 = await service.sync_knowledge_source("src-1")
        assert res3["skipped"] == 1
        assert res3["updated"] == 1
        assert res3["created"] == 0

    # Verify chunk version was incremented on the updated document
    pricing_doc = test_db.query(KnowledgeDocument).filter(KnowledgeDocument.source_url == "https://acme.com/pricing").first()
    active_pricing_chunks = test_db.query(KnowledgeChunk).filter(
        KnowledgeChunk.document_id == pricing_doc.id,
        KnowledgeChunk.is_active == True
    ).all()
    assert all(c.version == 2 for c in active_pricing_chunks)
    assert any("79/mo" in c.content for c in active_pricing_chunks)


@pytest.mark.asyncio
async def test_sync_company_website(test_db):
    tenant_id = "test-tenant-1"
    service = WebsiteSyncService(test_db, tenant_id)

    mock_pages = [
        {"url": "https://acme.com", "title": "Acme Official", "markdown": "# Acme Enterprise\nLeading AI Operations."}
    ]

    with patch.object(FirecrawlClient, "crawl_website", return_value=mock_pages):
        res = await service.sync_company_website()
        assert res["url"] == "https://acme.com"
        assert res["created"] == 1
        assert res["active_pages"] == 1

    source = test_db.query(KnowledgeSource).filter(KnowledgeSource.kind == "company_site").first()
    assert source is not None
    assert source.url == "https://acme.com"
