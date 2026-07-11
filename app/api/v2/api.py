from fastapi import APIRouter, Depends
from sqlalchemy import text
from app.db.session import SessionLocal
from app.core.config import settings
import redis

api_router = APIRouter()


@api_router.get("/health", tags=["system"])
def check_health():
    """Real health: DB + Redis (+ Celery optional)."""
    status = {
        "status": "healthy",
        "api_version": "v2",
        "enterprise_hardened": True,
        "checks": {},
    }
    # DB
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        status["checks"]["database"] = "ok"
    except Exception as e:
        status["checks"]["database"] = f"error: {e}"
        status["status"] = "degraded"

    # Redis
    try:
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, socket_connect_timeout=2)
        pong = r.ping()
        status["checks"]["redis"] = "ok" if pong else "error"
        if not pong:
            status["status"] = "degraded"
    except Exception as e:
        status["checks"]["redis"] = f"error: {e}"
        status["status"] = "degraded"

    # Celery inspect (best-effort, non-fatal)
    try:
        from app.core.celery_app import celery_app
        insp = celery_app.control.inspect(timeout=1.0)
        ping = insp.ping() if insp else None
        status["checks"]["celery"] = "ok" if ping else "no_workers"
        if not ping:
            status["status"] = "degraded"
    except Exception as e:
        status["checks"]["celery"] = f"unavailable: {e}"

    return status
