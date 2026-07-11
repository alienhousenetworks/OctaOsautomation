from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response

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

origins = settings.cors_origin_list()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TenantMiddleware)
app.add_middleware(PrometheusMiddleware)

app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(api_router_v2, prefix="/api/v2")


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


@app.get("/metrics")
def get_metrics(_: None = Depends(require_metrics_token)):
    return Response(content=metrics_registry.generate_prometheus_format(), media_type="text/plain")


@app.get("/")
def root():
    return {"message": "Welcome to OctaOS API", "enterprise": True}
