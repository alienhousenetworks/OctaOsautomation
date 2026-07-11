from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from pydantic import BaseModel

from app.api import deps
from app.core.config import settings
from app.core.rbac import Action, Resource, require_permission
from app.models.base import User
from app.models.verticals import Ticket, TicketMessage
from app.models.base import APICredential
from app.services.webhook_security import (
    check_and_store_idempotency,
    ensure_tenant_active,
    payload_sha256,
    verify_email_hmac,
    verify_meta_signature,
    verify_whatsapp_token,
)

router = APIRouter()

class ReplyRequest(BaseModel):
    content: str

class SettingsRequest(BaseModel):
    whatsapp_auto_reply: bool
    email_auto_reply: bool


class EmailWebhookRequest(BaseModel):
    sender: str
    subject: str
    content: str

@router.get("/tickets")
def get_tickets(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    _: User = Depends(require_permission(Resource.TICKETS, Action.READ)),
) -> Any:
    tickets = db.query(Ticket).filter(Ticket.tenant_id == tenant_id).order_by(Ticket.created_at.desc()).all()
    return tickets

@router.get("/tickets/{ticket_id}/messages")
def get_ticket_messages(
    ticket_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.tenant_id == tenant_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    messages = db.query(TicketMessage).filter(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.created_at.asc()).all()
    return messages

@router.post("/tickets/{ticket_id}/reply")
async def manual_reply(
    ticket_id: str,
    payload: ReplyRequest,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.tenant_id == tenant_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    msg = TicketMessage(
        ticket_id=ticket.id,
        sender="agent",
        content=payload.content
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    
    from app.services.agents.support import SupportAgent
    agent = SupportAgent(db, tenant_id)
    try:
        await agent.send_message(ticket.channel, ticket.customer_contact, payload.content)
    except ValueError as e:
        ve_str = str(e)
        provider = None
        for p in ["linkedin", "meta", "facebook", "instagram", "twitter", "gmail", "whatsapp", "apollo", "hunter", "google_places", "google_calendar", "smtp", "greenhouse", "lever", "openai", "anthropic", "gemini"]:
            if p in ve_str.lower():
                provider = p
                break
        if provider:
            if provider == "smtp":
                msg = "I need your SMTP outgoing mail credentials. Please reply with: 'My smtp credential is: smtp://username:password@smtp.mailtrap.io:2525'."
            else:
                msg = f"I need your {provider} API key to complete this task. Please reply with 'My {provider} key is: [YOUR_KEY]'."
            return {"status": "action_required", "message": msg}
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return {"status": "success", "message": msg}

@router.get("/settings")
def get_support_settings(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    cred = db.query(APICredential).filter(
        APICredential.tenant_id == tenant_id,
        APICredential.provider == "support"
    ).first()
    if not cred:
        return {"whatsapp_auto_reply": True, "email_auto_reply": True}
    return cred.settings or {"whatsapp_auto_reply": True, "email_auto_reply": True}

@router.post("/settings")
def save_support_settings(
    payload: SettingsRequest,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    cred = db.query(APICredential).filter(
        APICredential.tenant_id == tenant_id,
        APICredential.provider == "support"
    ).first()
    if not cred:
        cred = APICredential(
            tenant_id=tenant_id,
            provider="support",
            encrypted_key="support_settings",
            settings=payload.dict()
        )
        db.add(cred)
    else:
        cred.settings = payload.dict()
    db.commit()
    return {"status": "success", "settings": cred.settings}


@router.get("/whatsapp/webhook/{tenant_id}")
def verify_whatsapp_webhook(
    tenant_id: str,
    db: Session = Depends(deps.get_db),
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
) -> Any:
    ensure_tenant_active(db, tenant_id)
    if hub_mode == "subscribe" and hub_challenge:
        if not verify_whatsapp_token(db, tenant_id, hub_verify_token):
            raise HTTPException(status_code=403, detail="Invalid verify token")
        return int(hub_challenge) if hub_challenge.isdigit() else hub_challenge
    return "Invalid webhook verification request"


@router.post("/whatsapp/webhook/{tenant_id}")
async def receive_whatsapp_webhook(
    tenant_id: str,
    request: Request,
    db: Session = Depends(deps.get_db),
) -> Any:
    ensure_tenant_active(db, tenant_id)
    raw = await request.body()
    sig = request.headers.get("X-Hub-Signature-256")
    if settings.META_APP_SECRET:
        if not verify_meta_signature(settings.META_APP_SECRET, raw, sig):
            raise HTTPException(status_code=403, detail="Invalid webhook signature")
    elif not settings.DEV:
        raise HTTPException(status_code=503, detail="META_APP_SECRET not configured")

    import json
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    try:
        entry = payload.get("entry", [])[0]
        change = entry.get("changes", [])[0]
        value = change.get("value", {})
        messages = value.get("messages", [])
        if messages:
            msg = messages[0]
            event_id = msg.get("id") or payload_sha256(raw)
            if not check_and_store_idempotency(
                db,
                tenant_id=tenant_id,
                provider="whatsapp",
                event_id=str(event_id),
                payload_hash=payload_sha256(raw),
            ):
                return {"status": "duplicate"}
            sender = msg.get("from")
            text_body = msg.get("text", {}).get("body", "")
            if sender and text_body:
                from app.services.agents.support import SupportAgent
                agent = SupportAgent(db, tenant_id)
                await agent.handle_incoming_message(
                    channel="whatsapp",
                    sender=sender,
                    content=text_body,
                    external_id=msg.get("id"),
                )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error parsing WhatsApp webhook: {e}")
    return {"status": "ok"}


@router.post("/email/webhook/{tenant_id}")
async def receive_email_webhook(
    tenant_id: str,
    request: Request,
    db: Session = Depends(deps.get_db),
) -> Any:
    from app.services.agents.support import SupportAgent

    ensure_tenant_active(db, tenant_id)
    raw = await request.body()
    sig = (
        request.headers.get("X-Octa-Signature")
        or request.headers.get("X-Hub-Signature-256")
        or request.headers.get("X-Signature")
    )
    # Per-tenant secret from API credentials settings, else global
    secret = settings.EMAIL_WEBHOOK_HMAC_SECRET
    cred = (
        db.query(APICredential)
        .filter(
            APICredential.tenant_id == tenant_id,
            APICredential.provider.in_(["email_webhook", "smtp", "support"]),
        )
        .first()
    )
    if cred and cred.settings and cred.settings.get("webhook_hmac_secret"):
        secret = cred.settings.get("webhook_hmac_secret")
    if secret:
        if not verify_email_hmac(secret, raw, sig):
            raise HTTPException(status_code=403, detail="Invalid email webhook signature")
    elif not settings.DEV:
        raise HTTPException(status_code=503, detail="Email webhook HMAC secret not configured")

    sender = None
    subject = None
    content = None
    external_id = None

    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data") or content_type.startswith(
        "application/x-www-form-urlencoded"
    ):
        # Re-parse from body is hard; use form after signature check on raw
        form_data = await request.form()
        sender = form_data.get("sender") or form_data.get("from")
        subject = form_data.get("subject", "")
        content = (
            form_data.get("stripped-text")
            or form_data.get("body-plain")
            or form_data.get("text")
            or form_data.get("body-html")
            or form_data.get("html")
        )
        external_id = form_data.get("Message-Id") or form_data.get("message-id")
    else:
        try:
            import json
            json_data = json.loads(raw.decode("utf-8") or "{}")
            sender = json_data.get("sender") or json_data.get("from")
            subject = json_data.get("subject", "")
            content = (
                json_data.get("stripped-text")
                or json_data.get("body-plain")
                or json_data.get("content")
                or json_data.get("text")
            )
            external_id = json_data.get("message_id") or json_data.get("Message-Id")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid payload")

    if not sender or not content:
        raise HTTPException(status_code=400, detail="Missing sender or content")

    eid = str(external_id or payload_sha256(raw))
    if not check_and_store_idempotency(
        db, tenant_id=tenant_id, provider="email", event_id=eid, payload_hash=payload_sha256(raw)
    ):
        return {"status": "duplicate"}

    agent = SupportAgent(db, tenant_id)
    try:
        await agent.handle_incoming_message(
            channel="email",
            sender=str(sender),
            content=str(content),
            subject=str(subject) if subject else None,
            external_id=str(external_id) if external_id else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok"}
