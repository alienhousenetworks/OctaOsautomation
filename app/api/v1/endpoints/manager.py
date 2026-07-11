from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.api import deps
from app.core.rbac import Action, Resource, require_permission
from app.models.base import User
from app.models.memory import ManagerFeedback
from app.services.memory_service import MemoryService

router = APIRouter()


class ManagerFeedbackCreate(BaseModel):
    department: str
    original_output: str
    edited_output: str
    manager_comment: Optional[str] = None
    task_id: Optional[str] = None


@router.post("/feedback")
def submit_feedback(
    feedback: ManagerFeedbackCreate,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.UPDATE)),
):
    """
    Called by the UI when a human manager edits an AI generated action.
    The delta is captured as feedback for the Learning Service.
    """
    memory_service = MemoryService(db, tenant_id)
    record = memory_service.submit_manager_feedback(
        department=feedback.department,
        original_output=feedback.original_output,
        edited_output=feedback.edited_output,
        manager_comment=feedback.manager_comment,
        task_id=feedback.task_id,
    )
    return {"status": "success", "feedback_id": record.id}


@router.get("/feedback/pending")
def get_pending_feedback(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.READ)),
):
    feedbacks = (
        db.query(ManagerFeedback)
        .filter_by(tenant_id=tenant_id, is_processed=False)
        .all()
    )
    return {"feedbacks": feedbacks}
