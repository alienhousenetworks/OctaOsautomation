from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Any
from app.api import deps
from app.models import base
from app.models.base import User
from app.core.rbac import Action, Resource, require_permission
from pydantic import BaseModel

router = APIRouter()


class TenantBase(BaseModel):
    name: str
    subdomain: str


class TenantCreate(TenantBase):
    pass


class Tenant(TenantBase):
    id: str
    is_active: bool

    class Config:
        from_attributes = True


@router.get("/me", response_model=Tenant)
def read_my_tenant(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    tenant = db.query(base.Tenant).filter(base.Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.get("/", response_model=List[Tenant])
def read_tenants(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_permission(Resource.SETTINGS, Action.READ)),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List tenants — system admins only (or superuser)."""
    if not (getattr(current_user, "is_system_admin", False) or getattr(current_user, "is_superuser", False)):
        # Non-system users only see their own tenant
        tenant = db.query(base.Tenant).filter(base.Tenant.id == current_user.tenant_id).first()
        return [tenant] if tenant else []
    tenants = db.query(base.Tenant).offset(skip).limit(limit).all()
    return tenants


@router.post("/", response_model=Tenant)
def create_tenant(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    tenant_in: TenantCreate,
) -> Any:
    """Only system admins may create tenants outside signup flow."""
    if not (getattr(current_user, "is_system_admin", False) or getattr(current_user, "is_superuser", False)):
        raise HTTPException(status_code=403, detail="Only system admins can create tenants")
    tenant = base.Tenant(name=tenant_in.name, subdomain=tenant_in.subdomain)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant
