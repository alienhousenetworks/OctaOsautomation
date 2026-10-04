"""Groundedness and Anti-Hallucination Evaluation Harness.

Validates that:
1. Every claim in an Account Brief or Outreach message is traceable to an EvidenceRecord or verified Primary Source.
2. Confidence score of all claims exceeds the threshold (default: >= 0.85).
3. Any unsupported claim is flagged as UNGROUNDED and blocks automated dispatch.
"""
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class GroundedClaim(BaseModel):
    claim_text: str
    source_type: str
    source_reference: str
    confidence: float
    is_grounded: bool
    unsupported_reason: Optional[str] = None


class GroundednessReport(BaseModel):
    is_fully_grounded: bool
    groundedness_score: float  # 0.0 to 1.0 (grounded_claims / total_claims)
    total_claims: int
    grounded_claims: int
    ungrounded_claims: List[str] = Field(default_factory=list)
    claims: List[GroundedClaim] = Field(default_factory=list)


class GroundednessEvaluator:
    """Evaluates whether generated copy adheres to primary source evidence."""

    def __init__(self, min_confidence: float = 0.85):
        self.min_confidence = min_confidence

    def evaluate(
        self,
        generated_text: str,
        available_evidence: List[Dict[str, Any]],
        strict_mode: bool = True,
    ) -> GroundednessReport:
        """Evaluate generated text against a list of verified evidence records.

        Each evidence item should have:
        - "claim" or "snippet" (str)
        - "source" (str)
        - "confidence" (float, optional, default 1.0)
        """
        # Extract factual sentences/clauses
        sentences = [
            s.strip()
            for s in re.split(r"[.!?\n]+", generated_text)
            if len(s.strip()) > 15
        ]

        if not sentences:
            return GroundednessReport(
                is_fully_grounded=True,
                groundedness_score=1.0,
                total_claims=0,
                grounded_claims=0,
                claims=[],
            )

        # Normalize evidence corpus for token/subsequence matching
        evidence_corpus = []
        for ev in available_evidence:
            text = (ev.get("raw_snippet") or ev.get("claim") or ev.get("snippet") or "").lower()
            conf = float(ev.get("confidence", 1.0))
            src = ev.get("source_id") or ev.get("source") or "internal_kb"
            if text:
                evidence_corpus.append({"text": text, "confidence": conf, "source": src})

        evaluated_claims: List[GroundedClaim] = []
        ungrounded: List[str] = []

        for sent in sentences:
            sent_lower = sent.lower()
            
            # Skip generic conversational boilerplate (greetings, signoffs, scheduling questions)
            boilerplate = [
                "hope you are well",
                "let me know",
                "looking forward to",
                "would love to connect",
                "are you available for a brief",
                "what does your calendar look like",
                "thanks for getting back to me",
                "open to a brief",
                "open to a quick",
                "open to a conversation",
                "feel free to",
                "best regards",
                "sincerely",
                "hi ",
                "hello ",
            ]
            if any(b in sent_lower for b in boilerplate) and len(sent.split()) < 12:
                continue

            # Check overlap against verified evidence corpus
            sent_tokens = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", sent_lower))
            best_match = None
            best_overlap = 0

            for ev in evidence_corpus:
                ev_tokens = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", ev["text"]))
                common = sent_tokens & ev_tokens
                overlap_ratio = len(common) / max(len(sent_tokens), 1)
                
                if overlap_ratio > best_overlap:
                    best_overlap = overlap_ratio
                    best_match = ev

            is_grounded = False
            unsupported_reason = None
            source_ref = "UNKNOWN"
            conf = 0.0

            if best_match and best_overlap >= 0.40:
                conf = best_match["confidence"]
                source_ref = best_match["source"]
                if conf >= self.min_confidence:
                    is_grounded = True
                else:
                    unsupported_reason = f"Evidence confidence {conf:.2f} below required {self.min_confidence:.2f}"
            else:
                unsupported_reason = "No supporting evidence found in verified company knowledge base or signals"

            claim_obj = GroundedClaim(
                claim_text=sent,
                source_type=best_match["source"] if best_match else "unverified",
                source_reference=source_ref,
                confidence=conf,
                is_grounded=is_grounded,
                unsupported_reason=unsupported_reason,
            )
            evaluated_claims.append(claim_obj)

            if not is_grounded:
                ungrounded.append(sent)

        total = len(evaluated_claims)
        grounded_count = sum(1 for c in evaluated_claims if c.is_grounded)
        score = grounded_count / total if total > 0 else 1.0
        is_fully_grounded = (len(ungrounded) == 0) if strict_mode else (score >= 0.85)

        return GroundednessReport(
            is_fully_grounded=is_fully_grounded,
            groundedness_score=round(score, 3),
            total_claims=total,
            grounded_claims=grounded_count,
            ungrounded_claims=ungrounded,
            claims=evaluated_claims,
        )
