import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.executive import SideEffectOutbox, KillSwitch
from app.core.capabilities import get_capability_instance
from app.core.event_ledger import EventLedger

logger = logging.getLogger(__name__)

class OutboxWorker:
    def __init__(self, db: Session, worker_id: str):
        self.db = db
        self.worker_id = worker_id

    async def process_batch(self, batch_size: int = 20) -> int:
        """
        Fetches staged outbox rows using FOR UPDATE SKIP LOCKED with short lease.
        Prevents dual dispatch and handles unacked crash recovery safely.
        Returns the number of processed actions.
        """
        now = datetime.now(timezone.utc)
        lease_window = now + timedelta(seconds=60)

        # 1. Acquire leased rows
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            stmt = text("""
                SELECT id FROM side_effect_outbox
                WHERE status IN ('STAGED', 'FAILED')
                  AND (lease_expires_at IS NULL OR lease_expires_at < :now)
                  AND retry_count < max_retries
                ORDER BY staged_at ASC
                LIMIT :batch_size
                FOR UPDATE SKIP LOCKED;
            """)
        else:
            stmt = text("""
                SELECT id FROM side_effect_outbox
                WHERE status IN ('STAGED', 'FAILED')
                  AND (lease_expires_at IS NULL OR lease_expires_at < :now)
                  AND retry_count < max_retries
                ORDER BY staged_at ASC
                LIMIT :batch_size;
            """)

        rows = self.db.execute(stmt, {"now": now, "batch_size": batch_size}).fetchall()
        if not rows:
            return 0

        row_ids = [r[0] for r in rows]
        # Set lease
        self.db.query(SideEffectOutbox).filter(SideEffectOutbox.id.in_(row_ids)).update({
            "lease_owner": self.worker_id,
            "lease_expires_at": lease_window
        }, synchronize_session=False)
        self.db.commit()

        processed_count = 0
        # 2. Process each leased action
        for outbox_id in row_ids:
            item = self.db.query(SideEffectOutbox).filter_by(id=outbox_id).first()
            if not item:
                continue

            # Kill-switch gate at time of dispatch!
            if self._is_kill_switch_engaged(item.capability_id, item.tenant_id):
                item.status = "FAILED"
                item.last_error = f"Dispatch aborted: kill-switch engaged for capability '{item.capability_id}'."
                item.lease_expires_at = None
                self.db.commit()
                continue

            # Re-verify payload hash (prevents database-level payload tampering)
            canonical = json.dumps(item.payload, sort_keys=True, separators=(",", ":"))
            if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != item.payload_hash:
                item.status = "DEAD_LETTER"
                item.last_error = "Integrity check failed: payload hash mismatch."
                item.lease_expires_at = None
                self.db.commit()
                continue

            # Mark state as DISPATCHED_UNKNOWN during execution window (prevents blind retries if killed)
            item.status = "DISPATCHED_UNKNOWN"
            self.db.commit()

            try:
                capability = get_capability_instance(item.capability_id, item.capability_version)
                result = await capability.execute(item.tenant_id, item.payload, item.idempotency_key)

                # Action succeeded: update outbox and record event atomically in the SAME transaction
                item.status = "ACKNOWLEDGED"
                item.acknowledged_at = datetime.now(timezone.utc)
                item.last_error = None
                item.lease_expires_at = None

                EventLedger.append_event(
                    db=self.db,
                    tenant_id=item.tenant_id,
                    workflow_id=item.workflow_id,
                    execution_id=item.id,
                    event_type="outbox_action_acknowledged",
                    actor_type="SYSTEM",
                    actor_id=self.worker_id,
                    task_id=item.task_id,
                    payload={"result": result, "idempotency_key": item.idempotency_key},
                    correlation_id=item.idempotency_key
                )
                self.db.commit()
                processed_count += 1

            except Exception as e:
                logger.error(f"Error executing outbox item {item.id}: {e}")
                self.db.rollback()
                item = self.db.query(SideEffectOutbox).filter_by(id=outbox_id).first()
                item.retry_count += 1
                item.status = "FAILED" if item.retry_count < item.max_retries else "DEAD_LETTER"
                item.last_error = str(e)
                item.lease_expires_at = None
                self.db.commit()

        return processed_count

    def _is_kill_switch_engaged(self, capability_id: str, tenant_id: str) -> bool:
        engaged = self.db.query(KillSwitch).filter(
            KillSwitch.id.in_(["GLOBAL", capability_id, f"tenant:{tenant_id}"]),
            KillSwitch.engaged == True
        ).first()
        return engaged is not None
