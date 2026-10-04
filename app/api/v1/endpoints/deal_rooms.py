"""API endpoints for Deal Rooms, Buying Committee, and Agent Capabilities."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.api import deps
from app.models.base import User
from app.models.deal_room import DealRoom, BuyingCommitteeMember, AccountSignal, DealObjection
from app.services.sales_os.agents.qualifier import QualifierAgent
from app.services.sales_os.agents.account_researcher import AccountResearcherAgent
from app.services.sales_os.agents.composer import ComposerAgent
from app.services.sales_os.agents.conversation import ConversationAgent
from app.services.sales_os.agents.deal_desk import DealDeskAgent

router = APIRouter()


class DealRoomCreate(BaseModel):
    company_name: str
    domain: str
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    annual_revenue_usd: Optional[float] = None
    website: Optional[str] = None


class CommitteeMemberCreate(BaseModel):
    name: str
    email: str
    title: str
    role_type: str = "influencer"  # economic_buyer | champion | influencer | technical | gatekeeper
    phone: Optional[str] = None
    department: Optional[str] = None


class ComposeRequest(BaseModel):
    committee_member_id: Optional[str] = None
    channel: str = "email"


class InboundReplyRequest(BaseModel):
    inbound_text: str
    sender_email: Optional[str] = None


@router.get("/")
def list_deal_rooms(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    stage: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
) -> Any:
    q = db.query(DealRoom).filter(DealRoom.tenant_id == tenant_id)
    if stage and stage != "all":
        q = q.filter(DealRoom.stage == stage)
    if search:
        search_filter = f"%{search}%"
        q = q.filter((DealRoom.company_name.ilike(search_filter)) | (DealRoom.domain.ilike(search_filter)))
    
    rooms = q.order_by(DealRoom.priority_index.desc(), DealRoom.updated_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "company_name": r.company_name,
            "domain": r.domain,
            "industry": r.industry,
            "stage": r.stage,
            "icp_fit_score": r.icp_fit_score,
            "timing_score": r.timing_score,
            "priority_index": r.priority_index,
            "calibrated_win_prob": r.calibrated_win_prob,
            "is_multi_threaded": r.is_multi_threaded,
            "committee_coverage": r.committee_coverage,
            "risk_flags": r.risk_flags,
            "next_best_action": r.next_best_action,
            "last_activity_at": r.last_activity_at.isoformat() if r.last_activity_at else None,
        }
        for r in rooms
    ]


@router.post("/", status_code=201)
def create_deal_room(
    data: DealRoomCreate,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    domain = data.domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0].replace("www.", "")
    exists = db.query(DealRoom).filter(DealRoom.tenant_id == tenant_id, DealRoom.domain == domain).first()
    if exists:
        return {"status": "exists", "id": exists.id, "company_name": exists.company_name}

    room = DealRoom(
        tenant_id=tenant_id,
        company_name=data.company_name,
        domain=domain,
        industry=data.industry,
        employee_count=data.employee_count,
        annual_revenue_usd=data.annual_revenue_usd,
        website=data.website or f"https://{domain}",
        stage="discovered",
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return {"status": "created", "id": room.id, "company_name": room.company_name}


@router.get("/{deal_room_id}")
def get_deal_room_detail(
    deal_room_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    room = db.query(DealRoom).filter(DealRoom.id == deal_room_id, DealRoom.tenant_id == tenant_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="DealRoom not found")

    committee = db.query(BuyingCommitteeMember).filter(BuyingCommitteeMember.deal_room_id == deal_room_id).all()
    signals = db.query(AccountSignal).filter(AccountSignal.deal_room_id == deal_room_id).all()
    objections = db.query(DealObjection).filter(DealObjection.deal_room_id == deal_room_id).all()

    return {
        "deal_room": {
            "id": room.id,
            "company_name": room.company_name,
            "domain": room.domain,
            "website": room.website,
            "industry": room.industry,
            "employee_count": room.employee_count,
            "stage": room.stage,
            "icp_fit_score": room.icp_fit_score,
            "timing_score": room.timing_score,
            "priority_index": room.priority_index,
            "calibrated_win_prob": room.calibrated_win_prob,
            "is_multi_threaded": room.is_multi_threaded,
            "risk_flags": room.risk_flags,
            "next_best_action": room.next_best_action,
            "account_brief": room.account_brief,
            "pain_hypotheses": room.pain_hypotheses,
        },
        "buying_committee": [
            {
                "id": m.id,
                "name": m.name,
                "email": m.email,
                "phone": m.phone,
                "title": m.title,
                "role_type": m.role_type,
                "engagement_state": m.engagement_state,
                "provenance": m.provenance,
            }
            for m in committee
        ],
        "signals": [
            {
                "id": s.id,
                "signal_type": s.signal_type,
                "headline": s.headline,
                "evidence_url": s.evidence_url,
                "confidence": s.confidence,
                "observed_at": s.observed_at.isoformat() if s.observed_at else None,
            }
            for s in signals
        ],
        "objections": [
            {
                "id": o.id,
                "category": o.objection_category,
                "statement": o.prospect_statement,
                "counter_argument": o.applied_counter_argument,
                "status": o.status,
            }
            for o in objections
        ],
    }


@router.post("/{deal_room_id}/committee")
def add_committee_member(
    deal_room_id: str,
    data: CommitteeMemberCreate,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    room = db.query(DealRoom).filter(DealRoom.id == deal_room_id, DealRoom.tenant_id == tenant_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="DealRoom not found")

    email = data.email.strip().lower()
    member = BuyingCommitteeMember(
        deal_room_id=deal_room_id,
        tenant_id=tenant_id,
        name=data.name,
        email=email,
        phone=data.phone,
        title=data.title,
        role_type=data.role_type,
        department=data.department,
        provenance={"source": "manual_entry", "confidence": 1.0},
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    # Recheck multi-threading
    count = db.query(BuyingCommitteeMember).filter(BuyingCommitteeMember.deal_room_id == deal_room_id).count()
    room.is_multi_threaded = count >= 2
    room.committee_coverage = min(1.0, round(count / 4.0, 2))
    db.commit()

    return {"status": "created", "id": member.id, "name": member.name}


@router.post("/{deal_room_id}/qualify")
async def qualify_deal_room(
    deal_room_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    agent = QualifierAgent(db, tenant_id)
    result = await agent.execute(deal_room_id)
    return result.dict()


@router.post("/{deal_room_id}/research")
async def research_deal_room(
    deal_room_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    agent = AccountResearcherAgent(db, tenant_id)
    result = await agent.execute(deal_room_id)
    return result.dict()


@router.post("/{deal_room_id}/compose")
async def compose_outreach(
    deal_room_id: str,
    req: ComposeRequest,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    agent = ComposerAgent(db, tenant_id)
    result = await agent.execute(deal_room_id, parameters=req.dict())
    return result.dict()


@router.post("/{deal_room_id}/inbound")
async def process_inbound_reply(
    deal_room_id: str,
    req: InboundReplyRequest,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    agent = ConversationAgent(db, tenant_id)
    result = await agent.execute(deal_room_id, parameters=req.dict())
    return result.dict()


@router.post("/{deal_room_id}/quote")
async def generate_quote(
    deal_room_id: str,
    discount_pct: float = Query(0.0),
    base_amount_usd: float = Query(25000.0),
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    agent = DealDeskAgent(db, tenant_id)
    result = await agent.execute(deal_room_id, parameters={
        "action_type": "quote",
        "requested_discount_pct": discount_pct,
        "base_amount_usd": base_amount_usd,
    })
    return result.dict()
