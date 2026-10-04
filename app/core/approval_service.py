import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.executive import ApprovalRequest, ApprovalDecision, SideEffectOutbox
from app.core.event_ledger import EventLedger

class ApprovalService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def create_request(
        self,
        workflow_id: str,
        plan_version_id: str,
        task_id: str,
        capability_id: str,
        capability_version: str,
        payload: Dict[str, Any],
        risk_class: str,
        title: str,
        description: str,
        financial_impact: float = 0.0,
        requester_user_id: Optional[str] = None,
        expires_in_hours: int = 24
    ) -> ApprovalRequest:
        """
        Creates an approval request cryptographically bound to the exact payload hash.
        """
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        required_keys = 2 if risk_class == "R4_FINANCIAL_CRITICAL" else 1
        now = datetime.now(timezone.utc)

        req = ApprovalRequest(
            tenant_id=self.tenant_id,
            workflow_id=workflow_id,
            plan_version_id=plan_version_id,
            task_id=task_id,
            capability_id=capability_id,
            capability_version=capability_version,
            payload_hash=payload_hash,
            risk_class=risk_class,
            required_keys=required_keys,
            status="PENDING",
            title=title,
            description=description,
            financial_impact=financial_impact,
            requester_user_id=requester_user_id,
            expires_at=now + timedelta(hours=expires_in_hours),
            created_at=now
        )
        self.db.add(req)
        self.db.flush()
        return req

    def record_decision(
        self,
        request_id: str,
        user_id: str,
        user_role: str,
        decision: str, # 'APPROVE', 'REJECT'
        rationale: str,
        payload: Dict[str, Any],
        idempotency_key: str
    ) -> Dict[str, Any]:
        """
        Records an approval decision. Enforces anti-self-approval and dual-key requirement.
        Upon final approval, atomically stages the action in SideEffectOutbox.
        """
        req = self.db.query(ApprovalRequest).filter_by(
            id=request_id,
            tenant_id=self.tenant_id
        ).with_for_update().first()

        if not req:
            raise ValueError("Approval request not found.")

        if req.status != "PENDING":
            return {"status": req.status, "message": f"Request already resolved as {req.status}."}

        # Anti-self-approval rule for high risk
        if req.risk_class in ["R3_EXTERNAL_IRREVERSIBLE", "R4_FINANCIAL_CRITICAL"]:
            if req.requester_user_id and req.requester_user_id == user_id:
                raise PermissionError("Anti-self-approval violation: requester cannot approve their own high-risk request.")

        # Re-verify payload hash matches
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        computed_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if computed_hash != req.payload_hash:
            raise ValueError("Payload tampering detected: supplied payload does not match approved payload hash.")

        # Record decision
        dec = ApprovalDecision(
            approval_request_id=req.id,
            user_id=user_id,
            user_role=user_role,
            decision=decision,
            rationale=rationale,
            decided_at=datetime.now(timezone.utc)
        )
        self.db.add(dec)
        self.db.flush()

        if decision == "REJECT":
            req.status = "REJECTED"
            self.db.flush()
            return {"status": "REJECTED", "message": "Approval request rejected."}

        # Check total approvals
        approvals = self.db.query(ApprovalDecision).filter_by(
            approval_request_id=req.id,
            decision="APPROVE"
        ).all()

        distinct_approver_ids = {a.user_id for a in approvals}

        if len(distinct_approver_ids) >= req.required_keys:
            req.status = "APPROVED"

            # Atomically stage into SideEffectOutbox in the SAME transaction
            outbox_entry = SideEffectOutbox(
                tenant_id=self.tenant_id,
                workflow_id=req.workflow_id,
                task_id=req.task_id,
                capability_id=req.capability_id,
                capability_version=req.capability_version,
                idempotency_key=idempotency_key,
                payload_hash=req.payload_hash,
                payload=payload,
                status="STAGED",
                staged_at=datetime.now(timezone.utc)
            )
            self.db.add(outbox_entry)

            # Record in event ledger
            EventLedger.append_event(
                db=self.db,
                tenant_id=self.tenant_id,
                workflow_id=req.workflow_id,
                execution_id=req.id,
                event_type="approval_granted_and_staged",
                actor_type="USER",
                actor_id=user_id,
                task_id=req.task_id,
                payload={"outbox_idempotency_key": idempotency_key, "payload_hash": req.payload_hash},
                correlation_id=idempotency_key
            )
            self.db.flush()
            return {"status": "APPROVED", "message": "All required keys satisfied. Action staged in Outbox."}

        return {
            "status": "PENDING",
            "message": f"Approval recorded ({len(distinct_approver_ids)} of {req.required_keys} required keys)."
        }
