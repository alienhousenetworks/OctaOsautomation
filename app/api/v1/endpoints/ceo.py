from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Any, List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.api import deps
from app.core.rbac import Action, Resource, require_permission
from app.models.base import User
from app.models.workflows import Workflow, WorkflowTask
from app.services.agents.ceo import CEOService
from app.core.celery_app import celery_app

router = APIRouter()

class ObjectiveRequest(BaseModel):
    prompt: str
    provider: Optional[str] = "gemini"
    model: Optional[str] = None

class TaskResponse(BaseModel):
    id: str
    workflow_id: str
    name: str
    task_type: str
    status: str
    payload: Optional[dict] = None
    result: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class WorkflowResponse(BaseModel):
    id: str
    name: str
    vertical: str
    status: str
    created_at: datetime
    tasks: List[TaskResponse]

    class Config:
        from_attributes = True


@router.get("/workflows", response_model=List[WorkflowResponse])
def get_ceo_workflows(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    workflows = db.query(Workflow).filter(
        Workflow.tenant_id == tenant_id,
        Workflow.vertical == "CEO"
    ).order_by(Workflow.created_at.desc()).all()
    return workflows

@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
def get_ceo_workflow_details(
    workflow_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.tenant_id == tenant_id,
        Workflow.vertical == "CEO"
    ).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="CEO Strategy Workflow not found")
    return workflow

@router.post("/plan", response_model=WorkflowResponse)
async def generate_ceo_plan(
    payload: ObjectiveRequest,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    if not payload.prompt.strip():
        raise HTTPException(status_code=400, detail="Objective prompt cannot be empty.")
    
    service = CEOService(db, tenant_id)
    try:
        workflow = await service.generate_plan(
            objective=payload.prompt,
            provider=payload.provider,
            model=payload.model
        )
        return workflow
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to generate CEO plan: {str(e)}")

@router.post("/run/{workflow_id}")
async def run_ceo_workflow(
    workflow_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    workflow = db.query(Workflow).filter(
        Workflow.id == workflow_id,
        Workflow.tenant_id == tenant_id,
        Workflow.vertical == "CEO"
    ).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="CEO Strategy Workflow not found")

    if workflow.status == "executing":
        return {"status": "already_running", "message": "Workflow is already executing."}

    # Trigger async Celery task or FastAPI background task
    try:
        celery_app.send_task("run_ceo_workflow_task", args=[tenant_id, workflow.id])
        return {"status": "queued", "message": "Growth strategy execution plan has been queued in background worker."}
    except Exception as e:
        print(f"Failed to queue Celery task, running in FastAPI background task: {e}")
        service = CEOService(db, tenant_id)
        background_tasks.add_task(service.execute_workflow, workflow.id)
        return {"status": "started", "message": "Growth strategy execution plan started in FastAPI thread."}
