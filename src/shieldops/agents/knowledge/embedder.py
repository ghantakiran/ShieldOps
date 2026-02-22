"""Document embedder — text chunking and embedding generation."""

from __future__ import annotations

import hashlib
import math
from typing import Any

import structlog

logger = structlog.get_logger()


class DocumentChunk(dict):  # type: ignore[type-arg]
    """A chunk of text with metadata for embedding."""

    def __init__(
        self,
        text: str,
        source: str = "",
        chunk_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            text=text,
            source=source,
            chunk_id=chunk_id or hashlib.sha256(text.encode()).hexdigest()[:16],
            metadata=metadata or {},
        )


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    """Split text into overlapping chunks.

    Args:
        text: The text to chunk.
        chunk_size: Target chunk size in characters.
        overlap: Number of overlapping characters between chunks.

    Returns:
        List of text chunks.
    """
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap

    return chunks


def simple_embedding(text: str, dimensions: int = 128) -> list[float]:
    """Generate a simple deterministic embedding for text.

    This is a lightweight fallback when no external embedding API is available.
    Uses character-level hashing to produce a pseudo-embedding vector.
    For production use, replace with a real embedding model.
    """
    if not text:
        return [0.0] * dimensions

    # Character frequency based embedding
    vector = [0.0] * dimensions

    for i, char in enumerate(text.lower()):
        idx = ord(char) % dimensions
        vector[idx] += 1.0
        # Add positional information
        pos_idx = (ord(char) + i) % dimensions
        vector[pos_idx] += 0.5

    # Normalize to unit vector
    magnitude = math.sqrt(sum(v * v for v in vector))
    if magnitude > 0:
        vector = [v / magnitude for v in vector]

    return vector


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(vec_a) != len(vec_b):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    magnitude_a = math.sqrt(sum(a * a for a in vec_a))
    magnitude_b = math.sqrt(sum(b * b for b in vec_b))

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


class DocumentEmbedder:
    """Embeds documents using simple embeddings or external API."""

    def __init__(
        self,
        embedding_model: str = "simple",
        dimensions: int = 128,
    ) -> None:
        self._model = embedding_model
        self._dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text."""
        return simple_embedding(text, dimensions=self._dimensions)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for multiple texts."""
        return [self.embed(t) for t in texts]

    @property
    def dimensions(self) -> int:
        return self._dimensions
