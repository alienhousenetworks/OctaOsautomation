import uuid
import json
import hashlib
import logging
from collections import defaultdict, deque
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.executive import PlanVersion, PlanNode, ClaimCluster, WorkflowEvent
from app.models.workflows import Workflow
from app.services.agents.executive.chief_of_staff import ChiefOfStaffAgent
from app.services.agents.executive.strategist import StrategistAgent
from app.services.agents.executive.quant_analyst import QuantAnalystEngine
from app.services.agents.executive.red_team import RedTeamCriticAgent
from app.services.agents.executive.compliance_sentinel import ComplianceSentinelAgent
from app.core.event_ledger import EventLedger

logger = logging.getLogger(__name__)

class StrategyCompiler:
    """
    CEO Workspace Strategy Compiler & Multi-Plan Generator (v5.2)
    Compiles high-level CEO directives into 3 validated, versioned, policy-checked DAG plans:
    1. Aggressive (High velocity, $P90 upside)
    2. Balanced (Milestone-gated, $P50 risk/reward)
    3. Conservative (Capital preservation, $P10 baseline)

    Enforces:
    - Evidence admission gate (only claims with confidence >= 0.70 admitted)
    - Kahn's Algorithm topological acyclicity validation
    - Deterministic seeded Monte Carlo quantitative forecasting
    - Adversarial Red Team pre-mortem inspection
    - Pre-flight compliance and suppression auditing
    - Cryptographic plan content hashing (SHA-256)
    """
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.chief_of_staff = ChiefOfStaffAgent(db, tenant_id)
        self.strategist = StrategistAgent(db, tenant_id)
        self.quant_engine = QuantAnalystEngine(db, tenant_id)
        self.red_team = RedTeamCriticAgent(db, tenant_id)
        self.compliance_sentinel = ComplianceSentinelAgent(db, tenant_id)

    @staticmethod
    def validate_acyclicity(nodes: List[Dict[str, Any]]) -> List[str]:
        """
        Validates that the proposed DAG has no cyclic dependencies using Kahn's Algorithm.
        Returns the topologically sorted node IDs. Raises ValueError if a cycle is detected.
        """
        in_degree: Dict[str, int] = {n["id"]: 0 for n in nodes}
        adjacency: Dict[str, List[str]] = defaultdict(list)
        node_ids = set(in_degree.keys())

        for node in nodes:
            nid = node["id"]
            deps = node.get("depends_on", [])
            for dep in deps:
                if dep in node_ids:
                    adjacency[dep].append(nid)
                    in_degree[nid] += 1

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        topological_order = []

        while queue:
            curr = queue.popleft()
            topological_order.append(curr)

            for neighbor in adjacency[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(topological_order) < len(nodes):
            unresolved = [nid for nid, deg in in_degree.items() if deg > 0]
            raise ValueError(f"Cycle detected in plan DAG. Nodes involved in cyclic dependency: {unresolved}")

        return topological_order

    @staticmethod
    def compute_plan_content_hash(
        workflow_id: str,
        version_num: int,
        variant: str,
        nodes: List[Dict[str, Any]]
    ) -> str:
        """
        Computes deterministic SHA-256 hash of the complete plan structure and parameters.
        """
        # Canonical sort of nodes and parameters
        sorted_nodes = sorted(
            [
                {
                    "id": n["id"],
                    "capability_id": n["capability_id"],
                    "capability_version": n.get("capability_version", "1.0.0"),
                    "depends_on": sorted(n.get("depends_on", [])),
                    "parameters": json.loads(json.dumps(n.get("parameters", {}), sort_keys=True))
                }
                for n in nodes
            ],
            key=lambda x: x["id"]
        )
        canonical_str = json.dumps(sorted_nodes, sort_keys=True, separators=(",", ":"))
        envelope = f"{workflow_id}|{version_num}|{variant}|{canonical_str}"
        return hashlib.sha256(envelope.encode("utf-8")).hexdigest()

    def compile_plans(
        self,
        workflow_id: str,
        prompt: str,
        budget_override: Optional[float] = None
    ) -> List[PlanVersion]:
        """
        Executes the authoritative 8-step compiler pipeline.
        """
        wf = self.db.query(Workflow).filter_by(id=workflow_id, tenant_id=self.tenant_id).first()
        if not wf:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        # Step 1: Parse Intent AST
        parsed = self.chief_of_staff.parse_intent(prompt, budget_override)
        intent_ast = parsed["intent_ast"]
        budget_cap = intent_ast["budget_envelope_cap"]

        # Step 2: Query and Filter Evidence Claims (confidence >= 0.70 admission gate)
        eligible_claims = self.db.query(ClaimCluster).filter(
            ClaimCluster.tenant_id == self.tenant_id,
            ClaimCluster.confidence_score >= 0.70
        ).all()

        evidence_factors = [
            {
                "id": c.id,
                "statement": c.normalized_statement,
                "numeric_consensus": float(c.numeric_consensus) if c.numeric_consensus is not None else None,
                "consensus_unit": c.consensus_unit,
                "confidence": float(c.confidence_score)
            }
            for c in eligible_claims
        ]

        # Step 3: Strategist synthesizes 3 candidate DAG variants
        variants_dict = self.strategist.compile_candidate_dags(
            intent_ast=intent_ast,
            verified_evidence=evidence_factors,
            budget_cap=budget_cap
        )

        # Determine next version number
        last_pv = self.db.query(PlanVersion).filter_by(
            workflow_id=workflow_id
        ).order_by(PlanVersion.version_num.desc()).first()
        version_num = (last_pv.version_num + 1) if last_pv else 1

        compiled_versions: List[PlanVersion] = []

        for variant_key in ["AGGRESSIVE", "BALANCED", "CONSERVATIVE"]:
            var_data = variants_dict[variant_key]
            nodes = var_data["nodes"]

            # Step 4: Validate acyclicity via Kahn's Algorithm
            self.validate_acyclicity(nodes)

            # Step 5: Seeded Quant Monte Carlo Simulation (1,000 runs)
            quant_forecast = self.quant_engine.run_monte_carlo(
                strategy_variant=variant_key,
                budget=var_data["estimated_budget"],
                evidence_factors=evidence_factors
            )

            # Step 6: Red Team Adversarial Critique
            red_team_critique = self.red_team.critique_plan(
                strategy_variant=variant_key,
                nodes=nodes,
                intent_constraints=intent_ast.get("explicit_constraints", [])
            )

            # Step 7: Pre-flight Compliance Sentinel Inspection
            compliance_scorecard = self.compliance_sentinel.inspect_dag_compliance(nodes)

            # Step 8: Compute Cryptographic Plan Content Hash
            content_hash = self.compute_plan_content_hash(
                workflow_id=workflow_id,
                version_num=version_num,
                variant=variant_key,
                nodes=nodes
            )

            # Persist PlanVersion
            plan_version = PlanVersion(
                tenant_id=self.tenant_id,
                workflow_id=workflow_id,
                version_num=version_num,
                strategy_variant=variant_key,
                status="DRAFT" if variant_key != "BALANCED" else "ACTIVE", # Default active to balanced
                plan_content_hash=content_hash,
                objective=intent_ast["primary_objective"],
                executive_summary=var_data["executive_summary"],
                estimated_budget=var_data["estimated_budget"],
                max_budget_envelope=var_data["max_budget_envelope"],
                quant_forecast=quant_forecast,
                red_team_critique=red_team_critique,
                compliance_scorecard=compliance_scorecard
            )
            self.db.add(plan_version)
            self.db.flush()

            # Persist PlanNodes
            for n in nodes:
                node_row = PlanNode(
                    id=n["id"],
                    plan_version_id=plan_version.id,
                    name=n["name"],
                    department=n.get("department", "EXECUTION"),
                    capability_id=n["capability_id"],
                    capability_version=n.get("capability_version", "1.0.0"),
                    parameters=n.get("parameters", {}),
                    depends_on=n.get("depends_on", []),
                    estimated_duration_seconds=n.get("estimated_duration_seconds", 60),
                    is_compensable=n.get("is_compensable", True)
                )
                self.db.add(node_row)

            # Record plan_compiled event on EventLedger
            EventLedger.append_event(
                db=self.db,
                tenant_id=self.tenant_id,
                workflow_id=workflow_id,
                execution_id=plan_version.id,
                event_type="plan_compiled",
                actor_type="COMPILER",
                actor_id="StrategyCompiler",
                payload={
                    "plan_version_id": plan_version.id,
                    "version_num": version_num,
                    "strategy_variant": variant_key,
                    "nodes_count": len(nodes),
                    "estimated_budget": float(var_data["estimated_budget"]),
                    "plan_content_hash": content_hash,
                    "fragility_score": red_team_critique.get("fragility_score")
                },
                correlation_id=plan_version.id
            )

            compiled_versions.append(plan_version)

        self.db.commit()
        return compiled_versions
