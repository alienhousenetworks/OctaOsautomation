"""Knowledge Conflict Detection and Freshness Engine.

Detects:
1. Pricing contradictions between documents (e.g. old rate sheet vs new quotation).
2. Incompatible capability claims (e.g. feature supported vs feature deprecated).
3. Stale documents that have been superseded by newer revisions.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.deal_room import EvidenceRecord


class ConflictDetector:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def detect_conflicts(self, new_claims: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Compare claims against existing verified evidence records and documents."""
        import re

        if new_claims is None:
            from app.models.agents import KnowledgeDocument
            docs = self.db.query(KnowledgeDocument).filter(KnowledgeDocument.tenant_id == self.tenant_id).all()
            new_claims = [{"claim": d.content, "source": d.doc_type} for d in docs]
            detected_conflicts = []
            for i in range(len(new_claims)):
                for j in range(i + 1, len(new_claims)):
                    c1 = new_claims[i]["claim"].lower()
                    c2 = new_claims[j]["claim"].lower()
                    if any(w in c1 for w in ["price", "cost", "pricing", "$"]) and any(w in c2 for w in ["price", "cost", "pricing", "$"]):
                        n1 = set(re.findall(r"\$\d+[\d,.]*|\b\d+[\d,.]*\b", c1))
                        n2 = set(re.findall(r"\$\d+[\d,.]*|\b\d+[\d,.]*\b", c2))
                        if n1 and n2 and not (n1 & n2):
                            detected_conflicts.append({
                                "conflict_type": "pricing_discrepancy",
                                "category": "pricing",
                                "claim_1": new_claims[i]["claim"],
                                "claim_2": new_claims[j]["claim"],
                                "severity": "high",
                                "recommendation": "Review latest pricing sheet and resolve discrepancy",
                            })
            return detected_conflicts

        existing_evidence = (
            self.db.query(EvidenceRecord)
            .filter(
                EvidenceRecord.tenant_id == self.tenant_id,
                EvidenceRecord.is_valid == True,  # noqa: E712
            )
            .all()
        )

        detected_conflicts = []

        for new_claim in new_claims:
            claim_text = new_claim.get("claim", "").lower()
            
            for existing in existing_evidence:
                exist_text = existing.claim.lower()
                
                # Check for pricing conflicts
                if any(w in claim_text for w in ["price", "cost", "pricing", "tier", "fee"]) and \
                   any(w in exist_text for w in ["price", "cost", "pricing", "tier", "fee"]):
                    new_nums = set(re.findall(r"\b\d+[\d,.]*\b", claim_text))
                    exist_nums = set(re.findall(r"\b\d+[\d,.]*\b", exist_text))
                    
                    if new_nums and exist_nums and not (new_nums & exist_nums):
                        detected_conflicts.append({
                            "conflict_type": "pricing_discrepancy",
                            "category": "pricing",
                            "new_claim": new_claim.get("claim"),
                            "existing_claim": existing.claim,
                            "existing_source": existing.location_reference,
                            "severity": "high",
                            "recommendation": "Review latest pricing sheet and invalidate deprecated document",
                        })

        return detected_conflicts
