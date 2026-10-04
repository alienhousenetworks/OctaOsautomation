"""API endpoints for Sales Manager Intelligence, Knowledge Gaps, and Sales Context."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Any, Optional
from pydantic import BaseModel

from app.api import deps
from app.models.deal_room import SuppressionRecord
from app.services.sales_os.agents.sales_manager import SalesManagerAgent
from app.services.knowledge_os.gap_analyzer import KnowledgeGapAnalyzer
from app.services.sales_os.context_materializer import SalesContextMaterializer
from app.services.sales_os.governance.suppression import SuppressionService

router = APIRouter()


class SuppressionCreate(BaseModel):
    identifier_type: str  # email | domain | phone
    identifier_value: str
    reason: str
    notes: Optional[str] = None
    expires_days: Optional[int] = None


@router.api_route("/daily-audit", methods=["GET", "POST"])
async def run_daily_pipeline_audit(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    agent = SalesManagerAgent(db, tenant_id)
    result = await agent.execute()
    return result.dict()


@router.get("/knowledge-gaps")
def audit_knowledge_gaps(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    analyzer = KnowledgeGapAnalyzer(db, tenant_id)
    gaps = analyzer.analyze_gaps()
    return {"gaps": gaps, "total_gaps": len(gaps)}


@router.post("/refresh-sales-context")
async def refresh_sales_context(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    materializer = SalesContextMaterializer(db, tenant_id)
    ctx = await materializer.materialize_context(force_new_version=True)
    return {
        "status": "success",
        "version": ctx.version,
        "company_name": ctx.company_overview.get("name"),
        "products_count": len(ctx.products_catalog or []),
        "personas_count": len(ctx.buyer_personas or []),
        "proof_points_count": len(ctx.proof_points or []),
    }


@router.get("/sales-context")
def get_current_sales_context(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    materializer = SalesContextMaterializer(db, tenant_id)
    ctx = materializer.get_active_context()
    if not ctx:
        return {"status": "empty", "message": "No materialized sales context found. Run /refresh-sales-context."}
    return {
        "version": ctx.version,
        "company_overview": ctx.company_overview,
        "products_catalog": ctx.products_catalog,
        "icp_definitions": ctx.icp_definitions,
        "buyer_personas": ctx.buyer_personas,
        "proof_points": ctx.proof_points,
        "objection_playbook": ctx.objection_playbook,
        "policies": ctx.policies,
    }


@router.get("/suppression")
def list_suppression_records(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    records = db.query(SuppressionRecord).filter(SuppressionRecord.tenant_id == tenant_id).all()
    return [
        {
            "id": r.id,
            "identifier_type": r.identifier_type,
            "identifier_value": r.identifier_value,
            "reason": r.reason,
            "origin": r.origin,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.post("/suppression")
def add_suppression_record(
    data: SuppressionCreate,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
) -> Any:
    service = SuppressionService(db, tenant_id)
    rec = service.add_suppression(
        identifier_type=data.identifier_type,
        identifier_value=data.identifier_value,
        reason=data.reason,
        origin="user_manual",
        notes=data.notes,
        expires_days=data.expires_days,
    )
    return {"status": "success", "id": rec.id, "identifier": rec.identifier_value}
