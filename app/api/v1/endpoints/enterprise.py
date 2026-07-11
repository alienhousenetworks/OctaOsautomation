"""Enterprise APIs: policy, approvals, billing, CRM, compliance, DLQ, AI employees, ROI, KB RAG."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.core.rbac import Action, Resource, require_permission
from app.models.base import User
from app.services.policy_engine import PolicyEngine
from app.services.subscription_service import SubscriptionService
from app.services.razorpay_service import RazorpayNotConfigured, RazorpayService
from app.services.compliance_service import ComplianceService
from app.services.crm_sync import CRMSyncService
from app.services.kb_rag import KnowledgeRAGService
from app.services.durable_workflows import DeadLetterService, DurableWorkflowService
from app.services.outcome_service import OutcomeService
from app.services.ai_employee_service import AIEmployeeService
from app.services.roi_service import ROIService
from app.models.enterprise import TenantBudgetCap, TenantPolicy, FinanceRecord
from app.services.agents.finance import FinanceAgent

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class PolicyUpdate(BaseModel):
    default_mode: Optional[str] = None
    min_confidence: Optional[float] = None
    max_auto_amount: Optional[float] = None
    allowed_channels: Optional[List[str]] = None
    require_brand_pass: Optional[bool] = None
    channel_kill_switches: Optional[Dict[str, bool]] = None
    agent_kill_switches: Optional[Dict[str, bool]] = None
    always_approve: Optional[List[str]] = None
    support_refuse_if_not_in_kb: Optional[bool] = None


class ReviewApproval(BaseModel):
    approve: bool
    note: Optional[str] = None


class EvaluateAction(BaseModel):
    action_type: str
    channel: Optional[str] = None
    agent_name: Optional[str] = None
    confidence: Optional[float] = None
    amount: Optional[float] = None
    brand_pass: bool = True
    title: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None


class PlanChange(BaseModel):
    plan_code: str


class RazorpayCreateOrder(BaseModel):
    plan_code: str


class RazorpayVerifyPayment(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class BudgetCapUpdate(BaseModel):
    monthly_spend_usd: Optional[float] = None
    monthly_action_cap: Optional[int] = None
    hard_stop: Optional[bool] = None
    alert_at_pct: Optional[float] = None


class CRMConnect(BaseModel):
    provider: str
    credentials: Dict[str, Any]
    settings: Optional[Dict[str, Any]] = None


class GDPRBody(BaseModel):
    subject_email: EmailStr


class RetentionUpdate(BaseModel):
    leads_days: Optional[int] = None
    tickets_days: Optional[int] = None
    audit_days: Optional[int] = None
    messages_days: Optional[int] = None
    auto_purge_enabled: Optional[bool] = None


class OutcomeIn(BaseModel):
    outcome_type: str
    agent_name: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    decision_id: Optional[str] = None
    value: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


class PlaybookIn(BaseModel):
    name: str
    department: str
    content: str
    icp_json: Optional[Dict[str, Any]] = None
    playbook_id: Optional[str] = None


class AIEmployeeUpdate(BaseModel):
    manager_user_id: Optional[str] = None
    quota_daily: Optional[int] = None
    sop_id: Optional[str] = None
    kpis: Optional[Dict[str, Any]] = None
    schedule: Optional[Dict[str, Any]] = None
    escalation_path: Optional[List[str]] = None
    is_active: Optional[bool] = None
    status: Optional[str] = None


class TakeoverBody(BaseModel):
    ticket_id: str


class KBQuery(BaseModel):
    query: str
    department: Optional[str] = None
    refuse_if_empty: Optional[bool] = None


class FinanceRecordIn(BaseModel):
    record_type: str  # invoice, expense, ar_followup
    counterparty: Optional[str] = None
    amount: float
    currency: str = "USD"
    category: Optional[str] = None
    status: str = "open"
    description: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class CheckpointIn(BaseModel):
    workflow_name: str
    run_id: str
    step_index: int = 0
    step_name: str = "start"
    state: Dict[str, Any] = Field(default_factory=dict)
    status: str = "running"
    idempotency_key: Optional[str] = None


# ── Policy & Approvals ───────────────────────────────────────────────────────

@router.get("/policy")
def get_policy(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.READ)),
):
    return PolicyEngine(db, tenant_id).get_or_create_policy()


@router.put("/policy")
def update_policy(
    body: PolicyUpdate,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.UPDATE)),
):
    return PolicyEngine(db, tenant_id).update_policy(body.dict(exclude_unset=True))


@router.post("/policy/evaluate")
def evaluate_action(
    body: EvaluateAction,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    user: User = Depends(require_permission(Resource.SETTINGS, Action.EXECUTE)),
):
    engine = PolicyEngine(db, tenant_id)
    return engine.evaluate(**body.dict(), requested_by=user.id)


@router.get("/approvals")
def list_approvals(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.CAMPAIGNS, Action.READ)),
    limit: int = Query(50, le=200),
):
    items = PolicyEngine(db, tenant_id).list_pending(limit=limit)
    return [
        {
            "id": a.id,
            "action_type": a.action_type,
            "channel": a.channel,
            "agent_name": a.agent_name,
            "title": a.title,
            "payload": a.payload,
            "confidence": a.confidence,
            "status": a.status,
            "policy_reason": a.policy_reason,
            "created_at": a.created_at,
        }
        for a in items
    ]


@router.post("/approvals/{approval_id}/review")
def review_approval(
    approval_id: str,
    body: ReviewApproval,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    user: User = Depends(require_permission(Resource.CAMPAIGNS, Action.UPDATE)),
):
    try:
        a = PolicyEngine(db, tenant_id).review(
            approval_id, approve=body.approve, reviewer_id=user.id, note=body.note
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": a.id, "status": a.status, "reviewed_at": a.reviewed_at}


# ── Billing / Entitlements ───────────────────────────────────────────────────

@router.get("/billing/plans")
def list_plans(db: Session = Depends(deps.get_db)):
    plans = SubscriptionService(db).list_plans()
    return [
        {
            "code": p.code,
            "name": p.name,
            "price_usd_monthly": p.price_usd_monthly,
            "price_inr_monthly": p.price_inr_monthly,
            "seat_limit": p.seat_limit,
            "action_quota_monthly": p.action_quota_monthly,
            "allowed_agents": p.allowed_agents,
            "feature_flags": p.feature_flags,
        }
        for p in plans
    ]


@router.get("/billing/entitlements")
def entitlements(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.READ)),
):
    return SubscriptionService(db).entitlements(tenant_id)


@router.post("/billing/plan")
def change_plan(
    body: PlanChange,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    user: User = Depends(require_permission(Resource.SETTINGS, Action.UPDATE)),
):
    """
    Admin free plan switch. When RAZORPAY_REQUIRE_PAYMENT=true, non-superusers
    must pay via /billing/razorpay/* instead.
    """
    from app.core.config import settings as app_settings

    if (
        app_settings.RAZORPAY_REQUIRE_PAYMENT
        and not getattr(user, "is_system_admin", False)
        and not getattr(user, "is_superuser", False)
    ):
        raise HTTPException(
            402,
            "Payment required. Use Razorpay checkout: POST /enterprise/billing/razorpay/create-order",
        )
    try:
        SubscriptionService(db).change_plan(tenant_id, body.plan_code)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return SubscriptionService(db).entitlements(tenant_id)


@router.get("/billing/payments/config")
def payment_config(db: Session = Depends(deps.get_db)):
    """Public-ish config for checkout (key_id only). Auth still required for tenant context."""
    return RazorpayService(db).public_config()


@router.post("/billing/razorpay/create-order")
def razorpay_create_order(
    body: RazorpayCreateOrder,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    user: User = Depends(require_permission(Resource.SETTINGS, Action.UPDATE)),
):
    try:
        return RazorpayService(db).create_order_for_plan(
            tenant_id=tenant_id, plan_code=body.plan_code, user=user
        )
    except RazorpayNotConfigured as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.post("/billing/razorpay/verify")
def razorpay_verify(
    body: RazorpayVerifyPayment,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    user: User = Depends(require_permission(Resource.SETTINGS, Action.UPDATE)),
):
    try:
        return RazorpayService(db).verify_and_activate(
            tenant_id=tenant_id,
            razorpay_order_id=body.razorpay_order_id,
            razorpay_payment_id=body.razorpay_payment_id,
            razorpay_signature=body.razorpay_signature,
            user=user,
        )
    except RazorpayNotConfigured as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/billing/razorpay/webhook")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(deps.get_db),
):
    """Razorpay server webhook — configure URL in Razorpay dashboard."""
    raw = await request.body()
    sig = request.headers.get("X-Razorpay-Signature")
    try:
        return RazorpayService(db).handle_webhook(raw, sig)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/billing/orders")
def list_payment_orders(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.READ)),
    limit: int = 20,
):
    orders = RazorpayService(db).list_orders(tenant_id, limit=limit)
    return [
        {
            "id": o.id,
            "plan_code": o.plan_code,
            "amount": o.amount,
            "currency": o.currency,
            "status": o.status,
            "razorpay_order_id": o.razorpay_order_id,
            "razorpay_payment_id": o.razorpay_payment_id,
            "paid_at": o.paid_at,
            "created_at": o.created_at,
        }
        for o in orders
    ]


@router.get("/billing/budget")
def get_budget(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.READ)),
):
    cap = db.query(TenantBudgetCap).filter(TenantBudgetCap.tenant_id == tenant_id).first()
    check = SubscriptionService(db).check_action_allowed(tenant_id)
    return {"cap": cap, "usage": check}


@router.put("/billing/budget")
def update_budget(
    body: BudgetCapUpdate,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.UPDATE)),
):
    cap = db.query(TenantBudgetCap).filter(TenantBudgetCap.tenant_id == tenant_id).first()
    if not cap:
        cap = TenantBudgetCap(tenant_id=tenant_id)
        db.add(cap)
    for k, v in body.dict(exclude_unset=True).items():
        setattr(cap, k, v)
    db.commit()
    db.refresh(cap)
    return cap


# ── CRM ──────────────────────────────────────────────────────────────────────

@router.get("/crm/connections")
def crm_list(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.INTEGRATIONS, Action.READ)),
):
    conns = CRMSyncService(db, tenant_id).list_connections()
    return [
        {
            "id": c.id,
            "provider": c.provider,
            "is_active": c.is_active,
            "last_sync_at": c.last_sync_at,
            "sync_status": c.sync_status,
        }
        for c in conns
    ]


@router.post("/crm/connect")
def crm_connect(
    body: CRMConnect,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.INTEGRATIONS, Action.CREATE)),
):
    try:
        conn = CRMSyncService(db, tenant_id).connect(body.provider, body.credentials, body.settings)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": conn.id, "provider": conn.provider, "status": "connected"}


@router.post("/crm/sync/lead/{lead_id}")
def crm_sync_lead(
    lead_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.LEADS, Action.CREATE)),
    provider: Optional[str] = None,
):
    try:
        return CRMSyncService(db, tenant_id).sync_lead_outbound(lead_id, provider=provider)
    except ValueError as e:
        raise HTTPException(404, str(e))


# ── Compliance / GDPR ────────────────────────────────────────────────────────

@router.get("/compliance/retention")
def get_retention(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.READ)),
):
    return ComplianceService(db, tenant_id).get_or_create_retention()


@router.put("/compliance/retention")
def update_retention(
    body: RetentionUpdate,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.UPDATE)),
):
    return ComplianceService(db, tenant_id).update_retention(body.dict(exclude_unset=True))


@router.post("/compliance/gdpr/export")
def gdpr_export(
    body: GDPRBody,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    user: User = Depends(require_permission(Resource.AUDIT_LOGS, Action.CREATE)),
):
    return ComplianceService(db, tenant_id).request_export(body.subject_email, requested_by=user.id)


@router.post("/compliance/gdpr/delete")
def gdpr_delete(
    body: GDPRBody,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    user: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
):
    return ComplianceService(db, tenant_id).request_delete(body.subject_email, requested_by=user.id)


# ── Outcomes / Playbooks ─────────────────────────────────────────────────────

@router.post("/outcomes")
def record_outcome(
    body: OutcomeIn,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.LEADS, Action.CREATE)),
):
    ev = OutcomeService(db, tenant_id).record(
        body.outcome_type,
        agent_name=body.agent_name,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        decision_id=body.decision_id,
        value=body.value,
        metadata=body.metadata,
    )
    return {"id": ev.id, "outcome_type": ev.outcome_type}


@router.get("/outcomes/summary")
def outcomes_summary(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.LEADS, Action.READ)),
):
    return OutcomeService(db, tenant_id).summary()


@router.get("/playbooks")
def list_playbooks(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.READ)),
):
    return OutcomeService(db, tenant_id).list_playbooks()


@router.post("/playbooks")
def upsert_playbook(
    body: PlaybookIn,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
):
    return OutcomeService(db, tenant_id).upsert_playbook(**body.dict())


# ── KB RAG ───────────────────────────────────────────────────────────────────

@router.post("/kb/index/{document_id}")
def index_kb_doc(
    document_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
):
    try:
        n = KnowledgeRAGService(db, tenant_id).index_document(document_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"document_id": document_id, "chunks_indexed": n}


@router.post("/kb/query")
def kb_query(
    body: KBQuery,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.TICKETS, Action.CREATE)),
):
    return KnowledgeRAGService(db, tenant_id).answer_context(
        body.query, department=body.department, refuse_if_empty=body.refuse_if_empty
    )


# ── DLQ / Durable workflows ──────────────────────────────────────────────────

@router.get("/ops/dlq")
def list_dlq(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.READ)),
    status: str = "failed",
):
    jobs = DeadLetterService(db).list_jobs(tenant_id=tenant_id, status=status)
    return [
        {
            "id": j.id,
            "task_name": j.task_name,
            "error_message": j.error_message,
            "status": j.status,
            "attempts": j.attempts,
            "created_at": j.created_at,
        }
        for j in jobs
    ]


@router.post("/ops/dlq/{job_id}/replay")
def replay_dlq(
    job_id: str,
    db: Session = Depends(deps.get_db),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.EXECUTE)),
):
    try:
        return DeadLetterService(db).replay(job_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/ops/dlq/{job_id}/discard")
def discard_dlq(
    job_id: str,
    db: Session = Depends(deps.get_db),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
):
    try:
        j = DeadLetterService(db).discard(job_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"id": j.id, "status": j.status}


@router.post("/ops/workflows/checkpoint")
def workflow_checkpoint(
    body: CheckpointIn,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.EXECUTE)),
):
    svc = DurableWorkflowService(db, tenant_id)
    existing = svc.get_run(body.run_id)
    if not existing:
        cp = svc.start_run(
            body.workflow_name,
            body.run_id,
            initial_state=body.state,
            idempotency_key=body.idempotency_key,
        )
    else:
        cp = svc.checkpoint(
            body.run_id,
            step_index=body.step_index,
            step_name=body.step_name,
            state=body.state,
            status=body.status,
        )
    return {
        "id": cp.id,
        "run_id": cp.run_id,
        "step_index": cp.step_index,
        "step_name": cp.step_name,
        "status": cp.status,
    }


@router.get("/ops/workflows/{run_id}")
def get_workflow_run(
    run_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.READ)),
):
    cp = DurableWorkflowService(db, tenant_id).get_run(run_id)
    if not cp:
        raise HTTPException(404, "Run not found")
    return cp


# ── AI Employees ─────────────────────────────────────────────────────────────

@router.get("/ai-employees")
def list_ai_employees(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.USERS, Action.READ)),
):
    return AIEmployeeService(db, tenant_id).list_employees()


@router.patch("/ai-employees/{employee_id}")
def update_ai_employee(
    employee_id: str,
    body: AIEmployeeUpdate,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.USERS, Action.UPDATE)),
):
    try:
        return AIEmployeeService(db, tenant_id).update_employee(
            employee_id, body.dict(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/ai-employees/standup")
def ai_standup(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.USERS, Action.READ)),
    employee_id: Optional[str] = None,
):
    return AIEmployeeService(db, tenant_id).generate_standup(employee_id)


@router.post("/ai-employees/takeover")
def takeover(
    body: TakeoverBody,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    user: User = Depends(require_permission(Resource.TICKETS, Action.CREATE)),
):
    try:
        return AIEmployeeService(db, tenant_id).takeover_ticket(body.ticket_id, user.id)
    except ValueError as e:
        raise HTTPException(404, str(e))


# ── ROI ──────────────────────────────────────────────────────────────────────

@router.get("/roi/dashboard")
def roi_dashboard(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.READ)),
):
    return ROIService(db, tenant_id).dashboard()


@router.get("/roi/monthly-report")
def roi_monthly(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.READ)),
):
    return ROIService(db, tenant_id).monthly_pdf_payload()


# ── Finance vertical (real records) ──────────────────────────────────────────

@router.get("/finance/records")
def list_finance(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.READ)),
    record_type: Optional[str] = None,
):
    q = db.query(FinanceRecord).filter(FinanceRecord.tenant_id == tenant_id)
    if record_type:
        q = q.filter(FinanceRecord.record_type == record_type)
    return q.order_by(FinanceRecord.created_at.desc()).limit(200).all()


@router.post("/finance/records")
def create_finance(
    body: FinanceRecordIn,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
):
    rec = FinanceRecord(tenant_id=tenant_id, **body.dict())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.post("/finance/ar-followup/{record_id}")
async def ar_followup(
    record_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.EXECUTE)),
):
    rec = (
        db.query(FinanceRecord)
        .filter(FinanceRecord.id == record_id, FinanceRecord.tenant_id == tenant_id)
        .first()
    )
    if not rec:
        raise HTTPException(404, "Record not found")
    agent = FinanceAgent(db, tenant_id)
    result = await agent.execute_task(
        {
            "action": "ar_followup",
            "parameters": {
                "record_id": record_id,
                "counterparty": rec.counterparty,
                "amount": rec.amount,
                "status": rec.status,
            },
        }
    )
    return result
