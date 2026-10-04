import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.services.executive_os.quarantined_reader import QuarantinedResearchReader
from app.services.agents.executive.research_verifier import ResearchVerifierAgent

logger = logging.getLogger(__name__)

class CompetitorWatchAgent:
    """
    Agent #6: Competitor Watch (Executive Cognitive Layer)
    Trust Level: L0 Read-only (Competitive Intelligence)

    Responsibilities:
    - Tracks competitor pricing, feature announcements, and market moves
    - Ingests pricing sheets and public filings via QuarantinedResearchReader
    - Submits claims to ResearchVerifierAgent to filter rumors and unverified single-sources
    """
    AGENT_ID = "agent_06_competitor_watch"
    AGENT_NAME = "Competitor Watch"
    DEPARTMENT = "COMPETITIVE_INTEL"

    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.reader = QuarantinedResearchReader(db, tenant_id)
        self.verifier = ResearchVerifierAgent(db, tenant_id)

    def monitor_competitor(
        self,
        competitor_name: str,
        sources_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Ingests competitor intelligence sources and extracts verified claims.
        """
        processed_sources = []
        verified_clusters = []

        for src in sources_data:
            url = src.get("url", f"https://{competitor_name.lower()}.com/pricing")
            content = src.get("content", "")
            title = src.get("title", f"{competitor_name} Intel")
            reputation = src.get("reputation", 0.70)

            ingest_res = self.reader.ingest_document(
                url=url,
                raw_content=content,
                title=title,
                domain_reputation=reputation
            )
            processed_sources.append(ingest_res)

            for claim in ingest_res.get("extracted_claims", []):
                cluster_res = self.verifier.cluster_and_verify_claim(
                    source_id=ingest_res["source_id"],
                    normalized_statement=claim["raw_statement"],
                    entity_id=f"competitor:{competitor_name.lower().replace(' ', '_')}",
                    extracted_value=claim.get("extracted_value"),
                    consensus_unit=claim.get("unit")
                )
                verified_clusters.append(cluster_res)

        return {
            "competitor_name": competitor_name,
            "sources_analyzed_count": len(processed_sources),
            "sources": processed_sources,
            "verified_clusters": verified_clusters
        }
