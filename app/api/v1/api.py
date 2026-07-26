from fastapi import APIRouter
from app.api.v1.endpoints import (
    tenants, leads, marketing, llm, commands, dashboard, auth, support, hr,
    coordination, google, meta_oauth, linkedin_oauth, ceo, system_admin, audit, usage, videos,
    enterprise, manager, federated_learning,
)

from app.api.v1.orchestrator import router as orchestrator_router

api_router = APIRouter()
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(leads.router, prefix="/leads", tags=["leads"])
api_router.include_router(marketing.router, prefix="/marketing", tags=["marketing"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(commands.router, prefix="/commands", tags=["commands"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(support.router, prefix="/support", tags=["support"])
api_router.include_router(hr.router, prefix="/hr", tags=["hr"])
api_router.include_router(coordination.router, prefix="/coordination", tags=["coordination"])
api_router.include_router(ceo.router, prefix="/ceo", tags=["ceo"])
api_router.include_router(google.router, prefix="/google", tags=["google"])
api_router.include_router(meta_oauth.router, prefix="/meta", tags=["meta-oauth"])
api_router.include_router(linkedin_oauth.router, prefix="/linkedin", tags=["linkedin-oauth"])
api_router.include_router(system_admin.router, prefix="/system-admin", tags=["system-admin"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(enterprise.router, prefix="/enterprise", tags=["enterprise"])
api_router.include_router(manager.router, prefix="/manager", tags=["manager"])
api_router.include_router(federated_learning.router, prefix="/learning", tags=["federated-learning"])
api_router.include_router(orchestrator_router, prefix="/octa", tags=["octa-orchestrator"])





