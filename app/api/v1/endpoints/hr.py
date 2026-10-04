from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Any, Optional, Dict
from pydantic import BaseModel
from datetime import datetime
import re

from app.api import deps
from app.core.rbac import Action, Resource, require_permission
from app.models.base import User, APICredential
from app.schemas import verticals as schemas
from app.models import verticals as models
from app.services.agents.hr import HRAgent
from app.services.llm_gateway import LLMGateway
from app.services.hr.resume_parser import (
    extract_resume_text,
    extract_heuristic_entities,
    calculate_ats_keyword_score,
    evaluate_semantic_fit,
    compute_composite_ranking,
)
from app.services.hr.contract_service import (
    get_available_templates,
    render_contract_document,
    generate_offer_email_content,
)

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

class InterviewEmailRequest(BaseModel):
    interview_date: str
    interview_time: Optional[str] = "11:00 AM"
    round_name: Optional[str] = "Technical Screen"
    meeting_link: Optional[str] = "https://meet.google.com/new"
    interviewer_name: Optional[str] = "Engineering Lead"
    custom_notes: Optional[str] = None
    channel: str = "smtp"

class GenerateOfferRequest(BaseModel):
    template_id: str = "full_time_standard"
    variables: Dict[str, Any] = {}

class SendOfferEmailRequest(BaseModel):
    template_id: str = "full_time_standard"
    variables: Dict[str, Any] = {}
    channel: str = "smtp"

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

# --- BATCH RESUME UPLOAD, ATS MATCHING & RANKING ---

@router.post("/resumes/upload-batch")
async def upload_resumes_batch(
    files: List[UploadFile] = File(...),
    role: str = Form(...),
    requirements: str = Form(...),
    salary: str = Form("$120,000/year"),
    provider: str = Form("auto"),
    model: Optional[str] = Form(None),
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.HR, Action.CREATE)),
) -> Any:
    """Accepts multiple resume files or folder uploads, extracts text, computes zero-cost ATS match,

    performs condensed semantic fit evaluation, and ranks all candidates.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No resume files uploaded.")

    llm_gateway = LLMGateway(db, tenant_id)
    raw_candidates = []

    for file in files:
        # Read file bytes
        content = await file.read()
        filename = file.filename or "resume.pdf"

        # Tier 1: Deterministic Local Text Extraction ($0 cost)
        extracted_text = extract_resume_text(filename, content)
        if not extracted_text:
            try:
                extracted_text = content.decode("utf-8", errors="ignore")
            except Exception:
                extracted_text = ""

        # Tier 2: Local Heuristic Entity & ATS Keyword Match ($0 cost)
        entities = extract_heuristic_entities(extracted_text, filename=filename)
        ats_results = calculate_ats_keyword_score(entities["skills"], extracted_text, requirements, role)

        condensed_profile = {
            **entities,
            **ats_results,
            "filename": filename,
            "text_excerpt": extracted_text[:1500]
        }

        # Tier 3: Condensed Semantic Evaluation via Low-Cost / Fast LLM (<500 tokens)
        try:
            semantic_res = await evaluate_semantic_fit(
                llm_gateway=llm_gateway,
                condensed_profile=condensed_profile,
                role=role,
                requirements=requirements,
                provider=provider,
                model=model
            )
        except Exception as e:
            semantic_res = {
                "semantic_score": ats_results.get("ats_score", 50),
                "experience_summary": f"Candidate with {entities.get('experience_years', 0)} years experience.",
                "strengths": [f"Skill match: {s}" for s in ats_results.get("matched_skills", [])[:3]],
                "gaps": [f"Missing: {s}" for s in ats_results.get("missing_skills", [])[:2]],
                "recommendation": "Consider",
                "fit_verdict": "Assessed via deterministic heuristics."
            }

        candidate_data = {
            **condensed_profile,
            **semantic_res,
            "filename": filename,
            "raw_text_excerpt": extracted_text[:800]
        }
        raw_candidates.append(candidate_data)

    # Compute composite rank across the batch
    ranked_candidates = compute_composite_ranking(raw_candidates)

    created_or_updated = []
    for item in ranked_candidates:
        cand_email = item.get("email")
        existing = None
        if cand_email:
            existing = db.query(models.Candidate).filter_by(
                tenant_id=tenant_id, email=cand_email
            ).first()

        scorecard = {
            "rank": item.get("rank", 1),
            "composite_score": item.get("composite_score", 60),
            "ats_score": item.get("ats_score", 60),
            "semantic_score": item.get("semantic_score", 60),
            "match_score": item.get("composite_score", 60),
            "skills": item.get("skills", []),
            "matched_skills": item.get("matched_skills", []),
            "missing_skills": item.get("missing_skills", []),
            "experience_years": item.get("experience_years", 0),
            "experience_summary": item.get("experience_summary", ""),
            "education": item.get("education", ""),
            "phone_number": item.get("phone", ""),
            "linkedin": item.get("linkedin", ""),
            "github": item.get("github", ""),
            "strengths": item.get("strengths", []),
            "gaps": item.get("gaps", []),
            "recommendation": item.get("recommendation", "Consider"),
            "fit_verdict": item.get("fit_verdict", ""),
            "requirements_match": f"Matched {len(item.get('matched_skills', []))} required skills. {item.get('fit_verdict', '')}",
            "salary_expectation": salary,
            "filename": item.get("filename", ""),
            "source_platform": "Batch Resume Ingestion",
            "resume_excerpt": item.get("raw_text_excerpt", "")
        }

        if existing:
            existing.role = role
            existing.scorecard = scorecard
            existing.status = "sourced"
            created_or_updated.append(existing)
        else:
            new_cand = models.Candidate(
                tenant_id=tenant_id,
                name=item.get("name") or f"Candidate {item.get('rank', 1)}",
                email=cand_email or f"candidate_{item.get('rank', 1)}@applicant.internal",
                role=role,
                scorecard=scorecard,
                status="sourced"
            )
            db.add(new_cand)
            created_or_updated.append(new_cand)

    db.commit()
    for c in created_or_updated:
        db.refresh(c)

    return {
        "status": "success",
        "processed_count": len(ranked_candidates),
        "candidates": [schemas.Candidate.from_orm(c) for c in created_or_updated]
    }


# --- INTERVIEW INVITATION EMAIL ---

@router.post("/{candidate_id}/send-interview-email")
async def send_interview_email(
    candidate_id: str,
    request: InterviewEmailRequest,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.HR, Action.CREATE)),
) -> Any:
    """Dispatches a personalized interview invitation email to the approved candidate."""
    candidate = db.query(models.Candidate).filter(
        models.Candidate.id == candidate_id,
        models.Candidate.tenant_id == tenant_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    company_name = "OctaOS Technologies Inc."
    subject = f"Interview Invitation: {candidate.role} at {company_name}"
    
    body = f"""Dear {candidate.name},

Thank you for your application for the position of {candidate.role} at {company_name}. 
We reviewed your profile and were impressed by your background. We would love to invite you to an interview!

Interview Details:
- Round: {request.round_name}
- Date: {request.interview_date}
- Time: {request.interview_time}
- Interviewer: {request.interviewer_name}
- Meeting Link: {request.meeting_link}

{f"Additional Notes:\n{request.custom_notes}\n" if request.custom_notes else ""}
Please reply directly to this email if you need to reschedule or have any questions.

We look forward to speaking with you!

Warm regards,
Talent Acquisition Team
{company_name}
"""

    agent = HRAgent(db, tenant_id)
    sent_successfully = False
    delivery_note = "Logged interview invite"

    # Attempt SMTP or Gmail dispatch if credentials exist
    try:
        if request.channel == "smtp":
            cred = db.query(APICredential).filter_by(tenant_id=tenant_id, provider="smtp").first()
            if cred and cred.encrypted_key:
                from app.core.security import decrypt_api_key
                smtp_creds = agent._parse_smtp_credentials(decrypt_api_key(cred.encrypted_key))
                if smtp_creds and candidate.email and "@" in candidate.email:
                    sent_successfully = agent._send_actual_email(smtp_creds, candidate.email, subject, body)
                    delivery_note = "Sent via SMTP"
        elif request.channel == "gmail":
            cred = db.query(APICredential).filter_by(tenant_id=tenant_id, provider="gmail").first()
            if cred and cred.encrypted_key:
                from app.core.security import decrypt_api_key
                agent._send_gmail_api_email(decrypt_api_key(cred.encrypted_key), candidate.email, subject, body)
                sent_successfully = True
                delivery_note = "Sent via Gmail API"
    except Exception as e:
        delivery_note = f"Delivery attempted (Note: {str(e)[:100]})"

    # Update candidate status and scorecard
    candidate.status = "interviewed"
    existing_scorecard = candidate.scorecard or {}
    candidate.scorecard = {
        **existing_scorecard,
        "meeting_time": f"{request.interview_date} at {request.interview_time}",
        "meeting_link": request.meeting_link,
        "interview_round": request.round_name,
        "interviewer_name": request.interviewer_name,
        "interview_email_subject": subject,
        "interview_email_body": body,
        "interview_delivery_status": delivery_note,
        "calendar_booked": True
    }
    db.commit()
    db.refresh(candidate)

    return {
        "status": "success",
        "message": f"Interview invitation successfully recorded. ({delivery_note})",
        "candidate": schemas.Candidate.from_orm(candidate)
    }


# --- OFFER LETTER & CONTRACT TEMPLATES STUDIO ---

@router.get("/contract-templates")
def list_contract_templates(
    _: User = Depends(require_permission(Resource.HR, Action.READ)),
) -> Any:
    """Returns available contract templates and default attributes."""
    return get_available_templates()


@router.post("/{candidate_id}/generate-offer")
def generate_offer_document(
    candidate_id: str,
    request: GenerateOfferRequest,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.HR, Action.READ)),
) -> Any:
    """Renders an employment contract or offer letter with dynamic variable substitution."""
    candidate = db.query(models.Candidate).filter(
        models.Candidate.id == candidate_id,
        models.Candidate.tenant_id == tenant_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    vars_payload = {
        "candidate_name": candidate.name,
        "candidate_email": candidate.email,
        "job_title": candidate.role,
        **(request.variables or {})
    }

    doc = render_contract_document(request.template_id, vars_payload)
    return {
        "status": "success",
        "document": doc
    }


@router.post("/{candidate_id}/send-offer-email")
async def send_offer_email(
    candidate_id: str,
    request: SendOfferEmailRequest,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.HR, Action.CREATE)),
) -> Any:
    """Generates official offer contract and dispatches offer email to candidate."""
    candidate = db.query(models.Candidate).filter(
        models.Candidate.id == candidate_id,
        models.Candidate.tenant_id == tenant_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    vars_payload = {
        "candidate_name": candidate.name,
        "candidate_email": candidate.email,
        "job_title": candidate.role,
        **(request.variables or {})
    }

    # Render contract
    doc = render_contract_document(request.template_id, vars_payload)
    company_name = vars_payload.get("company_name", "OctaOS Technologies Inc.")
    start_date = vars_payload.get("start_date", "Immediate")
    salary_amount = vars_payload.get("salary_amount", "120,000")
    salary_currency = vars_payload.get("salary_currency", "USD")

    subject, body = generate_offer_email_content(
        candidate.name, candidate.role, company_name, start_date, salary_amount, salary_currency
    )

    agent = HRAgent(db, tenant_id)
    sent_successfully = False
    delivery_note = "Offer draft registered in system"

    try:
        if request.channel == "smtp":
            cred = db.query(APICredential).filter_by(tenant_id=tenant_id, provider="smtp").first()
            if cred and cred.encrypted_key:
                from app.core.security import decrypt_api_key
                smtp_creds = agent._parse_smtp_credentials(decrypt_api_key(cred.encrypted_key))
                if smtp_creds and candidate.email and "@" in candidate.email:
                    sent_successfully = agent._send_actual_email(smtp_creds, candidate.email, subject, body)
                    delivery_note = "Sent via SMTP"
        elif request.channel == "gmail":
            cred = db.query(APICredential).filter_by(tenant_id=tenant_id, provider="gmail").first()
            if cred and cred.encrypted_key:
                from app.core.security import decrypt_api_key
                agent._send_gmail_api_email(decrypt_api_key(cred.encrypted_key), candidate.email, subject, body)
                sent_successfully = True
                delivery_note = "Sent via Gmail API"
    except Exception as e:
        delivery_note = f"Delivery registered ({str(e)[:100]})"

    # Update candidate status to offered
    candidate.status = "offered"
    existing_scorecard = candidate.scorecard or {}
    candidate.scorecard = {
        **existing_scorecard,
        "offer_details": {
            "template_id": request.template_id,
            "template_name": doc["template_name"],
            "variables": vars_payload,
            "email_subject": subject,
            "email_body": body,
            "contract_html": doc["html"],
            "delivery_note": delivery_note,
            "offered_at": datetime.now().isoformat()
        }
    }
    db.commit()
    db.refresh(candidate)

    return {
        "status": "success",
        "message": f"Offer letter & contract successfully prepared for {candidate.name}. ({delivery_note})",
        "candidate": schemas.Candidate.from_orm(candidate),
        "contract": doc
    }

