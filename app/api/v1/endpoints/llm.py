from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Any, Dict
from app.api import deps
from app.core.rbac import Action, Resource, require_permission
from app.models.base import User
from app.models.base import ProviderUsage, AIBatchJob, APICredential
from app.services.ai_gateway import ai_gateway

router = APIRouter()

@router.get("/usage")
def read_usage(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.READ)),
    skip: int = 0,
    limit: int = 100
) -> Any:
    usage = db.query(ProviderUsage).filter(ProviderUsage.tenant_id == tenant_id).offset(skip).limit(limit).all()
    return usage

@router.get("/optimization-metrics")
def get_optimization_metrics(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    # 1. Active Providers (configured keys)
    active_providers = ai_gateway._get_configured_providers(db, tenant_id)
    
    # 2. Query usage stats
    usages = db.query(ProviderUsage).filter(ProviderUsage.tenant_id == tenant_id).all()
    
    # Pre-fill structure for all expected providers
    provider_metrics = {}
    for p in ["openai", "anthropic", "gemini", "grok", "groq", "mistral", "cohere", "local"]:
        provider_metrics[p] = {
            "spend": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "calls": 0,
            "success_calls": 0,
            "failover_calls": 0,
            "failed_calls": 0,
            "total_latency": 0.0,
            "avg_latency": 0.0,
            "uptime": 100.0
        }
        
    cache_hits = 0
    cache_tokens_saved = 0
    total_calls = len(usages)
    non_cached_latencies = []
    
    routing_stats = {
        "marketing": {},
        "sales": {},
        "support": {},
        "finance": {},
        "general": {}
    }
    
    failover_events = 0

    for u in usages:
        p = u.provider.lower()
        if p not in provider_metrics:
            provider_metrics[p] = {
                "spend": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "calls": 0,
                "success_calls": 0,
                "failover_calls": 0,
                "failed_calls": 0,
                "total_latency": 0.0,
                "avg_latency": 0.0,
                "uptime": 100.0
            }
        
        provider_metrics[p]["calls"] += 1
        
        if u.status == "success":
            provider_metrics[p]["success_calls"] += 1
        elif u.status == "failover":
            provider_metrics[p]["failover_calls"] += 1
            failover_events += 1
        elif u.status == "failed":
            provider_metrics[p]["failed_calls"] += 1
            failover_events += 1

        if u.status in ["success", "failover"]:
            provider_metrics[p]["spend"] += u.cost or 0.0
            provider_metrics[p]["input_tokens"] += u.input_tokens or 0
            provider_metrics[p]["output_tokens"] += u.output_tokens or 0
            provider_metrics[p]["total_latency"] += u.latency or 0.0
            if not u.cache_hit:
                non_cached_latencies.append(u.latency or 0.0)
                
        if u.cache_hit:
            cache_hits += 1
            cache_tokens_saved += u.cached_tokens or 0

        # Routing Analytics
        t_type = u.task_type or "general"
        if t_type not in routing_stats:
            routing_stats[t_type] = {}
        routing_stats[t_type][p] = routing_stats[t_type].get(p, 0) + 1

    # Post-process provider metrics
    for p, stats in provider_metrics.items():
        if stats["calls"] > 0:
            valid_calls = stats["success_calls"] + stats["failover_calls"]
            stats["avg_latency"] = round(stats["total_latency"] / max(1, valid_calls), 3)
            stats["uptime"] = round((stats["success_calls"] + stats["failover_calls"]) / stats["calls"] * 100.0, 1)
        else:
            stats["uptime"] = 100.0 if p in active_providers else 0.0

    # Cache hit rate & Latency Saved calculation
    hit_rate = round((cache_hits / max(1, total_calls)) * 100.0, 1) if total_calls > 0 else 0.0
    avg_non_cached_latency = sum(non_cached_latencies) / max(1, len(non_cached_latencies)) if non_cached_latencies else 0.0
    latency_saved = round(cache_hits * avg_non_cached_latency, 2)
    
    optimized_spend = sum(stats["spend"] for stats in provider_metrics.values())
    avg_call_cost = optimized_spend / max(1, total_calls - cache_hits) if (total_calls - cache_hits) > 0 else 0.005
    estimated_savings = cache_hits * avg_call_cost

    # 3. Query Batch Jobs
    batches = db.query(AIBatchJob).filter(AIBatchJob.tenant_id == tenant_id).all()
    batch_stats = {
        "total_jobs": len(batches),
        "completed_jobs": sum(1 for b in batches if b.status == "completed"),
        "processing_jobs": sum(1 for b in batches if b.status == "processing"),
        "failed_jobs": sum(1 for b in batches if b.status == "failed"),
        "total_tasks_processed": sum(b.completed_tasks for b in batches),
        "async_savings": sum(b.completed_tasks * 0.005 for b in batches) # Representative batch discount savings
    }

    # Ensure all departments are represented in routing stats
    for dept in ["marketing", "sales", "support", "finance", "general"]:
        if dept not in routing_stats:
            routing_stats[dept] = {}

    return {
        "active_providers": active_providers,
        "provider_metrics": provider_metrics,
        "cache_metrics": {
            "hit_rate": hit_rate,
            "token_reuse": cache_tokens_saved,
            "latency_saved": latency_saved,
            "hits": cache_hits,
            "total_calls": total_calls,
            "savings": estimated_savings
        },
        "batch_metrics": batch_stats,
        "routing_analytics": routing_stats,
        "failover_events": failover_events,
        "total_spend": round(optimized_spend, 4)
    }

from pydantic import BaseModel

class BatchCreateRequest(BaseModel):
    provider: str
    model: str
    tasks: List[Dict[str, Any]]

@router.post("/batches")
async def create_batch_job(
    *,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.SETTINGS, Action.CREATE)),
    request: BatchCreateRequest
) -> Any:
    job = await ai_gateway.executeBatch(db, tenant_id, request.tasks, request.provider, request.model)
    return {"batch_id": job.id, "status": job.status, "total_tasks": job.total_tasks}

@router.get("/batches/{batch_id}")
def get_batch_job(
    batch_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    job = db.query(AIBatchJob).filter(AIBatchJob.id == batch_id, AIBatchJob.tenant_id == tenant_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")
    return {
        "id": job.id,
        "provider": job.provider,
        "model": job.model,
        "status": job.status,
        "total_tasks": job.total_tasks,
        "completed_tasks": job.completed_tasks,
        "failed_tasks": job.failed_tasks,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "results": job.results.get("completed", []) if isinstance(job.results, dict) else []
    }

from typing import Optional

class PlanTaskRequest(BaseModel):
    complexity: str = "medium"
    realtime: bool = False
    bulk: bool = False
    provider: Optional[str] = None
    model: Optional[str] = None

@router.post("/plan-task")
def plan_ai_task(
    req: PlanTaskRequest,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    from app.services.ai_gateway.routing import AIRoutingEngine, MODEL_REGISTRY
    
    # Get configured providers
    creds = db.query(APICredential).filter(APICredential.tenant_id == tenant_id).all()
    configured_providers = [c.provider for c in creds]
    
    if not configured_providers:
        raise HTTPException(status_code=400, detail="No AI keys configured.")
        
    try:
        if req.provider and req.provider != "auto":
            provider = req.provider
            if req.model:
                model = req.model
            else:
                model = next((v["model"] for k, v in MODEL_REGISTRY.items() if v["provider"] == provider), "unknown")
            reasoning = f"This model was selected because you explicitly chose {provider}/{model} from the UI. User choice takes first priority."
        else:
            provider, model = AIRoutingEngine.selectProvider(
                configured_providers, 
                complexity=req.complexity, 
                realtime=req.realtime, 
                bulk=req.bulk
            )
            reasoning = "This model was selected based on your configured API keys and the default cost-efficiency routing logic."
            if req.bulk:
                reasoning = f"This is a bulk task. {provider}/{model} was selected because it supports batching and is the most cost-effective option."
            elif req.realtime:
                reasoning = f"This is a realtime task. {provider}/{model} was selected for its ultra-low latency."
            elif req.complexity == "high":
                reasoning = f"This is a highly complex task. {provider}/{model} was selected as the strongest reasoning model available."
            else:
                reasoning = f"{provider}/{model} was selected because it offers the lowest overall cost for general tasks among your connected providers."
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    # Get model specs
    spec = None
    for k, v in MODEL_REGISTRY.items():
        if v["provider"] == provider and v["model"] == model:
            spec = v
            break
            
    if not spec:
        spec = {"input_cost_1m": 0.0, "output_cost_1m": 0.0, "latency": "unknown"}

    return {
        "selected_provider": provider,
        "selected_model": model,
        "reasoning": reasoning,
        "estimated_cost_per_1m_tokens": f"${spec['input_cost_1m'] + spec['output_cost_1m']:.2f}",
        "estimated_latency": f"{spec['latency']}s" if isinstance(spec['latency'], (float, int)) else spec['latency']
    }
