"""Knowledge Access Controller & Enterprise Data Classification Guard.

Workstream A:
- Document-level classification (public, internal, confidential, restricted)
- Mandatory `approved_for_external_use` gating for public/campaign/outreach intents
- PII detection & redaction
- Indirect prompt injection scanner at ingestion
"""
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import logging

from app.models.agents import KnowledgeDocument

logger = logging.getLogger(__name__)


class DataClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class IntentType(str, Enum):
    CAMPAIGN_MARKETING = "campaign_marketing"
    SALES_OUTREACH = "sales_outreach"
    EMAIL_COMMUNICATION = "email_communication"
    SOCIAL_THOUGHT_LEADERSHIP = "social_thought_leadership"
    CUSTOMER_SUPPORT = "customer_support"
    INTERNAL_OPERATIONS = "internal_operations"
    EXECUTIVE_AUDIT = "executive_audit"


EXTERNAL_INTENTS = {
    IntentType.CAMPAIGN_MARKETING,
    IntentType.SALES_OUTREACH,
    IntentType.EMAIL_COMMUNICATION,
    IntentType.SOCIAL_THOUGHT_LEADERSHIP,
}

# Regex patterns for adversarial prompt injection detection
INJECTION_PATTERNS = [
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\[INST\]",
    r"\[/INST\]",
    r"<<SYS>>",
    r"<</SYS>>",
    r"(?i)ignore\s+(all\s+)?previous\s+instructions",
    r"(?i)disregard\s+(all\s+)?prior\s+prompts",
    r"(?i)system\s*:\s*you\s+are\s+now",
    r"(?i)developer\s+mode\s+enabled",
    r"(?i)jailbreak",
]

# Regex patterns for common sensitive PII
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


class KnowledgeAccessController:
    """Enterprise policy enforcement for Knowledge Base document retrieval and exposure."""

    @staticmethod
    def scan_for_prompt_injection(content: str) -> List[str]:
        """Scan raw document text for adversarial injection attempts."""
        findings = []
        for pattern in INJECTION_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                findings.append(f"Adversarial pattern match: {pattern}")
        return findings

    @staticmethod
    def detect_and_redact_pii(text: str, mask_emails: bool = False) -> Tuple[str, Dict[str, int]]:
        """Redact sensitive PII before chunking or external exposure."""
        counts = {"ssn": 0, "credit_card": 0, "phone": 0, "email": 0}
        
        def ssn_sub(match):
            counts["ssn"] += 1
            return "[REDACTED_SSN]"

        def cc_sub(match):
            counts["credit_card"] += 1
            return "[REDACTED_CARD]"

        def phone_sub(match):
            counts["phone"] += 1
            return "[REDACTED_PHONE]"

        redacted = SSN_PATTERN.sub(ssn_sub, text)
        redacted = CREDIT_CARD_PATTERN.sub(cc_sub, redacted)
        redacted = PHONE_PATTERN.sub(phone_sub, redacted)

        if mask_emails:
            def email_sub(match):
                counts["email"] += 1
                return "[REDACTED_EMAIL]"
            redacted = EMAIL_PATTERN.sub(email_sub, redacted)

        return redacted, counts

    @classmethod
    def can_access_document(
        cls,
        doc: KnowledgeDocument,
        intent: IntentType,
        user_role: str = "member",
    ) -> Tuple[bool, Optional[str]]:
        """Determine if a document is eligible for an execution intent."""
        # 1. Active check
        if not getattr(doc, "is_active", True):
            return False, "Document is marked inactive"

        # 2. Expiry check
        valid_until = getattr(doc, "valid_until", None)
        if valid_until:
            now_utc = datetime.now(timezone.utc)
            if valid_until.tzinfo is None:
                valid_until = valid_until.replace(tzinfo=timezone.utc)
            if valid_until < now_utc:
                return False, f"Document expired on {valid_until.isoformat()}"

        classification = getattr(doc, "classification", DataClassification.INTERNAL)
        approved_external = bool(getattr(doc, "approved_for_external_use", False))

        # 3. External Publishing Guardrail (Critical Security Boundary)
        if intent in EXTERNAL_INTENTS:
            # Absolute rule: confidential or restricted documents CAN NEVER be externalized
            if classification in (DataClassification.CONFIDENTIAL, DataClassification.RESTRICTED):
                return False, f"Document classified as '{classification}' cannot be used for external intent '{intent.value}'"

            # Mandatory external approval flag
            if not approved_external:
                return False, f"Document lacks mandatory 'approved_for_external_use' clearance for intent '{intent.value}'"

            return True, None

        # 4. Internal Operations Guardrail
        if intent == IntentType.INTERNAL_OPERATIONS:
            if classification == DataClassification.RESTRICTED and user_role != "admin":
                return False, "Restricted documents require admin clearance"
            return True, None

        # 5. Executive Audit Intent
        if intent == IntentType.EXECUTIVE_AUDIT:
            return True, None

        # Default fallback
        if classification in (DataClassification.CONFIDENTIAL, DataClassification.RESTRICTED):
            return False, "Confidential documents disallowed by default"

        return True, None

    @classmethod
    def filter_documents_for_intent(
        cls,
        documents: List[KnowledgeDocument],
        intent: IntentType,
        user_role: str = "member",
    ) -> List[KnowledgeDocument]:
        """Filter a collection of documents according to security access rules."""
        authorized_docs = []
        for doc in documents:
            allowed, reason = cls.can_access_document(doc, intent, user_role)
            if allowed:
                authorized_docs.append(doc)
            else:
                logger.debug(f"[AccessControl] Filtered out doc {getattr(doc, 'id', 'unknown')}: {reason}")
        return authorized_docs
