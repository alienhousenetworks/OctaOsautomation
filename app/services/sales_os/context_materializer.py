"""Company Sales Context Materializer (Background Capabilities 1–6).

Synthesizes:
1. Company Intelligence (Overview, mission, geography, business model)
2. Product Intelligence (Catalog, features, pricing, differentiators)
3. ICP Intelligence (Firmographic criteria, technographics, buying signals)
4. Buyer Persona Intelligence (Key personas, responsibilities, pain points)
5. Market Intelligence (Industry trends, external context)
6. Competitor Intelligence (Battlecards, competitor pricing, objection playbooks)

Materializes into a versioned `CompanySalesContext` record for sub-5ms agent retrieval.
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.deal_room import CompanySalesContext, EvidenceRecord
from app.models.verticals import BusinessProfile
from app.models.agents import KnowledgeDocument
from app.services.llm_gateway import LLMGateway
from app.services.knowledge_os.entity_extractor import extract_json_safe


class SalesContextMaterializer:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.llm = LLMGateway(db, tenant_id)

    async def materialize_context(self, force_new_version: bool = False) -> CompanySalesContext:
        """Execute background intelligence extraction and materialize CompanySalesContext."""
        # 1. Fetch current profile & documents
        profile = (
            self.db.query(BusinessProfile)
            .filter(BusinessProfile.tenant_id == self.tenant_id)
            .first()
        )
        docs = (
            self.db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.tenant_id == self.tenant_id)
            .all()
        )

        doc_summary = "\n\n".join([f"[{d.doc_type} ({d.department})]:\n{d.content[:1500]}" for d in docs[:10]])

        # 2. Query Background Intelligence Synthesis
        prompt = f"""You are the OctaOS Background Intelligence Synthesis Engine.
Synthesize the authoritative Company Sales Context from the company profile and verified documents below.

Business Profile:
Company Name: {profile.company_name if profile else 'Target Enterprise'}
Website: {profile.website if profile else ''}
Industry: {profile.industry if profile else ''}
Service Description: {profile.service_description if profile else ''}
Target Budget Range: {profile.target_budget_range if profile else '1L-5L'}
USP: {profile.usp if profile else ''}
Offer Details: {profile.offer_details if profile else ''}

Knowledge Documents:
{doc_summary if doc_summary else 'No additional documents uploaded yet.'}

Output a comprehensive JSON object matching this schema:
{{
  "company_overview": {{
    "name": "string",
    "website": "string",
    "industry": "string",
    "business_model": "B2B SaaS / Agency / Service / Enterprise",
    "core_value_prop": "string",
    "usp": "string"
  }},
  "products_catalog": [
    {{
      "name": "string",
      "description": "string",
      "features": ["string"],
      "pricing_tier": "string",
      "differentiators": ["string"]
    }}
  ],
  "services_catalog": [],
  "icp_definitions": {{
    "industries": ["string"],
    "company_sizes": ["string"],
    "budget_range": "string",
    "key_pain_points": ["string"],
    "buying_triggers": ["string"]
  }},
  "buyer_personas": [
    {{
      "title": "string",
      "department": "string",
      "priorities": ["string"],
      "pain_points": ["string"],
      "preferred_angle": "string"
    }}
  ],
  "proof_points": [],
  "competitor_battlecards": [],
  "objection_playbook": {{
    "pricing": ["string counter-arguments"],
    "timing": ["string counter-arguments"],
    "competitor": ["string counter-arguments"]
  }},
  "policies": {{
    "max_discount_pct": 10,
    "require_human_approval_over_usd": 5000
  }}
}}
Return only valid JSON."""

        try:
            resp = await self.llm.complete(prompt=prompt, model="claude-3-haiku-20240307", provider="anthropic")
            synthesized = extract_json_safe(resp)
        except Exception:
            synthesized = {}

        if not synthesized or not synthesized.get("icp_definitions"):
            ev_records = self.db.query(EvidenceRecord).filter(EvidenceRecord.tenant_id == self.tenant_id).all()
            inferred_industries = []
            for ev in ev_records:
                if "saas" in ev.claim.lower():
                    inferred_industries.append("SaaS")
            if not inferred_industries and profile and profile.industry:
                inferred_industries.append(profile.industry)
            if not inferred_industries:
                inferred_industries = ["SaaS", "Technology"]

            synthesized = {
                "company_overview": {
                    "name": profile.company_name if profile else "Company",
                    "industry": inferred_industries[0],
                },
                "products_catalog": [],
                "services_catalog": [],
                "icp_definitions": {
                    "industries": inferred_industries,
                    "min_employees": 50,
                    "max_employees": 1000,
                },
                "buyer_personas": [],
                "proof_points": [e.claim for e in ev_records],
                "competitor_battlecards": [],
                "objection_playbook": {},
                "policies": {"max_discount_pct": 15},
            }

        # 3. Determine version number
        latest = (
            self.db.query(CompanySalesContext)
            .filter(CompanySalesContext.tenant_id == self.tenant_id)
            .order_by(CompanySalesContext.version.desc())
            .first()
        )
        new_version = (latest.version + 1) if latest else 1

        # Deactivate old versions
        if latest:
            self.db.query(CompanySalesContext).filter(
                CompanySalesContext.tenant_id == self.tenant_id
            ).update({"is_active": False})

        # 4. Save new active materialized context
        ctx = CompanySalesContext(
            tenant_id=self.tenant_id,
            version=new_version,
            company_overview=synthesized.get("company_overview", {}),
            products_catalog=synthesized.get("products_catalog", []),
            services_catalog=synthesized.get("services_catalog", []),
            icp_definitions=synthesized.get("icp_definitions", {}),
            buyer_personas=synthesized.get("buyer_personas", []),
            proof_points=synthesized.get("proof_points", []),
            competitor_battlecards=synthesized.get("competitor_battlecards", []),
            objection_playbook=synthesized.get("objection_playbook", {}),
            policies=synthesized.get("policies", {}),
            is_active=True,
        )
        self.db.add(ctx)
        self.db.commit()
        self.db.refresh(ctx)
        return ctx

    def materialize(self) -> CompanySalesContext:
        """Synchronous wrapper for materializing context."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self.materialize_context()).result()
            return loop.run_until_complete(self.materialize_context())
        except Exception:
            return asyncio.run(self.materialize_context())

    def get_active_context(self) -> Optional[CompanySalesContext]:
        """Fetch current active materialized context in sub-5ms."""
        return (
            self.db.query(CompanySalesContext)
            .filter(
                CompanySalesContext.tenant_id == self.tenant_id,
                CompanySalesContext.is_active == True,  # noqa: E712
            )
            .first()
        )


ContextMaterializer = SalesContextMaterializer
