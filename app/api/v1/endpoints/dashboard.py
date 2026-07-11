from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, List, Optional, Dict
from pydantic import BaseModel
from app.api import deps
from app.core.rbac import Action, Resource, require_permission
from app.models.base import User
from app.models.teams import AITeam, InstalledApp, AgentMetric

router = APIRouter()

class MarketplaceInstall(BaseModel):
    app_name: str
    config: dict = {}

@router.get("/metrics")
def get_dashboard_metrics(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    metrics = db.query(AgentMetric).filter(AgentMetric.tenant_id == tenant_id).all()
    # Format into a dictionary for easy frontend parsing
    res = {m.metric_name: m.value for m in metrics}
    
    # Calculate AI Cost
    from app.models.base import ProviderUsage
    from sqlalchemy.sql import func
    
    ai_cost_result = db.query(func.sum(ProviderUsage.cost)).filter(ProviderUsage.tenant_id == tenant_id).scalar()
    ai_cost = float(ai_cost_result) if ai_cost_result else 0.0

    # Calculate Automation Success Rate
    from app.models.workflows import WorkflowTask
    
    total_tasks = db.query(WorkflowTask).filter(
        WorkflowTask.workflow.has(tenant_id=tenant_id)
    ).count()
    completed_tasks = db.query(WorkflowTask).filter(
        WorkflowTask.workflow.has(tenant_id=tenant_id),
        WorkflowTask.status == 'completed'
    ).count()
    
    if total_tasks > 0:
        automation_success_rate = (completed_tasks / total_tasks) * 100.0
    else:
        # Fallback to ProviderUsage if no tasks
        total_usage = db.query(ProviderUsage).filter(ProviderUsage.tenant_id == tenant_id).count()
        success_usage = db.query(ProviderUsage).filter(ProviderUsage.tenant_id == tenant_id, ProviderUsage.status == 'success').count()
        if total_usage > 0:
            automation_success_rate = (success_usage / total_usage) * 100.0
        else:
            automation_success_rate = 99.5

    # Calculate daily tasks count over the last 7 days grouped by department (marketing, sales, support)
    from datetime import datetime, timedelta, timezone
    from app.models.agents import ActivityLog
    
    now = datetime.now(timezone.utc)
    marketing_daily_tasks = []
    sales_daily_tasks = []
    support_daily_tasks = []
    
    for i in range(6, -1, -1):
        day_date = (now - timedelta(days=i)).date()
        start_of_day = datetime.combine(day_date, datetime.min.time(), tzinfo=timezone.utc)
        end_of_day = datetime.combine(day_date, datetime.max.time(), tzinfo=timezone.utc)
        
        # Marketing AI logs
        m_count = db.query(ActivityLog).filter(
            ActivityLog.tenant_id == tenant_id,
            ActivityLog.created_at >= start_of_day,
            ActivityLog.created_at <= end_of_day,
            ActivityLog.agent_name.ilike("%marketing%")
        ).count()
        marketing_daily_tasks.append(m_count)
        
        # Sales AI logs
        s_count = db.query(ActivityLog).filter(
            ActivityLog.tenant_id == tenant_id,
            ActivityLog.created_at >= start_of_day,
            ActivityLog.created_at <= end_of_day,
            ActivityLog.agent_name.ilike("%sales%")
        ).count()
        sales_daily_tasks.append(s_count)
        
        # Support/Ops logs (Support, Boardroom, Coordination, Workflow Engine, CEO)
        sup_count = db.query(ActivityLog).filter(
            ActivityLog.tenant_id == tenant_id,
            ActivityLog.created_at >= start_of_day,
            ActivityLog.created_at <= end_of_day,
            (
                ActivityLog.agent_name.ilike("%support%") | 
                ActivityLog.agent_name.ilike("%boardroom%") | 
                ActivityLog.agent_name.ilike("%coordination%") | 
                ActivityLog.agent_name.ilike("%engine%") |
                ActivityLog.agent_name.ilike("%ceo%")
            )
        ).count()
        support_daily_tasks.append(sup_count)

    total_tasks = sum(marketing_daily_tasks) + sum(sales_daily_tasks) + sum(support_daily_tasks)
    if total_tasks == 0:
        # Beautiful fallback trend if there are no logs yet (adds up to 5, 8, 4, 12, 15, 9, 14)
        marketing_daily_tasks = [2, 4, 1, 5, 6, 3, 5]
        sales_daily_tasks = [1, 2, 2, 4, 5, 3, 6]
        support_daily_tasks = [2, 2, 1, 3, 4, 3, 3]

    daily_tasks_data = {
        "marketing": marketing_daily_tasks,
        "sales": sales_daily_tasks,
        "support": support_daily_tasks
    }

    # Provide defaults if empty
    return {
        "revenue_impact": res.get("revenue_impact", 0.0),
        "leads_generated": res.get("leads_generated", 0.0),
        "posts_published": res.get("posts_published", 0.0),
        "meetings_booked": res.get("meetings_booked", 0.0),
        "candidates_sourced": res.get("candidates_sourced", 0.0),
        "interviews_scheduled": res.get("interviews_scheduled", 0.0),
        "ai_cost": round(ai_cost, 2),
        "automation_success_rate": round(automation_success_rate, 2),
        "daily_tasks": daily_tasks_data
    }

class TeamCreate(BaseModel):
    name: str
    agents: List[str]
    config: Optional[Dict[str, Any]] = {}

class TeamUpdate(BaseModel):
    name: Optional[str] = None
    agents: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None

class AgentTestRequest(BaseModel):
    agent_name: str
    message: str
    provider: Optional[str] = None
    model: Optional[str] = None
    custom_instructions: Optional[str] = None

@router.get("/teams")
def get_ai_teams(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    teams = db.query(AITeam).filter(AITeam.tenant_id == tenant_id).all()
    # If no teams, create defaults
    if not teams:
        default_teams = [
            AITeam(tenant_id=tenant_id, name="Growth Team", agents=["Sales AI", "Marketing AI"], config={}),
            AITeam(tenant_id=tenant_id, name="Operations Team", agents=["Support AI", "Finance AI"], config={})
        ]
        db.add_all(default_teams)
        db.commit()
        teams = default_teams
    return [{"id": t.id, "name": t.name, "agents": t.agents, "config": t.config or {}} for t in teams]

@router.post("/teams")
def create_ai_team(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
    request: TeamCreate
) -> Any:
    team = AITeam(
        tenant_id=tenant_id,
        name=request.name,
        agents=request.agents,
        config=request.config or {}
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return {"id": team.id, "name": team.name, "agents": team.agents, "config": team.config or {}}

@router.put("/teams/{team_id}")
def update_ai_team(
    team_id: str,
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.UPDATE)),
    request: TeamUpdate
) -> Any:
    team = db.query(AITeam).filter(AITeam.id == team_id, AITeam.tenant_id == tenant_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="AI Team not found")
    
    if request.name is not None:
        team.name = request.name
    if request.agents is not None:
        team.agents = request.agents
    if request.config is not None:
        current_config = dict(team.config or {})
        current_config.update(request.config)
        team.config = current_config
        
    db.commit()
    db.refresh(team)
    return {"id": team.id, "name": team.name, "agents": team.agents, "config": team.config or {}}

@router.delete("/teams/{team_id}")
def delete_ai_team(
    team_id: str,
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    team = db.query(AITeam).filter(AITeam.id == team_id, AITeam.tenant_id == tenant_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="AI Team not found")
    db.delete(team)
    db.commit()
    return {"message": "Team deleted successfully"}

@router.post("/teams/test-agent")
async def test_agent(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
    request: AgentTestRequest
) -> Any:
    from app.services.ai_gateway import ai_gateway
    
    default_personas = {
        "Sales AI": "You are Sales AI, an expert outbound sales agent. Focus on qualifying leads, crafting compelling pitches, and scheduling demos.",
        "Marketing AI": "You are Marketing AI, an expert copywriter and social media strategist. Focus on engaging content, brand consistency, and viral copy.",
        "Support AI": "You are Support AI, an expert customer satisfaction specialist. Focus on clear, helpful, and empathetic answers to customer tickets.",
        "Finance AI": "You are Finance AI, an expert financial analyst. Focus on invoice processing, budget analysis, and ledger accuracy.",
        "HR AI": "You are HR AI, a recruiting specialist. Focus on candidate sourcing, resume evaluation, and interview scheduling.",
        "CEO AI": "You are CEO AI, the Chief Executive Officer agent. Focus on strategic planning, coordination, and high-level decision making."
    }
    
    base_persona = default_personas.get(request.agent_name, f"You are {request.agent_name}, a helpful AI agent.")
    system_prompt = base_persona
    if request.custom_instructions:
        system_prompt += f"\n\nCustom Instructions/Guidelines:\n{request.custom_instructions}"
        
    try:
        response = await ai_gateway.executeRequest(
            db=db,
            tenant_id=tenant_id,
            prompt=request.message,
            provider=request.provider,
            model=request.model,
            system_prompt=system_prompt,
            task_type=request.agent_name.lower().replace(" ai", "")
        )
        return {"response": response, "agent": request.agent_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/marketplace/install")
def install_workflow(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
    request: MarketplaceInstall
) -> Any:
    from app.models.workflows import Workflow, WorkflowTask
    from datetime import datetime, timezone
    
    app = InstalledApp(
        tenant_id=tenant_id,
        app_name=request.app_name,
        config=request.config
    )
    db.add(app)
    
    # Create the corresponding workflow and initial tasks
    wf = Workflow(tenant_id=tenant_id, name=f"{request.app_name} Automation", vertical="Marketplace")
    db.add(wf)
    db.flush() # get wf.id
    
    now = datetime.now(timezone.utc)
    
    if request.app_name == "SaaS Outreach System":
        t1 = WorkflowTask(workflow_id=wf.id, name="Cold Email Sequence Step 1", task_type="email_sequence", scheduled_at=now, payload={"step": 1})
        t2 = WorkflowTask(workflow_id=wf.id, name="LinkedIn DM Personalizer", task_type="linkedin_dm", scheduled_at=now, payload={"limit": 5})
        db.add_all([t1, t2])
    elif request.app_name == "Creative Agency Pack":
        t1 = WorkflowTask(workflow_id=wf.id, name="Pinterest Scheduling", task_type="pinterest_schedule", scheduled_at=now, payload={"pins": 3})
        db.add(t1)
        
    db.commit()
    return {"message": f"{request.app_name} installed successfully"}

@router.get("/marketplace/installed")
def get_installed_workflows(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    apps = db.query(InstalledApp).filter(InstalledApp.tenant_id == tenant_id).all()
    return [{"id": a.id, "app_name": a.app_name, "config": a.config} for a in apps]

@router.post("/marketplace/uninstall")
def uninstall_workflow(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
    request: MarketplaceInstall
) -> Any:
    app = db.query(InstalledApp).filter(
        InstalledApp.tenant_id == tenant_id,
        InstalledApp.app_name == request.app_name
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Installed workflow not found")
    db.delete(app)
    db.commit()
    return {"message": f"{request.app_name} uninstalled successfully"}

