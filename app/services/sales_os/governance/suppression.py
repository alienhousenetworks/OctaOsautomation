"""3-Point Suppression and Frequency Enforcement Service.

Enforces:
1. Discovery Check: Pre-filtering known unsubscribed, bounced, or DNC domains/emails before enrichment.
2. Composition Check: Verifying recipient suppression and contact frequency limits (per person and company).
3. Send Socket Check: Final real-time assertion immediately before socket transmission.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from app.models.deal_room import SuppressionRecord, DealActivity
from app.models.verticals import Lead


class SuppressionCheckResult(tuple):
    def __new__(cls, is_suppressed: bool, reason: Optional[str] = None):
        return super().__new__(cls, (is_suppressed, reason))

    @property
    def is_suppressed(self) -> bool:
        return self[0]

    @property
    def reason(self) -> Optional[str]:
        return self[1]

    def __bool__(self) -> bool:
        return self[0]

    def __eq__(self, other):
        if isinstance(other, bool):
            return self[0] == other
        return super().__eq__(other)


class SuppressionService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def is_suppressed(
        self,
        identifier_value: Optional[str] = None,
        identifier_type: Optional[str] = None,
        *,
        email: Optional[str] = None,
        domain: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> SuppressionCheckResult:
        """Check if email, domain, or phone is suppressed for this tenant.

        Returns SuppressionCheckResult(is_suppressed, reason).
        """
        now = datetime.now(timezone.utc)

        # Handle positional usage: is_suppressed("val", "email")
        if identifier_value and identifier_type:
            if identifier_type == "email":
                email = identifier_value
            elif identifier_type == "domain":
                domain = identifier_value
            elif identifier_type == "phone":
                phone = identifier_value
        elif identifier_value and not identifier_type:
            if "@" in identifier_value:
                email = identifier_value
            else:
                domain = identifier_value

        # 1. Check email
        if email:
            clean_email = email.strip().lower()
            record = (
                self.db.query(SuppressionRecord)
                .filter(
                    SuppressionRecord.tenant_id == self.tenant_id,
                    SuppressionRecord.identifier_type == "email",
                    SuppressionRecord.identifier_value == clean_email,
                )
                .first()
            )
            if record and (not record.expires_at or record.expires_at > now):
                return SuppressionCheckResult(True, f"Email suppressed: {record.reason}")

            # Check domain part of email
            if "@" in clean_email:
                email_domain = clean_email.split("@")[-1]
                dom_result = self.is_suppressed(domain=email_domain)
                if dom_result.is_suppressed:
                    return SuppressionCheckResult(True, f"Email domain suppressed: {dom_result.reason}")

        # 2. Check domain
        if domain:
            clean_domain = domain.strip().lower().replace("www.", "")
            record = (
                self.db.query(SuppressionRecord)
                .filter(
                    SuppressionRecord.tenant_id == self.tenant_id,
                    SuppressionRecord.identifier_type == "domain",
                    SuppressionRecord.identifier_value == clean_domain,
                )
                .first()
            )
            if record and (not record.expires_at or record.expires_at > now):
                return SuppressionCheckResult(True, f"Domain suppressed: {record.reason}")

        # 3. Check phone
        if phone:
            import re
            clean_phone = re.sub(r"\D", "", phone)
            if clean_phone:
                record = (
                    self.db.query(SuppressionRecord)
                    .filter(
                        SuppressionRecord.tenant_id == self.tenant_id,
                        SuppressionRecord.identifier_type == "phone",
                        SuppressionRecord.identifier_value == clean_phone,
                    )
                    .first()
                )
                if record and (not record.expires_at or record.expires_at > now):
                    return SuppressionCheckResult(True, f"Phone suppressed: {record.reason}")

        return SuppressionCheckResult(False, None)

    def check_frequency_limit(
        self,
        email: Optional[str] = None,
        deal_room_id: Optional[str] = None,
        max_touches_per_contact_days: int = 3,
        max_touches_per_company_week: int = 4,
    ) -> Tuple[bool, Optional[str]]:
        """Verify frequency limits to prevent spamming.

        - Max 1 touch per contact within `max_touches_per_contact_days` days
        - Max `max_touches_per_company_week` touches across the whole company per week
        """
        now = datetime.now(timezone.utc)

        # Contact check
        if email:
            contact_cutoff = now - timedelta(days=max_touches_per_contact_days)
            recent_contact = (
                self.db.query(DealActivity)
                .filter(
                    DealActivity.tenant_id == self.tenant_id,
                    DealActivity.direction == "outbound",
                    DealActivity.created_at >= contact_cutoff,
                    DealActivity.metadata_json.contains({"recipient_email": email.lower()}),
                )
                .first()
            )
            if recent_contact:
                return False, f"Contact frequency limit reached: Contacted within last {max_touches_per_contact_days} days"

        # Company deal room check
        if deal_room_id:
            week_cutoff = now - timedelta(days=7)
            recent_company_touches = (
                self.db.query(DealActivity)
                .filter(
                    DealActivity.tenant_id == self.tenant_id,
                    DealActivity.deal_room_id == deal_room_id,
                    DealActivity.direction == "outbound",
                    DealActivity.created_at >= week_cutoff,
                )
                .count()
            )
            if recent_company_touches >= max_touches_per_company_week:
                return False, f"Company frequency limit reached: {recent_company_touches} touches in past 7 days"

        return True, None

    def add_suppression(
        self,
        identifier_type: str,
        identifier_value: str,
        reason: str,
        origin: str = "system",
        notes: Optional[str] = None,
        expires_days: Optional[int] = None,
    ) -> SuppressionRecord:
        """Add an entry to the suppression registry."""
        clean_val = identifier_value.strip().lower()
        if identifier_type == "phone":
            import re
            clean_val = re.sub(r"\D", "", clean_val)
        elif identifier_type == "domain":
            clean_val = clean_val.replace("www.", "")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=expires_days) if expires_days else None

        existing = (
            self.db.query(SuppressionRecord)
            .filter(
                SuppressionRecord.tenant_id == self.tenant_id,
                SuppressionRecord.identifier_type == identifier_type,
                SuppressionRecord.identifier_value == clean_val,
            )
            .first()
        )
        if existing:
            existing.reason = reason
            existing.origin = origin
            existing.notes = notes
            existing.expires_at = expires_at
            self.db.commit()
            return existing

        record = SuppressionRecord(
            tenant_id=self.tenant_id,
            identifier_type=identifier_type,
            identifier_value=clean_val,
            reason=reason,
            origin=origin,
            notes=notes,
            expires_at=expires_at,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record


SuppressionEngine = SuppressionService
