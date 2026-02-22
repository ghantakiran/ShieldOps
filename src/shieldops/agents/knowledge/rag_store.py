"""RAG Store — in-memory vector store for semantic search over incidents and playbooks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

from shieldops.agents.knowledge.embedder import (
    DocumentEmbedder,
    chunk_text,
    cosine_similarity,
)

logger = structlog.get_logger()


class SearchResult(BaseModel):
    """A single search result from the RAG store."""

    chunk_id: str
    text: str
    source: str = ""
    source_type: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class IndexStats(BaseModel):
    """Statistics about the RAG index."""

    total_documents: int = 0
    total_chunks: int = 0
    incident_chunks: int = 0
    playbook_chunks: int = 0
    last_updated: datetime | None = None
    embedding_dimensions: int = 128


class StoredChunk(BaseModel):
    """A chunk stored in the vector store with its embedding."""

    chunk_id: str
    text: str
    source: str = ""
    source_type: str = ""  # incident, playbook, runbook
    embedding: list[float] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    indexed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RAGStore:
    """In-memory vector store for semantic search.

    Supports ingesting incidents and playbooks, then searching
    via cosine similarity over embeddings.
    """

    def __init__(
        self,
        embedding_model: str = "simple",
        embedding_dimensions: int = 128,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> None:
        self._embedder = DocumentEmbedder(
            embedding_model=embedding_model,
            dimensions=embedding_dimensions,
        )
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._chunks: list[StoredChunk] = []
        self._document_count = 0
        self._incident_chunk_count = 0
        self._playbook_chunk_count = 0

    def ingest_incident(
        self,
        incident_id: str,
        description: str,
        root_cause: str = "",
        resolution: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Ingest an incident into the store.

        Returns the number of chunks created.
        """
        text_parts = [f"Incident: {incident_id}"]
        if description:
            text_parts.append(f"Description: {description}")
        if root_cause:
            text_parts.append(f"Root Cause: {root_cause}")
        if resolution:
            text_parts.append(f"Resolution: {resolution}")

        full_text = "\n".join(text_parts)
        chunks = chunk_text(full_text, self._chunk_size, self._chunk_overlap)

        count = 0
        for chunk_text_str in chunks:
            embedding = self._embedder.embed(chunk_text_str)
            stored = StoredChunk(
                chunk_id=f"inc-{uuid4().hex[:12]}",
                text=chunk_text_str,
                source=incident_id,
                source_type="incident",
                embedding=embedding,
                metadata=metadata or {},
            )
            self._chunks.append(stored)
            count += 1

        self._document_count += 1
        self._incident_chunk_count += count

        logger.info(
            "incident_ingested",
            incident_id=incident_id,
            chunks=count,
        )
        return count

    def ingest_playbook(
        self,
        playbook_name: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Ingest a playbook into the store.

        Returns the number of chunks created.
        """
        full_text = f"Playbook: {playbook_name}\n{content}"
        chunks = chunk_text(full_text, self._chunk_size, self._chunk_overlap)

        count = 0
        for chunk_text_str in chunks:
            embedding = self._embedder.embed(chunk_text_str)
            stored = StoredChunk(
                chunk_id=f"pb-{uuid4().hex[:12]}",
                text=chunk_text_str,
                source=playbook_name,
                source_type="playbook",
                embedding=embedding,
                metadata=metadata or {},
            )
            self._chunks.append(stored)
            count += 1

        self._document_count += 1
        self._playbook_chunk_count += count

        logger.info(
            "playbook_ingested",
            playbook=playbook_name,
            chunks=count,
        )
        return count

    def ingest_text(
        self,
        source: str,
        source_type: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Ingest arbitrary text into the store."""
        chunks = chunk_text(text, self._chunk_size, self._chunk_overlap)
        count = 0
        for chunk_text_str in chunks:
            embedding = self._embedder.embed(chunk_text_str)
            stored = StoredChunk(
                chunk_id=f"doc-{uuid4().hex[:12]}",
                text=chunk_text_str,
                source=source,
                source_type=source_type,
                embedding=embedding,
                metadata=metadata or {},
            )
            self._chunks.append(stored)
            count += 1

        self._document_count += 1
        return count

    def search(
        self,
        query: str,
        top_k: int = 5,
        source_type: str | None = None,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        """Semantic search using cosine similarity.

        Args:
            query: The search query text.
            top_k: Number of results to return.
            source_type: Filter by source type (incident, playbook).
            min_score: Minimum similarity score threshold.

        Returns:
            Ranked list of search results.
        """
        if not self._chunks:
            return []

        query_embedding = self._embedder.embed(query)

        # Filter by source type if specified
        candidates = self._chunks
        if source_type:
            candidates = [c for c in candidates if c.source_type == source_type]

        # Score all candidates
        scored: list[tuple[StoredChunk, float]] = []
        for chunk in candidates:
            score = cosine_similarity(query_embedding, chunk.embedding)
            if score >= min_score:
                scored.append((chunk, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Return top_k
        results = []
        for chunk, score in scored[:top_k]:
            results.append(
                SearchResult(
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    source=chunk.source,
                    source_type=chunk.source_type,
                    score=round(score, 4),
                    metadata=chunk.metadata,
                )
            )

        return results

    def get_stats(self) -> IndexStats:
        """Return statistics about the index."""
        return IndexStats(
            total_documents=self._document_count,
            total_chunks=len(self._chunks),
            incident_chunks=self._incident_chunk_count,
            playbook_chunks=self._playbook_chunk_count,
            last_updated=self._chunks[-1].indexed_at if self._chunks else None,
            embedding_dimensions=self._embedder.dimensions,
        )

    def clear(self) -> None:
        """Clear all stored chunks."""
        self._chunks.clear()
        self._document_count = 0
        self._incident_chunk_count = 0
        self._playbook_chunk_count = 0
        logger.info("rag_store_cleared")
