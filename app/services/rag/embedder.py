"""Dense Text Embedding Service for Hybrid RAG.

Supports OpenAI text-embedding-3-small (1536 dims), OpenRouter, and Gemini.
Degrades gracefully to None if no key is configured, allowing hybrid retrieval
to continue via high-performance sparse BM25 matching.
"""
import logging
from typing import List, Optional
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.enterprise import KnowledgeChunk

logger = logging.getLogger(__name__)


def _get_provider_key(db: Session, tenant_id: str, provider: str) -> str:
    """Resolve API key using tenant BYOK first, then platform env settings."""
    try:
        from app.services.ai_gateway import ai_gateway
        return ai_gateway._get_api_key(db, tenant_id, provider)
    except Exception as e:
        logger.debug(f"Could not resolve key for {provider}: {e}")
        return ""


async def embed_texts(
    db: Session,
    tenant_id: str,
    texts: List[str],
) -> Optional[List[List[float]]]:
    """Generate 1536-dimensional dense embeddings for a list of text strings."""
    if not texts:
        return []

    # Clean texts
    clean_texts = [t.strip().replace("\n", " ") for t in texts]
    clean_texts = [t if t else "empty" for t in clean_texts]

    # 1. Try OpenAI embedding first (native 1536 dimensions)
    openai_key = _get_provider_key(db, tenant_id, "openai")
    if openai_key:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                    json={"model": "text-embedding-3-small", "input": clean_texts},
                    timeout=30.0,
                )
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    return [item["embedding"] for item in data]
                else:
                    logger.warning(f"OpenAI embedding returned HTTP {res.status_code}: {res.text}")
        except Exception as e:
            logger.warning(f"OpenAI embedding request failed: {e}")

    # 2. Try OpenRouter embedding (routes to text-embedding-3-small)
    openrouter_key = _get_provider_key(db, tenant_id, "openrouter")
    if openrouter_key:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://openrouter.ai/api/v1/embeddings",
                    headers={"Authorization": f"Bearer {openrouter_key}", "Content-Type": "application/json"},
                    json={"model": "openai/text-embedding-3-small", "input": clean_texts},
                    timeout=30.0,
                )
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    return [item["embedding"] for item in data]
        except Exception as e:
            logger.debug(f"OpenRouter embedding failed: {e}")

    # 3. Try Gemini embedding
    gemini_key = _get_provider_key(db, tenant_id, "gemini")
    if gemini_key:
        try:
            async with httpx.AsyncClient() as client:
                embeddings = []
                for t in clean_texts:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={gemini_key}"
                    res = await client.post(
                        url,
                        json={"content": {"parts": [{"text": t[:2000]}]}},
                        timeout=15.0,
                    )
                    if res.status_code == 200:
                        vals = res.json().get("embedding", {}).get("values", [])
                        # If 768 dims, pad to 1536 to match pgvector column
                        if len(vals) < 1536:
                            vals = vals + [0.0] * (1536 - len(vals))
                        embeddings.append(vals[:1536])
                    else:
                        break
                if len(embeddings) == len(clean_texts):
                    return embeddings
        except Exception as e:
            logger.debug(f"Gemini embedding failed: {e}")

    return None


async def embed_single(db: Session, tenant_id: str, query: str) -> Optional[List[float]]:
    """Generate dense embedding for a single query string."""
    results = await embed_texts(db, tenant_id, [query])
    return results[0] if results else None


async def embed_chunks_for_document(db: Session, tenant_id: str, document_id: str) -> int:
    """Calculate and store dense embeddings for all active chunks of a document."""
    chunks = (
        db.query(KnowledgeChunk)
        .filter(
            KnowledgeChunk.tenant_id == tenant_id,
            KnowledgeChunk.document_id == document_id,
            KnowledgeChunk.is_active == True,
            KnowledgeChunk.embedding == None,  # noqa: E711
        )
        .all()
    )
    if not chunks:
        return 0

    texts = [c.content for c in chunks]
    embeddings = await embed_texts(db, tenant_id, texts)
    if not embeddings or len(embeddings) != len(chunks):
        return 0

    dialect = db.bind.dialect.name if db.bind else ""
    if dialect != "postgresql":
        # Non-postgres (e.g. SQLite in unit tests) doesn't have pgvector
        return 0

    for chunk, vec in zip(chunks, embeddings):
        chunk.embedding = vec

    db.commit()
    return len(chunks)
