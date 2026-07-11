from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base
import uuid
from sqlalchemy.sql import func

# --- SALES & MARKETING (Phase 1) ---

class Lead(Base):
    __tablename__ = "leads"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(String, nullable=True, index=True)
    name = Column(String)
    email = Column(String, index=True)
    phone = Column(String)
    company = Column(String)
    source = Column(String)
    score = Column(Integer, default=0)
    status = Column(String, default="captured")
    personal_email = Column(String, nullable=True)
    company_email = Column(String, nullable=True)
    mobile_no = Column(String, nullable=True)
    company_contact_no = Column(String, nullable=True)
    need_of_what = Column(Text, nullable=True)
    how_much = Column(String, nullable=True)
    why = Column(Text, nullable=True)
    target_context = Column(Text, nullable=True)
    priority = Column(String, default="medium")
    assigned_to = Column(String, default="Sales AI Agent", nullable=True)
    data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ContentPost(Base):
    __tablename__ = "content_posts"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(String, nullable=True, index=True)
    platform = Column(String)
    content = Column(Text)
    image_url = Column(String, nullable=True)
    video_url = Column(String, nullable=True)
    media_prompt = Column(Text, nullable=True)
    media_prompt_enabled = Column(Boolean, default=False)
    image_prompt = Column(Text, nullable=True)
    image_prompt_enabled = Column(Boolean, default=False)
    video_prompt = Column(Text, nullable=True)
    video_prompt_enabled = Column(Boolean, default=False)
    remotion_prompt = Column(Text, nullable=True)
    remotion_prompt_enabled = Column(Boolean, default=False)
    remotion_provider = Column(String, default="gemini")
    remotion_model = Column(String, default="gemini-2.5-flash")

    is_manual_media = Column(Boolean, default=False)
    day = Column(Integer, nullable=True)
    status = Column(String, default="draft")
    approval_status = Column(String, default="pending") # pending, approved, rejected, published
    scheduled_at = Column(DateTime(timezone=True))
    published_at = Column(DateTime(timezone=True))
    # Platform publish + analytics
    external_post_id = Column(String, nullable=True, index=True)  # FB/IG/LinkedIn id after publish
    external_url = Column(String, nullable=True)
    impressions = Column(Float, default=0.0)
    reach = Column(Float, default=0.0)
    engagement = Column(Float, default=0.0)  # likes+comments+shares+saves aggregate
    likes = Column(Float, default=0.0)
    comments = Column(Float, default=0.0)
    shares = Column(Float, default=0.0)
    clicks = Column(Float, default=0.0)
    ctr = Column(Float, default=0.0)  # clicks / impressions
    engagement_rate = Column(Float, default=0.0)  # engagement / impressions
    performance_score = Column(Float, default=0.0)  # 0-100 learned quality signal
    insights_raw = Column(JSON, default=dict)
    insights_synced_at = Column(DateTime(timezone=True), nullable=True)
    learning_tags = Column(JSON, default=list)  # e.g. ["question_hook", "short_cta"]
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MarketingInsightSnapshot(Base):
    """Time-series snapshots of post performance for learning curves."""
    __tablename__ = "marketing_insight_snapshots"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    post_id = Column(String, ForeignKey("content_posts.id"), nullable=False, index=True)
    platform = Column(String, nullable=True)
    impressions = Column(Float, default=0.0)
    reach = Column(Float, default=0.0)
    engagement = Column(Float, default=0.0)
    likes = Column(Float, default=0.0)
    comments = Column(Float, default=0.0)
    shares = Column(Float, default=0.0)
    clicks = Column(Float, default=0.0)
    ctr = Column(Float, default=0.0)
    engagement_rate = Column(Float, default=0.0)
    raw = Column(JSON, default=dict)
    captured_at = Column(DateTime(timezone=True), server_default=func.now())


class MarketingLearningPattern(Base):
    """What works / fails for this tenant — used to improve generation prompts."""
    __tablename__ = "marketing_learning_patterns"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    platform = Column(String, nullable=True, index=True)  # linkedin, facebook, instagram, or null=all
    pattern_type = Column(String, nullable=False)  # hook_style, cta, length, emoji, media_type, topic
    pattern_key = Column(String, nullable=False)  # e.g. "question_open", "short_cta", "with_image"
    sample_count = Column(Integer, default=0)
    avg_engagement_rate = Column(Float, default=0.0)
    avg_ctr = Column(Float, default=0.0)
    avg_performance_score = Column(Float, default=0.0)
    weight = Column(Float, default=0.0)  # positive = boost, negative = avoid
    examples = Column(JSON, default=list)  # short content samples
    banned = Column(Boolean, default=False)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# --- LEGAL (Phase 4) ---

class Contract(Base):
    __tablename__ = "contracts"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(String, nullable=True, index=True)
    title = Column(String)
    file_url = Column(String)
    risk_score = Column(String) # Critical, Advisory, Informational
    analysis = Column(JSON)
    approval_status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# --- FINANCE (Phase 4) ---

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(String, nullable=True, index=True)
    amount = Column(Float)
    currency = Column(String, default="INR")
    description = Column(String)
    is_anomaly = Column(Boolean, default=False)
    category = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

# --- HR (Phase 5) ---

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(String, nullable=True, index=True)
    name = Column(String)
    email = Column(String)
    role = Column(String)
    scorecard = Column(JSON)
    status = Column(String, default="sourced") # sourced, screened, interviewed, offered, hired
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# --- SUPPORT (Phase 3) ---

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(String, nullable=True, index=True)
    subject = Column(String)
    description = Column(Text)
    status = Column(String, default="open")
    priority = Column(String, default="medium")
    channel = Column(String) # email, whatsapp, chat
    customer_contact = Column(String, nullable=True) # email address or whatsapp number
    approval_status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    messages = relationship("TicketMessage", back_populates="ticket", cascade="all, delete-orphan")

class TicketMessage(Base):
    __tablename__ = "ticket_messages"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    ticket_id = Column(String, ForeignKey("tickets.id"), nullable=False)
    sender = Column(String) # "customer" or "agent"
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    ticket = relationship("Ticket", back_populates="messages")

class AgentMeeting(Base):
    __tablename__ = "agent_meetings"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(String, nullable=True, index=True)
    title = Column(String, nullable=False)
    status = Column(String, default="active") # active, completed
    trigger_type = Column(String) # support_ticket, transaction_anomaly, candidate_hiring, manual
    trigger_id = Column(String, nullable=True) # ID of ticket, lead, candidate, etc.
    context_summary = Column(Text, nullable=True)
    participants = Column(JSON, nullable=False) # list of agent names e.g., ["Support AI", "Sales AI", "CEO AI"]
    transcript = Column(JSON, default=[]) # list of message objects
    action_items = Column(JSON, default=[]) # list of action item objects
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class BusinessProfile(Base):
    __tablename__ = "business_profiles"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(String, nullable=True, index=True)
    company_name = Column(String, nullable=True)
    website = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    service_description = Column(Text, nullable=True)
    target_countries = Column(JSON, nullable=True)
    target_industries = Column(JSON, nullable=True)
    target_company_size = Column(String, nullable=True)
    target_budget_range = Column(String, nullable=True)
    target_decision_makers = Column(JSON, nullable=True)
    usp = Column(Text, nullable=True)
    case_studies = Column(Text, nullable=True)
    offer_details = Column(Text, nullable=True)
    calendars = Column(JSON, nullable=True)
    communication_channels = Column(JSON, nullable=True)
    extra_context = Column(Text, nullable=True)
    v3_workflow_status = Column(JSON, nullable=True)
    sales_emails = Column(JSON, nullable=True)
    support_emails = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Contact(Base):
    __tablename__ = "contacts"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(String, nullable=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, index=True, nullable=True)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(String, nullable=True, index=True)
    name = Column(String, nullable=False)
    status = Column(String, default="draft")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(String, nullable=True, index=True)
    sender = Column(String, nullable=True)
    recipient = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    channel = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(String, nullable=True, index=True)
    title = Column(String, nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Integration(Base):
    __tablename__ = "integrations"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(String, nullable=True, index=True)
    provider = Column(String, nullable=False)
    config = Column(JSON, default={})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    organization_id = Column(String, nullable=True, index=True)
    user_id = Column(String, nullable=True)
    action = Column(String, nullable=False)
    resource = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

