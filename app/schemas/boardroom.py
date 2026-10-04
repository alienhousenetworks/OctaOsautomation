"""
boardroom.py — Pydantic schemas for boardroom V2.

These schemas are used to:
1. Validate LLM JSON output (agents must return conforming objects)
2. Provide typed API response shapes for the frontend
3. Enable the grounding check (evidence_ids must reference real evidence)
"""
from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# ---------------------------------------------------------------------------
# Agent output schemas (validated after each LLM call)
# ---------------------------------------------------------------------------

class Finding(BaseModel):
    """A single claim made by a specialist agent, grounded to evidence."""
    claim: str
    evidence_ids: list[str] = Field(default_factory=list)  # must reference MeetingEvidence.source_ref
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ProposedAction(BaseModel):
    """An action recommended by a specialist."""
    assigned_to: str
    description: str
    evidence_ids: list[str] = Field(default_factory=list)


class SpecialistAnalysis(BaseModel):
    """Validated output from a single specialist agent's analysis phase."""
    agent: str
    stance: Literal["support", "oppose", "neutral"] = "neutral"
    summary: str
    findings: list[Finding] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    confidence_rationale: Optional[str] = None


class AgentCritique(BaseModel):
    """Validated output from a specialist agent's critique of other analyses."""
    agent: str
    agreement_points: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class SynthesisActionItem(BaseModel):
    """An action item in the CEO synthesis output."""
    assigned_to: str
    description: str
    sources: list[str] = Field(default_factory=list)


class CEOSynthesis(BaseModel):
    """Validated output from the CEO AI synthesis phase."""
    executive_summary: str
    key_findings: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    financial_impact: list[str] = Field(default_factory=list)
    operational_impact: list[str] = Field(default_factory=list)
    risk_matrix: list[str] = Field(default_factory=list)
    alternative_options: list[str] = Field(default_factory=list)
    expert_disagreements: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    sources: list[str] = Field(default_factory=list)
    action_items: list[SynthesisActionItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API response schemas (frontend consumption)
# ---------------------------------------------------------------------------

class MeetingEventOut(BaseModel):
    id: str
    meeting_id: str
    seq: int
    event_type: str
    phase: Optional[str] = None
    actor: Optional[str] = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingEvidenceOut(BaseModel):
    id: str
    meeting_id: str
    source_ref: str
    source_type: str
    trust_score: Optional[int] = None
    freshness_score: Optional[int] = None
    reliability_score: Optional[int] = None
    completeness_score: Optional[int] = None
    excerpt: Optional[str] = None
    redacted: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingActionOut(BaseModel):
    id: str
    meeting_id: str
    action_type: str
    assigned_to: str
    description: str
    risk_tier: str
    status: str
    idempotency_key: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    result: Optional[dict] = None
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingActionApprove(BaseModel):
    approved_by: str = "user"  # user ID or username


class MeetingActionReject(BaseModel):
    rejected_by: str = "user"
    reason: Optional[str] = None


class ConfidenceBreakdown(BaseModel):
    """Derived confidence score with per-component breakdown for UI display."""
    overall: int = Field(ge=0, le=100)
    evidence_trust: int = Field(ge=0, le=100)
    evidence_freshness: int = Field(ge=0, le=100)
    agent_agreement: int = Field(ge=0, le=100)
    grounding_pass_rate: int = Field(ge=0, le=100)
    rationale: str = ""
