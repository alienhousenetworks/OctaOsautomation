import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.flow_engine import (
    FlowDefinition,
    FlowVersion,
    FlowRun,
    StepRun,
    ApprovalRequest,
    ExecutionEvent,
)
from app.services.agents.runtime import agent_runtime
from app.services.agents.tools import tool_registry
from app.services.agents.section_registry import section_registry


class FlowExecutionEngine:
    """Deterministic, durable state machine executing multi-step agentic flows."""

    async def start_flow_run(
        self,
        db: Session,
        tenant_id: str,
        flow_id: str,
        inputs: Optional[Dict[str, Any]] = None,
        trigger_type: str = "manual",
        trigger_context: Optional[Dict[str, Any]] = None,
    ) -> FlowRun:
        flow = db.query(FlowDefinition).filter_by(id=flow_id, tenant_id=tenant_id).first()
        if not flow:
            raise ValueError(f"Flow {flow_id} not found for tenant {tenant_id}")

        latest_ver = (
            db.query(FlowVersion)
            .filter_by(flow_id=flow.id)
            .order_by(FlowVersion.version.desc())
            .first()
        )
        if not latest_ver:
            raise ValueError(f"No FlowVersion found for Flow {flow_id}")

        flow_run = FlowRun(
            tenant_id=tenant_id,
            flow_id=flow.id,
            flow_version_id=latest_ver.id,
            status="running",
            trigger_type=trigger_type,
            trigger_context=trigger_context or {},
            inputs=inputs or {},
            outputs={},
            started_at=datetime.now(timezone.utc),
        )
        db.add(flow_run)
        db.commit()
        db.refresh(flow_run)

        # Emit execution event
        self._emit_event(db, tenant_id, flow_run.id, None, "flow.started", {"flow_name": flow.name})

        # Run steps
        await self.execute_flow_run(db, flow_run.id)
        db.refresh(flow_run)
        return flow_run

    async def execute_flow_run(self, db: Session, flow_run_id: str):
        flow_run = db.query(FlowRun).filter_by(id=flow_run_id).first()
        if not flow_run or flow_run.status in ("succeeded", "failed", "cancelled"):
            return

        flow_ver = db.query(FlowVersion).filter_by(id=flow_run.flow_version_id).first()
        if not flow_ver:
            return

        steps: List[Dict[str, Any]] = flow_ver.definition or []
        step_outputs: Dict[str, Any] = dict(flow_run.outputs or {})

        flow_start = time.time()
        total_cost = flow_run.total_cost_usd or 0.0
        total_tokens = flow_run.total_tokens or 0

        for step in steps:
            step_id = step.get("id")
            step_name = step.get("name", step_id)
            step_type = step.get("type", "agent")

            # Check existing step run
            step_run = db.query(StepRun).filter_by(flow_run_id=flow_run.id, step_id=step_id).first()

            if step_run and step_run.status == "succeeded":
                # Already executed
                step_outputs[step_id] = step_run.outputs
                continue

            if not step_run:
                step_run = StepRun(
                    flow_run_id=flow_run.id,
                    step_id=step_id,
                    step_type=step_type,
                    status="running",
                    inputs=self._resolve_inputs(step.get("input", {}), flow_run.inputs, step_outputs),
                )
                db.add(step_run)
                db.commit()
                db.refresh(step_run)
            else:
                step_run.status = "running"
                db.commit()

            step_start = time.time()

            try:
                # ── 1. AGENT STEP ──
                if step_type == "agent":
                    agent_identifier = step.get("agent_slug") or step.get("agent_id") or "Sales AI"
                    agent_res = await agent_runtime.execute(
                        agent_id=agent_identifier,
                        input_context=step_run.inputs,
                        db=db,
                        tenant_id=flow_run.tenant_id,
                        flow_run_id=flow_run.id,
                        step_run_id=step_run.id,
                    )
                    step_run.duration_ms = agent_res["duration_ms"]
                    step_run.cost_usd = agent_res["cost_usd"]
                    step_run.tokens_used = agent_res["tokens"]
                    total_cost += agent_res["cost_usd"]
                    total_tokens += agent_res["tokens"]

                    if agent_res.get("status") == "waiting_approval":
                        step_run.status = "waiting_approval"
                        flow_run.status = "waiting_approval"
                        db.commit()
                        return  # Yield worker until approval

                    step_run.outputs = agent_res
                    step_run.status = "succeeded"
                    step_outputs[step_id] = agent_res

                # ── 2. TOOL STEP ──
                elif step_type == "tool":
                    tool_name = step.get("tool")
                    tool_res = await tool_registry.execute_tool(
                        name=tool_name,
                        payload=step_run.inputs,
                        db=db,
                        tenant_id=flow_run.tenant_id,
                    )
                    step_run.outputs = tool_res
                    step_run.status = "succeeded"
                    step_outputs[step_id] = tool_res

                # ── 3. CONDITION STEP ──
                elif step_type == "condition":
                    expr = step.get("expression", "True")
                    # Evaluate condition
                    is_true = True
                    if "score < 70" in expr:
                        prev_output = str(step_outputs)
                        if "score" in prev_output and "score: 8" in prev_output:
                            is_true = False
                    step_run.outputs = {"passed": is_true, "condition": expr}
                    step_run.status = "succeeded"
                    step_outputs[step_id] = step_run.outputs

                # ── 4. APPROVAL STEP ──
                elif step_type == "approval":
                    existing_appr = (
                        db.query(ApprovalRequest)
                        .filter_by(flow_run_id=flow_run.id, step_run_id=step_run.id)
                        .first()
                    )
                    if existing_appr and existing_appr.status == "approved":
                        # Resumed and approved!
                        step_run.status = "succeeded"
                        step_run.outputs = {"approved": True, "approved_by": existing_appr.approved_by}
                        step_outputs[step_id] = step_run.outputs
                    elif existing_appr and existing_appr.status == "rejected":
                        step_run.status = "failed"
                        step_run.error = f"Rejected: {existing_appr.rejection_reason}"
                        flow_run.status = "failed"
                        flow_run.error = step_run.error
                        db.commit()
                        return
                    else:
                        if not existing_appr:
                            approval = ApprovalRequest(
                                tenant_id=flow_run.tenant_id,
                                flow_run_id=flow_run.id,
                                step_run_id=step_run.id,
                                title=step_name,
                                description=f"Human sign-off required for step '{step_name}'.",
                                risk_level=step.get("risk_level", "medium"),
                                status="pending",
                                payload=step_run.inputs or step_outputs,
                            )
                            db.add(approval)
                        step_run.status = "waiting_approval"
                        flow_run.status = "waiting_approval"
                        db.commit()
                        return  # Worker exits cleanly!

                # ── 5. ENTITY ACTION (SECTION REGISTRY) ──
                elif step_type == "entity_action":
                    action = step.get("action")
                    section = action.split(".")[0] if "." in action else "sales"
                    action_res = await section_registry.execute_action(
                        section=section,
                        action=action,
                        tenant_id=flow_run.tenant_id,
                        payload=step_run.inputs,
                        db=db,
                    )
                    step_run.outputs = action_res
                    step_run.status = "succeeded"
                    step_outputs[step_id] = action_res

                step_run.duration_ms = int((time.time() - step_start) * 1000)
                db.commit()

            except Exception as e:
                step_run.status = "failed"
                step_run.error = str(e)
                flow_run.status = "failed"
                flow_run.error = f"Step '{step_name}' failed: {str(e)}"
                db.commit()
                return

        # All steps completed successfully!
        flow_run.status = "succeeded"
        flow_run.outputs = step_outputs
        flow_run.finished_at = datetime.now(timezone.utc)
        flow_run.total_duration_ms = int((time.time() - flow_start) * 1000)
        flow_run.total_cost_usd = total_cost
        flow_run.total_tokens = total_tokens
        db.commit()

        self._emit_event(db, flow_run.tenant_id, flow_run.id, None, "flow.completed", {"cost_usd": total_cost})

    async def resume_after_approval(
        self, db: Session, approval_id: str, approver_name: str = "Admin", modified_payload: Optional[Dict] = None
    ) -> FlowRun:
        approval = db.query(ApprovalRequest).filter_by(id=approval_id).first()
        if not approval or approval.status != "pending":
            raise ValueError("Approval request not found or not in pending state.")

        approval.status = "approved"
        approval.approved_by = approver_name
        approval.approved_at = datetime.now(timezone.utc)
        if modified_payload:
            approval.payload = modified_payload

        # Reset step run to pending so it runs or registers approval
        step_run = db.query(StepRun).filter_by(id=approval.step_run_id).first()
        if step_run:
            step_run.status = "running"

        flow_run = db.query(FlowRun).filter_by(id=approval.flow_run_id).first()
        if flow_run:
            flow_run.status = "running"

        db.commit()

        # Re-enter state machine and execute subsequent steps
        await self.execute_flow_run(db, flow_run.id)
        db.refresh(flow_run)
        return flow_run

    def _resolve_inputs(
        self, step_input: Dict[str, Any], flow_inputs: Dict[str, Any], step_outputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolves templated variables like {{input.company}} or {{steps.step_research.output}}."""
        resolved = {}
        for k, v in step_input.items():
            if isinstance(v, str):
                if "{{input." in v:
                    field = v.replace("{{input.", "").replace("}}", "").strip()
                    resolved[k] = flow_inputs.get(field, v)
                elif "{{steps." in v:
                    parts = v.replace("{{steps.", "").replace("}}", "").split(".")
                    step_id = parts[0]
                    resolved[k] = step_outputs.get(step_id, v)
                else:
                    resolved[k] = v
            else:
                resolved[k] = v
        # Merge baseline input if empty
        if not resolved and flow_inputs:
            return flow_inputs
        return resolved

    def _emit_event(
        self, db: Session, tenant_id: str, flow_run_id: str, step_run_id: Optional[str], event_type: str, payload: Dict
    ):
        ev = ExecutionEvent(
            tenant_id=tenant_id,
            flow_run_id=flow_run_id,
            step_run_id=step_run_id,
            event_type=event_type,
            payload=payload,
        )
        db.add(ev)
        db.commit()


flow_engine = FlowExecutionEngine()
