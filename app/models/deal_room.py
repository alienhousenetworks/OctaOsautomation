"""Persistent Deal Room, Buying Committee, Signals, Objections, Suppression, and Sales Context models."""
import uuid
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Float,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from app.models.base import Base


class SuppressionRecord(Base):
    """3-point suppression registry (discovery, compose, send) for DNC, unsubscribes, bounces."""
    __tablename__ = "suppression_records"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    identifier_type = Column(String, nullable=False, index=True)  # email | domain | phone
    identifier_value = Column(String, nullable=False, index=True)
    reason = Column(String, nullable=False)  # unsubscribe | bounced | manual_dnc | complaint | invalid_format
    origin = Column(String, default="system")  # user | webhook | bounce_detector | import
    notes = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "identifier_type", "identifier_value", name="uq_tenant_suppression"),
    )


class DealRoom(Base):
    """Persistent account-level Deal Room state machine."""
    __tablename__ = "deal_rooms"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    organization_id = Column(String, nullable=True, index=True)
    
    company_name = Column(String, nullable=False, index=True)
    domain = Column(String, nullable=False, index=True)
    website = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    employee_count = Column(Integer, nullable=True)
    annual_revenue_usd = Column(Float, nullable=True)
    country = Column(String, nullable=True)
    city = Column(String, nullable=True)
    tech_stack = Column(JSON, default=list)
    
    # Deal State & Stage
    stage = Column(String, default="discovered", index=True)
    # discovered | qualified | researching | outreach_ready | in_cadence | replied | meeting_booked | proposal | closing | won | lost | nurtured
    
    # Explainable Scoring Dimensions
    icp_fit_score = Column(Float, default=0.0)         # 0.0 - 1.0 (firmographic/technographic fit)
    timing_score = Column(Float, default=0.0)          # 0.0 - 1.0 (signal velocity with decay)
    evidence_score = Column(Float, default=0.0)        # 0.0 - 1.0 (coverage of verified facts)
    accessibility_score = Column(Float, default=0.0)   # 0.0 - 1.0 (contactability & verified channels)
    priority_index = Column(Float, default=0.0)        # Fit * Timing * Evidence * Accessibility
    calibrated_win_prob = Column(Float, default=0.0)   # Bayesian / conversion calibrated probability
    
    # Multi-threading status
    is_multi_threaded = Column(Boolean, default=False)
    committee_coverage = Column(Float, default=0.0)    # % of key personas identified & verified
    
    # Risk flags & Next Best Action
    risk_flags = Column(JSON, default=list)            # ["single_threaded", "stalled_7_days", "unresolved_objection"]
    next_best_action = Column(JSON, default=dict)      # {"action": "email_cro", "persona": "CRO", "reason": "...", "confidence": 0.9}
    assigned_human_id = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Raw research & context
    account_brief = Column(JSON, default=dict)         # Executive Intelligence Brief
    pain_hypotheses = Column(JSON, default=list)       # [{"signal": "...", "inference": "...", "confidence": 0.85}]
    solution_matches = Column(JSON, default=list)      # [{"pain": "...", "product": "...", "proof_point": "..."}]
    
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "domain", name="uq_tenant_deal_room_domain"),
    )


class BuyingCommitteeMember(Base):
    """Stakeholder in the multi-threaded buying committee for an account."""
    __tablename__ = "buying_committee_members"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_room_id = Column(String, ForeignKey("deal_rooms.id"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=True)
    title = Column(String, nullable=False)
    role_type = Column(String, default="influencer")  # economic_buyer | champion | influencer | technical | gatekeeper
    department = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    
    engagement_state = Column(String, default="uncontacted")  # uncontacted | contacted | replied | meeting_attended | opted_out
    provenance = Column(JSON, default=dict)                   # {"source": "apollo", "confidence": 0.95, "verified_at": "..."}
    messaging_angle = Column(String, nullable=True)           # role-specific value angle
    
    last_contacted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint("deal_room_id", "email", name="uq_deal_room_member_email"),
    )


class AccountSignal(Base):
    """Temporal buying signals and intent events with decay half-life."""
    __tablename__ = "account_signals"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_room_id = Column(String, ForeignKey("deal_rooms.id"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    
    signal_type = Column(String, nullable=False, index=True) # funding | hiring_expansion | executive_change | tech_migration | public_statement
    headline = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    evidence_url = Column(String, nullable=True)
    confidence = Column(Float, default=1.0)
    decay_half_life_days = Column(Integer, default=14)
    
    is_active = Column(Boolean, default=True)
    observed_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DealObjection(Base):
    """Tracked objections raised in sales conversations and applied counter-arguments."""
    __tablename__ = "deal_objections"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_room_id = Column(String, ForeignKey("deal_rooms.id"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    committee_member_id = Column(String, ForeignKey("buying_committee_members.id"), nullable=True)
    
    objection_category = Column(String, nullable=False)  # pricing | timing | competitor | authority | security_compliance
    prospect_statement = Column(Text, nullable=False)
    applied_counter_argument = Column(Text, nullable=True)
    provenance_playbook_id = Column(String, nullable=True)
    status = Column(String, default="open")  # open | resolved | conceded | escalated_to_human
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DealActivity(Base):
    """Chronological event log across all stakeholders and channels in a Deal Room."""
    __tablename__ = "deal_activities"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_room_id = Column(String, ForeignKey("deal_rooms.id"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    committee_member_id = Column(String, ForeignKey("buying_committee_members.id"), nullable=True)
    
    activity_type = Column(String, nullable=False, index=True)
    # email_sent | email_opened | email_replied | whatsapp_sent | whatsapp_replied | meeting_scheduled | signal_detected | note_added | stage_changed
    channel = Column(String, nullable=True)
    direction = Column(String, default="outbound")  # inbound | outbound | internal
    subject = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EvidenceRecord(Base):
    """Atomic claims and evidence provenance from primary sources."""
    __tablename__ = "evidence_records"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    
    claim = Column(Text, nullable=False)               # "Product supports HIPAA encryption"
    source_type = Column(String, nullable=False)       # company_doc | crm | public_web | verified_signal
    source_id = Column(String, nullable=False)         # doc_id or verified URL
    location_reference = Column(String, nullable=True) # "Page 14, Table 3"
    raw_snippet = Column(Text, nullable=False)         # Exact verified quote
    
    confidence = Column(Float, default=1.0)
    authority_score = Column(Float, default=1.0)
    observed_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_valid = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CompanySalesContext(Base):
    """Materialized, versioned Company Sales Context for Background Capabilities."""
    __tablename__ = "company_sales_contexts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    
    company_overview = Column(JSON, nullable=False, default=dict)
    products_catalog = Column(JSON, nullable=False, default=list)
    services_catalog = Column(JSON, nullable=False, default=list)
    icp_definitions = Column(JSON, nullable=False, default=dict)
    buyer_personas = Column(JSON, nullable=False, default=list)
    proof_points = Column(JSON, nullable=False, default=list)
    competitor_battlecards = Column(JSON, nullable=False, default=list)
    objection_playbook = Column(JSON, nullable=False, default=dict)
    policies = Column(JSON, nullable=False, default=dict)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
