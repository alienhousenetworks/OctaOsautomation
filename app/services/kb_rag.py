"""Knowledge base RAG with citations and refuse-if-not-in-KB mode."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.agents import KnowledgeDocument
from app.models.enterprise import KnowledgeChunk, TenantPolicy


class KnowledgeRAGService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def index_document(self, document_id: str) -> int:
        doc = (
            self.db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.tenant_id == self.tenant_id,
            )
            .first()
        )
        if not doc:
            raise ValueError("Document not found")

        # Deactivate old chunks
        old = (
            self.db.query(KnowledgeChunk)
            .filter(
                KnowledgeChunk.document_id == document_id,
                KnowledgeChunk.tenant_id == self.tenant_id,
            )
            .all()
        )
        max_ver = max([c.version for c in old], default=0)
        for c in old:
            c.is_active = False

        chunks = self._chunk_text(doc.content or "")
        for i, text in enumerate(chunks):
            self.db.add(
                KnowledgeChunk(
                    tenant_id=self.tenant_id,
                    document_id=doc.id,
                    department=doc.department or "General",
                    version=max_ver + 1,
                    title=f"{doc.doc_type} #{i+1}",
                    content=text,
                    embedding_hint=self._fingerprint(text),
                    is_active=True,
                )
            )
        self.db.commit()
        return len(chunks)

    def _chunk_text(self, text: str, size: int = 800) -> List[str]:
        text = text.strip()
        if not text:
            return []
        parts = re.split(r"\n{2,}", text)
        chunks: List[str] = []
        buf = ""
        for p in parts:
            if len(buf) + len(p) < size:
                buf = f"{buf}\n\n{p}".strip()
            else:
                if buf:
                    chunks.append(buf)
                buf = p
        if buf:
            chunks.append(buf)
        return chunks

    def _fingerprint(self, text: str) -> str:
        words = re.findall(r"[a-zA-Z0-9]{3,}", text.lower())
        # keep frequent-ish unique tokens
        return " ".join(sorted(set(words))[:40])

    def retrieve(
        self,
        query: str,
        *,
        department: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        from app.services.rag.hybrid_engine import HybridRAGEngine
        engine = HybridRAGEngine(self.db, self.tenant_id)
        hits = engine.retrieve(query, department=department, top_k=top_k)
        if hits:
            return hits

        # Fallback to raw documents if no chunk hits
        docs = (
            self.db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.tenant_id == self.tenant_id,
                KnowledgeDocument.is_active == True,
            )
            .all()
        )
        results = []
        query_tokens = set(re.findall(r"[a-zA-Z0-9]{3,}", query.lower()))
        for d in docs:
            content = d.content or ""
            tokens = set(re.findall(r"[a-zA-Z0-9]{3,}", content.lower()))
            score = len(query_tokens & tokens)
            if score > 0 or query.lower() in content.lower():
                results.append(
                    {
                        "chunk_id": None,
                        "document_id": d.id,
                        "title": d.doc_type,
                        "department": d.department,
                        "content": content[:1200],
                        "score": score + (5 if query.lower() in content.lower() else 0),
                        "citation": f"[{d.doc_type}] (doc:{d.id[:8]})",
                    }
                )
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def answer_context(
        self,
        query: str,
        *,
        department: Optional[str] = None,
        refuse_if_empty: Optional[bool] = None,
    ) -> Dict[str, Any]:
        hits = self.retrieve(query, department=department)
        if refuse_if_empty is None:
            policy = (
                self.db.query(TenantPolicy)
                .filter(TenantPolicy.tenant_id == self.tenant_id)
                .first()
            )
            refuse_if_empty = bool(policy.support_refuse_if_not_in_kb) if policy else True

        if not hits:
            if refuse_if_empty:
                return {
                    "mode": "refuse",
                    "answer_allowed": False,
                    "message": "I don't have this information in the knowledge base. Escalating to a human agent.",
                    "citations": [],
                    "context": "",
                }
            return {
                "mode": "open",
                "answer_allowed": True,
                "message": None,
                "citations": [],
                "context": "",
            }

        context_parts = []
        citations = []
        for h in hits:
            context_parts.append(f"{h['citation']}:\n{h['content']}")
            citations.append(h["citation"])
        return {
            "mode": "grounded",
            "answer_allowed": True,
            "message": None,
            "citations": citations,
            "context": "\n\n---\n\n".join(context_parts),
            "hits": hits,
        }
