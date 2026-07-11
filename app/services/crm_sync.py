"""Bidirectional CRM / helpdesk sync scaffolding (HubSpot, Zendesk, Salesforce, Freshdesk)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.security import decrypt_api_key, encrypt_api_key
from app.models.enterprise import CRMConnection, CRMSyncRecord
from app.models.verticals import Lead
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class CRMSyncService:
    SUPPORTED = ("hubspot", "salesforce", "zendesk", "freshdesk")

    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def connect(self, provider: str, credentials: Dict[str, Any], settings: Optional[dict] = None) -> CRMConnection:
        provider = provider.lower()
        if provider not in self.SUPPORTED:
            raise ValueError(f"Unsupported CRM provider: {provider}")
        existing = (
            self.db.query(CRMConnection)
            .filter(CRMConnection.tenant_id == self.tenant_id, CRMConnection.provider == provider)
            .first()
        )
        enc = encrypt_api_key(json.dumps(credentials))
        if existing:
            existing.encrypted_credentials = enc
            existing.settings = settings or existing.settings or {}
            existing.is_active = True
            conn = existing
        else:
            conn = CRMConnection(
                tenant_id=self.tenant_id,
                provider=provider,
                encrypted_credentials=enc,
                settings=settings or {},
                is_active=True,
            )
            self.db.add(conn)
        self.db.commit()
        self.db.refresh(conn)
        AuditService.log_event(
            self.db,
            action="crm.connected",
            tenant_id=self.tenant_id,
            resource="crm",
            details={"provider": provider},
        )
        return conn

    def _creds(self, conn: CRMConnection) -> dict:
        return json.loads(decrypt_api_key(conn.encrypted_credentials))

    def list_connections(self) -> List[CRMConnection]:
        return (
            self.db.query(CRMConnection)
            .filter(CRMConnection.tenant_id == self.tenant_id, CRMConnection.is_active == True)  # noqa: E712
            .all()
        )

    def sync_lead_outbound(self, lead_id: str, provider: Optional[str] = None) -> Dict[str, Any]:
        lead = (
            self.db.query(Lead)
            .filter(Lead.id == lead_id, Lead.tenant_id == self.tenant_id)
            .first()
        )
        if not lead:
            raise ValueError("Lead not found")

        q = self.db.query(CRMConnection).filter(
            CRMConnection.tenant_id == self.tenant_id,
            CRMConnection.is_active == True,  # noqa: E712
        )
        if provider:
            q = q.filter(CRMConnection.provider == provider)
        connections = q.all()
        results = []
        for conn in connections:
            try:
                remote_id = self._push_contact(conn, lead)
                self._upsert_sync(conn.provider, "lead", lead.id, remote_id)
                results.append({"provider": conn.provider, "remote_id": remote_id, "status": "ok"})
            except Exception as e:
                logger.exception("CRM push failed")
                results.append({"provider": conn.provider, "status": "error", "error": str(e)})
        return {"lead_id": lead_id, "results": results}

    def _push_contact(self, conn: CRMConnection, lead: Lead) -> str:
        creds = self._creds(conn)
        if conn.provider == "hubspot":
            token = creds.get("access_token") or creds.get("api_key")
            props = {
                "email": lead.email,
                "firstname": (getattr(lead, "name", None) or "").split(" ")[0] if getattr(lead, "name", None) else "",
                "company": getattr(lead, "company", None) or "",
            }
            with httpx.Client(timeout=30.0) as client:
                # search first
                search = client.post(
                    "https://api.hubapi.com/crm/v3/objects/contacts/search",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "filterGroups": [
                            {
                                "filters": [
                                    {"propertyName": "email", "operator": "EQ", "value": lead.email or ""}
                                ]
                            }
                        ]
                    },
                )
                if search.status_code == 200 and search.json().get("results"):
                    rid = search.json()["results"][0]["id"]
                    client.patch(
                        f"https://api.hubapi.com/crm/v3/objects/contacts/{rid}",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"properties": props},
                    )
                    return str(rid)
                create = client.post(
                    "https://api.hubapi.com/crm/v3/objects/contacts",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"properties": props},
                )
                create.raise_for_status()
                return str(create.json().get("id"))

        if conn.provider == "zendesk":
            # Store as end-user note / user
            subdomain = creds.get("subdomain")
            email = creds.get("email")
            api_token = creds.get("api_token")
            auth = (f"{email}/token", api_token)
            with httpx.Client(timeout=30.0) as client:
                r = client.post(
                    f"https://{subdomain}.zendesk.com/api/v2/users/create_or_update.json",
                    auth=auth,
                    json={
                        "user": {
                            "email": lead.email,
                            "name": getattr(lead, "name", None) or lead.email,
                            "role": "end-user",
                        }
                    },
                )
                r.raise_for_status()
                return str(r.json().get("user", {}).get("id"))

        if conn.provider == "freshdesk":
            domain = creds.get("domain")
            api_key = creds.get("api_key")
            with httpx.Client(timeout=30.0) as client:
                r = client.post(
                    f"https://{domain}.freshdesk.com/api/v2/contacts",
                    auth=(api_key, "X"),
                    json={
                        "name": getattr(lead, "name", None) or lead.email,
                        "email": lead.email,
                        "company_id": None,
                    },
                )
                if r.status_code in (200, 201):
                    return str(r.json().get("id"))
                # already exists
                if r.status_code == 409:
                    return "existing"
                r.raise_for_status()
                return str(r.json().get("id"))

        if conn.provider == "salesforce":
            # Minimal REST create Lead — requires instance_url + access_token
            instance = creds.get("instance_url")
            token = creds.get("access_token")
            with httpx.Client(timeout=30.0) as client:
                r = client.post(
                    f"{instance}/services/data/v59.0/sobjects/Lead",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "LastName": (getattr(lead, "name", None) or "Unknown").split()[-1],
                        "Company": getattr(lead, "company", None) or "Unknown",
                        "Email": lead.email,
                    },
                )
                r.raise_for_status()
                return str(r.json().get("id"))

        raise ValueError(f"No push implementation for {conn.provider}")

    def _upsert_sync(self, provider: str, local_type: str, local_id: str, remote_id: str) -> None:
        rec = (
            self.db.query(CRMSyncRecord)
            .filter(
                CRMSyncRecord.tenant_id == self.tenant_id,
                CRMSyncRecord.provider == provider,
                CRMSyncRecord.local_type == local_type,
                CRMSyncRecord.local_id == local_id,
            )
            .first()
        )
        if rec:
            rec.remote_id = remote_id
            rec.last_synced_at = datetime.now(timezone.utc)
        else:
            self.db.add(
                CRMSyncRecord(
                    tenant_id=self.tenant_id,
                    provider=provider,
                    local_type=local_type,
                    local_id=local_id,
                    remote_id=remote_id,
                )
            )
        conn = (
            self.db.query(CRMConnection)
            .filter(CRMConnection.tenant_id == self.tenant_id, CRMConnection.provider == provider)
            .first()
        )
        if conn:
            conn.last_sync_at = datetime.now(timezone.utc)
            conn.sync_status = "ok"
        self.db.commit()
