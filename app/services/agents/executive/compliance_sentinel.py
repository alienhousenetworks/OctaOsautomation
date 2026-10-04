import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.executive import SuppressionList, KillSwitch, PolicyRule

logger = logging.getLogger(__name__)

class ComplianceSentinelAgent:
    """
    Agent #8: Compliance Sentinel (Executive Cognitive Layer)
    Trust Level: L0 Read-only (Legal & Regulatory Pre-Flight Auditor)

    Responsibilities:
    - Pre-flight compliance inspection of proposed DAG node parameters
    - Enforces opt-out suppression blocklists (CAN-SPAM, GDPR, Legal holds)
    - Validates active kill-switches and company governance policies
    - Emits a structured Compliance Scorecard
    """
    AGENT_ID = "agent_08_compliance_sentinel"
    AGENT_NAME = "Compliance Sentinel"
    DEPARTMENT = "COMPLIANCE"

    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def inspect_dag_compliance(self, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Inspects all candidate nodes for policy violations, suppressed recipients, or active kill switches.
        """
        violations = []
        warnings = []

        # 1. Fetch active suppression list for this tenant
        suppressions = self.db.query(SuppressionList).filter_by(tenant_id=self.tenant_id).all()
        suppressed_emails = {s.target_value.lower() for s in suppressions if s.target_type == "EMAIL"}
        suppressed_domains = {s.target_value.lower() for s in suppressions if s.target_type == "DOMAIN"}

        # 2. Fetch active kill-switches
        kill_switches = self.db.query(KillSwitch).filter_by(engaged=True).all()
        engaged_switches = {ks.id for ks in kill_switches if ks.tenant_id in [self.tenant_id, None]}

        for node in nodes:
            cap_id = node.get("capability_id", "")
            params = node.get("parameters", {})
            node_id = node.get("id", "unknown")

            # Check kill switches
            if "GLOBAL" in engaged_switches:
                violations.append({
                    "node_id": node_id,
                    "rule": "KILL_SWITCH",
                    "detail": "Global system-wide kill switch is actively engaged."
                })
            elif cap_id in engaged_switches:
                violations.append({
                    "node_id": node_id,
                    "rule": "KILL_SWITCH",
                    "detail": f"Capability '{cap_id}' is halted by an active kill switch."
                })

            # Check suppression list on lead parameters
            leads = params.get("lead_ids", [])
            for lead in leads:
                lead_str = str(lead).lower()
                if lead_str in suppressed_emails:
                    violations.append({
                        "node_id": node_id,
                        "rule": "SUPPRESSION_LIST",
                        "detail": f"Target recipient '{lead_str}' is on the compliance opt-out suppression list."
                    })
                elif "@" in lead_str:
                    domain = lead_str.split("@")[-1]
                    if domain in suppressed_domains:
                        violations.append({
                            "node_id": node_id,
                            "rule": "SUPPRESSION_LIST",
                            "detail": f"Target domain '{domain}' is on the compliance suppression list."
                        })

        is_compliant = len(violations) == 0
        risk_score = 0.05 if is_compliant else min(1.0, 0.20 * len(violations))

        return {
            "is_compliant": is_compliant,
            "violations_count": len(violations),
            "violations": violations,
            "warnings": warnings,
            "risk_score": round(risk_score, 2),
            "compliance_status": "PASSED" if is_compliant else "VIOLATIONS_DETECTED"
        }
