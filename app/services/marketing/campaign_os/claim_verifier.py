"""Deterministic Claim Extractor & Evidence Matcher.

Deterministic Service 3 & Gate 1:
- Extracts empirical metrics, percentages, and performance claims from copy
- Matches against verified EvidenceRecord database
- Strictly enforces 0 unsupported numeric claims
"""
import re
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel, Field


NUMERIC_CLAIM_REGEX = re.compile(
    r"(?i)(?:\$\s*\d+(?:\.\d+)?[kmb]?|\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?x\b|\b\d{1,3}(?:,\d{3})+\b|\b\d+\+?\s*(?:customers|users|hours|days|leads|deals|reduction|increase|uplift)\b)"
)


class ClaimVerificationResult(BaseModel):
    all_claims_grounded: bool
    verified_claims: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    citation_coverage_score: float = Field(1.0, ge=0.0, le=1.0)


class ClaimVerifier:
    """Deterministic extractor verifying post assertions against approved evidence."""

    @classmethod
    def verify_post_claims(
        cls,
        content: str,
        approved_evidence: List[Dict[str, Any]],
    ) -> ClaimVerificationResult:
        # 1. Extract numeric and statistical claims
        raw_matches = NUMERIC_CLAIM_REGEX.findall(content)
        detected_metrics = list(set([m.strip() for m in raw_matches]))

        if not detected_metrics:
            # No specific quantitative claims made
            return ClaimVerificationResult(
                all_claims_grounded=True,
                verified_claims=[],
                unsupported_claims=[],
                citation_coverage_score=1.0,
            )

        # 2. Compile pool of verified facts text
        verified_fact_corpus = " ".join([
            f"{e.get('claim', '')} {e.get('raw_snippet', '')}".lower()
            for e in approved_evidence
        ]).lower()

        verified = []
        unsupported = []

        for metric in detected_metrics:
            m_clean = metric.lower().replace(",", "")
            # Check if this metric or normalized number exists in verified facts
            # e.g., "25%" or "$1,200"
            if m_clean in verified_fact_corpus or metric.lower() in verified_fact_corpus:
                verified.append(metric)
            else:
                # Also check without % or $
                bare_num = re.sub(r"[^\d.]", "", m_clean)
                if bare_num and bare_num in verified_fact_corpus:
                    verified.append(metric)
                else:
                    unsupported.append(metric)

        total = len(detected_metrics)
        coverage = round(len(verified) / float(total), 2) if total > 0 else 1.0
        all_grounded = len(unsupported) == 0

        return ClaimVerificationResult(
            all_claims_grounded=all_grounded,
            verified_claims=verified,
            unsupported_claims=unsupported,
            citation_coverage_score=coverage,
        )
