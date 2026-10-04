import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
from sqlalchemy.orm import Session

from app.models.workflows import Workflow, WorkflowTask
from app.models.executive import (
    WorkflowEvent, PlanVersion, PlanNode, ApprovalRequest,
    SideEffectOutbox, CapabilityRegistry
)
from app.core.governance import DeterministicGovernanceKernel
from app.core.event_ledger import EventLedger
from app.core.approval_service import ApprovalService
from app.core.capabilities import get_capability_instance
from app.services.executive_os.state_machine import (
    WorkflowState, TaskState, validate_workflow_transition, validate_task_transition
)
from app.services.executive_os.sse_manager import SSEManager

logger = logging.getLogger(__name__)

class DurableExecutionEngine:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.kernel = DeterministicGovernanceKernel(db, tenant_id)
        self.approval_service = ApprovalService(db, tenant_id)

    def _record_and_publish(
        self,
        workflow_id: str,
        execution_id: str,
        event_type: str,
        actor_type: str,
        actor_id: str,
        payload: Dict[str, Any],
        correlation_id: str,
        task_id: Optional[str] = None,
        causation_id: Optional[str] = None
    ) -> WorkflowEvent:
        """
        Appends an event to the EventLedger, commits atomically,
        and broadcasts to connected SSE clients.
        """
        ev = EventLedger.append_event(
            db=self.db,
            tenant_id=self.tenant_id,
            workflow_id=workflow_id,
            execution_id=execution_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=payload,
            correlation_id=correlation_id,
            task_id=task_id,
            causation_id=causation_id
        )
        self.db.commit()

        # Real-time notification to SSE subscribers
        try:
            payload_data = json.loads(ev.canonical_payload) if isinstance(ev.canonical_payload, str) else ev.canonical_payload
            SSEManager.publish(workflow_id, {
                "sequence_num": ev.sequence_num,
                "event_type": ev.event_type,
                "actor_type": ev.actor_type,
                "actor_id": ev.actor_id,
                "task_id": ev.task_id,
                "payload": payload_data,
                "event_hash": ev.event_hash,
                "created_at": ev.timestamp_iso
            })
        except Exception as e:
            logger.debug(f"Failed to publish SSE event: {e}")

        return ev

    def start_workflow(self, workflow_id: str, plan_version_id: str, execution_id: Optional[str] = None) -> Workflow:
        """
        Transitions workflow to RUNNING and records workflow_started event.
        """
        execution_id = execution_id or str(uuid.uuid4())
        wf = self.db.query(Workflow).filter_by(id=workflow_id, tenant_id=self.tenant_id).first()
        if not wf:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        current_state = WorkflowState(wf.status.upper()) if hasattr(WorkflowState, wf.status.upper()) else WorkflowState.COMPILED
        if not validate_workflow_transition(current_state, WorkflowState.RUNNING):
            if current_state != WorkflowState.RUNNING:
                raise ValueError(f"Invalid transition from {current_state} to RUNNING.")

        wf.status = WorkflowState.RUNNING.value
        self.db.flush()

        self._record_and_publish(
            workflow_id=workflow_id,
            execution_id=execution_id,
            event_type="workflow_started",
            actor_type="SYSTEM",
            actor_id="DurableExecutionEngine",
            payload={"plan_version_id": plan_version_id},
            correlation_id=execution_id
        )
        return wf

    def get_workflow_projection(self, workflow_id: str) -> Dict[str, Any]:
        """
        Reconstructs the authoritative in-flight state of the workflow and its tasks
        from the event ledger.
        """
        events = self.db.query(WorkflowEvent).filter_by(
            workflow_id=workflow_id
        ).order_by(WorkflowEvent.sequence_num.asc()).all()

        task_states: Dict[str, str] = {}
        task_results: Dict[str, Any] = {}
        task_errors: Dict[str, str] = {}
        workflow_status = WorkflowState.DRAFT.value
        execution_id = str(uuid.uuid4())
        plan_version_id = None

        for ev in events:
            execution_id = ev.execution_id
            payload = json.loads(ev.canonical_payload) if isinstance(ev.canonical_payload, str) else ev.canonical_payload

            if ev.event_type == "workflow_started":
                workflow_status = WorkflowState.RUNNING.value
                plan_version_id = payload.get("plan_version_id")
            elif ev.event_type == "workflow_paused":
                workflow_status = WorkflowState.PAUSED.value
            elif ev.event_type == "workflow_resumed":
                workflow_status = WorkflowState.RUNNING.value
            elif ev.event_type == "workflow_completed":
                workflow_status = WorkflowState.COMPLETED.value
            elif ev.event_type == "workflow_failed":
                workflow_status = WorkflowState.FAILED.value
            elif ev.event_type == "workflow_cancelled":
                workflow_status = WorkflowState.CANCELLED.value

            # Task level events
            if ev.task_id:
                tid = ev.task_id
                if ev.event_type in ["task_ready", "task_retried"]:
                    task_states[tid] = TaskState.READY.value
                elif ev.event_type == "task_waiting_approval":
                    task_states[tid] = TaskState.WAITING_APPROVAL.value
                elif ev.event_type == "task_in_progress":
                    task_states[tid] = TaskState.IN_PROGRESS.value
                elif ev.event_type in ["task_completed", "outbox_action_acknowledged"]:
                    task_states[tid] = TaskState.COMPLETED.value
                    if "result" in payload:
                        task_results[tid] = payload["result"]
                elif ev.event_type == "task_failed":
                    task_states[tid] = TaskState.FAILED.value
                    task_errors[tid] = payload.get("error", "Unknown error")
                elif ev.event_type == "task_skipped":
                    task_states[tid] = TaskState.SKIPPED.value
                elif ev.event_type == "task_compensated":
                    task_states[tid] = TaskState.COMPENSATED.value

        return {
            "workflow_id": workflow_id,
            "execution_id": execution_id,
            "plan_version_id": plan_version_id,
            "workflow_status": workflow_status,
            "task_states": task_states,
            "task_results": task_results,
            "task_errors": task_errors
        }

    async def execute_tick(self, workflow_id: str, plan_version_id: str) -> Dict[str, Any]:
        """
        Single atomic execution tick of the workflow DAG:
        1. Projects state from event ledger.
        2. Resolves dependencies.
        3. Fires ready tasks through Governance Kernel.
        4. Handles approval blocks, dry-runs, and execution.
        """
        proj = self.get_workflow_projection(workflow_id)
        if proj["workflow_status"] in [WorkflowState.PAUSED.value, WorkflowState.CANCELLED.value, WorkflowState.COMPLETED.value]:
            return {"status": proj["workflow_status"], "message": f"Workflow is {proj['workflow_status']}."}

        execution_id = proj["execution_id"]
        nodes = self.db.query(PlanNode).filter_by(plan_version_id=plan_version_id).all()
        if not nodes:
            raise ValueError(f"No plan nodes found for PlanVersion '{plan_version_id}'.")

        completed_or_skipped = {
            tid for tid, st in proj["task_states"].items()
            if st in [TaskState.COMPLETED.value, TaskState.SKIPPED.value]
        }
        failed_tasks = {
            tid for tid, st in proj["task_states"].items()
            if st == TaskState.FAILED.value
        }

        if failed_tasks:
            # Abort workflow and trigger compensation
            wf = self.db.query(Workflow).filter_by(id=workflow_id).first()
            if wf:
                wf.status = WorkflowState.FAILED.value
            self._record_and_publish(
                workflow_id=workflow_id,
                execution_id=execution_id,
                event_type="workflow_failed",
                actor_type="SYSTEM",
                actor_id="DurableExecutionEngine",
                payload={"failed_task_ids": list(failed_tasks)},
                correlation_id=execution_id
            )
            await self.compensate_workflow(workflow_id, plan_version_id)
            return {"status": "FAILED", "failed_task_ids": list(failed_tasks)}

        # Find ready nodes: not completed, not in-progress, not waiting approval (unless approved), all dependencies completed/skipped
        ready_nodes = []
        for node in nodes:
            current_state = proj["task_states"].get(node.id, TaskState.PENDING.value)
            if current_state == TaskState.WAITING_APPROVAL.value:
                approved_req = self.db.query(ApprovalRequest).filter_by(
                    workflow_id=workflow_id,
                    task_id=node.id,
                    status="APPROVED"
                ).first()
                if not approved_req:
                    continue
            elif current_state in [TaskState.COMPLETED.value, TaskState.SKIPPED.value, TaskState.IN_PROGRESS.value]:
                continue

            deps = node.depends_on if isinstance(node.depends_on, list) else []
            if all(d in completed_or_skipped for d in deps):
                ready_nodes.append(node)

        # Check if entire workflow is finished
        if not ready_nodes and len(completed_or_skipped) == len(nodes):
            wf = self.db.query(Workflow).filter_by(id=workflow_id).first()
            if wf:
                wf.status = WorkflowState.COMPLETED.value
            self._record_and_publish(
                workflow_id=workflow_id,
                execution_id=execution_id,
                event_type="workflow_completed",
                actor_type="SYSTEM",
                actor_id="DurableExecutionEngine",
                payload={"total_nodes": len(nodes)},
                correlation_id=execution_id
            )
            return {"status": "COMPLETED", "completed_count": len(nodes)}

        # Process each ready node through Governance Kernel
        executed_nodes = []
        for node in ready_nodes:
            params = node.parameters if isinstance(node.parameters, dict) else {}

            # Evaluate with Deterministic Governance Kernel
            gov_res = self.kernel.evaluate(
                capability_id=node.capability_id,
                capability_version=node.capability_version,
                inputs=params,
                actor_autonomy="L2",
                context={"workflow_id": workflow_id, "task_id": node.id}
            )

            decision = gov_res["decision"]

            # If approval required, check if already approved
            if decision == "REQUIRE_APPROVAL":
                approved_req = self.db.query(ApprovalRequest).filter_by(
                    workflow_id=workflow_id,
                    task_id=node.id,
                    status="APPROVED"
                ).first()
                if approved_req:
                    decision = "ALLOW"
            if decision == "DENY":
                self._record_and_publish(
                    workflow_id=workflow_id,
                    execution_id=execution_id,
                    event_type="task_failed",
                    actor_type="POLICY_KERNEL",
                    actor_id="GovernanceKernel",
                    task_id=node.id,
                    payload={"error": f"Policy Kernel DENY: {gov_res.get('reason', 'Policy violation')}"},
                    correlation_id=execution_id
                )
                return {"status": "TASK_DENIED", "node_id": node.id}

            elif decision == "REQUIRE_APPROVAL":
                # Check if approval request already created
                existing_req = self.db.query(ApprovalRequest).filter_by(
                    workflow_id=workflow_id,
                    task_id=node.id,
                    status="PENDING"
                ).first()

                if not existing_req:
                    req = self.approval_service.create_request(
                        workflow_id=workflow_id,
                        plan_version_id=plan_version_id,
                        task_id=node.id,
                        capability_id=node.capability_id,
                        capability_version=node.capability_version,
                        payload=params,
                        risk_class=gov_res["effective_risk"],
                        title=f"Approval Required: {node.name}",
                        description=f"Action '{node.capability_id}' requires executive approval.",
                        financial_impact=gov_res.get("cost_estimate", 0.0)
                    )
                    self._record_and_publish(
                        workflow_id=workflow_id,
                        execution_id=execution_id,
                        event_type="task_waiting_approval",
                        actor_type="POLICY_KERNEL",
                        actor_id="GovernanceKernel",
                        task_id=node.id,
                        payload={"approval_request_id": req.id, "risk_class": gov_res["effective_risk"]},
                        correlation_id=execution_id
                    )
                continue

            elif decision == "ALLOW":
                # Dispatch capability
                self._record_and_publish(
                    workflow_id=workflow_id,
                    execution_id=execution_id,
                    event_type="task_in_progress",
                    actor_type="SYSTEM",
                    actor_id="DurableExecutionEngine",
                    task_id=node.id,
                    payload={"capability_id": node.capability_id},
                    correlation_id=execution_id
                )

                try:
                    cap = get_capability_instance(node.capability_id, node.capability_version)
                    idemp_key = f"tick-{workflow_id}-{node.id}"
                    result = await cap.execute(self.tenant_id, params, idemp_key)

                    self._record_and_publish(
                        workflow_id=workflow_id,
                        execution_id=execution_id,
                        event_type="task_completed",
                        actor_type="AGENT",
                        actor_id=node.department,
                        task_id=node.id,
                        payload={"result": result},
                        correlation_id=idemp_key
                    )
                    executed_nodes.append(node.id)
                except Exception as e:
                    logger.error(f"Error executing node {node.id}: {e}")
                    self._record_and_publish(
                        workflow_id=workflow_id,
                        execution_id=execution_id,
                        event_type="task_failed",
                        actor_type="SYSTEM",
                        actor_id="DurableExecutionEngine",
                        task_id=node.id,
                        payload={"error": str(e)},
                        correlation_id=execution_id
                    )

        return {
            "status": "TICK_PROCESSED",
            "executed_nodes": executed_nodes,
            "ready_count": len(ready_nodes)
        }

    def pause_workflow(self, workflow_id: str) -> bool:
        wf = self.db.query(Workflow).filter_by(id=workflow_id, tenant_id=self.tenant_id).first()
        if not wf or wf.status != WorkflowState.RUNNING.value:
            return False
        wf.status = WorkflowState.PAUSED.value
        self.db.flush()
        self._record_and_publish(
            workflow_id=workflow_id,
            execution_id=str(uuid.uuid4()),
            event_type="workflow_paused",
            actor_type="USER",
            actor_id="CEO",
            payload={"reason": "User requested pause"},
            correlation_id=str(uuid.uuid4())
        )
        return True

    def resume_workflow(self, workflow_id: str) -> bool:
        wf = self.db.query(Workflow).filter_by(id=workflow_id, tenant_id=self.tenant_id).first()
        if not wf or wf.status != WorkflowState.PAUSED.value:
            return False
        wf.status = WorkflowState.RUNNING.value
        self.db.flush()
        self._record_and_publish(
            workflow_id=workflow_id,
            execution_id=str(uuid.uuid4()),
            event_type="workflow_resumed",
            actor_type="USER",
            actor_id="CEO",
            payload={"reason": "User requested resume"},
            correlation_id=str(uuid.uuid4())
        )
        return True

    def cancel_workflow(self, workflow_id: str) -> bool:
        wf = self.db.query(Workflow).filter_by(id=workflow_id, tenant_id=self.tenant_id).first()
        if not wf:
            return False
        wf.status = WorkflowState.CANCELLED.value
        self.db.flush()
        self._record_and_publish(
            workflow_id=workflow_id,
            execution_id=str(uuid.uuid4()),
            event_type="workflow_cancelled",
            actor_type="USER",
            actor_id="CEO",
            payload={"reason": "User requested cancellation"},
            correlation_id=str(uuid.uuid4())
        )
        return True

    def retry_task(self, workflow_id: str, task_id: str) -> bool:
        wf = self.db.query(Workflow).filter_by(id=workflow_id, tenant_id=self.tenant_id).first()
        if not wf:
            return False
        if wf.status == WorkflowState.FAILED.value:
            wf.status = WorkflowState.RUNNING.value
            self.db.flush()

        self._record_and_publish(
            workflow_id=workflow_id,
            execution_id=str(uuid.uuid4()),
            event_type="task_retried",
            actor_type="USER",
            actor_id="CEO",
            task_id=task_id,
            payload={"action": "Manual retry initiated"},
            correlation_id=str(uuid.uuid4())
        )
        return True

    def skip_task(self, workflow_id: str, task_id: str) -> bool:
        self._record_and_publish(
            workflow_id=workflow_id,
            execution_id=str(uuid.uuid4()),
            event_type="task_skipped",
            actor_type="USER",
            actor_id="CEO",
            task_id=task_id,
            payload={"reason": "Manual skip by operator"},
            correlation_id=str(uuid.uuid4())
        )
        return True

    async def compensate_workflow(self, workflow_id: str, plan_version_id: str) -> Dict[str, Any]:
        """
        Executes compensation handlers in reverse order for completed tasks.
        Respects is_compensable = False for irreversible external actions.
        """
        proj = self.get_workflow_projection(workflow_id)
        nodes = self.db.query(PlanNode).filter_by(plan_version_id=plan_version_id).all()
        node_map = {n.id: n for n in nodes}

        completed_tasks = [
            tid for tid, st in proj["task_states"].items()
            if st == TaskState.COMPLETED.value
        ]

        compensated_count = 0
        unsupported_count = 0

        for tid in reversed(completed_tasks):
            node = node_map.get(tid)
            if not node:
                continue

            try:
                cap = get_capability_instance(node.capability_id, node.capability_version)
                params = node.parameters if isinstance(node.parameters, dict) else {}
                result = proj["task_results"].get(tid, {})

                comp_res = await cap.compensate(self.tenant_id, params, result)
                if comp_res.get("status") == "COMPENSATION_NOT_SUPPORTED":
                    unsupported_count += 1
                    self._record_and_publish(
                        workflow_id=workflow_id,
                        execution_id=proj["execution_id"],
                        event_type="compensation_unsupported",
                        actor_type="SYSTEM",
                        actor_id="DurableExecutionEngine",
                        task_id=tid,
                        payload=comp_res,
                        correlation_id=proj["execution_id"]
                    )
                else:
                    compensated_count += 1
                    self._record_and_publish(
                        workflow_id=workflow_id,
                        execution_id=proj["execution_id"],
                        event_type="task_compensated",
                        actor_type="SYSTEM",
                        actor_id="DurableExecutionEngine",
                        task_id=tid,
                        payload=comp_res,
                        correlation_id=proj["execution_id"]
                    )
            except Exception as e:
                logger.error(f"Error compensating task {tid}: {e}")

        return {
            "compensated_count": compensated_count,
            "unsupported_count": unsupported_count
        }
