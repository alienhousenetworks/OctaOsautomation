"""GDPR export/delete, retention policies, audit helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.enterprise import DataRetentionPolicy, GDPRRequest
from app.models.verticals import Lead
from app.models.base import User
from app.services.audit_service import AuditService


class ComplianceService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def get_or_create_retention(self) -> DataRetentionPolicy:
        pol = (
            self.db.query(DataRetentionPolicy)
            .filter(DataRetentionPolicy.tenant_id == self.tenant_id)
            .first()
        )
        if not pol:
            pol = DataRetentionPolicy(tenant_id=self.tenant_id)
            self.db.add(pol)
            self.db.commit()
            self.db.refresh(pol)
        return pol

    def update_retention(self, updates: Dict[str, Any]) -> DataRetentionPolicy:
        pol = self.get_or_create_retention()
        for k, v in updates.items():
            if hasattr(pol, k) and v is not None:
                setattr(pol, k, v)
        self.db.commit()
        self.db.refresh(pol)
        return pol

    def request_export(self, subject_email: str, requested_by: Optional[str] = None) -> GDPRRequest:
        req = GDPRRequest(
            tenant_id=self.tenant_id,
            request_type="export",
            subject_email=subject_email.lower(),
            status="processing",
            requested_by=requested_by,
        )
        self.db.add(req)
        self.db.commit()

        # Collect subject data
        leads = (
            self.db.query(Lead)
            .filter(Lead.tenant_id == self.tenant_id, Lead.email == subject_email)
            .all()
        )
        users = (
            self.db.query(User)
            .filter(User.tenant_id == self.tenant_id, User.email == subject_email)
            .all()
        )
        payload = {
            "email": subject_email,
            "leads": [
                {
                    "id": l.id,
                    "name": getattr(l, "name", None),
                    "email": l.email,
                    "company": getattr(l, "company", None),
                    "status": getattr(l, "status", None),
                }
                for l in leads
            ],
            "users": [{"id": u.id, "email": u.email, "name": u.name, "role": u.role} for u in users],
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        req.result_payload = payload
        req.status = "completed"
        req.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(req)

        AuditService.log_event(
            self.db,
            action="gdpr.export",
            tenant_id=self.tenant_id,
            user_id=requested_by,
            resource="gdpr",
            resource_id=req.id,
            details={"subject": subject_email},
        )
        return req

    def request_delete(self, subject_email: str, requested_by: Optional[str] = None) -> GDPRRequest:
        req = GDPRRequest(
            tenant_id=self.tenant_id,
            request_type="delete",
            subject_email=subject_email.lower(),
            status="processing",
            requested_by=requested_by,
        )
        self.db.add(req)
        self.db.commit()

        leads = (
            self.db.query(Lead)
            .filter(Lead.tenant_id == self.tenant_id, Lead.email == subject_email)
            .all()
        )
        deleted_leads = 0
        for lead in leads:
            # anonymize rather than hard-delete for audit continuity
            lead.email = f"redacted+{lead.id}@deleted.local"
            if hasattr(lead, "name"):
                lead.name = "REDACTED"
            if hasattr(lead, "phone") and lead.phone:
                lead.phone = None
            if hasattr(lead, "data") and isinstance(lead.data, dict):
                lead.data = {"redacted": True}
            deleted_leads += 1

        req.result_payload = {"anonymized_leads": deleted_leads}
        req.status = "completed"
        req.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(req)

        AuditService.log_event(
            self.db,
            action="gdpr.delete",
            tenant_id=self.tenant_id,
            user_id=requested_by,
            resource="gdpr",
            resource_id=req.id,
            details={"subject": subject_email},
        )
        return req
