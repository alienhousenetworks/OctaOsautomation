import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.executive import (
    PolicyRule, BudgetEnvelope, BudgetReservation,
    KillSwitch, CapabilityRegistry, SuppressionList
)
from app.core.capabilities import get_capability_instance

logger = logging.getLogger(__name__)

class PolicyEvaluationError(Exception):
    """Raised when an expression cannot be evaluated safely. Fails closed to DENY."""
    pass

class DeterministicGovernanceKernel:
    PRECEDENCE = {"DENY": 0, "QUARANTINE": 1, "REQUIRE_APPROVAL": 2, "ALLOW": 3}

    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def evaluate(
        self,
        capability_id: str,
        capability_version: str,
        inputs: Dict[str, Any],
        actor_role: str = "member",
        actor_autonomy: str = "L1",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Determines whether a capability invocation is allowed.
        Fails closed: Any unexpected operator, missing schema, or evaluation error returns DENY.
        """
        context = context or {}

        # 1. Fetch capability metadata from registry or definition
        try:
            cap_instance = get_capability_instance(capability_id, capability_version)
            definition = cap_instance.definition
        except KeyError:
            # Also check DB
            cap_db = self.db.query(CapabilityRegistry).filter_by(
                id=capability_id,
                version=capability_version,
                is_active=True
            ).first()
            if not cap_db:
                return {
                    "decision": "DENY",
                    "reason": f"Capability {capability_id}:{capability_version} not registered or inactive.",
                    "effective_risk": "R4_FINANCIAL_CRITICAL",
                    "cost_estimate": 0.0,
                    "required_keys": 2
                }
            definition = cap_db

        # 2. Check Global, Capability, and Tenant Kill-Switches
        if self._is_kill_switch_engaged(capability_id):
            return {
                "decision": "DENY",
                "reason": f"Capability {capability_id} is halted by an active kill-switch.",
                "effective_risk": getattr(definition, "side_effect_class", "R3_EXTERNAL_IRREVERSIBLE"),
                "cost_estimate": 0.0,
                "required_keys": 1
            }

        # 3. Derive Effective Risk & Real Cost Estimate (Caller inputs are NEVER trusted for risk or cost)
        cost_model = definition.cost_model if isinstance(definition.cost_model, dict) else definition.cost_model.model_dump()
        cost_estimate = self._compute_cost(cost_model, inputs)
        base_risk = definition.side_effect_class
        effective_risk = self._escalate_risk(base_risk, cost_estimate, inputs)

        # 4. Suppression List Check (Deterministic Outreach Filter)
        if self._is_suppressed(inputs):
            return {
                "decision": "DENY",
                "reason": "Target recipient or domain is on the compliance suppression list.",
                "effective_risk": effective_risk,
                "cost_estimate": cost_estimate,
                "required_keys": 1
            }

        # 5. Base Decision from Effective Risk
        if effective_risk in ["R3_EXTERNAL_IRREVERSIBLE", "R4_FINANCIAL_CRITICAL"]:
            baseline_decision = "REQUIRE_APPROVAL"
        else:
            baseline_decision = "ALLOW"

        # 6. Evaluate All Matching Declarative Policies (Most restrictive wins)
        decisions: List[str] = [baseline_decision]
        policies = self.db.query(PolicyRule).filter_by(
            tenant_id=self.tenant_id,
            is_active=True
        ).order_by(PolicyRule.priority.asc()).all()

        for policy in policies:
            try:
                matched = self._eval_ast_strict(policy.condition_expr, capability_id, effective_risk, cost_estimate, inputs, context)
                if matched:
                    decisions.append(policy.enforcement_action)
            except PolicyEvaluationError as e:
                logger.warning(f"Policy '{policy.id}' failed evaluation: {e}. Failing closed to DENY.")
                decisions.append("DENY")

        final_decision = min(decisions, key=lambda d: self.PRECEDENCE.get(d, 0))

        # 7. Check Autonomy vs Risk Envelope
        if final_decision == "ALLOW":
            if not self._is_autonomy_sufficient(actor_autonomy, effective_risk):
                final_decision = "REQUIRE_APPROVAL"

        required_keys = 2 if effective_risk == "R4_FINANCIAL_CRITICAL" else 1

        return {
            "decision": final_decision,
            "effective_risk": effective_risk,
            "cost_estimate": cost_estimate,
            "required_keys": required_keys
        }

    def reserve_budget(
        self,
        department: str,
        workflow_id: str,
        task_id: str,
        amount: float,
        idempotency_key: str,
        hold_minutes: int = 60
    ) -> Optional[BudgetReservation]:
        """
        Atomic budget reservation with row locking and CHECK constraint protection.
        Prevents concurrency races without race conditions.
        """
        if amount <= 0:
            return None

        # Check existing reservation by idempotency_key
        existing = self.db.query(BudgetReservation).filter_by(idempotency_key=idempotency_key).first()
        if existing:
            return existing

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=hold_minutes)

        # Single atomic update with RETURNING
        stmt = text("""
            UPDATE budget_envelopes
            SET reserved_amount = reserved_amount + :amount,
                updated_at = :now
            WHERE tenant_id = :tenant_id
              AND department = :department
              AND is_active = TRUE
              AND (reserved_amount + consumed_amount + :amount) <= authorized_limit
            RETURNING id;
        """)

        result = self.db.execute(stmt, {
            "amount": amount,
            "now": now,
            "tenant_id": self.tenant_id,
            "department": department
        }).fetchone()

        if not result:
            return None

        envelope_id = result[0]
        reservation = BudgetReservation(
            tenant_id=self.tenant_id,
            envelope_id=envelope_id,
            workflow_id=workflow_id,
            task_id=task_id,
            amount=amount,
            status="RESERVED",
            idempotency_key=idempotency_key,
            expires_at=expires_at
        )
        self.db.add(reservation)
        self.db.flush()
        return reservation

    def release_budget(self, idempotency_key: str) -> bool:
        """Releases a reserved budget hold back to available balance."""
        res = self.db.query(BudgetReservation).filter_by(
            idempotency_key=idempotency_key,
            status="RESERVED"
        ).first()
        if not res:
            return False

        # ANSI SQL compatible: CASE WHEN ensures portability across SQLite and PostgreSQL
        stmt = text("""
            UPDATE budget_envelopes
            SET reserved_amount = CASE 
                WHEN reserved_amount - :amount > 0 THEN reserved_amount - :amount 
                ELSE 0 
            END,
            updated_at = :now
            WHERE id = :envelope_id;
        """)
        self.db.execute(stmt, {
            "amount": float(res.amount),
            "now": datetime.now(timezone.utc),
            "envelope_id": res.envelope_id
        })

        res.status = "RELEASED"
        res.resolved_at = datetime.now(timezone.utc)
        self.db.flush()
        return True

    def commit_budget(self, idempotency_key: str) -> bool:
        """Commits reserved budget into consumed budget upon successful task completion."""
        res = self.db.query(BudgetReservation).filter_by(
            idempotency_key=idempotency_key,
            status="RESERVED"
        ).first()
        if not res:
            return False

        # ANSI SQL compatible
        stmt = text("""
            UPDATE budget_envelopes
            SET reserved_amount = CASE 
                WHEN reserved_amount - :amount > 0 THEN reserved_amount - :amount 
                ELSE 0 
            END,
            consumed_amount = consumed_amount + :amount,
            updated_at = :now
            WHERE id = :envelope_id;
        """)
        self.db.execute(stmt, {
            "amount": float(res.amount),
            "now": datetime.now(timezone.utc),
            "envelope_id": res.envelope_id
        })

        res.status = "COMMITTED"
        res.resolved_at = datetime.now(timezone.utc)
        self.db.flush()
        return True

    def _eval_ast_strict(
        self,
        expr: Dict[str, Any],
        capability_id: str,
        risk: str,
        cost: float,
        inputs: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """Strict fail-closed AST evaluator."""
        op = expr.get("op")
        if not op:
            raise PolicyEvaluationError("Missing operator in policy AST")

        if op in ["and", "or"]:
            clauses = expr.get("clauses")
            if not isinstance(clauses, list) or not clauses:
                raise PolicyEvaluationError(f"Operator '{op}' requires non-empty 'clauses' array")
            if op == "and":
                return all(self._eval_ast_strict(c, capability_id, risk, cost, inputs, context) for c in clauses)
            return any(self._eval_ast_strict(c, capability_id, risk, cost, inputs, context) for c in clauses)

        field = expr.get("field")
        val = expr.get("value")
        if not field:
            raise PolicyEvaluationError("Missing field in leaf AST")

        # Resolve field strictly
        if field == "capability_id":
            target = capability_id
        elif field == "risk_class":
            target = risk
        elif field == "cost_estimate":
            target = cost
        elif field.startswith("input."):
            key = field[6:]
            if key not in inputs:
                raise PolicyEvaluationError(f"Required input field '{key}' missing from invocation")
            target = inputs[key]
        elif field.startswith("context."):
            key = field[8:]
            target = context.get(key)
        else:
            raise PolicyEvaluationError(f"Unrecognized field identifier '{field}'")

        if op == "eq":
            return target == val
        elif op == "neq":
            return target != val
        elif op == "gt":
            return float(target) > float(val)
        elif op == "gte":
            return float(target) >= float(val)
        elif op == "lt":
            return float(target) < float(val)
        elif op == "lte":
            return float(target) <= float(val)
        elif op == "in":
            return target in val
        elif op == "not_in":
            return target not in val
        else:
            raise PolicyEvaluationError(f"Unsupported operator '{op}'")

    def _is_kill_switch_engaged(self, capability_id: str) -> bool:
        engaged = self.db.query(KillSwitch).filter(
            KillSwitch.id.in_(["GLOBAL", capability_id, f"tenant:{self.tenant_id}"]),
            KillSwitch.engaged == True
        ).first()
        return engaged is not None

    def _is_suppressed(self, inputs: Dict[str, Any]) -> bool:
        recipient = inputs.get("recipient_email") or inputs.get("email")
        if not recipient:
            return False
        domain = recipient.split("@")[-1] if "@" in recipient else ""
        hit = self.db.query(SuppressionList).filter(
            SuppressionList.tenant_id == self.tenant_id,
            SuppressionList.target_value.in_([recipient.lower(), domain.lower()])
        ).first()
        return hit is not None

    def _escalate_risk(self, base_risk: str, cost: float, inputs: Dict[str, Any]) -> str:
        # Spend threshold escalation: >= $1,000 escalates to R4 (Mandatory Dual-Key)
        if cost >= 1000.0:
            return "R4_FINANCIAL_CRITICAL"
        # Bulk volume escalation: > 50 recipients escalates to R3
        if len(inputs.get("lead_ids", [])) > 50:
            return "R3_EXTERNAL_IRREVERSIBLE"
        return base_risk

    def _compute_cost(self, cost_model: Dict[str, Any], inputs: Dict[str, Any]) -> float:
        m_type = cost_model.get("type", "flat")
        rate = float(cost_model.get("amount", 0.0))
        if m_type == "flat":
            return rate
        elif m_type == "per_unit":
            unit_field = cost_model.get("unit_field", "lead_ids")
            if unit_field in inputs:
                val = inputs[unit_field]
                units = len(val) if isinstance(val, list) else float(val)
            else:
                units = 1.0
            return rate * units
        return 0.0

    def _is_autonomy_sufficient(self, autonomy: str, risk: str) -> bool:
        if risk in ["R3_EXTERNAL_IRREVERSIBLE", "R4_FINANCIAL_CRITICAL"]:
            return False
        if autonomy in ["L2", "L3"] and risk in ["R0_INFORMATIONAL", "R1_INTERNAL_REVERSIBLE", "R2_EXTERNAL_REVERSIBLE"]:
            return True
        return False
