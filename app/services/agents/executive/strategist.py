import uuid
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class StrategistAgent:
    """
    Agent #2: Strategist (Executive Cognitive Layer)
    Trust Level: L0 Read-only (Plan Synthesis)

    Responsibilities:
    - Compiles verified evidence and IntentAST into three distinct DAG variants:
      1. AGGRESSIVE: Maximum velocity and upside ($P90 focus)
      2. BALANCED: Sequenced milestones and balanced risk ($P50 focus)
      3. CONSERVATIVE: Organic validation and low spend ($P10 focus)
    - Emits typed capability IDs from the Capability Registry only
    """
    AGENT_ID = "agent_02_strategist"
    AGENT_NAME = "Strategist"
    DEPARTMENT = "STRATEGY"

    def __init__(self, db: Optional[Session] = None, tenant_id: Optional[str] = None):
        self.db = db
        self.tenant_id = tenant_id

    def compile_candidate_dags(
        self,
        intent_ast: Dict[str, Any],
        verified_evidence: List[Dict[str, Any]],
        budget_cap: float
    ) -> Dict[str, Dict[str, Any]]:
        """
        Synthesizes candidate DAG structures for Aggressive, Balanced, and Conservative strategies.
        """
        objective = intent_ast.get("primary_objective", "Scale revenue operations")
        pillar = intent_ast.get("strategic_pillar", "REVENUE")

        # 1. Aggressive Variant
        agg_budget = round(budget_cap * 0.95, 2)
        agg_nodes = [
            {
                "id": "node-agg-tag-1",
                "name": "Rapid Lead Qualification & Tagging",
                "department": "CRM",
                "capability_id": "crm.tag_contact",
                "capability_version": "1.0.0",
                "parameters": {"contact_id": "batch-agg-1", "tag": "HIGH_GROWTH_TARGET"},
                "depends_on": [],
                "estimated_duration_seconds": 30,
                "is_compensable": True
            },
            {
                "id": "node-agg-email-1",
                "name": "Mass Multi-Touch Sequence Dispatch",
                "department": "Sales",
                "capability_id": "sales.send_sequence",
                "capability_version": "1.0.0",
                "parameters": {"lead_ids": ["lead-agg-1", "lead-agg-2", "lead-agg-3"], "template_id": "tpl-aggressive-v1", "channel": "smtp"},
                "depends_on": ["node-agg-tag-1"],
                "estimated_duration_seconds": 60,
                "is_compensable": False
            }
        ]

        # 2. Balanced Variant
        bal_budget = round(budget_cap * 0.60, 2)
        bal_nodes = [
            {
                "id": "node-bal-tag-1",
                "name": "Precision Prospect Categorization",
                "department": "CRM",
                "capability_id": "crm.tag_contact",
                "capability_version": "1.0.0",
                "parameters": {"contact_id": "batch-bal-1", "tag": "QUALIFIED_ICP"},
                "depends_on": [],
                "estimated_duration_seconds": 30,
                "is_compensable": True
            },
            {
                "id": "node-bal-email-1",
                "name": "Personalized Milestone Outreach",
                "department": "Sales",
                "capability_id": "sales.send_sequence",
                "capability_version": "1.0.0",
                "parameters": {"lead_ids": ["lead-bal-1", "lead-bal-2"], "template_id": "tpl-balanced-v1", "channel": "smtp"},
                "depends_on": ["node-bal-tag-1"],
                "estimated_duration_seconds": 45,
                "is_compensable": False
            }
        ]

        # 3. Conservative Variant
        con_budget = round(budget_cap * 0.25, 2)
        con_nodes = [
            {
                "id": "node-con-tag-1",
                "name": "Organic Audience Verification",
                "department": "CRM",
                "capability_id": "crm.tag_contact",
                "capability_version": "1.0.0",
                "parameters": {"contact_id": "batch-con-1", "tag": "ORGANIC_NURTURE"},
                "depends_on": [],
                "estimated_duration_seconds": 20,
                "is_compensable": True
            },
            {
                "id": "node-con-email-1",
                "name": "Low-Volume Focused Sequence",
                "department": "Sales",
                "capability_id": "sales.send_sequence",
                "capability_version": "1.0.0",
                "parameters": {"lead_ids": ["lead-con-1"], "template_id": "tpl-conservative-v1", "channel": "smtp"},
                "depends_on": ["node-con-tag-1"],
                "estimated_duration_seconds": 30,
                "is_compensable": False
            }
        ]

        return {
            "AGGRESSIVE": {
                "variant": "AGGRESSIVE",
                "executive_summary": f"High-velocity execution focusing on rapid market capture for '{objective}'.",
                "estimated_budget": agg_budget,
                "max_budget_envelope": budget_cap,
                "nodes": agg_nodes
            },
            "BALANCED": {
                "variant": "BALANCED",
                "executive_summary": f"Milestone-gated execution balancing growth and efficiency for '{objective}'.",
                "estimated_budget": bal_budget,
                "max_budget_envelope": budget_cap,
                "nodes": bal_nodes
            },
            "CONSERVATIVE": {
                "variant": "CONSERVATIVE",
                "executive_summary": f"Risk-averse organic execution safeguarding capital while addressing '{objective}'.",
                "estimated_budget": con_budget,
                "max_budget_envelope": budget_cap,
                "nodes": con_nodes
            }
        }
