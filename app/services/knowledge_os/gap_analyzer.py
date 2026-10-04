"""Knowledge Gap Analysis Engine.

Identifies missing critical sales assets before outreach:
- Missing pricing or packaging rules
- Missing ICP criteria (industries, revenue bands, size)
- Missing proof points / case studies for target industries
- Missing objection handling playbooks
"""
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.models.agents import KnowledgeDocument
from app.models.deal_room import EvidenceRecord


class KnowledgeGapAnalyzer:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def analyze_gaps(self) -> List[Dict[str, Any]]:
        """Audit the tenant knowledge base for coverage gaps."""
        docs = (
            self.db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.tenant_id == self.tenant_id)
            .all()
        )

        all_text = " ".join([d.content or "" for d in docs]).lower()
        gaps = []

        # 1. Check for pricing documentation
        has_pricing = any(
            d.doc_type.lower() in ("pricing", "rate card", "quotation")
            or "pricing" in (d.content or "").lower()
            for d in docs
        )
        if not has_pricing:
            gaps.append({
                "category": "pricing",
                "severity": "high",
                "title": "Missing Pricing Documentation",
                "description": "No documented pricing tiers, packaging, or rate cards found. Sales AI will be unable to answer pricing inquiries.",
                "suggested_action": "Upload your official pricing sheet or rate card."
            })

        # 2. Check for case studies / customer proof points
        has_case_studies = any(
            "case study" in (d.content or "").lower()
            or "customer story" in (d.content or "").lower()
            or "%" in (d.content or "").lower()
            for d in docs
        )
        if not has_case_studies:
            gaps.append({
                "category": "case_studies",
                "severity": "medium",
                "title": "No Verified Case Studies or Metrics",
                "description": "No customer proof points or ROI metrics detected. Cold outreach will lack social proof.",
                "suggested_action": "Upload at least one customer case study with quantifiable results."
            })

        # 3. Check for competitor battlecards & objections
        has_objections = any(
            "objection" in (d.content or "").lower()
            or "competitor" in (d.content or "").lower()
            or "battlecard" in (d.content or "").lower()
            for d in docs
        )
        if not has_objections:
            gaps.append({
                "category": "objections",
                "severity": "medium",
                "title": "Missing Objection Handling Playbook",
                "description": "No objection handling responses found. The Conversation Agent will rely on generic counter-arguments.",
                "suggested_action": "Upload sales playbooks or common competitor battlecards."
            })

        # 4. Check for compliance/security
        has_security = any(
            w in all_text for w in ["soc2", "soc 2", "gdpr", "hipaa", "iso 27001", "encryption", "compliance"]
        )
        if not has_security:
            gaps.append({
                "category": "security_compliance",
                "severity": "low",
                "title": "No Security or Compliance Documentation",
                "description": "Enterprise prospects frequently ask for security/compliance validation. Deal Desk cannot auto-fill RFPs without this.",
                "suggested_action": "Upload your security whitepaper or compliance certification summary."
            })

        return gaps

    def audit_coverage(self) -> Dict[str, Any]:
        gaps = self.analyze_gaps()
        gap_categories = [g["category"] for g in gaps]
        gap_keys = list(gap_categories)
        for c in gap_categories:
            gap_keys.append(f"missing_{c}")
        return {
            "gaps": gap_keys,
            "gap_details": gaps,
            "missing_case_studies": "case_studies" in gap_categories,
            "missing_pricing": "pricing" in gap_categories,
        }


GapAnalyzer = KnowledgeGapAnalyzer
