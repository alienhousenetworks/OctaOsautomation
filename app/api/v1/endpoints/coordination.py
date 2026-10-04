import asyncio
import json
import logging
from typing import List, Optional, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Header, Query
from fastapi.responses import StreamingResponse, PlainTextResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api import deps
from app.core.config import settings
from app.core.celery_app import celery_app
from app.models.verticals import AgentMeeting
from app.models.boardroom_events import MeetingEvent, MeetingEvidence, MeetingAction
from app.schemas import verticals as schemas
from app.schemas.boardroom import (
    MeetingEventOut,
    MeetingEvidenceOut,
    MeetingActionOut,
    MeetingActionApprove,
    MeetingActionReject,
)
from app.services.agents.boardroom import BoardroomService

logger = logging.getLogger(__name__)

router = APIRouter()


class ManualMeetingRequest(BaseModel):
    title: str
    topic: str
    participants: Optional[List[str]] = None
    auto_select_experts: bool = True
    industry: Optional[str] = None
    decision_category: Optional[str] = None
    trigger_type: str = "manual"
    trigger_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


@router.get("/meetings", response_model=List[schemas.AgentMeeting])
def get_meetings(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    meetings = db.query(AgentMeeting).filter(
        AgentMeeting.tenant_id == tenant_id
    ).order_by(AgentMeeting.created_at.desc()).all()
    return meetings


@router.get("/meetings/{meeting_id}", response_model=schemas.AgentMeeting)
def get_meeting_details(
    meeting_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    meeting = db.query(AgentMeeting).filter(
        AgentMeeting.id == meeting_id,
        AgentMeeting.tenant_id == tenant_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.post("/meetings/create", response_model=schemas.AgentMeeting)
async def create_manual_meeting(
    payload: ManualMeetingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    service = BoardroomService(db, tenant_id, provider=payload.provider, model=payload.model)
    decision_profile = service.build_decision_profile(
        title=payload.title,
        context=payload.topic,
        industry=payload.industry,
        decision_category=payload.decision_category,
    )
    if payload.auto_select_experts:
        parts = service.assemble_boardroom(decision_profile, payload.participants)
    else:
        if not payload.participants:
            raise HTTPException(status_code=400, detail="At least one participant is required.")
        parts = service.assemble_boardroom(decision_profile, payload.participants, include_dynamic=False)

    meeting = AgentMeeting(
        tenant_id=tenant_id,
        title=payload.title,
        status="active",
        current_phase="assembly",
        trigger_type=payload.trigger_type,
        trigger_id=payload.trigger_id,
        context_summary=service.format_decision_context(payload.topic, decision_profile),
        participants=parts,
        transcript=[],
        action_items=[]
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    from app.models.agents import ActivityLog
    log = ActivityLog(
        tenant_id=tenant_id,
        agent_name="CEO AI",
        action="Meeting Summoned",
        description=f"Summoned custom boardroom discussion: '{meeting.title}'.",
        status="success"
    )
    db.add(log)
    db.commit()

    try:
        celery_app.send_task("run_boardroom_meeting_task", args=[tenant_id, meeting.id])
    except Exception as e:
        logger.warning("Failed to queue celery task. Running in FastAPI background task: %s", e)
        background_tasks.add_task(service.run_meeting, meeting.id)

    return meeting


# ---------------------------------------------------------------------------
# SSE Live Event Stream
# ---------------------------------------------------------------------------

@router.get("/meetings/{meeting_id}/stream")
async def stream_meeting_events(
    meeting_id: str,
    last_event_id: Optional[int] = Header(None, alias="Last-Event-ID"),
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Server-Sent Events (SSE) endpoint providing real-time boardroom updates.
    Supports reconnection and missed-event replay using standard `Last-Event-ID`.
    """
    meeting = db.query(AgentMeeting).filter(
        AgentMeeting.id == meeting_id,
        AgentMeeting.tenant_id == tenant_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    missed_events = []
    if last_event_id is not None:
        missed_events = db.query(MeetingEvent).filter(
            MeetingEvent.meeting_id == meeting_id,
            MeetingEvent.seq > last_event_id
        ).order_by(MeetingEvent.seq.asc()).all()

    async def event_generator():
        # 1. Replay missed events if client reconnected with Last-Event-ID
        for ev in missed_events:
            msg_payload = {
                "id": ev.seq,
                "event": ev.event_type,
                "phase": ev.phase,
                "actor": ev.actor,
                "payload": ev.payload or {},
                "ts": ev.created_at.isoformat() if ev.created_at else None,
            }
            yield f"id: {ev.seq}\nevent: {ev.event_type}\ndata: {json.dumps(msg_payload)}\n\n"

        # 2. If meeting already terminal and no missed events, send current snapshot and close
        if meeting.status in ("completed", "failed", "cancelled") and not missed_events:
            snap_payload = {
                "id": 0,
                "event": f"meeting.{meeting.status}",
                "phase": meeting.current_phase,
                "actor": "system",
                "payload": {"status": meeting.status},
                "ts": datetime.now().isoformat()
            }
            yield f"id: 0\nevent: meeting.{meeting.status}\ndata: {json.dumps(snap_payload)}\n\n"
            return

        # 3. Subscribe to Redis pub/sub channel for real-time live events
        pubsub = None
        redis_client = None
        try:
            import redis as redis_lib
            redis_client = redis_lib.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                socket_connect_timeout=2
            )
            pubsub = redis_client.pubsub()
            pubsub.subscribe(f"boardroom:{meeting_id}")
        except Exception as exc:
            logger.warning("Redis pubsub unavailable for SSE stream (%s). Fallback heartbeat.", exc)

        try:
            idle_ticks = 0
            while True:
                if pubsub:
                    msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if msg and msg.get("type") == "message":
                        raw_data = msg["data"]
                        if isinstance(raw_data, bytes):
                            raw_data = raw_data.decode("utf-8")
                        try:
                            parsed = json.loads(raw_data)
                            event_type = parsed.get("event", "message")
                            seq = parsed.get("id", 0)
                            yield f"id: {seq}\nevent: {event_type}\ndata: {json.dumps(parsed)}\n\n"
                            if event_type in ("meeting.completed", "meeting.failed", "meeting.cancelled"):
                                break
                        except Exception as e:
                            logger.error("Error decoding SSE redis message: %s", e)
                else:
                    await asyncio.sleep(2.0)

                # Keep-alive heartbeat every 15s
                idle_ticks += 1
                if idle_ticks >= 15:
                    yield ": keep-alive\n\n"
                    idle_ticks = 0
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            pass
        finally:
            if pubsub:
                try:
                    pubsub.unsubscribe()
                    pubsub.close()
                except Exception:
                    pass
            if redis_client:
                try:
                    redis_client.close()
                except Exception:
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ---------------------------------------------------------------------------
# Events, Evidence, and Governance Endpoints
# ---------------------------------------------------------------------------

@router.get("/meetings/{meeting_id}/events", response_model=List[MeetingEventOut])
def get_meeting_events(
    meeting_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    meeting = db.query(AgentMeeting).filter(
        AgentMeeting.id == meeting_id,
        AgentMeeting.tenant_id == tenant_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    events = db.query(MeetingEvent).filter(
        MeetingEvent.meeting_id == meeting_id
    ).order_by(MeetingEvent.seq.asc()).all()
    return events


@router.get("/meetings/{meeting_id}/evidence", response_model=List[MeetingEvidenceOut])
def get_meeting_evidence(
    meeting_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    meeting = db.query(AgentMeeting).filter(
        AgentMeeting.id == meeting_id,
        AgentMeeting.tenant_id == tenant_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    evidence = db.query(MeetingEvidence).filter(
        MeetingEvidence.meeting_id == meeting_id
    ).order_by(MeetingEvidence.created_at.asc()).all()
    return evidence


@router.get("/meetings/{meeting_id}/actions", response_model=List[MeetingActionOut])
def get_meeting_actions(
    meeting_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    meeting = db.query(AgentMeeting).filter(
        AgentMeeting.id == meeting_id,
        AgentMeeting.tenant_id == tenant_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    actions = db.query(MeetingAction).filter(
        MeetingAction.meeting_id == meeting_id
    ).order_by(MeetingAction.created_at.asc()).all()
    return actions


@router.post("/meetings/{meeting_id}/actions/{action_id}/approve", response_model=MeetingActionOut)
async def approve_meeting_action(
    meeting_id: str,
    action_id: str,
    payload: MeetingActionApprove = MeetingActionApprove(),
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    meeting = db.query(AgentMeeting).filter(
        AgentMeeting.id == meeting_id,
        AgentMeeting.tenant_id == tenant_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    service = BoardroomService(db, tenant_id)
    try:
        updated_action = await service.approve_action(action_id, approved_by=payload.approved_by)
        return updated_action
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/meetings/{meeting_id}/actions/{action_id}/reject", response_model=MeetingActionOut)
def reject_meeting_action(
    meeting_id: str,
    action_id: str,
    payload: MeetingActionReject = MeetingActionReject(),
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    meeting = db.query(AgentMeeting).filter(
        AgentMeeting.id == meeting_id,
        AgentMeeting.tenant_id == tenant_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    service = BoardroomService(db, tenant_id)
    try:
        updated_action = service.reject_action(action_id, rejected_by=payload.rejected_by, reason=payload.reason)
        return updated_action
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/meetings/{meeting_id}/cancel", response_model=schemas.AgentMeeting)
def cancel_meeting(
    meeting_id: str,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    meeting = db.query(AgentMeeting).filter(
        AgentMeeting.id == meeting_id,
        AgentMeeting.tenant_id == tenant_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    service = BoardroomService(db, tenant_id)
    res = service.cancel_meeting(meeting_id)
    return res


@router.post("/meetings/{meeting_id}/rerun", response_model=schemas.AgentMeeting)
async def rerun_meeting(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    meeting = db.query(AgentMeeting).filter(
        AgentMeeting.id == meeting_id,
        AgentMeeting.tenant_id == tenant_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    meeting.status = "active"
    meeting.current_phase = "assembly"
    meeting.failure_reason = None
    db.commit()

    service = BoardroomService(db, tenant_id)
    try:
        celery_app.send_task("run_boardroom_meeting_task", args=[tenant_id, meeting.id])
    except Exception as e:
        logger.warning("Celery queue failed for rerun, using background task: %s", e)
        background_tasks.add_task(service.run_meeting, meeting.id)

    return meeting


@router.get("/meetings/{meeting_id}/export")
def export_meeting(
    meeting_id: str,
    format: str = Query("md", regex="^(md|json)$"),
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    meeting = db.query(AgentMeeting).filter(
        AgentMeeting.id == meeting_id,
        AgentMeeting.tenant_id == tenant_id
    ).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    evidence = db.query(MeetingEvidence).filter(MeetingEvidence.meeting_id == meeting_id).all()
    actions = db.query(MeetingAction).filter(MeetingAction.meeting_id == meeting_id).all()
    events = db.query(MeetingEvent).filter(MeetingEvent.meeting_id == meeting_id).order_by(MeetingEvent.seq.asc()).all()

    if format == "json":
        return JSONResponse({
            "id": meeting.id,
            "title": meeting.title,
            "status": meeting.status,
            "current_phase": meeting.current_phase,
            "participants": meeting.participants,
            "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
            "started_at": meeting.started_at.isoformat() if meeting.started_at else None,
            "finished_at": meeting.finished_at.isoformat() if meeting.finished_at else None,
            "evidence": [{"source_ref": e.source_ref, "type": e.source_type, "trust": e.trust_score, "excerpt": e.excerpt} for e in evidence],
            "actions": [{"id": a.id, "type": a.action_type, "assigned_to": a.assigned_to, "risk": a.risk_tier, "status": a.status, "desc": a.description} for a in actions],
            "transcript": meeting.transcript or [],
            "events_count": len(events)
        })

    # Format Markdown export
    lines = [
        f"# 🏛️ AI Boardroom Decision Record",
        f"**Topic**: {meeting.title}",
        f"**Status**: {meeting.status} (Phase: {meeting.current_phase})",
        f"**Date**: {meeting.created_at.strftime('%Y-%m-%d %H:%M UTC') if meeting.created_at else 'N/A'}",
        f"**Participants**: {', '.join(meeting.participants or [])}",
        "",
        "## 1. Evidence Pack",
        "| Source | Type | Trust Score | Excerpt |",
        "|---|---|---|---|",
    ]
    for ev in evidence:
        lines.append(f"| `{ev.source_ref}` | {ev.source_type} | {ev.trust_score or 'N/A'}% | {ev.excerpt or ''} |")

    lines.extend([
        "",
        "## 2. Governed Action Items",
        "| ID | Risk | Assignee | Status | Description | Approved By |",
        "|---|---|---|---|---|---|",
    ])
    for act in actions:
        lines.append(f"| `{act.id}` | **{act.risk_tier.upper()}** | {act.assigned_to} | `{act.status}` | {act.description} | {act.approved_by or '-'} |")

    lines.extend([
        "",
        "## 3. Deliberation Transcript",
    ])
    for msg in (meeting.transcript or []):
        sender = msg.get("sender", "Agent")
        phase = msg.get("phase", "")
        content = msg.get("content", "")
        lines.append(f"### {sender} ({phase})")
        lines.append(content)
        lines.append("")

    return PlainTextResponse("\n".join(lines), media_type="text/markdown")


@router.get("/analytics")
def get_boardroom_analytics(
    db: Session = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id)
) -> Any:
    """Boardroom executive analytics: meeting volume, action approvals, and risk distribution."""
    total_meetings = db.query(func.count(AgentMeeting.id)).filter(AgentMeeting.tenant_id == tenant_id).scalar() or 0
    completed_meetings = db.query(func.count(AgentMeeting.id)).filter(
        AgentMeeting.tenant_id == tenant_id,
        AgentMeeting.status == "completed"
    ).scalar() or 0
    awaiting_meetings = db.query(func.count(AgentMeeting.id)).filter(
        AgentMeeting.tenant_id == tenant_id,
        AgentMeeting.status == "awaiting_approval"
    ).scalar() or 0

    total_actions = db.query(func.count(MeetingAction.id)).join(
        AgentMeeting, MeetingAction.meeting_id == AgentMeeting.id
    ).filter(AgentMeeting.tenant_id == tenant_id).scalar() or 0

    approved_actions = db.query(func.count(MeetingAction.id)).join(
        AgentMeeting, MeetingAction.meeting_id == AgentMeeting.id
    ).filter(AgentMeeting.tenant_id == tenant_id, MeetingAction.status.in_(["executing", "completed"])).scalar() or 0

    high_risk_actions = db.query(func.count(MeetingAction.id)).join(
        AgentMeeting, MeetingAction.meeting_id == AgentMeeting.id
    ).filter(AgentMeeting.tenant_id == tenant_id, MeetingAction.risk_tier == "high").scalar() or 0

    return {
        "total_meetings": total_meetings,
        "completed_meetings": completed_meetings,
        "awaiting_approval_meetings": awaiting_meetings,
        "completion_rate": round((completed_meetings / total_meetings * 100), 1) if total_meetings else 0,
        "total_actions": total_actions,
        "approved_actions": approved_actions,
        "high_risk_actions": high_risk_actions,
        "auto_approval_rate": round(((total_actions - high_risk_actions) / total_actions * 100), 1) if total_actions else 0,
    }
