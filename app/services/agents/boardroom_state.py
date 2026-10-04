"""
boardroom_state.py — Single source of truth for boardroom phase transitions,
risk-tier classification, and Redis pub/sub event publishing.

All state changes in boardroom.py must go through `transition()` and `emit_event()`.
This eliminates the scattered `meeting.transcript.append()` / `db.commit()` pattern
and gives the SSE endpoint a consistent event stream to replay.
"""
from __future__ import annotations

import json
import logging
import uuid
import datetime
from typing import Optional, Any

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phase ordering (used for forward-only guard)
# ---------------------------------------------------------------------------

PHASES = [
    "assembly",
    "evidence",
    "analysis",
    "critique",
    "synthesis",
    "approval",
    "execution",
    "completed",
]

TERMINAL_PHASES = {"completed", "failed", "cancelled"}

# ---------------------------------------------------------------------------
# Risk tier classification
# Anything not explicitly listed defaults to "high" (safe-fail).
# ---------------------------------------------------------------------------

ACTION_TYPE_MAP: dict[str, tuple[str, str]] = {
    # description keywords → (action_type, risk_tier)
    # Checked in order; first match wins.
    "create_internal_note":    ("create_internal_note", "low"),
    "create internal note":    ("create_internal_note", "low"),
    "internal note":           ("create_internal_note", "low"),
    "tag_lead":                ("tag_lead", "low"),
    "tag lead":                ("tag_lead", "low"),
    "update_tag":              ("tag_lead", "low"),
    "create lead":             ("create_lead", "medium"),
    "create_lead":             ("create_lead", "medium"),
    "capture lead":            ("create_lead", "medium"),
    "update ticket status":    ("update_ticket_status", "medium"),
    "update_ticket_status":    ("update_ticket_status", "medium"),
    "update the ticket":       ("update_ticket_status", "medium"),
    "send customer":           ("send_customer_reply", "high"),
    "reply to customer":       ("send_customer_reply", "high"),
    "notify customer":         ("send_customer_reply", "high"),
    "send a customer":         ("send_customer_reply", "high"),
    "promote candidate":       ("promote_candidate", "high"),
    "promote_candidate":       ("promote_candidate", "high"),
    "update candidate":        ("promote_candidate", "high"),
    "send email":              ("send_customer_reply", "high"),
    "send whatsapp":           ("send_customer_reply", "high"),
}

# Confidence threshold above which "medium" tier auto-approves
AUTO_APPROVE_CONFIDENCE_THRESHOLD = 0.75


def classify_action(description: str) -> tuple[str, str]:
    """Return (action_type, risk_tier) for a given action description."""
    lower = description.lower()
    for keyword, (action_type, tier) in ACTION_TYPE_MAP.items():
        if keyword in lower:
            return action_type, tier
    return "unknown", "high"


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------

def _next_seq(db: Session, meeting_id: str) -> int:
    """Return the next monotonic sequence number for a meeting."""
    from app.models.boardroom_events import MeetingEvent
    count = db.query(func.count(MeetingEvent.id)).filter(
        MeetingEvent.meeting_id == meeting_id
    ).scalar()
    return (count or 0) + 1


def _publish_to_redis(meeting_id: str, payload: dict) -> None:
    """Publish a boardroom event to the per-meeting Redis channel. Fails silently."""
    import os
    if os.environ.get("TESTING") == "1":
        return
    try:
        import redis as redis_lib
        from app.core.config import settings
        r = redis_lib.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT,
                            socket_connect_timeout=1)
        r.publish(f"boardroom:{meeting_id}", json.dumps(payload, default=str))
        r.close()
    except Exception as exc:
        logger.debug("Redis publish skipped (non-fatal): %s", exc)


def emit_event(
    db: Session,
    meeting_id: str,
    event_type: str,
    actor: str = "system",
    phase: Optional[str] = None,
    payload: Optional[dict] = None,
    publish: bool = True,
) -> Any:
    """
    Append a MeetingEvent row and optionally publish to Redis for SSE fan-out.
    This is the single write point for all boardroom events.
    """
    from app.models.boardroom_events import MeetingEvent

    seq = _next_seq(db, meeting_id)
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    event = MeetingEvent(
        meeting_id=meeting_id,
        seq=seq,
        event_type=event_type,
        phase=phase,
        actor=actor,
        payload=payload or {},
    )
    db.add(event)
    db.commit()

    if publish:
        _publish_to_redis(meeting_id, {
            "id": seq,
            "event": event_type,
            "phase": phase,
            "actor": actor,
            "payload": payload or {},
            "ts": ts,
        })

    return event


def transition(
    db: Session,
    meeting,  # AgentMeeting ORM instance
    to_phase: str,
    publish: bool = True,
) -> None:
    """
    Move a meeting to a new phase. Writes a `phase.changed` event and commits.
    Refuses to go backward (except to terminal states).
    """
    from_phase = meeting.current_phase

    if to_phase not in TERMINAL_PHASES:
        from_idx = PHASES.index(from_phase) if from_phase in PHASES else -1
        to_idx = PHASES.index(to_phase) if to_phase in PHASES else -1
        if to_idx < from_idx:
            logger.warning(
                "Refusing backward phase transition %s → %s for meeting %s",
                from_phase, to_phase, meeting.id,
            )
            return

    meeting.current_phase = to_phase
    db.add(meeting)
    db.commit()

    emit_event(
        db=db,
        meeting_id=meeting.id,
        event_type="phase.changed",
        actor="system",
        phase=to_phase,
        payload={"from_phase": from_phase, "to_phase": to_phase},
        publish=publish,
    )
