"""Webhook signature verification, verify tokens, and idempotency."""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.base import APICredential, Tenant
from app.models.enterprise import WebhookEvent
from app.core.security import decrypt_api_key

logger = logging.getLogger(__name__)


def _get_whatsapp_settings(db: Session, tenant_id: str) -> dict:
    cred = (
        db.query(APICredential)
        .filter(
            APICredential.tenant_id == tenant_id,
            APICredential.provider.in_(["whatsapp", "meta_whatsapp", "meta"]),
        )
        .first()
    )
    if not cred:
        return {}
    settings = cred.settings or {}
    # verify_token may live in settings
    return settings


def verify_whatsapp_token(db: Session, tenant_id: str, hub_verify_token: Optional[str]) -> bool:
    if not tenant_id:
        return False
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.is_active == True).first()  # noqa: E712
    if not tenant:
        return False
    settings = _get_whatsapp_settings(db, tenant_id)
    expected = settings.get("webhook_verify_token") or settings.get("verify_token")
    if not expected:
        # Fail closed in production-minded mode: require configured token
        logger.warning("WhatsApp verify token not configured for tenant %s", tenant_id)
        return False
    return hmac.compare_digest(str(expected), str(hub_verify_token or ""))


def verify_meta_signature(app_secret: str, raw_body: bytes, signature_header: Optional[str]) -> bool:
    """Validate X-Hub-Signature-256: sha256=<hex>."""
    if not app_secret or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected_sig = signature_header.split("=", 1)[1]
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected_sig)


def verify_email_hmac(
    secret: str,
    raw_body: bytes,
    signature_header: Optional[str],
    header_name_style: str = "sha256",
) -> bool:
    if not secret:
        return False
    if not signature_header:
        return False
    sig = signature_header
    if "=" in signature_header:
        sig = signature_header.split("=", 1)[-1]
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, sig)


def ensure_tenant_active(db: Session, tenant_id: str) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


def check_and_store_idempotency(
    db: Session,
    *,
    tenant_id: str,
    provider: str,
    event_id: str,
    payload_hash: Optional[str] = None,
) -> bool:
    """
    Returns True if this is a NEW event (should process).
    Returns False if already processed (skip).
    """
    if not event_id:
        return True
    existing = (
        db.query(WebhookEvent)
        .filter(
            WebhookEvent.tenant_id == tenant_id,
            WebhookEvent.provider == provider,
            WebhookEvent.event_id == event_id,
        )
        .first()
    )
    if existing:
        return False
    db.add(
        WebhookEvent(
            tenant_id=tenant_id,
            provider=provider,
            event_id=event_id,
            payload_hash=payload_hash,
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        return False
    return True


def payload_sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
