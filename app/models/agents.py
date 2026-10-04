from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, Integer, JSON, Float
from app.models.base import Base
import uuid
from sqlalchemy.sql import func

class KnowledgeSource(Base):
    """External or crawled knowledge sources (websites, company domains, sync jobs)."""
    __tablename__ = "knowledge_sources"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    url = Column(String, nullable=False)
    kind = Column(String, nullable=False, default="web") # web, company_site
    max_pages = Column(Integer, default=50)
    crawl_depth = Column(Integer, default=2)
    include_paths = Column(JSON, default=list) # e.g. ["/docs", "/pricing"]
    exclude_paths = Column(JSON, default=list) # e.g. ["/blog", "/tag"]
    schedule = Column(String, default="manual") # manual, daily, weekly
    last_crawled_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String, default="idle") # idle, running, completed, failed
    last_error = Column(Text, nullable=True)
    pages_indexed = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    department = Column(String, nullable=False) # e.g. "Marketing", "General", "HR", "Finance"
    doc_type = Column(String, nullable=False) # e.g. "Brand Guidelines", "FAQ", "Pricing"
    content = Column(Text, nullable=False)
    
    # Ingestion & Web metadata
    source_type = Column(String, default="text", nullable=True) # text, file, web
    source_url = Column(String, nullable=True)
    content_hash = Column(String, nullable=True, index=True)
    source_id = Column(String, ForeignKey("knowledge_sources.id"), nullable=True, index=True)
    extraction_method = Column(String, nullable=True)
    quality_score = Column(Float, nullable=True, default=1.0)

    # Workstream A: Security, Classification & Truth Management
    classification = Column(String, nullable=False, default="internal") # public, internal, confidential, restricted
    approved_for_external_use = Column(Boolean, nullable=False, default=False)
    source_authority = Column(Integer, nullable=False, default=1) # 1 (draft) to 5 (signed master truth)
    valid_until = Column(DateTime(timezone=True), nullable=True) # Expiry for seasonal rates or time-bound facts
    metadata_json = Column(JSON, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    agent_name = Column(String, nullable=False) # e.g. "Marketing AI", "Orchestrator AI"
    action = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="success") # success, pending, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
