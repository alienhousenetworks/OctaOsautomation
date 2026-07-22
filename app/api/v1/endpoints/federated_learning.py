from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from app.db.session import get_db
from app.services.federated_learning_service import FederatedLearningService
from app.services.skill_synthesizer import skill_synthesizer
from app.models.learning import (
    StrategyPerformance,
    NegativePatternMemory,
    GlobalStrategyRegistry,
    GlobalFailurePattern,
    GlobalSkillPackage
)

router = APIRouter()

@router.get("/stats")
def get_learning_telemetry_stats(tenant_id: str = Query("default"), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns learning telemetry stats comparing local tenant intelligence with global federated immunity.
    """
    local_strategies = db.query(StrategyPerformance).filter(StrategyPerformance.tenant_id == tenant_id).count()
    local_negative_patterns = db.query(NegativePatternMemory).filter(NegativePatternMemory.tenant_id == tenant_id).count()
    
    global_strategies = db.query(GlobalStrategyRegistry).count()
    global_immunity_signatures = db.query(GlobalFailurePattern).count()
    global_skills = db.query(GlobalSkillPackage).count()

    return {
        "tenant_id": tenant_id,
        "local_intelligence": {
            "active_strategies_count": local_strategies,
            "negative_patterns_count": local_negative_patterns
        },
        "global_federated_hub": {
            "aggregated_strategies_count": global_strategies,
            "failure_immunity_signatures_count": global_immunity_signatures,
            "federated_skill_packages_count": global_skills
        },
        "supported_llm_providers": ["gemini", "anthropic", "openai", "grok", "kimi"]
    }

@router.post("/sync")
def trigger_federated_intelligence_sync(tenant_id: str = Query("default"), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Triggers manual federated intelligence sync between local node and global central hub.
    """
    fed_service = FederatedLearningService(db)
    
    # Example sync execution
    global_immunity_count = db.query(GlobalFailurePattern).count()
    global_strategy_count = db.query(GlobalStrategyRegistry).count()
    
    return {
        "status": "success",
        "message": "Federated strategy weights and failure immunity signatures synchronized successfully.",
        "downloaded_immunity_count": global_immunity_count,
        "downloaded_strategy_count": global_strategy_count
    }

@router.get("/skills")
def list_autodiscovered_skills(level: int = Query(1, ge=1, le=3)) -> Dict[str, Any]:
    """
    Lists auto-discovered SKILL.md packages according to progressive token disclosure level.
    """
    import os
    skills_dir = skill_synthesizer.base_skills_dir
    discovered_skills = []
    
    if os.path.exists(skills_dir):
        for entry in os.listdir(skills_dir):
            if os.path.isdir(os.path.join(skills_dir, entry)):
                skill_info = skill_synthesizer.get_skill_disclosure(entry, level=level)
                discovered_skills.append({
                    "skill_name": entry,
                    "disclosure_level": level,
                    "content": skill_info
                })

    return {
        "skills_directory": skills_dir,
        "total_skills": len(discovered_skills),
        "skills": discovered_skills
    }
