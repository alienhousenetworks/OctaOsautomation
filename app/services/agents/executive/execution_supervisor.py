import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.executive import PlanNode, WorkflowEvent
from app.core.event_ledger import EventLedger
from app.services.executive_os.execution_engine import DurableExecutionEngine
from app.services.executive_os.state_machine import TaskState, WorkflowState

logger = logging.getLogger(__name__)

class ExecutionSupervisorAgent:
    """
    Agent #9: Execution Supervisor (Executive Cognitive Layer)
    Trust Level: L0 Read-only (Telemetry & Diagnostic Advisory)

    Responsibilities:
    - In-flight DAG telemetry and progress monitoring
    - Execution drift detection (tasks exceeding 1.5x estimated duration)
    - Deadlock and stalled dependency detection
    - Diagnostic reporting and remediation advisory
    """
    AGENT_ID = "agent_09_execution_supervisor"
    AGENT_NAME = "Execution Supervisor"
    DEPARTMENT = "TELEMETRY"

    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.engine = DurableExecutionEngine(db, tenant_id)

    def inspect_workflow(
        self,
        workflow_id: str,
        plan_version_id: str,
        now_dt: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Conducts an in-flight telemetry audit of the DAG execution.
        Detects drift, stalls, and dependency deadlocks.
        """
        now = now_dt or datetime.now(timezone.utc)
        proj = self.engine.get_workflow_projection(workflow_id)
        nodes = self.db.query(PlanNode).filter_by(plan_version_id=plan_version_id).all()
        node_map = {n.id: n for n in nodes}

        # Query events to compute task start times
        events = self.db.query(WorkflowEvent).filter_by(
            workflow_id=workflow_id
        ).order_by(WorkflowEvent.sequence_num.asc()).all()

        task_start_times: Dict[str, datetime] = {}
        for ev in events:
            if ev.task_id and ev.event_type == "task_in_progress":
                dt = ev.created_at
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                task_start_times[ev.task_id] = dt

        drifting_tasks = []
        in_progress_tasks = [
            tid for tid, st in proj["task_states"].items()
            if st == TaskState.IN_PROGRESS.value
        ]

        for tid in in_progress_tasks:
            node = node_map.get(tid)
            if not node:
                continue

            start_time = task_start_times.get(tid)
            if not start_time:
                continue

            elapsed_seconds = (now - start_time).total_seconds()
            estimated_seconds = float(node.estimated_duration_seconds or 60)
            drift_ratio = elapsed_seconds / estimated_seconds if estimated_seconds > 0 else 1.0

            if drift_ratio >= 1.5:
                drift_info = {
                    "task_id": tid,
                    "task_name": node.name,
                    "capability_id": node.capability_id,
                    "elapsed_seconds": round(elapsed_seconds, 2),
                    "estimated_seconds": estimated_seconds,
                    "drift_ratio": round(drift_ratio, 2)
                }
                drifting_tasks.append(drift_info)

                # Record drift alert event on event ledger
                EventLedger.append_event(
                    db=self.db,
                    tenant_id=self.tenant_id,
                    workflow_id=workflow_id,
                    execution_id=proj["execution_id"],
                    event_type="supervisor_drift_detected",
                    actor_type="AGENT",
                    actor_id=self.AGENT_ID,
                    task_id=tid,
                    payload=drift_info,
                    correlation_id=proj["execution_id"]
                )
                self.db.commit()

        # Check for dependency deadlock or stalls
        completed_or_skipped = {
            tid for tid, st in proj["task_states"].items()
            if st in [TaskState.COMPLETED.value, TaskState.SKIPPED.value]
        }
        failed_tasks = {
            tid for tid, st in proj["task_states"].items()
            if st == TaskState.FAILED.value
        }
        waiting_approval = {
            tid for tid, st in proj["task_states"].items()
            if st == TaskState.WAITING_APPROVAL.value
        }

        deadlocked_tasks = []
        if failed_tasks:
            for node in nodes:
                if node.id not in completed_or_skipped and node.id not in failed_tasks:
                    deps = node.depends_on if isinstance(node.depends_on, list) else []
                    if any(d in failed_tasks for d in deps):
                        deadlocked_tasks.append(node.id)

        # Formulate health verdict and recommendation
        status = "HEALTHY"
        recommendation = "PROCEED"

        if drifting_tasks:
            status = "DRIFT_DETECTED"
            recommendation = "INVESTIGATE_LATENCY_OR_SCALE"
        elif deadlocked_tasks:
            status = "DEADLOCKED"
            recommendation = "COMPENSATE_OR_RETRY_FAILED"
        elif waiting_approval:
            status = "WAITING_APPROVAL"
            recommendation = "AWAIT_EXECUTIVE_KEY"

        return {
            "workflow_id": workflow_id,
            "status": status,
            "drifting_tasks": drifting_tasks,
            "deadlocked_tasks": deadlocked_tasks,
            "in_progress_count": len(in_progress_tasks),
            "waiting_approval_count": len(waiting_approval),
            "recommendation": recommendation,
            "inspected_at": now.isoformat()
        }
