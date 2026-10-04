import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.services.executive_os.quarantined_reader import QuarantinedResearchReader
from app.services.agents.executive.research_verifier import ResearchVerifierAgent

logger = logging.getLogger(__name__)

class MarketScoutAgent:
    """
    Agent #5: Market Scout (Executive Cognitive Layer)
    Trust Level: L0 Read-only (Market Discovery & TAM Sizing)

    Responsibilities:
    - Discovery of market size, growth rates (CAGR), and regulatory shifts
    - Ingests raw external text through QuarantinedResearchReader
    - Submits claims to ResearchVerifierAgent to establish multi-source consensus
    """
    AGENT_ID = "agent_05_market_scout"
    AGENT_NAME = "Market Scout"
    DEPARTMENT = "STRATEGY"

    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.reader = QuarantinedResearchReader(db, tenant_id)
        self.verifier = ResearchVerifierAgent(db, tenant_id)

    def analyze_market_signal(
        self,
        topic: str,
        sources_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Ingests external market sources and compiles verified market claims.
        """
        processed_sources = []
        verified_clusters = []

        for src in sources_data:
            url = src.get("url", "https://market-intelligence.internal/doc")
            content = src.get("content", "")
            title = src.get("title", topic)
            reputation = src.get("reputation", 0.75)

            # Ingest through isolated quarantine reader
            ingest_res = self.reader.ingest_document(
                url=url,
                raw_content=content,
                title=title,
                domain_reputation=reputation
            )
            processed_sources.append(ingest_res)

            # Route each extracted claim through the Research Verifier
            for claim in ingest_res.get("extracted_claims", []):
                cluster_res = self.verifier.cluster_and_verify_claim(
                    source_id=ingest_res["source_id"],
                    normalized_statement=claim["raw_statement"],
                    entity_id=f"market:{topic.lower().replace(' ', '_')}",
                    extracted_value=claim.get("extracted_value"),
                    consensus_unit=claim.get("unit")
                )
                verified_clusters.append(cluster_res)

        return {
            "topic": topic,
            "sources_analyzed_count": len(processed_sources),
            "sources": processed_sources,
            "verified_clusters": verified_clusters
        }
