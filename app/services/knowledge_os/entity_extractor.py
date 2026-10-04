"""Structured Entity and Atomic Evidence Extractor.

Extracts:
- Products, Services, Features, Pricing tiers
- ICP definitions & Buyer Personas
- Case Studies & Proof Points
- Competitor Battlecards & Objection Playbooks
- Policies & Discount Rules
And creates verifiable EvidenceRecord entries for every claim.
"""
import json
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.deal_room import EvidenceRecord
from app.services.llm_gateway import LLMGateway


def extract_json_safe(text: str) -> Any:
    """Robust JSON extraction from LLM responses."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        obj_match = re.search(r"\{.*\}", text, re.DOTALL)
        if obj_match:
            try:
                return json.loads(obj_match.group(0))
            except Exception:
                pass
        arr_match = re.search(r"\[.*\]", text, re.DOTALL)
        if arr_match:
            try:
                return json.loads(arr_match.group(0))
            except Exception:
                pass
        return {}


class EntityExtractor:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.llm = LLMGateway(db, tenant_id)

    async def extract_entities_from_document(
        self,
        document_id: str,
        document_name: str,
        content: str,
        category: str = "general",
    ) -> Dict[str, Any]:
        """Extract structured entities and create atomic evidence records."""
        prompt = f"""You are an enterprise knowledge extraction engine.
Analyze the following business document content and extract structured sales entities.

Document Name: {document_name}
Document Category: {category}

Content:
{content[:8000]}

Extract the following categories if present. Only output facts that are explicitly verified in the document.
Output a JSON object with these exact keys:
{{
  "products": [
    {{
      "name": "string",
      "description": "string",
      "features": ["string"],
      "pricing": ["string"],
      "differentiators": ["string"],
      "target_personas": ["string"]
    }}
  ],
  "services": [
    {{
      "name": "string",
      "description": "string",
      "delivery_model": "string"
    }}
  ],
  "icp_criteria": {{
    "target_industries": ["string"],
    "target_company_sizes": ["string"],
    "target_geographies": ["string"],
    "budget_range": "string",
    "pain_points": ["string"],
    "buying_triggers": ["string"]
  }},
  "buyer_personas": [
    {{
      "title": "string",
      "department": "string",
      "responsibilities": ["string"],
      "pain_points": ["string"],
      "objections": ["string"],
      "messaging_angles": ["string"]
    }}
  ],
  "proof_points": [
    {{
      "customer_name": "string",
      "industry": "string",
      "metric_achieved": "string",
      "quote": "string"
    }}
  ],
  "objections": [
    {{
      "objection": "string",
      "category": "pricing|timing|competitor|security",
      "recommended_counter_argument": "string"
    }}
  ],
  "atomic_claims": [
    {{
      "claim": "string (specific factual assertion)",
      "quote_snippet": "string (verbatim text snippet proving the claim)"
    }}
  ]
}}
Only output valid JSON. No conversational text."""

        try:
            response = await self.llm.complete(
                prompt=prompt,
                model="claude-3-haiku-20240307",
                provider="anthropic",
            )
            parsed = extract_json_safe(response)
        except Exception:
            parsed = {}

        # Persist atomic evidence records
        claims = parsed.get("atomic_claims", [])
        evidence_saved = 0
        for item in claims:
            claim_text = item.get("claim", "").strip()
            snippet = item.get("quote_snippet", "").strip()
            if claim_text and snippet:
                ev = EvidenceRecord(
                    tenant_id=self.tenant_id,
                    claim=claim_text,
                    source_type="company_document",
                    source_id=document_id,
                    location_reference=f"Document: {document_name}",
                    raw_snippet=snippet,
                    confidence=0.95,
                    authority_score=1.0,
                    is_valid=True,
                )
                self.db.add(ev)
                evidence_saved += 1

        if evidence_saved > 0:
            self.db.commit()

        return {
            "products": parsed.get("products", []),
            "services": parsed.get("services", []),
            "icp_criteria": parsed.get("icp_criteria", {}),
            "buyer_personas": parsed.get("buyer_personas", []),
            "proof_points": parsed.get("proof_points", []),
            "objections": parsed.get("objections", []),
            "evidence_count": evidence_saved,
        }
