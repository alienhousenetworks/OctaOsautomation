from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.octa_orchestrator.orchestrator.manager import AIManagerOrchestrator
from app.octa_orchestrator.telemetry.proxy import router as telemetry_router

router = APIRouter(prefix="/orchestrator", tags=["AI Manager Orchestrator"])
router.include_router(telemetry_router)

class ExecuteGoalRequest(BaseModel):
    goal: str
    risk_level: Optional[str] = "NORMAL"

@router.post("/execute")
async def execute_manager_goal(payload: ExecuteGoalRequest):
    """
    Triggers the AI Executive Manager to decompose goals into a DAG task graph,
    route tasks dynamically to SLMs/Frontier models, enforce quality gates, and deliver high ROI outcomes.
    """
    if not payload.goal.strip():
        raise HTTPException(status_code=400, detail="Goal prompt cannot be empty.")
        
    manager = AIManagerOrchestrator()
    try:
        result = await manager.execute_goal(payload.goal, payload.risk_level)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestration failure: {str(e)}")
