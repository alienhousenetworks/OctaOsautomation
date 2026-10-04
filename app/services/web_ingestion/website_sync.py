"""Website Knowledge Synchronization Service.

Orchestrates multi-page website crawls, content change detection (hashes),
versioned chunk replacement, and one-click company website synchronization.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.models.base import Tenant
from app.models.agents import KnowledgeDocument, KnowledgeSource
from app.models.enterprise import KnowledgeChunk
from app.services.document_processing.pipeline import DocumentProcessingPipeline
from app.services.web_ingestion.firecrawl_client import FirecrawlClient

logger = logging.getLogger(__name__)


class WebsiteSyncService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.pipeline = DocumentProcessingPipeline(db, tenant_id)

    async def sync_knowledge_source(self, source_id: str) -> Dict[str, Any]:
        """Execute crawl job for a registered KnowledgeSource and update the KB."""
        source = (
            self.db.query(KnowledgeSource)
            .filter(KnowledgeSource.id == source_id, KnowledgeSource.tenant_id == self.tenant_id)
            .first()
        )
        if not source:
            raise ValueError(f"Knowledge source '{source_id}' not found.")

        source.last_status = "running"
        source.last_error = None
        self.db.commit()

        try:
            client = FirecrawlClient(db=self.db, tenant_id=self.tenant_id)
            pages = client.crawl_website(
                url=source.url,
                max_pages=source.max_pages or 50,
                crawl_depth=source.crawl_depth or 2,
                include_paths=source.include_paths or [],
                exclude_paths=source.exclude_paths or [],
            )

            created_count = 0
            updated_count = 0
            skipped_count = 0
            crawled_urls = set()

            for page in pages:
                url = page["url"]
                crawled_urls.add(url)
                title = page.get("title") or url
                markdown = page.get("markdown", "")

                result = self.pipeline.process_web_content(
                    url=url,
                    content=markdown,
                    title=title,
                    department="General",
                    category="Company Website" if source.kind == "company_site" else "Web Source",
                )

                content_hash = result["content_hash"]
                chunks = result.get("chunks", [])

                # Check if this URL is already stored
                existing_doc = (
                    self.db.query(KnowledgeDocument)
                    .filter(
                        KnowledgeDocument.tenant_id == self.tenant_id,
                        KnowledgeDocument.source_url == url,
                    )
                    .first()
                )

                if existing_doc:
                    # Check if content changed
                    if existing_doc.content_hash == content_hash and existing_doc.is_active:
                        skipped_count += 1
                        continue

                    # Content changed: update document & increment chunk version
                    existing_doc.content = f"Source URL: {url}\nTitle: {title}\n\n{result['content']}"
                    existing_doc.content_hash = content_hash
                    existing_doc.quality_score = result.get("quality_score", 1.0)
                    existing_doc.source_id = source.id
                    existing_doc.is_active = True
                    existing_doc.updated_at = func.now()

                    # Deactivate old chunks
                    old_chunks = (
                        self.db.query(KnowledgeChunk)
                        .filter(
                            KnowledgeChunk.tenant_id == self.tenant_id,
                            KnowledgeChunk.document_id == existing_doc.id,
                        )
                        .all()
                    )
                    max_version = max([c.version for c in old_chunks], default=0)
                    for oc in old_chunks:
                        oc.is_active = False

                    # Insert new chunks
                    for c in chunks:
                        self.db.add(
                            KnowledgeChunk(
                                tenant_id=self.tenant_id,
                                document_id=existing_doc.id,
                                department=existing_doc.department,
                                version=max_version + 1,
                                title=f"{title} #{c['chunk_index']}",
                                content=c["text"],
                                embedding_hint=c["text"][:100],
                                page_start=c.get("page_start", 1),
                                page_end=c.get("page_end", 1),
                                section_title=c.get("section_title", "General"),
                                source_url=url,
                                content_hash=c.get("content_hash"),
                                is_active=True,
                            )
                        )
                    updated_count += 1
                else:
                    # New page: create KnowledgeDocument and initial chunks
                    doc = KnowledgeDocument(
                        tenant_id=self.tenant_id,
                        department="General",
                        doc_type="Company Website" if source.kind == "company_site" else "Web Source",
                        source_type="web",
                        source_url=url,
                        source_id=source.id,
                        content_hash=content_hash,
                        content=f"Source URL: {url}\nTitle: {title}\n\n{result['content']}",
                        extraction_method="firecrawl_web",
                        quality_score=result.get("quality_score", 1.0),
                        is_active=True,
                    )
                    self.db.add(doc)
                    self.db.flush()

                    for c in chunks:
                        self.db.add(
                            KnowledgeChunk(
                                tenant_id=self.tenant_id,
                                document_id=doc.id,
                                department="General",
                                version=1,
                                title=f"{title} #{c['chunk_index']}",
                                content=c["text"],
                                embedding_hint=c["text"][:100],
                                page_start=c.get("page_start", 1),
                                page_end=c.get("page_end", 1),
                                section_title=c.get("section_title", "General"),
                                source_url=url,
                                content_hash=c.get("content_hash"),
                                is_active=True,
                            )
                        )
                    created_count += 1

                self.db.commit()

            # Mark removed pages inactive
            removed_docs = (
                self.db.query(KnowledgeDocument)
                .filter(
                    KnowledgeDocument.tenant_id == self.tenant_id,
                    KnowledgeDocument.source_id == source.id,
                    KnowledgeDocument.source_url.notin_(list(crawled_urls)),
                    KnowledgeDocument.is_active == True,
                )
                .all()
            )
            for rd in removed_docs:
                rd.is_active = False
                for rc in self.db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == rd.id).all():
                    rc.is_active = False
            self.db.commit()

            # Update source stats
            total_active = (
                self.db.query(KnowledgeDocument)
                .filter(
                    KnowledgeDocument.tenant_id == self.tenant_id,
                    KnowledgeDocument.source_id == source.id,
                    KnowledgeDocument.is_active == True,
                )
                .count()
            )
            source.pages_indexed = total_active
            source.last_status = "completed"
            source.last_crawled_at = datetime.now(timezone.utc)
            self.db.commit()

            # Materialize sales context in background
            try:
                from app.services.sales_os.context_materializer import SalesContextMaterializer
                materializer = SalesContextMaterializer(self.db, self.tenant_id)
                await materializer.materialize_context()
            except Exception as me:
                logger.debug(f"Sales context materializer skipped after sync: {me}")

            return {
                "source_id": source.id,
                "url": source.url,
                "status": "completed",
                "total_pages_crawled": len(pages),
                "created": created_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "removed": len(removed_docs),
                "active_pages": total_active,
            }

        except Exception as e:
            logger.error(f"Sync failed for source '{source_id}': {e}")
            source.last_status = "failed"
            source.last_error = str(e)
            self.db.commit()
            raise

    async def sync_company_website(self, max_pages: int = 50, crawl_depth: int = 2) -> Dict[str, Any]:
        """One-click synchronization of the tenant's registered company website."""
        tenant = self.db.query(Tenant).filter(Tenant.id == self.tenant_id).first()
        if not tenant or not tenant.company_website:
            raise ValueError(
                "Company website is not configured. Please add your website URL under Settings → Company Profile."
            )

        website_url = tenant.company_website.strip()
        if not website_url.startswith(("http://", "https://")):
            website_url = f"https://{website_url}"

        # Find or create company_site KnowledgeSource
        source = (
            self.db.query(KnowledgeSource)
            .filter(
                KnowledgeSource.tenant_id == self.tenant_id,
                KnowledgeSource.kind == "company_site",
            )
            .first()
        )

        if not source:
            source = KnowledgeSource(
                tenant_id=self.tenant_id,
                url=website_url,
                kind="company_site",
                max_pages=max_pages,
                crawl_depth=crawl_depth,
                schedule="daily",
                last_status="idle",
            )
            self.db.add(source)
            self.db.commit()
            self.db.refresh(source)
        else:
            source.url = website_url
            source.max_pages = max_pages
            source.crawl_depth = crawl_depth
            self.db.commit()

        return await self.sync_knowledge_source(source.id)
