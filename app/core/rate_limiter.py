import time
import logging
from fastapi import Request, HTTPException, status
from app.core.config import settings
from app.services.ai_gateway.caching import get_redis_client

logger = logging.getLogger(__name__)

# Fallback in-memory sliding window tracking if Redis is unavailable
_in_memory_windows: dict = {}

class RateLimiter:
    @staticmethod
    def check_rate_limit(
        key_identifier: str,
        limit: int = 100,
        window_seconds: int = 60
    ) -> None:
        """
        Enforces a sliding-window rate limit using Redis.
        Falls back to in-memory sliding-window if Redis is down.
        Throws HTTPException with status 429 if the limit is exceeded.
        """
        now = time.time()
        redis_client = get_redis_client()
        
        if redis_client:
            try:
                # Key format
                key = f"rate_limit:{key_identifier}"
                clear_before = now - window_seconds
                
                # Use pipeline to execute atomically
                pipe = redis_client.pipeline()
                # Remove timestamps older than current window
                pipe.zremrangebyscore(key, 0, clear_before)
                # Add current request timestamp
                pipe.zadd(key, {str(now): now})
                # Count total elements in the window
                pipe.zcard(key)
                # Set TTL to prevent keys from persisting forever
                pipe.expire(key, window_seconds + 10)
                
                # Execute transaction
                _, _, current_count, _ = pipe.execute()
                
                if current_count > limit:
                    logger.warning(f"Rate limit exceeded for {key_identifier}: {current_count}/{limit}")
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate limit exceeded. Please try again later."
                    )
                return
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Redis rate limiter failed: {e}. Falling back to in-memory limiter.")
        
        # In-memory fallback
        import threading
        lock = threading.Lock()
        with lock:
            if key_identifier not in _in_memory_windows:
                _in_memory_windows[key_identifier] = []
            
            # Clear old timestamps
            timestamps = _in_memory_windows[key_identifier]
            cutoff = now - window_seconds
            _in_memory_windows[key_identifier] = [t for t in timestamps if t > cutoff]
            
            # Add new request
            _in_memory_windows[key_identifier].append(now)
            current_count = len(_in_memory_windows[key_identifier])
            
            if current_count > limit:
                logger.warning(f"Rate limit exceeded (In-memory) for {key_identifier}: {current_count}/{limit}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please try again later."
                )

def rate_limit_endpoint(limit: int = None, window_seconds: int = 60):
    """
    FastAPI dependency helper to apply rate limiting.
    Differentiates by tenant if tenant_id exists, otherwise falls back to IP.
    Default limit is high (TENANT_API_RATE_LIMIT_PER_MINUTE) so users can explore freely.
    """
    def dependency(request: Request) -> None:
        eff_limit = limit if limit is not None else getattr(
            settings, "TENANT_API_RATE_LIMIT_PER_MINUTE", 300
        )
        # Resolve identifier: prefer tenant_id header, fallback to client IP
        tenant_id = request.headers.get("X-Tenant-ID") or "anonymous"
        client_ip = request.client.host if request.client else "unknown-ip"
        
        # Combine with endpoint path to enforce per-route limits
        path = request.url.path
        key_identifier = f"{tenant_id}:{client_ip}:{path}"
        
        RateLimiter.check_rate_limit(key_identifier, eff_limit, window_seconds)
        
    return dependency


def tenant_action_rate_limit():
    """
    Dependency: enforce subscription weekly + monthly + lifetime action quotas
    (high defaults on explorer plan). Use on heavy AI endpoints.
    """
    from app.api import deps
    from app.services.subscription_service import SubscriptionService
    from fastapi import Depends
    from sqlalchemy.orm import Session

    def dependency(
        request: Request,
        db: Session = Depends(deps.get_db),
        current_user=Depends(deps.get_current_user),
    ):
        # Per-minute API burst (high)
        tenant_id = current_user.tenant_id
        client_ip = request.client.host if request.client else "unknown-ip"
        per_min = getattr(settings, "TENANT_API_RATE_LIMIT_PER_MINUTE", 300)
        RateLimiter.check_rate_limit(
            f"tenant_api:{tenant_id}:{client_ip}",
            limit=per_min,
            window_seconds=60,
        )
        # Subscription quotas
        check = SubscriptionService(db).check_action_allowed(tenant_id)
        if not check.get("allowed"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=check.get("reason") or "Action quota exceeded",
            )
        return check

    return dependency
