"""Hybrid RAG Engine with Reciprocal Rank Fusion, Dense pgvector, and Citation Provenance.

Combines:
1. Dense Vector Similarity Search (pgvector cosine distance <=> operator)
2. Sparse Keyword Matching (BM25 token intersection + phrase exact boost)
3. Reciprocal Rank Fusion (RRF) Reranking: RRF(d) = 1/(k + rank_dense) + 1/(k + rank_sparse)
4. Exact Citation & Provenance Assembling with page numbers and source URLs
"""
import re
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.enterprise import KnowledgeChunk
from app.models.agents import KnowledgeDocument
from app.models.deal_room import EvidenceRecord
from app.services.rag.embedder import embed_single

logger = logging.getLogger(__name__)


STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "are", "from", "about", "tell",
    "what", "does", "how", "why", "who", "when", "where", "can", "you", "all",
    "our", "your", "its", "was", "were", "been", "have", "has", "had", "will",
    "would", "could", "should", "not", "but", "into", "also", "than", "then", "per",
}


class HybridRAGEngine:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        department: Optional[str] = None,
        category: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute hybrid retrieval over knowledge chunks and atomic evidence."""
        query_tokens = {w for w in re.findall(r"\b[a-zA-Z0-9]{3,}\b", query.lower()) if w not in STOP_WORDS}
        
        # 1. Fetch active candidate chunks
        q = (
            self.db.query(KnowledgeChunk)
            .filter(
                KnowledgeChunk.tenant_id == self.tenant_id,
                KnowledgeChunk.is_active == True,  # noqa: E712
            )
        )
        if department and department.lower() not in ("all", "general"):
            q = q.filter(KnowledgeChunk.department.in_([department, "General", "general"]))
            
        chunks = q.limit(250).all()

        # 2. Sparse / Keyword Scoring (BM25 token intersection approximation)
        sparse_scored = []
        for c in chunks:
            c_text = (c.content or "").lower()
            c_tokens = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", c_text))
            
            overlap = len(query_tokens & c_tokens)
            exact_boost = 5 if query.lower() in c_text else 0
            
            # Additional hint boost if embedding_hint overlaps
            hint_tokens = set((c.embedding_hint or "").lower().split())
            hint_overlap = len(query_tokens & hint_tokens)

            score = overlap + exact_boost + (hint_overlap * 2)
            if score > 0:
                sparse_scored.append({"item": c, "score": score})

        sparse_scored.sort(key=lambda x: x["score"], reverse=True)
        sparse_ranks = {item["item"].id: idx + 1 for idx, item in enumerate(sparse_scored)}

        # 3. Dense Vector Scoring (pgvector cosine distance)
        dense_ranks = {}
        if query_vector:
            try:
                dialect = self.db.bind.dialect.name if self.db.bind else ""
                if dialect == "postgresql":
                    sql = text("""
                        SELECT id, 1 - (embedding <=> :vector) as sim
                        FROM knowledge_chunks
                        WHERE tenant_id = :tenant_id 
                          AND is_active = true 
                          AND embedding IS NOT NULL
                        ORDER BY embedding <=> :vector
                        LIMIT 30
                    """)
                    rows = self.db.execute(sql, {"tenant_id": self.tenant_id, "vector": query_vector}).fetchall()
                    dense_ranks = {r[0]: idx + 1 for idx, r in enumerate(rows)}
            except Exception as e:
                logger.debug(f"pgvector query skipped or failed: {e}")

        # 4. Reciprocal Rank Fusion (RRF, k=60)
        k_rrf = 60
        fused_scores = {}
        all_chunk_ids = set(sparse_ranks.keys()) | set(dense_ranks.keys())

        for chunk_id in all_chunk_ids:
            score = 0.0
            if chunk_id in sparse_ranks:
                score += 1.0 / (k_rrf + sparse_ranks[chunk_id])
            if chunk_id in dense_ranks:
                score += 1.0 / (k_rrf + dense_ranks[chunk_id])
            fused_scores[chunk_id] = score

        # Sort chunks by fused score
        sorted_chunk_ids = sorted(fused_scores.keys(), key=lambda cid: fused_scores[cid], reverse=True)[:top_k]
        
        # Build results with citations
        results = []
        chunk_map = {c.id: c for c in chunks}
        
        for cid in sorted_chunk_ids:
            chunk = chunk_map.get(cid)
            if chunk:
                # Format page / url citation
                page_info = f" p.{chunk.page_start}" if chunk.page_start else ""
                url_info = f" ({chunk.source_url})" if chunk.source_url and chunk.source_url.startswith("http") else ""
                citation = f"[{chunk.title or 'KB Document'}{page_info}{url_info}] (chunk:{chunk.id[:8]} v{chunk.version})"
                
                results.append({
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "title": chunk.title,
                    "content": chunk.content,
                    "citation": citation,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "source_url": chunk.source_url,
                    "section_title": chunk.section_title,
                    "score": round(fused_scores[cid], 4),
                })

        return results

    async def async_retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        department: Optional[str] = None,
        category: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Async retrieve that automatically computes query vector if not supplied."""
        vec = query_vector
        if vec is None:
            try:
                vec = await embed_single(self.db, self.tenant_id, query)
            except Exception as e:
                logger.debug(f"Could not compute query vector: {e}")

        return self.retrieve(query, top_k=top_k, department=department, category=category, query_vector=vec)

    def assemble_context(
        self,
        query: str,
        *,
        top_k: int = 5,
        department: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Assemble cited context payload for LLM consumption."""
        hits = self.retrieve(query, top_k=top_k, department=department, query_vector=query_vector)
        
        if not hits:
            # Query atomic evidence directly as fallback
            evidence = (
                self.db.query(EvidenceRecord)
                .filter(EvidenceRecord.tenant_id == self.tenant_id, EvidenceRecord.is_valid == True)
                .limit(5)
                .all()
            )
            if evidence:
                context_blocks = [f"[{e.location_reference}]: {e.claim}" for e in evidence]
                return {
                    "mode": "evidence_grounded",
                    "context": "\n\n".join(context_blocks),
                    "citations": [e.location_reference for e in evidence],
                    "hits": len(evidence),
                }

            return {
                "mode": "empty",
                "context": "",
                "citations": [],
                "hits": 0,
            }

        context_parts = []
        citations = []
        for h in hits:
            context_parts.append(f"{h['citation']}:\n{h['content']}")
            citations.append(h["citation"])

        return {
            "mode": "grounded",
            "context": "\n\n---\n\n".join(context_parts),
            "citations": citations,
            "hits": len(hits),
        }
