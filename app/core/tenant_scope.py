"""Session-scoped tenant isolation helpers.

Prefer applying filters via `scoped_query` for every tenant-owned model.
For Postgres RLS, run the companion SQL in migrations when enabled.
"""
from __future__ import annotations

from typing import Optional, Type, TypeVar
from sqlalchemy.orm import Query, Session

from app.models.base import tenant_context, org_context

T = TypeVar("T")


def current_tenant_id() -> Optional[str]:
    return tenant_context.get()


def current_org_id() -> Optional[str]:
    return org_context.get()


def scoped_query(
    db: Session,
    model: Type[T],
    tenant_id: Optional[str] = None,
    *,
    require_tenant: bool = True,
) -> Query:
    """Return a query pre-filtered by tenant_id (and org_id when present on model)."""
    tid = tenant_id or current_tenant_id()
    if require_tenant and not tid:
        raise ValueError("Tenant context required for scoped query")

    q = db.query(model)
    if tid and hasattr(model, "tenant_id"):
        q = q.filter(model.tenant_id == tid)

    oid = current_org_id()
    if oid and hasattr(model, "organization_id"):
        # Soft org filter only when org is set in context
        q = q.filter(
            (model.organization_id == oid) | (model.organization_id.is_(None))
        )
    return q


def assert_same_tenant(entity, tenant_id: str) -> None:
    if entity is None:
        return
    entity_tid = getattr(entity, "tenant_id", None)
    if entity_tid and entity_tid != tenant_id:
        raise PermissionError("Cross-tenant access denied")
