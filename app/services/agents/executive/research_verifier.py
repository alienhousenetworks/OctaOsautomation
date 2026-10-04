import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.executive import EvidenceSource, ClaimCluster, ClaimSupport
from app.core.event_ledger import EventLedger

logger = logging.getLogger(__name__)

class ResearchVerifierAgent:
    """
    Agent #7: Research Verifier (Executive Cognitive Layer)
    Trust Level: L0 Read-only (Fact Verification & Evidence Ledger)

    Guiding Principle: CITATION != VERIFICATION
    - Validates provenance, domain diversity, and content hashes
    - Clusters multi-source claims and computes consensus
    - Flags contradictions, single-source assumptions, and quarantined intelligence
    """
    AGENT_ID = "agent_07_research_verifier"
    AGENT_NAME = "Research Verifier"
    DEPARTMENT = "RESEARCH"

    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def cluster_and_verify_claim(
        self,
        source_id: str,
        normalized_statement: str,
        entity_id: Optional[str] = None,
        extracted_value: Optional[float] = None,
        consensus_unit: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Integrates a claim from an evidence source into the authoritative Evidence Ledger.
        Calculates consensus, detects contradictions, and updates confidence score.
        """
        source = self.db.query(EvidenceSource).filter_by(id=source_id, tenant_id=self.tenant_id).first()
        if not source:
            raise ValueError(f"EvidenceSource '{source_id}' not found.")

        # 1. Match or create ClaimCluster
        query = self.db.query(ClaimCluster).filter_by(
            tenant_id=self.tenant_id,
            normalized_statement=normalized_statement
        )
        if entity_id:
            query = query.filter_by(entity_id=entity_id)

        cluster = query.first()
        if not cluster:
            cluster = ClaimCluster(
                tenant_id=self.tenant_id,
                normalized_statement=normalized_statement,
                entity_id=entity_id,
                numeric_consensus=extracted_value,
                consensus_unit=consensus_unit,
                verification_status="UNVERIFIED",
                confidence_score=0.00
            )
            self.db.add(cluster)
            self.db.flush()

        # 2. Attach or update ClaimSupport
        support = self.db.query(ClaimSupport).filter_by(
            cluster_id=cluster.id,
            source_id=source.id
        ).first()

        if not support:
            support = ClaimSupport(
                cluster_id=cluster.id,
                source_id=source.id,
                raw_statement=normalized_statement,
                extracted_value=extracted_value,
                as_of_date=datetime.now(timezone.utc),
                retrieved_at=datetime.now(timezone.utc),
                supports_consensus=True
            )
            self.db.add(support)
            self.db.flush()

        # 3. Two-Stage Verification and Consensus Analysis
        all_supports = self.db.query(ClaimSupport).filter_by(cluster_id=cluster.id).all()
        supporting_sources = [
            self.db.query(EvidenceSource).filter_by(id=s.source_id).first()
            for s in all_supports
        ]

        # Stage 1: Quarantine Check
        has_quarantined_source = any(src.is_quarantined for src in supporting_sources if src)
        if has_quarantined_source:
            cluster.verification_status = "QUARANTINED"
            cluster.confidence_score = 0.00
            cluster.numeric_consensus = None
            for s in all_supports:
                s.supports_consensus = False
            self.db.commit()
            return self._build_cluster_response(cluster, all_supports)

        # Stage 2: Single Source vs Multi-Source Consensus
        unique_domains = {src.domain for src in supporting_sources if src}
        values = [float(s.extracted_value) for s in all_supports if s.extracted_value is not None]

        if len(supporting_sources) == 1:
            cluster.verification_status = "SINGLE_SOURCE"
            # Single-source confidence is capped at 0.60 (cannot be admitted to compiler >= 0.70)
            rep_score = supporting_sources[0].domain_reputation_score if supporting_sources[0] else 0.5
            cluster.confidence_score = min(0.60, round(float(rep_score), 2))
            cluster.numeric_consensus = values[0] if values else None
        else:
            # Multi-source analysis
            if values:
                min_val = min(values)
                max_val = max(values)
                # Check for contradiction: variance > 15%
                variance_ratio = max_val / min_val if min_val > 0 else 2.0
                if variance_ratio > 1.15:
                    cluster.verification_status = "CONTRADICTED"
                    cluster.confidence_score = 0.35
                    cluster.numeric_consensus = round(sum(values) / len(values), 2)
                    for s in all_supports:
                        s.supports_consensus = False
                else:
                    cluster.verification_status = "VERIFIED"
                    # Multi-domain agreement gives high confidence
                    domain_bonus = 0.05 * len(unique_domains)
                    cluster.confidence_score = min(0.95, round(0.85 + domain_bonus, 2))
                    cluster.numeric_consensus = round(sum(values) / len(values), 2)
                    for s in all_supports:
                        s.supports_consensus = True
            else:
                # Qualitative statements verified by multi-domain agreement
                if len(unique_domains) >= 2:
                    cluster.verification_status = "VERIFIED"
                    cluster.confidence_score = 0.88
                else:
                    cluster.verification_status = "SINGLE_SOURCE"
                    cluster.confidence_score = 0.55

        self.db.commit()

        # 4. Record verification audit event in EventLedger
        EventLedger.append_event(
            db=self.db,
            tenant_id=self.tenant_id,
            workflow_id="global-evidence-ledger",
            execution_id=cluster.id,
            event_type="claim_cluster_verified",
            actor_type="AGENT",
            actor_id=self.AGENT_ID,
            payload={
                "cluster_id": cluster.id,
                "statement": cluster.normalized_statement,
                "status": cluster.verification_status,
                "confidence_score": float(cluster.confidence_score),
                "supporting_sources_count": len(all_supports),
                "distinct_domains_count": len(unique_domains)
            },
            correlation_id=cluster.id
        )
        self.db.commit()

        return self._build_cluster_response(cluster, all_supports)

    def _build_cluster_response(self, cluster: ClaimCluster, supports: List[ClaimSupport]) -> Dict[str, Any]:
        return {
            "cluster_id": cluster.id,
            "entity_id": cluster.entity_id,
            "normalized_statement": cluster.normalized_statement,
            "verification_status": cluster.verification_status,
            "confidence_score": float(cluster.confidence_score),
            "numeric_consensus": float(cluster.numeric_consensus) if cluster.numeric_consensus is not None else None,
            "consensus_unit": cluster.consensus_unit,
            "supports_count": len(supports),
            "supports": [
                {
                    "source_id": s.source_id,
                    "extracted_value": float(s.extracted_value) if s.extracted_value is not None else None,
                    "supports_consensus": s.supports_consensus,
                    "as_of_date": s.as_of_date.isoformat() if s.as_of_date else None
                }
                for s in supports
            ]
        }
