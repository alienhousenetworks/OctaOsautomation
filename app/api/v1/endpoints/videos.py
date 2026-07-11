from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, List, Optional
from app.api import deps
from app.core.config import settings
from app.core.rbac import Action, Resource, require_permission
from app.models.base import User
from pydantic import BaseModel
from app.models.video import VideoProject, VideoAsset, VideoRender
from app.models.agents import ActivityLog
from datetime import datetime

def require_video_enabled() -> None:
    if not getattr(settings, "ENABLE_IN_APP_VIDEO", False):
        raise HTTPException(
            status_code=503,
            detail="In-app video creation is temporarily unavailable.",
        )


router = APIRouter(dependencies=[Depends(require_video_enabled)])


class VideoCreateRequest(BaseModel):
    prompt: str
    title: Optional[str] = "Untitled Video"
    provider: Optional[str] = None
    model: Optional[str] = None

class VideoProjectResponse(BaseModel):
    id: str
    tenant_id: str
    organization_id: Optional[str] = None
    title: str
    prompt: Optional[str] = None
    status: str
    duration_seconds: int
    blueprint: dict
    final_video_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        orm_mode = True

@router.post("/create", response_model=VideoProjectResponse)
def create_video_project(
    req: VideoCreateRequest,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    project = VideoProject(
        tenant_id=tenant_id,
        title=req.title,
        prompt=req.prompt,
        llm_provider=req.provider,
        llm_model=req.model,
        status="planning"
    )
    db.add(project)
    
    log = ActivityLog(
        tenant_id=tenant_id,
        agent_name="Video AI",
        action="Video Project Created",
        description=f"Created video project: {req.title}",
        status="success"
    )
    db.add(log)
    db.commit()
    db.refresh(project)
    
    # Trigger Celery workflow for video generation here
    from app.worker.tasks import plan_video_task
    plan_video_task.delay(tenant_id, project.id)
    
    return project

@router.get("/{project_id}", response_model=VideoProjectResponse)
def get_video_project(
    project_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    project = db.query(VideoProject).filter(VideoProject.id == project_id, VideoProject.tenant_id == tenant_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.post("/{project_id}/render")
def trigger_video_render(
    project_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    project = db.query(VideoProject).filter(VideoProject.id == project_id, VideoProject.tenant_id == tenant_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status == "rendering":
        raise HTTPException(status_code=400, detail="Video is already rendering")
    project.status = "queued"
    db.commit()
    
    from app.worker.tasks import render_video_task
    render_video_task.delay(tenant_id, project.id)
    
    return {"status": "processing", "message": "Render task queued"}

@router.get("/", response_model=List[VideoProjectResponse])
def list_video_projects(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    return db.query(VideoProject).filter(VideoProject.tenant_id == tenant_id).order_by(VideoProject.created_at.desc()).all()

@router.delete("/{project_id}")
def delete_video_project(
    project_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    project = db.query(VideoProject).filter(VideoProject.id == project_id, VideoProject.tenant_id == tenant_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"status": "success", "message": "Video project deleted"}

@router.get("/templates")
def list_video_templates() -> Any:
    return {
        "templates": [
            {"id": "linkedin_ad", "name": "LinkedIn Explainer", "duration": 30, "aspect_ratio": "16:9"},
            {"id": "instagram_reel", "name": "Instagram Reel Demo", "duration": 30, "aspect_ratio": "9:16"}
        ]
    }
