"""
Boardroom V2 — append-only event log, evidence catalog, and governed action table.
These three tables replace the JSON-column approach for auditability and governance.
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, JSON, Float
from app.models.base import Base
import uuid
from sqlalchemy.sql import func


class MeetingEvent(Base):
    """
    Append-only ordered log of everything that happens in a boardroom meeting.
    Serves as: live-stream source (Redis pub/sub), audit trail, and SSE replay buffer.
    `seq` is monotonically increasing per meeting and used as SSE Last-Event-ID.
    """
    __tablename__ = "meeting_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String, ForeignKey("agent_meetings.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    seq = Column(Integer, nullable=False)           # ordered, resumable
    event_type = Column(String, nullable=False)
    # meeting.started | phase.changed | agent.thinking | agent.completed | agent.failed |
    # evidence.added | critique.posted | synthesis.posted |
    # action.proposed | action.approved | action.rejected | action.executed |
    # meeting.completed | meeting.failed | meeting.cancelled
    phase = Column(String, nullable=True)           # boardroom phase at time of event
    actor = Column(String, nullable=True)           # agent name, user ID, or "system"
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MeetingEvidence(Base):
    """
    Typed, trust-scored evidence sources collected before agent analysis begins.
    Each row is a source the agents can cite by `source_ref`.
    The `redacted` flag allows PII-safe exports.
    """
    __tablename__ = "meeting_evidence"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String, ForeignKey("agent_meetings.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    source_ref = Column(String, nullable=False)     # e.g., "ticket:abc123", "knowledge:xyz"
    source_type = Column(String, nullable=False)
    # support_ticket | knowledge_base | db_query | credential_inventory | meeting_context
    trust_score = Column(Integer, nullable=True)    # 0-100 overall
    freshness_score = Column(Integer, nullable=True)
    reliability_score = Column(Integer, nullable=True)
    completeness_score = Column(Integer, nullable=True)
    excerpt = Column(Text, nullable=True)           # short human-readable summary
    redacted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MeetingAction(Base):
    """
    A proposed action item from the boardroom, with risk-tiered approval state.
    Replaces the ad-hoc `action_items` JSON column with a proper governance record.
    `idempotency_key` ensures retries never create duplicate leads/replies/promotions.
    """
    __tablename__ = "meeting_actions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String, ForeignKey("agent_meetings.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    action_type = Column(String, nullable=False)
    # create_lead | send_customer_reply | promote_candidate | update_ticket_status |
    # create_internal_note | tag_lead | unknown
    assigned_to = Column(String, nullable=False)    # e.g., "Sales AI", "Support AI"
    description = Column(Text, nullable=False)
    risk_tier = Column(String, nullable=False)      # low | medium | high
    status = Column(String, default="pending")
    # pending | awaiting_approval | executing | completed | failed | rejected
    idempotency_key = Column(String, nullable=True, unique=True)
    approved_by = Column(String, nullable=True)     # user ID, "auto", or "auto-confidence"
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_by = Column(String, nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    result = Column(JSON, nullable=True)            # execution output
    evidence_ids = Column(JSON, default=list)       # list of MeetingEvidence.id
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
