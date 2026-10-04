import re
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class ChiefOfStaffAgent:
    """
    Agent #1: Chief of Staff (Executive Cognitive Layer)
    Trust Level: L0 Read-only (Intent Ingestion & Strategic Routing)

    Responsibilities:
    - Ingests unstructured CEO directives / prompts
    - Compiles prompt into a typed IntentAST
    - Identifies strategic pillar (REVENUE, COST, TALENT, EXPANSION, CRISIS)
    - Extracts explicit constraints, target KPIs, and budget boundaries
    - Sets routing flags for Market Scout and Competitor Watch
    """
    AGENT_ID = "agent_01_chief_of_staff"
    AGENT_NAME = "Chief of Staff"
    DEPARTMENT = "EXECUTIVE"

    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def parse_intent(self, prompt: str, budget_override: Optional[float] = None) -> Dict[str, Any]:
        """
        Parses CEO directive into a validated IntentAST.
        """
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise ValueError("CEO objective prompt cannot be empty.")

        # Determine Strategic Pillar
        lower_prompt = clean_prompt.lower()
        if any(w in lower_prompt for w in ["sales", "pipeline", "revenue", "outreach", "lead", "deal", "grow", "arr", "acv"]):
            pillar = "REVENUE"
        elif any(w in lower_prompt for w in ["cost", "spend", "burn", "budget", "reduce", "cut", "save"]):
            pillar = "COST"
        elif any(w in lower_prompt for w in ["hire", "recruit", "talent", "headcount", "engineer", "sales rep"]):
            pillar = "TALENT"
        elif any(w in lower_prompt for w in ["expand", "international", "europe", "asia", "new market", "launch"]):
            pillar = "EXPANSION"
        elif any(w in lower_prompt for w in ["crisis", "outage", "security", "breach", "legal", "churn", "incident"]):
            pillar = "CRISIS"
        else:
            pillar = "REVENUE"

        # Extract budget cap
        budget_cap = budget_override
        if budget_cap is None:
            budget_match = re.search(r"\$(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:k|m|thousand|million)?", lower_prompt)
            if budget_match:
                val_str = budget_match.group(1).replace(",", "")
                multiplier = 1.0
                if "k" in budget_match.group(0).lower() or "thousand" in budget_match.group(0).lower():
                    multiplier = 1000.0
                elif "m" in budget_match.group(0).lower() or "million" in budget_match.group(0).lower():
                    multiplier = 1000000.0
                budget_cap = float(val_str) * multiplier
            else:
                budget_cap = 5000.0 # Default conservative executive envelope

        # Extract timeline days
        timeline_days = 30
        timeline_match = re.search(r"(\d+)\s*(?:days?|weeks?|months?)", lower_prompt)
        if timeline_match:
            num = int(timeline_match.group(1))
            matched_str = timeline_match.group(0).lower()
            if "week" in matched_str:
                timeline_days = num * 7
            elif "month" in matched_str:
                timeline_days = num * 30
            else:
                timeline_days = num

        # Extract constraints and ambiguities
        constraints = []
        ambiguities = []

        if "without" in lower_prompt:
            without_clause = clean_prompt[lower_prompt.find("without"):]
            constraints.append(without_clause)

        if "only" in lower_prompt:
            only_clause = clean_prompt[lower_prompt.find("only"):]
            constraints.append(only_clause)

        if len(clean_prompt.split()) < 6:
            ambiguities.append("Brief directive: parameters and channels are largely unconstrained.")

        # Intelligence routing decisions
        requires_market_scout = pillar in ["REVENUE", "EXPANSION"]
        requires_competitor_watch = any(w in lower_prompt for w in ["competitor", "pricing", "market", "alternative", "versus", "vs"])

        return {
            "intent_ast": {
                "primary_objective": clean_prompt,
                "strategic_pillar": pillar,
                "explicit_constraints": constraints,
                "ambiguities_flagged": ambiguities,
                "timeline_days": timeline_days,
                "budget_envelope_cap": budget_cap
            },
            "routing_plan": {
                "requires_market_scout": requires_market_scout,
                "requires_competitor_watch": requires_competitor_watch,
                "budget_envelope_cap": budget_cap
            }
        }
