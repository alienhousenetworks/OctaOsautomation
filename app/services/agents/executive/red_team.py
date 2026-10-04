import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class RedTeamCriticAgent:
    """
    Agent #3: Red Team Critic (Executive Cognitive Layer)
    Trust Level: L0 Read-only (Adversarial Plan Auditor)

    Responsibilities:
    - Pre-mortem critique of proposed DAG execution plans
    - Identifies attack vectors, single points of failure, and domain risks
    - Evaluates plan fragility score (0.00 to 1.00)
    - Recommends circuit breakers and fallback mitigations
    """
    AGENT_ID = "agent_03_red_team_critic"
    AGENT_NAME = "Red Team Critic"
    DEPARTMENT = "RED_TEAM"

    def __init__(self, db: Optional[Session] = None, tenant_id: Optional[str] = None):
        self.db = db
        self.tenant_id = tenant_id

    def critique_plan(
        self,
        strategy_variant: str,
        nodes: List[Dict[str, Any]],
        intent_constraints: List[str]
    ) -> Dict[str, Any]:
        """
        Conducts adversarial pre-mortem inspection of candidate DAG nodes.
        """
        attack_vectors = []
        node_ids = {n.get("id") for n in nodes}
        has_irreversible = False
        uncompensated_count = 0

        for node in nodes:
            cap_id = node.get("capability_id", "")
            is_comp = node.get("is_compensable", True)
            deps = node.get("depends_on", [])

            # 1. External irreversible action without upstream validation
            if not is_comp:
                has_irreversible = True
                uncompensated_count += 1
                if not deps:
                    attack_vectors.append({
                        "node_id": node.get("id"),
                        "failure_mode": f"Unrooted irreversible external dispatch in '{node.get('name')}'",
                        "severity": "CRITICAL",
                        "counter_hypothesis": "External recipients may receive unauthorized or erroneous sequence before CRM state is validated.",
                        "recommended_circuit_breaker": "Enforce upstream validation node or require explicit executive two-key approval."
                    })

            # 2. Dependency on missing node (broken edge)
            for d in deps:
                if d not in node_ids:
                    attack_vectors.append({
                        "node_id": node.get("id"),
                        "failure_mode": f"Dangling dependency '{d}' in node '{node.get('name')}'",
                        "severity": "CRITICAL",
                        "counter_hypothesis": "Execution engine will deadlock waiting on non-existent node.",
                        "recommended_circuit_breaker": "Remove dangling dependency or insert stub node."
                    })

            # 3. High volume outbound blast radius
            params = node.get("parameters", {})
            leads = params.get("lead_ids", [])
            if len(leads) > 500:
                attack_vectors.append({
                    "node_id": node.get("id"),
                    "failure_mode": f"Mass dispatch velocity ({len(leads)} recipients) in '{node.get('name')}'",
                    "severity": "HIGH",
                    "counter_hypothesis": "Sending to >500 leads simultaneously risks domain reputation burning or spam trigger.",
                    "recommended_circuit_breaker": "Throttle dispatch batches to <= 50 leads per hour."
                })

        # Calculate plan fragility score
        base_fragility = 0.20
        if strategy_variant == "AGGRESSIVE":
            base_fragility += 0.25
        elif strategy_variant == "CONSERVATIVE":
            base_fragility -= 0.10

        fragility_penalty = 0.15 * len([v for v in attack_vectors if v["severity"] == "CRITICAL"])
        fragility_penalty += 0.08 * len([v for v in attack_vectors if v["severity"] == "HIGH"])

        final_fragility = min(0.95, max(0.05, round(base_fragility + fragility_penalty, 2)))

        return {
            "strategy_variant": strategy_variant,
            "attack_vectors": attack_vectors,
            "fragility_score": final_fragility,
            "pre_mortem_verdict": "REJECT" if final_fragility >= 0.70 else "PROCEED_WITH_CAUTION" if final_fragility >= 0.40 else "APPROVED"
        }
