import hashlib
import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.executive import WorkflowEvent

class EventLedger:
    @staticmethod
    def append_event(
        db: Session,
        tenant_id: str,
        workflow_id: str,
        execution_id: str,
        event_type: str,
        actor_type: str,
        actor_id: str,
        payload: dict,
        correlation_id: str,
        task_id: str = None,
        causation_id: str = None
    ) -> WorkflowEvent:
        """
        Appends an event to the ledger within the caller's active database transaction.
        DOES NOT COMMIT internally. Commits atomically with caller's state changes.
        Uses PostgreSQL transaction-level advisory lock on workflow_id to avoid sequence collisions.
        """
        # PostgreSQL transaction-level advisory lock prevents sequence race on workflow
        if db.bind and db.bind.dialect.name == "postgresql":
            lock_id = int(hashlib.sha256(workflow_id.encode("utf-8")).hexdigest()[:8], 16)
            db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})

        last_event = db.query(WorkflowEvent).filter_by(
            workflow_id=workflow_id
        ).order_by(WorkflowEvent.sequence_num.desc()).first()

        prev_hash = last_event.event_hash if last_event else "0" * 64
        seq_num = (last_event.sequence_num + 1) if last_event else 1
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        # Deterministic canonical serialization
        canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

        canonical_string = (
            f"{prev_hash}|{seq_num}|{tenant_id}|{workflow_id}|{execution_id}|"
            f"{task_id or ''}|{event_type}|{actor_type}|{actor_id}|"
            f"{correlation_id}|{causation_id or ''}|{now_iso}|{payload_hash}"
        )
        event_hash = hashlib.sha256(canonical_string.encode("utf-8")).hexdigest()

        event = WorkflowEvent(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            execution_id=execution_id,
            sequence_num=seq_num,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            task_id=task_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            canonical_payload=canonical_payload,
            payload_hash=payload_hash,
            previous_hash=prev_hash,
            event_hash=event_hash,
            timestamp_iso=now_iso,
            created_at=now_dt
        )
        db.add(event)
        db.flush() # Flushes so it has an ID, but does NOT commit transaction
        return event

    @staticmethod
    def verify_ledger_integrity(db: Session, workflow_id: str) -> bool:
        """
        Mathematically verifies the hash chain from Genesis to Tip.
        Any missing row, altered payload, or mutated hash immediately returns False.
        """
        events = db.query(WorkflowEvent).filter_by(
            workflow_id=workflow_id
        ).order_by(WorkflowEvent.sequence_num.asc()).all()

        if not events:
            return True

        expected_prev_hash = "0" * 64
        for ev in events:
            # 1. Verify backward link
            if ev.previous_hash != expected_prev_hash:
                return False

            # 2. Verify payload hash against stored canonical text
            computed_payload_hash = hashlib.sha256(ev.canonical_payload.encode("utf-8")).hexdigest()
            if computed_payload_hash != ev.payload_hash:
                return False

            # 3. Recalculate event hash using the immutable stored timestamp_iso
            canonical_string = (
                f"{ev.previous_hash}|{ev.sequence_num}|{ev.tenant_id}|{ev.workflow_id}|{ev.execution_id}|"
                f"{ev.task_id or ''}|{ev.event_type}|{ev.actor_type}|{ev.actor_id}|"
                f"{ev.correlation_id}|{ev.causation_id or ''}|{ev.timestamp_iso}|{ev.payload_hash}"
            )
            expected_event_hash = hashlib.sha256(canonical_string.encode("utf-8")).hexdigest()

            # 4. Explicit hash assertion
            if ev.event_hash != expected_event_hash:
                return False

            expected_prev_hash = ev.event_hash

        return True
