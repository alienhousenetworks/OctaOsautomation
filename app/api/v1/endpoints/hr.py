from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Any, Optional
from pydantic import BaseModel

from app.api import deps
from app.core.rbac import Action, Resource, require_permission
from app.models.base import User
from app.schemas import verticals as schemas
from app.models import verticals as models
from app.services.agents.hr import HRAgent

router = APIRouter()

class SourceRequest(BaseModel):
    role: str
    requirements: str
    salary: str
    count: int = 5
    platforms: List[str] = ["linkedin", "indeed", "ziprecruiter", "greenhouse", "lever"]
    provider: str = "auto"
    model: Optional[str] = None

class OutreachRequest(BaseModel):
    channel: str = "free_outreach"
    subject: str = "Exciting job opportunity: {role}"
    body_template: str = "Hello {name},\n\nI saw your profile and thought you would be a great fit for our {role} opening..."
    provider: str = "auto"
    model: Optional[str] = None

class InterviewRequest(BaseModel):
    tool: str = "free_scheduling"
    provider: str = "auto"
    model: Optional[str] = None

class StatusUpdateRequest(BaseModel):
    status: str

@router.get("/", response_model=List[schemas.Candidate])
def read_candidates(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.HR, Action.READ)),
    skip: int = 0,
    limit: int = 100
) -> Any:
    candidates = db.query(models.Candidate).filter(
        models.Candidate.tenant_id == tenant_id
    ).order_by(models.Candidate.created_at.desc()).offset(skip).limit(limit).all()
    return candidates

@router.post("/", response_model=schemas.Candidate)
def create_candidate(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.HR, Action.CREATE)),
    candidate_in: schemas.CandidateCreate
) -> Any:
    candidate = models.Candidate(**candidate_in.dict(), tenant_id=tenant_id)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate

def handle_value_error(e: ValueError):
    ve_str = str(e)
    provider = None
    for p in ["linkedin", "meta", "facebook", "instagram", "twitter", "gmail", "whatsapp", "apollo", "hunter", "google_places", "google_calendar", "smtp", "greenhouse", "lever", "openai", "anthropic", "gemini"]:
        if p in ve_str.lower():
            provider = p
            break
    if provider:
        if provider == "smtp":
            msg = "I need your SMTP outgoing mail credentials. Please reply with: 'My smtp credential is: smtp://username:password@smtp.mailtrap.io:2525'."
        else:
            msg = f"I need your {provider} API key to complete this task. Please reply with 'My {provider} key is: [YOUR_KEY]'."
        return {"status": "action_required", "message": msg}
    raise HTTPException(status_code=400, detail=str(e))

@router.post("/source")
async def source_candidates(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.HR, Action.CREATE)),
    request: SourceRequest
) -> Any:
    agent = HRAgent(db, tenant_id)
    try:
        result = await agent.execute_task({
            "action": "source_candidates",
            "parameters": {
                "role": request.role,
                "requirements": request.requirements,
                "salary": request.salary,
                "count": request.count,
                "platforms": request.platforms,
                "provider": request.provider,
                "model": request.model
            }
        })
        return result
    except ValueError as e:
        return handle_value_error(e)

@router.post("/{candidate_id}/outreach")
async def candidate_outreach(
    candidate_id: str,
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.HR, Action.CREATE)),
    request: OutreachRequest
) -> Any:
    agent = HRAgent(db, tenant_id)
    try:
        result = await agent.execute_task({
            "action": "candidate_outreach",
            "parameters": {
                "candidate_id": candidate_id,
                "channel": request.channel,
                "subject": request.subject,
                "body_template": request.body_template,
                "provider": request.provider,
                "model": request.model
            }
        })
        return result
    except ValueError as e:
        return handle_value_error(e)

@router.post("/{candidate_id}/interview")
async def schedule_interview(
    candidate_id: str,
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.HR, Action.CREATE)),
    request: InterviewRequest
) -> Any:
    agent = HRAgent(db, tenant_id)
    try:
        result = await agent.execute_task({
            "action": "schedule_interview",
            "parameters": {
                "candidate_id": candidate_id,
                "tool": request.tool,
                "provider": request.provider,
                "model": request.model
            }
        })
        return result
    except ValueError as e:
        return handle_value_error(e)

@router.post("/{candidate_id}/status", response_model=schemas.Candidate)
def update_candidate_status(
    candidate_id: str,
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.HR, Action.CREATE)),
    request: StatusUpdateRequest
) -> Any:
    candidate = db.query(models.Candidate).filter(
        models.Candidate.id == candidate_id,
        models.Candidate.tenant_id == tenant_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    candidate.status = request.status
    db.commit()
    db.refresh(candidate)
    return candidate

@router.delete("/{candidate_id}")
def delete_candidate(
    candidate_id: str,
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.HR, Action.DELETE)),
) -> Any:
    candidate = db.query(models.Candidate).filter(
        models.Candidate.id == candidate_id,
        models.Candidate.tenant_id == tenant_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    db.delete(candidate)
    db.commit()
    return {"status": "success"}
