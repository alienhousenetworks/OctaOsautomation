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
from app.models.agents import ActivityLog, KnowledgeDocument
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

@router.post("/execute")
async def execute_command(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
    request: CommandRequest
) -> Any:
    # 1. Check if user has a primary AI key (for selected provider, or fallback to any primary)
    req_provider = request.provider or "anthropic"
    primary_key = db.query(APICredential).filter(
        APICredential.tenant_id == tenant_id,
        APICredential.provider == req_provider
    ).first()
    
    if not primary_key:
        primary_key = db.query(APICredential).filter(
            APICredential.tenant_id == tenant_id,
            APICredential.provider.in_(["anthropic", "openai", "gemini"])
        ).first()

    # 2. If no key, intercept the prompt
    if not primary_key:
        # Check if the user is pasting a key (simple heuristic)
        if "sk-" in request.prompt or "sk_ant" in request.prompt.lower():
            # Extract key
            match = re.search(r'(sk-[a-zA-Z0-9_\-]+)', request.prompt)
            if match:
                key = match.group(1)
                provider = "anthropic" if "ant" in key.lower() else "openai"
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
        return {"plan": {}, "results": [{"status": "action_required", "message": "Hi! Before I can start managing your business, I need an AI brain. Please reply with your Claude or OpenAI API key."}]}

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

@router.get("/keys")
def get_configured_keys(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    creds = db.query(APICredential).filter(APICredential.tenant_id == tenant_id).all()
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
    docs = db.query(KnowledgeDocument).filter(KnowledgeDocument.tenant_id == tenant_id).all()
    return [{"id": d.id, "department": d.department, "doc_type": d.doc_type, "content": d.content, "created_at": d.created_at.isoformat() if d.created_at else None} for d in docs]

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
    import io
    filename = file.filename
    content_bytes = await file.read()
    
    content = ""
    if filename.endswith(".pdf"):
        try:
            import pypdf
            pdf_reader = pypdf.PdfReader(io.BytesIO(content_bytes))
            text_runs = []
            for page in pdf_reader.pages:
                t = page.extract_text()
                if t:
                    text_runs.append(t)
            content = "\n".join(text_runs)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")
    elif filename.endswith(".docx"):
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(io.BytesIO(content_bytes)) as docx:
                xml_content = docx.read('word/document.xml')
                root = ET.fromstring(xml_content)
                paragraphs = []
                for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                    p_text = "".join(node.text for node in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if node.text)
                    if p_text:
                        paragraphs.append(p_text)
                content = "\n".join(paragraphs)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse DOCX: {str(e)}")
    elif filename.endswith((".txt", ".md", ".json", ".csv")):
        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content = content_bytes.decode("latin-1")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to decode text file: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF, DOCX, TXT, MD, CSV, or JSON.")
    
    if not content.strip():
        raise HTTPException(status_code=400, detail="Document appears to be empty or has no extractable text.")
    
    doc = KnowledgeDocument(
        tenant_id=tenant_id,
        department=department,
        doc_type=doc_type,
        content=f"Source Document: {filename}\n\n{content}"
    )
    db.add(doc)
    db.commit()
    return {"message": f"Successfully parsed and added document '{filename}' to Knowledge Base."}

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
    db.delete(doc)
    db.commit()
    return {"message": "Knowledge document deleted successfully"}
