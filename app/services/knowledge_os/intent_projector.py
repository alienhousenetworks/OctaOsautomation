"""Unified Knowledge Base Intent Projection Engine.

Workstream A:
- One single source of truth across all enterprise sections
- Projects context dynamically based on IntentType
- Strictly enforces KnowledgeAccessController boundaries (zero confidential leakage)
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.agents import KnowledgeDocument
from app.models.deal_room import EvidenceRecord, CompanySalesContext
from app.models.verticals import BusinessProfile
from app.services.knowledge_os.access_controller import (
    KnowledgeAccessController,
    IntentType,
    DataClassification,
)
from app.services.llm_gateway import LLMGateway
from app.services.knowledge_os.entity_extractor import extract_json_safe


class CampaignContextProjection(BaseModel):
    """Projection tailored for Marketing, Social Media, and Creative Campaigns."""
    company_name: str
    website: str
    industry: str
    brand_voice: Dict[str, Any] = Field(
        default_factory=lambda: {
            "tone": "Authoritative, Innovative, Pragmatic",
            "vocabulary": ["Autonomous", "Enterprise", "Reliable"],
            "banned_words": ["Revolutionary", "Game-changer", "Miracle"],
        }
    )
    visual_style: Dict[str, Any] = Field(
        default_factory=lambda: {
            "primary_color": "#059669",
            "accent_color": "#0F172A",
            "mood": "Editorial, Architectural, High-Tech",
            "photography_guidelines": "Natural lighting, authentic textures, no plastic skin",
        }
    )
    approved_claims: List[Dict[str, Any]] = Field(default_factory=list)
    product_highlights: List[Dict[str, Any]] = Field(default_factory=list)
    target_audiences: List[Dict[str, Any]] = Field(default_factory=list)
    compliance_rules: List[str] = Field(
        default_factory=lambda: [
            "Never guarantee specific financial ROI without disclaimers.",
            "Do not cite competitor pricing without verifiable timestamp.",
            "All statistics must map to an approved evidence record.",
        ]
    )
    source_documents_used: List[str] = Field(default_factory=list)


class SalesContextProjection(BaseModel):
    """Projection tailored for B2B Outbound Sales and Deal Desk."""
    company_name: str
    icp_definitions: Dict[str, Any] = Field(default_factory=dict)
    buyer_personas: List[Dict[str, Any]] = Field(default_factory=list)
    products_catalog: List[Dict[str, Any]] = Field(default_factory=list)
    pricing_tiers: List[Dict[str, Any]] = Field(default_factory=list)
    objection_playbook: Dict[str, str] = Field(default_factory=dict)
    competitor_battlecards: List[Dict[str, Any]] = Field(default_factory=list)
    source_documents_used: List[str] = Field(default_factory=list)


class EmailContextProjection(BaseModel):
    """Projection tailored for Email sequences and Inbound Replies."""
    company_name: str
    tone: str = "Concise, Professional, Value-first"
    max_length_words: int = 150
    subject_line_rules: List[str] = Field(
        default_factory=lambda: [
            "Max 6 words",
            "No spam trigger words (Free, Urgent, Act Now)",
            "Personalized with prospect company name",
        ]
    )
    mandatory_footer: str = "Reply STOP to unsubscribe."
    approved_proof_points: List[str] = Field(default_factory=list)


class CompanyContextProjectionEngine:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.llm = LLMGateway(db, tenant_id)

    async def get_projection(
        self,
        intent: IntentType = IntentType.CAMPAIGN_MARKETING,
        platform: Optional[str] = None,
        user_role: str = "member",
    ) -> Dict[str, Any]:
        """Synthesize unified knowledge into an intent-specific projection."""
        # 1. Fetch all tenant documents
        raw_docs = (
            self.db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.tenant_id == self.tenant_id,
                KnowledgeDocument.is_active == True,  # noqa: E712
            )
            .all()
        )

        # 2. Strict Security & Access Filtering
        authorized_docs = KnowledgeAccessController.filter_documents_for_intent(
            raw_docs, intent=intent, user_role=user_role
        )

        # 3. Fetch verified atomic evidence records
        verified_evidence = (
            self.db.query(EvidenceRecord)
            .filter(
                EvidenceRecord.tenant_id == self.tenant_id,
                EvidenceRecord.is_valid == True,  # noqa: E712
            )
            .all()
        )

        # 4. Fetch business profile (base fallback)
        profile = (
            self.db.query(BusinessProfile)
            .filter(BusinessProfile.tenant_id == self.tenant_id)
            .first()
        )

        company_name = profile.company_name if profile else "Enterprise System"
        website = profile.website if profile else ""
        industry = profile.industry if profile else "Technology"

        # 5. Format based on requested intent
        if intent == IntentType.CAMPAIGN_MARKETING:
            return self._build_campaign_projection(
                company_name=company_name,
                website=website,
                industry=industry,
                profile=profile,
                authorized_docs=authorized_docs,
                verified_evidence=verified_evidence,
                platform=platform,
            )
        elif intent == IntentType.SALES_OUTREACH:
            return self._build_sales_projection(
                company_name=company_name,
                profile=profile,
                authorized_docs=authorized_docs,
                verified_evidence=verified_evidence,
            )
        elif intent == IntentType.EMAIL_COMMUNICATION:
            return self._build_email_projection(
                company_name=company_name,
                profile=profile,
                verified_evidence=verified_evidence,
            )
        else:
            # General fallback projection
            return {
                "intent": intent.value,
                "company_name": company_name,
                "authorized_document_count": len(authorized_docs),
                "verified_evidence_count": len(verified_evidence),
            }

    def _build_campaign_projection(
        self,
        company_name: str,
        website: str,
        industry: str,
        profile: Optional[BusinessProfile],
        authorized_docs: List[KnowledgeDocument],
        verified_evidence: List[EvidenceRecord],
        platform: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assemble marketing-safe projection with verified proof points."""
        approved_claims = [
            {
                "evidence_id": e.id,
                "claim": e.claim,
                "source": e.source_type,
                "confidence": e.confidence,
            }
            for e in verified_evidence[:20]
        ]

        doc_summaries = []
        for d in authorized_docs:
            doc_summaries.append(f"[{d.doc_type} ({d.department})]: {d.content[:400]}")

        # Extract or fallback brand voice
        brand_voice = {
            "tone": "Visionary yet grounded, crisp B2B editorial",
            "vocabulary": ["Precision", "Autonomous", "Scalable", "Resilient"],
            "banned_words": ["Guaranteed riches", "Magic", "Cheat code", "10x overnight"],
        }
        visual_style = {
            "primary_color": "#059669",
            "secondary_color": "#0F172A",
            "accent_color": "#38BDF8",
            "mood": "Cinematic high-contrast, authentic textures, architectural minimalism",
            "platform": platform or "multi-channel",
        }

        projection = CampaignContextProjection(
            company_name=company_name,
            website=website,
            industry=industry,
            brand_voice=brand_voice,
            visual_style=visual_style,
            approved_claims=approved_claims,
            product_highlights=[
                {
                    "name": profile.company_name if profile else "Product",
                    "usp": profile.usp if profile else "Enterprise automation platform",
                    "offer": profile.offer_details if profile else "Request a product demonstration",
                }
            ],
            target_audiences=[
                {
                    "title": profile.target_decision_makers if profile else "VP / Director",
                    "industries": profile.target_industries if profile else "B2B SaaS, Technology",
                    "budget": profile.target_budget_range if profile else "Mid-Market to Enterprise",
                }
            ],
            source_documents_used=[d.id for d in authorized_docs],
        )

        return projection.model_dump()

    def _build_sales_projection(
        self,
        company_name: str,
        profile: Optional[BusinessProfile],
        authorized_docs: List[KnowledgeDocument],
        verified_evidence: List[EvidenceRecord],
    ) -> Dict[str, Any]:
        """Assemble sales-focused projection."""
        # Check if materialized sales context exists
        ctx = (
            self.db.query(CompanySalesContext)
            .filter(
                CompanySalesContext.tenant_id == self.tenant_id,
                CompanySalesContext.is_active == True,  # noqa: E712
            )
            .first()
        )

        if ctx:
            return {
                "company_name": company_name,
                "icp_definitions": ctx.icp_definitions or {},
                "buyer_personas": ctx.buyer_personas or [],
                "products_catalog": ctx.products_catalog or [],
                "pricing_tiers": ctx.pricing_tiers or [],
                "objection_playbook": ctx.objection_playbook or {},
                "competitor_battlecards": ctx.competitor_battlecards or [],
                "source_documents_used": [d.id for d in authorized_docs],
            }

        projection = SalesContextProjection(
            company_name=company_name,
            icp_definitions={"industries": [profile.target_industries if profile else "Technology"]},
            products_catalog=[{"name": company_name, "description": profile.service_description if profile else ""}],
            pricing_tiers=[{"tier": "Custom", "budget": profile.target_budget_range if profile else "1L-5L"}],
            source_documents_used=[d.id for d in authorized_docs],
        )
        return projection.model_dump()

    def _build_email_projection(
        self,
        company_name: str,
        profile: Optional[BusinessProfile],
        verified_evidence: List[EvidenceRecord],
    ) -> Dict[str, Any]:
        """Assemble email-focused projection."""
        proof_points = [e.claim for e in verified_evidence[:5]]
        projection = EmailContextProjection(
            company_name=company_name,
            approved_proof_points=proof_points,
        )
        return projection.model_dump()
