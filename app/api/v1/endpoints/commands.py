from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Any, List, Optional
from pydantic import BaseModel
from app.api import deps
from app.core.rbac import Action, Resource, require_permission
from app.models.base import User
from app.services.agents.orchestrator import OrchestratorAgent
from app.models.base import APICredential
from app.models.verticals import ContentPost, Lead
import re
from app.models.agents import ActivityLog, KnowledgeDocument, KnowledgeSource
from app.models.enterprise import KnowledgeChunk
from app.core.security import encrypt_api_key

router = APIRouter()

class CommandRequest(BaseModel):
    prompt: str
    provider: Optional[str] = "anthropic"
    model: Optional[str] = None

class APIKeyUpdate(BaseModel):
    provider: str
    key: str

class KnowledgeDocCreate(BaseModel):
    department: str
    doc_type: str
    content: str

class WebCrawlRequest(BaseModel):
    url: str
    max_pages: Optional[int] = 50
    crawl_depth: Optional[int] = 2
    include_paths: Optional[List[str]] = None
    exclude_paths: Optional[List[str]] = None
    schedule: Optional[str] = "manual"

class CompanySyncRequest(BaseModel):
    max_pages: Optional[int] = 50
    crawl_depth: Optional[int] = 2

@router.post("/execute")
async def execute_command(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
    request: CommandRequest
) -> Any:
    from app.services.ai_gateway import ai_gateway
    from app.core.config import settings

    configured_ai_providers = ai_gateway._get_configured_providers(db, tenant_id)
    ai_mode = ai_gateway.get_tenant_ai_mode(db, tenant_id)

    # 1. Check if user has an active key either via BYOK or Inbuilt platform provider
    req_provider = request.provider or getattr(settings, "DEFAULT_AI_PROVIDER", "openrouter")
    has_valid_key = bool(ai_gateway._get_api_key(db, tenant_id, req_provider))
    if not has_valid_key:
        for p in configured_ai_providers:
            if ai_gateway._get_api_key(db, tenant_id, p):
                has_valid_key = True
                break

    # 2. If no key, intercept the prompt (allow pasting key)
    if not has_valid_key:
        # Check if the user is pasting a key
        p_lower = request.prompt.lower()
        if any(prefix in p_lower for prefix in ["sk-or-", "sk-ant", "sk-proj", "sk-", "xai-", "gsk_"]):
            # Extract key
            match = re.search(r'((?:sk-or-|sk-ant-|sk-proj-|sk-|xai-|gsk_)[a-zA-Z0-9_\-]+)', request.prompt)
            if match:
                key = match.group(1)
                if key.startswith("sk-or-"):
                    provider = "openrouter"
                elif key.startswith("sk-ant"):
                    provider = "anthropic"
                elif key.startswith("gsk_"):
                    provider = "groq"
                elif key.startswith("xai-"):
                    provider = "grok"
                else:
                    provider = "openai"
                cred = APICredential(tenant_id=tenant_id, provider=provider, encrypted_key=encrypt_api_key(key))
                db.add(cred)
                
                # Log this activity
                log = ActivityLog(tenant_id=tenant_id, agent_name="System", action="Configuration", description=f"Saved {provider} API key.")
                db.add(log)
                db.commit()
                
                return {"plan": {}, "results": [{"status": "success", "message": f"Awesome! I have saved your {provider} API key. I am now fully operational. What would you like to do?"}]}
            
        # Return fallback asking for key
        log = ActivityLog(tenant_id=tenant_id, agent_name="System", action="ActionRequired", description="Waiting for primary AI API key.")
        db.add(log)
        db.commit()
        return {"plan": {}, "results": [{"status": "action_required", "message": "Hi! Before I can start managing your business, I need an AI brain. Please reply with your OpenRouter, Together AI, Groq, Claude, or OpenAI API key, or enable Inbuilt AI in Settings."}]}

    orchestrator = OrchestratorAgent(db, tenant_id)
    try:
        result = await orchestrator.handle_prompt(
            prompt=request.prompt,
            provider=request.provider,
            model=request.model
        )
    except ValueError as e:
        ve_str = str(e)
        provider = None
        for p in ["linkedin", "meta", "facebook", "instagram", "twitter", "gmail", "whatsapp", "apollo", "hunter", "google_places", "google_calendar", "smtp_marketing", "smtp_hr", "smtp_sales", "smtp", "greenhouse", "lever", "openai", "anthropic", "gemini", "zoominfo", "cognism", "people_data_labs", "clearbit", "crunchbase"]:
            if p in ve_str.lower():
                provider = p
                break
        if provider:
            if provider.startswith("smtp"):
                msg = f"I need your {provider.replace('_', ' ').upper()} credentials. Please reply with: 'My {provider} credential is: smtp://username:password@smtp.mailtrap.io:2525'."
            else:
                msg = f"I need your {provider} API key to complete this task. Please reply with 'My {provider} key is: [YOUR_KEY]'."
            return {"plan": {}, "results": [{"status": "action_required", "message": msg}]}
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return result

@router.post("/keys")
def update_api_key(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
    request: APIKeyUpdate
) -> Any:
    from app.services.security_service import SecretValidationService
    if not SecretValidationService.validate_api_key(request.provider, request.key):
        raise HTTPException(status_code=400, detail=f"Invalid key format for provider: {request.provider}")
        
    cred = db.query(APICredential).filter(
        APICredential.tenant_id == tenant_id,
        APICredential.provider == request.provider
    ).first()
    
    if cred:
        cred.encrypted_key = encrypt_api_key(request.key)
    else:
        # Check if this is the first key
        existing_keys_count = db.query(APICredential).filter(APICredential.tenant_id == tenant_id).count()
        is_main = existing_keys_count == 0
        
        cred = APICredential(
            tenant_id=tenant_id,
            provider=request.provider,
            encrypted_key=encrypt_api_key(request.key),
            is_main=is_main
        )
        db.add(cred)
    
    db.commit()
    return {"message": f"{request.provider} key updated successfully"}

class AIModeUpdate(BaseModel):
    mode: str  # "inbuilt" | "byok"

@router.get("/ai-mode")
def get_ai_mode(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    from app.services.ai_gateway import ai_gateway
    from app.core.config import settings

    current_mode = ai_gateway.get_tenant_ai_mode(db, tenant_id)
    
    inbuilt_providers = [
        p for p in ["openrouter", "together", "groq", "grok", "anthropic", "openai", "gemini"]
        if ai_gateway._get_system_env_key(p)
    ]
    
    byok_creds = db.query(APICredential).filter(
        APICredential.tenant_id == tenant_id,
        APICredential.provider != "ai_mode"
    ).all()
    byok_providers = [c.provider for c in byok_creds if c.encrypted_key]
    
    primary_provider = getattr(settings, "DEFAULT_AI_PROVIDER", "openrouter")
    primary_model = getattr(settings, "DEFAULT_AI_MODEL", None)

    return {
        "current_mode": current_mode,
        "inbuilt_enabled": len(inbuilt_providers) > 0,
        "inbuilt_providers": inbuilt_providers,
        "byok_providers": byok_providers,
        "primary_provider": primary_provider,
        "primary_model": primary_model,
    }

@router.post("/ai-mode")
def set_ai_mode(
    request: AIModeUpdate,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    from app.services.ai_gateway import ai_gateway
    saved_mode = ai_gateway.set_tenant_ai_mode(db, tenant_id, request.mode)
    return {"message": f"AI Mode updated to {saved_mode}", "current_mode": saved_mode}

@router.get("/keys")
def get_configured_keys(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    creds = db.query(APICredential).filter(
        APICredential.tenant_id == tenant_id,
        APICredential.provider != "ai_mode"
    ).all()
    # If there's exactly 1 key, ensure it is set to main
    if len(creds) == 1 and not creds[0].is_main:
        creds[0].is_main = True
        db.commit()
        
    return {
        "configured_providers": [{"provider": c.provider, "is_main": c.is_main} for c in creds]
    }

@router.post("/keys/{provider}/set-main")
def set_main_key(
    provider: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    cred = db.query(APICredential).filter(
        APICredential.tenant_id == tenant_id,
        APICredential.provider == provider
    ).first()
    if not cred:
        raise HTTPException(status_code=404, detail=f"No credential found for provider: {provider}")
        
    # Reset all to False
    db.query(APICredential).filter(APICredential.tenant_id == tenant_id).update({"is_main": False})
    
    # Set the selected one to True
    cred.is_main = True
    db.commit()
    return {"message": f"{provider} is now the main AI API provider"}

@router.delete("/keys/{provider}")
def delete_api_key(
    provider: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    cred = db.query(APICredential).filter(
        APICredential.tenant_id == tenant_id,
        APICredential.provider == provider
    ).first()
    if not cred:
        raise HTTPException(status_code=404, detail=f"No credential found for provider: {provider}")
    db.delete(cred)
    db.commit()
    return {"message": f"{provider} API key removed successfully"}

@router.get("/queue")
def get_content_queue(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    
    posts_to_check = db.query(ContentPost).filter(ContentPost.tenant_id == tenant_id).all()
    needs_commit = False
    
    for p in posts_to_check:
        # Delete if published
        if p.status == 'published' or p.approval_status == 'published':
            db.delete(p)
            needs_commit = True
            continue
            
        # Delete if pending and out of date (older than 2 days)
        if p.approval_status == 'pending' and p.created_at:
            created_at = p.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at < now - timedelta(days=2):
                db.delete(p)
                needs_commit = True
                continue

    if needs_commit:
        db.commit()

    posts = db.query(ContentPost).filter(ContentPost.tenant_id == tenant_id).order_by(ContentPost.day).all()
    leads = db.query(Lead).filter(Lead.tenant_id == tenant_id).all()
    
    posts_data = [{"id": p.id, "platform": p.platform, "content": p.content, "day": p.day, "status": p.status, "scheduled_at": p.scheduled_at} for p in posts]
    leads_data = [
        {
            "id": l.id,
            "name": l.name,
            "company": l.company,
            "source": l.source,
            "status": l.status,
            "score": l.score,
            "personal_email": l.personal_email,
            "company_email": l.company_email,
            "mobile_no": l.mobile_no or l.phone,
            "company_contact_no": l.company_contact_no,
            "need_of_what": l.need_of_what,
            "how_much": l.how_much,
            "why": l.why,
            "target_context": l.target_context,
            "priority": l.priority,
            "created_at": l.created_at.isoformat() if l.created_at else None,
            "updated_at": l.updated_at.isoformat() if l.updated_at else None,
            "data": l.data
        }
        for l in leads
    ]
    return {"posts": posts_data, "leads": leads_data}

@router.get("/timeline")
def get_timeline(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    logs = db.query(ActivityLog).filter(ActivityLog.tenant_id == tenant_id).order_by(ActivityLog.created_at.desc()).limit(50).all()
    return [{"id": log.id, "agent_name": log.agent_name, "action": log.action, "description": log.description, "status": log.status, "created_at": log.created_at.isoformat()} for log in logs]

@router.post("/knowledge")
def add_knowledge_doc(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
    request: KnowledgeDocCreate
) -> Any:
    doc = KnowledgeDocument(
        tenant_id=tenant_id,
        department=request.department,
        doc_type=request.doc_type,
        content=request.content
    )
    db.add(doc)
    db.commit()
    return {"message": "Knowledge document added successfully"}

@router.get("/knowledge")
def get_knowledge_docs(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    docs = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.tenant_id == tenant_id,
        KnowledgeDocument.is_active == True,
    ).order_by(KnowledgeDocument.created_at.desc()).all()
    return [
        {
            "id": d.id,
            "department": d.department,
            "doc_type": d.doc_type,
            "content": d.content,
            "source_type": d.source_type or "text",
            "source_url": d.source_url,
            "extraction_method": d.extraction_method,
            "quality_score": d.quality_score,
            "is_active": d.is_active,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]

@router.post("/knowledge/upload")
async def upload_knowledge_file(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
    file: UploadFile = File(...),
    department: str = Form(...),
    doc_type: str = Form(...)
) -> Any:
    filename = file.filename
    content_bytes = await file.read()
    
    from app.services.document_processing.pipeline import DocumentProcessingPipeline
    from app.services.knowledge_os.entity_extractor import EntityExtractor
    from app.services.sales_os.context_materializer import SalesContextMaterializer
    
    pipeline = DocumentProcessingPipeline(db, tenant_id)
    result = await pipeline.process_document(
        filename=filename,
        file_bytes=content_bytes,
        department=department,
        doc_type_override=doc_type,
    )
    
    content = result.get("text", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Document appears to be empty or has no extractable text.")
        
    doc = KnowledgeDocument(
        tenant_id=tenant_id,
        department=department,
        doc_type=result.get("category", doc_type),
        content=f"Source Document: {filename}\n\n{content}",
        source_type="file",
        source_url=filename,
        extraction_method=result.get("extraction_method"),
        quality_score=result.get("quality_score", 1.0),
        is_active=True,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    # Store chunks into KnowledgeChunk table with provenance
    chunks = result.get("chunks", [])
    for c in chunks:
        db.add(
            KnowledgeChunk(
                tenant_id=tenant_id,
                document_id=doc.id,
                department=department,
                version=1,
                title=f"{filename} #{c['chunk_index']}",
                content=c["text"],
                embedding_hint=c["text"][:100],
                page_start=c.get("page_start", 1),
                page_end=c.get("page_end", 1),
                section_title=c.get("section_title", "General"),
                source_url=filename,
                content_hash=c.get("content_hash"),
                is_active=True,
            )
        )
    db.commit()
    
    # Extract structured entities and atomic evidence
    extractor = EntityExtractor(db, tenant_id)
    entities = await extractor.extract_entities_from_document(
        document_id=doc.id,
        document_name=filename,
        content=content,
        category=result.get("category", doc_type),
    )
    
    # Refresh active Company Sales Context in background
    try:
        materializer = SalesContextMaterializer(db, tenant_id)
        await materializer.materialize_context()
    except Exception:
        pass
        
    return {
        "message": f"Successfully parsed and added document '{filename}' to Knowledge Base.",
        "document_id": doc.id,
        "method": result.get("extraction_method"),
        "quality_score": result.get("quality_score"),
        "chunks_indexed": len(chunks),
        "products_extracted": len(entities.get("products", [])),
        "evidence_records_created": entities.get("evidence_count", 0),
    }

@router.post("/knowledge/web")
async def crawl_website_knowledge(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
    request: WebCrawlRequest,
) -> Any:
    """Crawl a website and index pages into the tenant's knowledge base."""
    from app.services.web_ingestion.firecrawl_client import validate_target_url
    from app.services.web_ingestion.website_sync import WebsiteSyncService

    try:
        clean_url = validate_target_url(request.url)
    except Exception as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    # Register KnowledgeSource
    source = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.tenant_id == tenant_id, KnowledgeSource.url == clean_url)
        .first()
    )
    if not source:
        source = KnowledgeSource(
            tenant_id=tenant_id,
            url=clean_url,
            kind="web",
            max_pages=request.max_pages or 50,
            crawl_depth=request.crawl_depth or 2,
            include_paths=request.include_paths or [],
            exclude_paths=request.exclude_paths or [],
            schedule=request.schedule or "manual",
            last_status="idle",
        )
        db.add(source)
        db.commit()
        db.refresh(source)
    else:
        source.max_pages = request.max_pages or 50
        source.crawl_depth = request.crawl_depth or 2
        source.include_paths = request.include_paths or []
        source.exclude_paths = request.exclude_paths or []
        source.schedule = request.schedule or source.schedule
        db.commit()

    sync_service = WebsiteSyncService(db, tenant_id)
    try:
        sync_result = await sync_service.sync_knowledge_source(source.id)
        return {
            "message": f"Successfully crawled and synchronized {sync_result['total_pages_crawled']} pages from {clean_url}.",
            "source_id": source.id,
            "created": sync_result["created"],
            "updated": sync_result["updated"],
            "skipped": sync_result["skipped"],
            "active_pages": sync_result["active_pages"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Web crawl failed: {str(e)}")

@router.post("/knowledge/web/company-sync")
async def sync_company_website_knowledge(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
    request: CompanySyncRequest,
) -> Any:
    """One-click sync of company website from Tenant profile."""
    from app.services.web_ingestion.website_sync import WebsiteSyncService

    sync_service = WebsiteSyncService(db, tenant_id)
    try:
        sync_result = await sync_service.sync_company_website(
            max_pages=request.max_pages or 50,
            crawl_depth=request.crawl_depth or 2,
        )
        return {
            "message": f"Successfully synchronized official company website ({sync_result['active_pages']} pages active).",
            "source_id": sync_result["source_id"],
            "url": sync_result["url"],
            "created": sync_result["created"],
            "updated": sync_result["updated"],
            "skipped": sync_result["skipped"],
            "active_pages": sync_result["active_pages"],
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Company website sync failed: {str(e)}")

@router.get("/knowledge/sources")
def get_knowledge_sources(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    """List all registered external knowledge sources (websites, feeds)."""
    sources = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.tenant_id == tenant_id)
        .order_by(KnowledgeSource.created_at.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "url": s.url,
            "kind": s.kind,
            "max_pages": s.max_pages,
            "crawl_depth": s.crawl_depth,
            "schedule": s.schedule,
            "last_crawled_at": s.last_crawled_at.isoformat() if s.last_crawled_at else None,
            "last_status": s.last_status,
            "last_error": s.last_error,
            "pages_indexed": s.pages_indexed,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sources
    ]

@router.post("/knowledge/sources/{source_id}/recrawl")
async def recrawl_knowledge_source(
    source_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
) -> Any:
    """Manually trigger a re-crawl of a specific knowledge source."""
    from app.services.web_ingestion.website_sync import WebsiteSyncService

    sync_service = WebsiteSyncService(db, tenant_id)
    try:
        sync_result = await sync_service.sync_knowledge_source(source_id)
        return {
            "message": f"Successfully re-crawled source. {sync_result['updated']} updated, {sync_result['created']} added.",
            "stats": sync_result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Re-crawl failed: {str(e)}")

@router.delete("/knowledge/sources/{source_id}")
def delete_knowledge_source(
    source_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.DELETE)),
) -> Any:
    """Delete a knowledge source and all its associated documents and chunks."""
    source = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.id == source_id, KnowledgeSource.tenant_id == tenant_id)
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")

    docs = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.source_id == source.id, KnowledgeDocument.tenant_id == tenant_id)
        .all()
    )
    for d in docs:
        db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == d.id).delete()
        db.delete(d)

    db.delete(source)
    db.commit()
    return {"message": "Knowledge source and associated crawled pages deleted successfully."}

@router.delete("/knowledge/{doc_id}")
def delete_knowledge_doc(
    doc_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.tenant_id == tenant_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Knowledge document not found")
    
    # Clean up associated chunks
    db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).delete()
    db.delete(doc)
    db.commit()
    return {"message": "Knowledge document deleted successfully"}
