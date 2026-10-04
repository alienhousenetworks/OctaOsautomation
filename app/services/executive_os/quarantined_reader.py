import hashlib
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.executive import EvidenceSource

# Known prompt injection signatures and malicious payloads
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<script[\s>]", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"drop\s+table", re.IGNORECASE),
    re.compile(r"union\s+select", re.IGNORECASE),
    re.compile(r"\{\{.*\}\}"), # Template injection
    re.compile(r"\bexec\s*\(", re.IGNORECASE),
]

class QuarantinedResearchReader:
    """
    Isolated Ingestion Sandbox for External Research and Web Documents.
    Guarantees:
    - Pure extraction with ZERO tool-calling capability
    - Cryptographic content hashing (SHA-256)
    - Taint tracking and prompt injection defense
    - Structured claim parsing without executing raw input
    """
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def ingest_document(
        self,
        url: str,
        raw_content: str,
        title: Optional[str] = None,
        domain_reputation: float = 0.70
    ) -> Dict[str, Any]:
        """
        Ingests and quarantines raw document text.
        Computes SHA-256 hash and flags taint if prompt injection signatures are detected.
        """
        # 1. Parse domain
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0] or "unknown.domain"

        # 2. Cryptographic content hash of raw content
        content_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()

        # 3. Prompt injection & safety inspection
        taint_flags = []
        is_quarantined = False

        for pattern in INJECTION_PATTERNS:
            if pattern.search(raw_content):
                taint_flags.append(f"INJECTION_PATTERN_DETECTED:{pattern.pattern}")
                is_quarantined = True

        # Check for non-printable/hidden control characters
        non_printable = sum(1 for c in raw_content if ord(c) < 32 and c not in "\n\r\t")
        if non_printable > 5:
            taint_flags.append("SUSPICIOUS_CONTROL_CHARS")
            is_quarantined = True

        # 4. Persist EvidenceSource
        source = EvidenceSource(
            tenant_id=self.tenant_id,
            url=url,
            domain=domain.lower(),
            title=title or domain,
            content_hash=content_hash,
            raw_content=raw_content,
            domain_reputation_score=domain_reputation,
            is_quarantined=is_quarantined,
            taint_flags=taint_flags,
            retrieved_at=datetime.now(timezone.utc)
        )
        self.db.add(source)
        self.db.commit()

        # 5. Extract structured claims (pure pattern/heuristic parser, sandbox safe)
        extracted_claims = self._extract_claims_sandboxed(raw_content, is_quarantined)

        return {
            "source_id": source.id,
            "url": source.url,
            "domain": source.domain,
            "content_hash": content_hash,
            "is_quarantined": is_quarantined,
            "taint_flags": taint_flags,
            "extracted_claims": extracted_claims
        }

    def _extract_claims_sandboxed(self, text: str, is_quarantined: bool) -> List[Dict[str, Any]]:
        """
        Extracts factual statements and numeric figures safely without running LLM tool-calling.
        If quarantined, returns empty claims to prevent tainted text propagation.
        """
        if is_quarantined:
            return []

        claims = []
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        for line in lines:
            # Pattern for currency or numeric claims: e.g. "$45B", "15.4%", "1200 leads"
            metric_match = re.search(r"(\$?\d+(?:\.\d+)?\s*(?:[BKM%]|billion|million|leads|users|usd)?)", line, re.IGNORECASE)
            if metric_match and len(line) < 300:
                raw_val_str = metric_match.group(1).replace("$", "").strip()
                numeric_val = None
                unit = None

                # Extract number and multiplier
                multiplier = 1.0
                if "billion" in raw_val_str.lower() or raw_val_str.lower().endswith("b"):
                    multiplier = 1e9
                    raw_val_str = re.sub(r"[bB]|billion", "", raw_val_str, flags=re.IGNORECASE).strip()
                    unit = "USD"
                elif "million" in raw_val_str.lower() or raw_val_str.lower().endswith("m"):
                    multiplier = 1e6
                    raw_val_str = re.sub(r"[mM]|million", "", raw_val_str, flags=re.IGNORECASE).strip()
                    unit = "USD"
                elif "%" in raw_val_str:
                    raw_val_str = raw_val_str.replace("%", "").strip()
                    unit = "%"

                try:
                    numeric_val = float(raw_val_str) * multiplier
                except ValueError:
                    numeric_val = None

                claims.append({
                    "raw_statement": line,
                    "extracted_value": numeric_val,
                    "unit": unit
                })

        return claims
