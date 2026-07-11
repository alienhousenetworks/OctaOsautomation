"""Durable workflow checkpoints + persistent DLQ with replay."""
from __future__ import annotations

import logging
import traceback as tb_mod
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.enterprise import DeadLetterJob, WorkflowCheckpoint

logger = logging.getLogger(__name__)


class DurableWorkflowService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def start_run(
        self,
        workflow_name: str,
        run_id: str,
        *,
        initial_state: Optional[dict] = None,
        idempotency_key: Optional[str] = None,
    ) -> WorkflowCheckpoint:
        if idempotency_key:
            existing = (
                self.db.query(WorkflowCheckpoint)
                .filter(WorkflowCheckpoint.idempotency_key == idempotency_key)
                .first()
            )
            if existing:
                return existing
        cp = WorkflowCheckpoint(
            tenant_id=self.tenant_id,
            workflow_name=workflow_name,
            run_id=run_id,
            step_index=0,
            step_name="start",
            state=initial_state or {},
            status="running",
            idempotency_key=idempotency_key,
        )
        self.db.add(cp)
        self.db.commit()
        self.db.refresh(cp)
        return cp

    def checkpoint(
        self,
        run_id: str,
        *,
        step_index: int,
        step_name: str,
        state: dict,
        status: str = "running",
    ) -> WorkflowCheckpoint:
        cp = (
            self.db.query(WorkflowCheckpoint)
            .filter(
                WorkflowCheckpoint.tenant_id == self.tenant_id,
                WorkflowCheckpoint.run_id == run_id,
            )
            .order_by(WorkflowCheckpoint.created_at.desc())
            .first()
        )
        if not cp:
            raise ValueError("Run not found")
        cp.step_index = step_index
        cp.step_name = step_name
        cp.state = state
        cp.status = status
        self.db.commit()
        self.db.refresh(cp)
        return cp

    def get_run(self, run_id: str) -> Optional[WorkflowCheckpoint]:
        return (
            self.db.query(WorkflowCheckpoint)
            .filter(
                WorkflowCheckpoint.tenant_id == self.tenant_id,
                WorkflowCheckpoint.run_id == run_id,
            )
            .order_by(WorkflowCheckpoint.created_at.desc())
            .first()
        )


class DeadLetterService:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        *,
        task_name: str,
        task_id: Optional[str] = None,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None,
        error: Optional[str] = None,
        traceback: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> DeadLetterJob:
        job = DeadLetterJob(
            tenant_id=tenant_id,
            task_name=task_name,
            task_id=task_id,
            args=args or [],
            kwargs=kwargs or {},
            error_message=error,
            traceback=traceback,
            status="failed",
            attempts=1,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        logger.error("DLQ recorded: %s %s — %s", task_name, task_id, error)
        return job

    def list_jobs(
        self,
        *,
        tenant_id: Optional[str] = None,
        status: str = "failed",
        limit: int = 50,
    ) -> List[DeadLetterJob]:
        q = self.db.query(DeadLetterJob).filter(DeadLetterJob.status == status)
        if tenant_id:
            q = q.filter(DeadLetterJob.tenant_id == tenant_id)
        return q.order_by(DeadLetterJob.created_at.desc()).limit(limit).all()

    def replay(self, job_id: str) -> Dict[str, Any]:
        job = self.db.query(DeadLetterJob).filter(DeadLetterJob.id == job_id).first()
        if not job:
            raise ValueError("DLQ job not found")
        job.status = "replaying"
        job.attempts = (job.attempts or 0) + 1
        self.db.commit()

        try:
            from app.core.celery_app import celery_app

            # Re-dispatch original celery task by name
            celery_app.send_task(job.task_name, args=job.args or [], kwargs=job.kwargs or {})
            job.status = "resolved"
            job.resolved_at = datetime.now(timezone.utc)
            self.db.commit()
            return {"status": "replayed", "job_id": job_id, "task_name": job.task_name}
        except Exception as e:
            job.status = "failed"
            job.error_message = f"Replay failed: {e}"
            self.db.commit()
            return {"status": "error", "error": str(e)}

    def discard(self, job_id: str) -> DeadLetterJob:
        job = self.db.query(DeadLetterJob).filter(DeadLetterJob.id == job_id).first()
        if not job:
            raise ValueError("DLQ job not found")
        job.status = "discarded"
        job.resolved_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(job)
        return job
