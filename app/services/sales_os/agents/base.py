"""Base Sales Agent and Typed AgentResult Schema.

Guarantees:
- Every capability outputs a structured AgentResult
- Decisions are backed by explicit confidence and evidence
- Reasoning is concise (no raw chain-of-thought exposure)
- Unknowns and missing information are explicitly declared
"""
import uuid
import time
from typing import Generic, TypeVar, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.services.llm_gateway import LLMGateway

T = TypeVar("T")


class EvidenceItem(BaseModel):
    claim: str
    source: str
    citation: Optional[str] = None
    confidence: float = 1.0


class AgentResult(BaseModel, Generic[T]):
    agent_id: str
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    deal_room_id: Optional[str] = None
    lead_id: Optional[str] = None
    decision: str  # qualified | disqualified | action_required | ready | blocked | executed
    confidence: float  # 0.0 to 1.0
    evidence: List[EvidenceItem] = Field(default_factory=list)
    source: str = "internal_kb"
    reasoning_summary: str
    missing_information: List[str] = Field(default_factory=list)
    recommended_next_step: str
    data: Optional[T] = None
    execution_time_ms: int = 0


class BaseSalesAgent:
    def __init__(self, db: Session, tenant_id: str, agent_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.llm = LLMGateway(db, tenant_id)

    async def execute(self, deal_room_id: str, parameters: Dict[str, Any] = None) -> AgentResult:
        raise NotImplementedError("Each capability agent must implement execute()")
