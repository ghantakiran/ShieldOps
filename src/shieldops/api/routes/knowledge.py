"""API routes for RAG knowledge base."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shieldops.agents.knowledge.rag_store import RAGStore

router = APIRouter()

_store: RAGStore | None = None


def set_store(store: RAGStore) -> None:
    global _store
    _store = store


def _get_store() -> RAGStore:
    if _store is None:
        raise HTTPException(status_code=503, detail="RAG store not initialized")
    return _store


class IngestRequest(BaseModel):
    source: str
    source_type: str = "document"
    text: str


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    source_type: str | None = None
    min_score: float = 0.0


@router.post("/knowledge/ingest")
async def ingest_document(body: IngestRequest) -> dict[str, Any]:
    store = _get_store()
    chunks = store.ingest_text(
        source=body.source,
        source_type=body.source_type,
        text=body.text,
    )
    return {"source": body.source, "chunks_created": chunks}


@router.get("/knowledge/search")
async def search_knowledge(
    query: str,
    top_k: int = 5,
    source_type: str | None = None,
    min_score: float = 0.0,
) -> dict[str, Any]:
    store = _get_store()
    results = store.search(
        query=query,
        top_k=top_k,
        source_type=source_type,
        min_score=min_score,
    )
    return {"results": [r.model_dump() for r in results], "count": len(results)}


@router.get("/knowledge/stats")
async def knowledge_stats() -> dict[str, Any]:
    store = _get_store()
    stats = store.get_stats()
    return stats.model_dump()
