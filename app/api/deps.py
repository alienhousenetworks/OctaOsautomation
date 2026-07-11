from typing import Generator, Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.base import User, tenant_context, org_context

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=["HS256"]
        )
        token_type = payload.get("type", "access")
        if token_type not in ("access", None):
            # Reject refresh tokens used as access tokens
            if token_type == "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        token_data = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        org_id = payload.get("organization_id")
    except JWTError:
        # 401 so clients can attempt refresh / re-login (was 403 which looked like RBAC)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials — session expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == token_data).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    if user.tenant and not user.tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant organization is suspended",
        )

    if not getattr(user, "is_verified", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unverified user. Please complete OTP verification.",
        )

    # Bind request tenant context to authenticated user (ignore spoofed headers)
    if tenant_id and tenant_id != user.tenant_id and not getattr(user, "is_system_admin", False):
        raise HTTPException(status_code=403, detail="Token tenant mismatch")
    tenant_context.set(user.tenant_id)
    if org_id or user.organization_id:
        org_context.set(org_id or user.organization_id)

    return user


def get_current_tenant_id(current_user: User = Depends(get_current_user)) -> str:
    return current_user.tenant_id


def check_access(vertical: str):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_system_admin:
            return current_user
        if current_user.role in ("admin", "organization_admin"):
            return current_user
        allowed = current_user.allowed_sections
        if allowed is None:
            return current_user
        if "all" in allowed:
            return current_user
        if vertical in allowed:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to section: {vertical}",
        )

    return dependency


def require_metrics_token(authorization: Optional[str] = Header(None)) -> None:
    """Protect /metrics in non-dev environments when METRICS_TOKEN is set."""
    if settings.DEV and not settings.METRICS_TOKEN:
        return
    if not settings.METRICS_TOKEN:
        if settings.ENVIRONMENT in ("production", "staging"):
            raise HTTPException(status_code=403, detail="Metrics disabled")
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Metrics token required")
    token = authorization.split(" ", 1)[1]
    if token != settings.METRICS_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid metrics token")
