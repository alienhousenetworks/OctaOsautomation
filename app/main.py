from pathlib import Path

import logging

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response

from app.api.v1.api import api_router
from app.api.v2.api import api_router as api_router_v2
from app.core.config import settings
from app.core.middleware import TenantMiddleware
from app.core.observability import PrometheusMiddleware, metrics_registry
from app.api.deps import require_metrics_token

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json")

# Public media files for social platform APIs (Meta, LinkedIn)
_media_dir = Path(settings.MEDIA_UPLOAD_DIR)
_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(_media_dir)), name="media")

app.add_middleware(TenantMiddleware)
app.add_middleware(PrometheusMiddleware)
# Outermost so browser clients still receive CORS headers on error responses.
origins = settings.cors_origin_list()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(api_router_v2, prefix="/api/v2")


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    # Return a normal response so CORS headers are attached. An escaped
    # exception becomes a bare 500 and the browser reports it as a CORS failure.
    logging.getLogger("uvicorn.error").exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.on_event("startup")
def startup_db_check():
    from app.db.session import engine
    from sqlalchemy import text
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
        print("Database connection check successful.")
    except Exception as e:
        print(f"Error checking database connection: {e}")

    # Seed subscription plans (non-fatal)
    try:
        from app.db.session import SessionLocal
        from app.services.subscription_service import SubscriptionService
        db = SessionLocal()
        SubscriptionService(db).seed_plans()
        db.close()
        print("Subscription plans seeded.")
    except Exception as e:
        print(f"Plan seed skipped: {e}")

    # Ensure Flow Engine tables and seeded agents/packages exist
    try:
        from app.models.base import Base
        from app.models import flow_engine  # noqa: F401
        from app.db.session import SessionLocal
        from app.services.agents.seeder import seed_system_agents, seed_system_packages
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        seed_system_agents(db)
        seed_system_packages(db)
        db.close()
        print("System agents and marketplace packages verified.")
    except Exception as e:
        print(f"Flow engine startup check: {e}")


@app.get("/metrics")
def get_metrics(_: None = Depends(require_metrics_token)):
    return Response(content=metrics_registry.generate_prometheus_format(), media_type="text/plain")


@app.get("/")
def root():
    return {"message": "Welcome to OctaOS API", "enterprise": True}
