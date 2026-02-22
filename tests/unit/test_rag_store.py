"""Tests for RAG knowledge store — embedder utilities and RAGStore."""

import math

import pytest

from shieldops.agents.knowledge.embedder import (
    DocumentChunk,
    DocumentEmbedder,
    chunk_text,
    cosine_similarity,
    simple_embedding,
)
from shieldops.agents.knowledge.rag_store import (
    IndexStats,
    RAGStore,
    SearchResult,
    StoredChunk,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unit_vector(dimensions: int, index: int) -> list[float]:
    """Create a unit vector with 1.0 at *index* and 0.0 elsewhere."""
    vec = [0.0] * dimensions
    vec[index] = 1.0
    return vec


def _long_text(length: int = 2000) -> str:
    """Return a repeating string of the given length."""
    base = "The server experienced high CPU usage caused by a runaway process. "
    return (base * (length // len(base) + 1))[:length]


# ===========================================================================
# simple_embedding()
# ===========================================================================


class TestSimpleEmbedding:
    """Tests for the simple_embedding() function."""

    def test_returns_correct_dimensions(self):
        vec = simple_embedding("hello world", dimensions=128)
        assert len(vec) == 128

    def test_custom_dimensions(self):
        for dim in (32, 64, 256):
            vec = simple_embedding("test text", dimensions=dim)
            assert len(vec) == dim, f"Expected {dim} dimensions"

    def test_consistent_for_same_text(self):
        vec_a = simple_embedding("identical text")
        vec_b = simple_embedding("identical text")
        assert vec_a == vec_b, "Same text must produce identical embeddings"

    def test_different_for_different_text(self):
        vec_a = simple_embedding("server crashed")
        vec_b = simple_embedding("database timeout")
        assert vec_a != vec_b, "Different texts should produce different embeddings"

    def test_empty_string_returns_zero_vector(self):
        vec = simple_embedding("", dimensions=64)
        assert len(vec) == 64
        assert all(v == 0.0 for v in vec), "Empty text should yield a zero vector"

    def test_output_is_unit_vector(self):
        vec = simple_embedding("normalize me", dimensions=128)
        magnitude = math.sqrt(sum(v * v for v in vec))
        assert magnitude == pytest.approx(1.0, abs=1e-9), (
            "Non-empty embedding must be unit-normalized"
        )

    def test_single_character_produces_nonzero_vector(self):
        vec = simple_embedding("a", dimensions=128)
        assert any(v != 0.0 for v in vec)

    def test_case_insensitivity(self):
        vec_lower = simple_embedding("Hello World")
        vec_upper = simple_embedding("hello world")
        # The function calls text.lower(), so these should be identical
        assert vec_lower == vec_upper

    def test_all_elements_are_floats(self):
        vec = simple_embedding("type check")
        assert all(isinstance(v, float) for v in vec)


# ===========================================================================
# cosine_similarity()
# ===========================================================================


class TestCosineSimilarity:
    """Tests for the cosine_similarity() function."""

    def test_identical_vectors_return_one(self):
        vec = [1.0, 2.0, 3.0]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0, abs=1e-9)

    def test_orthogonal_vectors_return_zero(self):
        vec_a = _unit_vector(4, 0)  # [1,0,0,0]
        vec_b = _unit_vector(4, 1)  # [0,1,0,0]
        assert cosine_similarity(vec_a, vec_b) == pytest.approx(0.0, abs=1e-9)

    def test_opposite_vectors_return_negative_one(self):
        vec_a = [1.0, 0.0]
        vec_b = [-1.0, 0.0]
        assert cosine_similarity(vec_a, vec_b) == pytest.approx(-1.0, abs=1e-9)

    def test_different_length_vectors_return_zero(self):
        vec_a = [1.0, 2.0]
        vec_b = [1.0, 2.0, 3.0]
        assert cosine_similarity(vec_a, vec_b) == 0.0

    def test_zero_vector_a_returns_zero(self):
        zero = [0.0, 0.0, 0.0]
        non_zero = [1.0, 2.0, 3.0]
        assert cosine_similarity(zero, non_zero) == 0.0

    def test_zero_vector_b_returns_zero(self):
        non_zero = [1.0, 2.0, 3.0]
        zero = [0.0, 0.0, 0.0]
        assert cosine_similarity(non_zero, zero) == 0.0

    def test_both_zero_vectors_return_zero(self):
        zero = [0.0, 0.0]
        assert cosine_similarity(zero, zero) == 0.0

    def test_similar_embeddings_score_high(self):
        vec_a = simple_embedding("server crash")
        vec_b = simple_embedding("server failure")
        score = cosine_similarity(vec_a, vec_b)
        assert score > 0.5, f"Related texts should be fairly similar, got {score}"

    def test_unrelated_embeddings_score_lower(self):
        vec_related = cosine_similarity(
            simple_embedding("kubernetes pod restart"),
            simple_embedding("kubernetes container restart"),
        )
        vec_unrelated = cosine_similarity(
            simple_embedding("kubernetes pod restart"),
            simple_embedding("financial quarterly report"),
        )
        assert vec_related > vec_unrelated, "Related texts should score higher than unrelated texts"

    def test_commutative_property(self):
        vec_a = [1.0, 3.0, -5.0]
        vec_b = [4.0, -2.0, 1.0]
        assert cosine_similarity(vec_a, vec_b) == pytest.approx(
            cosine_similarity(vec_b, vec_a), abs=1e-12
        )


# ===========================================================================
# chunk_text()
# ===========================================================================


class TestChunkText:
    """Tests for the chunk_text() function."""

    def test_empty_string_returns_empty_list(self):
        assert chunk_text("") == []

    def test_short_text_returns_single_chunk(self):
        text = "short"
        result = chunk_text(text, chunk_size=500)
        assert result == [text]

    def test_text_exactly_at_chunk_size(self):
        text = "a" * 500
        result = chunk_text(text, chunk_size=500)
        assert len(result) == 1
        assert result[0] == text

    def test_text_splits_into_multiple_chunks(self):
        text = "a" * 1000
        result = chunk_text(text, chunk_size=500, overlap=50)
        assert len(result) >= 2

    def test_overlap_present_between_chunks(self):
        text = "abcdefghij" * 100  # 1000 chars
        result = chunk_text(text, chunk_size=500, overlap=100)
        # The end of chunk[0] and the start of chunk[1] should share characters
        if len(result) >= 2:
            end_of_first = result[0][-100:]
            start_of_second = result[1][:100]
            assert end_of_first == start_of_second, (
                "Overlapping region must match between consecutive chunks"
            )

    def test_no_overlap(self):
        text = "a" * 1000
        result = chunk_text(text, chunk_size=500, overlap=0)
        assert len(result) == 2

    def test_custom_chunk_size(self):
        text = "x" * 300
        result = chunk_text(text, chunk_size=100, overlap=0)
        assert len(result) == 3

    def test_whitespace_only_chunks_are_excluded(self):
        # If a chunk after trimming is empty, it should not appear
        text = "hello" + " " * 600 + "world"
        result = chunk_text(text, chunk_size=500, overlap=0)
        for chunk in result:
            assert chunk.strip() != "", "Whitespace-only chunks should be excluded"

    def test_all_text_represented_in_chunks(self):
        text = "".join(str(i % 10) for i in range(1500))
        result = chunk_text(text, chunk_size=500, overlap=50)
        # Every character in the original text should appear in at least one chunk
        combined = "".join(result)
        # Due to overlap, combined will be longer, but all original chars should appear
        for char in set(text):
            assert char in combined


# ===========================================================================
# DocumentChunk
# ===========================================================================


class TestDocumentChunk:
    """Tests for the DocumentChunk dataclass-like dict."""

    def test_basic_creation(self):
        chunk = DocumentChunk(text="hello", source="test.py")
        assert chunk["text"] == "hello"
        assert chunk["source"] == "test.py"
        assert chunk["chunk_id"] != ""
        assert chunk["metadata"] == {}

    def test_auto_generated_chunk_id(self):
        chunk = DocumentChunk(text="some text")
        assert len(chunk["chunk_id"]) == 16, "Auto-generated chunk_id should be 16 hex chars"

    def test_custom_chunk_id(self):
        chunk = DocumentChunk(text="data", chunk_id="custom-id")
        assert chunk["chunk_id"] == "custom-id"

    def test_same_text_produces_same_auto_id(self):
        a = DocumentChunk(text="deterministic")
        b = DocumentChunk(text="deterministic")
        assert a["chunk_id"] == b["chunk_id"]

    def test_is_dict_subclass(self):
        chunk = DocumentChunk(text="test")
        assert isinstance(chunk, dict)


# ===========================================================================
# DocumentEmbedder
# ===========================================================================


class TestDocumentEmbedder:
    """Tests for the DocumentEmbedder class."""

    def test_embed_returns_correct_dimensions(self):
        embedder = DocumentEmbedder(dimensions=64)
        vec = embedder.embed("hello")
        assert len(vec) == 64

    def test_default_dimensions(self):
        embedder = DocumentEmbedder()
        assert embedder.dimensions == 128

    def test_embed_consistent_output(self):
        embedder = DocumentEmbedder()
        assert embedder.embed("test") == embedder.embed("test")

    def test_embed_batch_returns_list_of_vectors(self):
        embedder = DocumentEmbedder(dimensions=32)
        texts = ["alpha", "beta", "gamma"]
        results = embedder.embed_batch(texts)
        assert len(results) == 3
        for vec in results:
            assert len(vec) == 32

    def test_embed_batch_empty_list(self):
        embedder = DocumentEmbedder()
        assert embedder.embed_batch([]) == []

    def test_embed_batch_consistency(self):
        embedder = DocumentEmbedder()
        individual = [embedder.embed(t) for t in ["x", "y"]]
        batched = embedder.embed_batch(["x", "y"])
        assert individual == batched

    def test_dimensions_property(self):
        embedder = DocumentEmbedder(dimensions=256)
        assert embedder.dimensions == 256


# ===========================================================================
# RAGStore — Ingestion
# ===========================================================================


class TestRAGStoreIngestion:
    """Tests for RAGStore ingest methods."""

    @pytest.fixture()
    def store(self) -> RAGStore:
        return RAGStore(chunk_size=500, chunk_overlap=50)

    def test_ingest_incident_returns_chunk_count(self, store: RAGStore):
        count = store.ingest_incident(
            incident_id="INC-001",
            description="Database connection pool exhausted",
        )
        assert count >= 1

    def test_ingest_incident_short_text_single_chunk(self, store: RAGStore):
        count = store.ingest_incident(
            incident_id="INC-002",
            description="Short",
        )
        assert count == 1

    def test_ingest_incident_with_all_fields(self, store: RAGStore):
        count = store.ingest_incident(
            incident_id="INC-003",
            description="CPU spike",
            root_cause="Runaway cron job",
            resolution="Killed the process and added resource limits",
            metadata={"severity": "P1", "team": "platform"},
        )
        assert count >= 1
        stats = store.get_stats()
        assert stats.total_documents == 1
        assert stats.incident_chunks == count

    def test_ingest_incident_long_description_creates_multiple_chunks(self, store: RAGStore):
        long_desc = _long_text(2000)
        count = store.ingest_incident(
            incident_id="INC-004",
            description=long_desc,
        )
        assert count > 1

    def test_ingest_playbook_returns_chunk_count(self, store: RAGStore):
        count = store.ingest_playbook(
            playbook_name="restart-service",
            content="Step 1: Check health. Step 2: Restart pod.",
        )
        assert count >= 1

    def test_ingest_playbook_with_metadata(self, store: RAGStore):
        count = store.ingest_playbook(
            playbook_name="scale-up",
            content="Increase replicas to handle load.",
            metadata={"category": "scaling"},
        )
        assert count >= 1
        stats = store.get_stats()
        assert stats.playbook_chunks == count

    def test_ingest_playbook_long_content(self, store: RAGStore):
        long_content = _long_text(3000)
        count = store.ingest_playbook(
            playbook_name="big-playbook",
            content=long_content,
        )
        assert count > 1

    def test_ingest_text_generic(self, store: RAGStore):
        count = store.ingest_text(
            source="wiki-page",
            source_type="runbook",
            text="How to debug memory leaks in Java applications.",
        )
        assert count >= 1
        stats = store.get_stats()
        assert stats.total_documents == 1
        assert stats.total_chunks == count

    def test_ingest_text_with_metadata(self, store: RAGStore):
        store.ingest_text(
            source="doc-1",
            source_type="documentation",
            text="Monitoring setup guide.",
            metadata={"author": "sre-team"},
        )
        results = store.search("monitoring setup")
        assert len(results) >= 1
        assert results[0].metadata == {"author": "sre-team"}

    def test_ingest_text_empty_string(self, store: RAGStore):
        count = store.ingest_text(
            source="empty-doc",
            source_type="runbook",
            text="",
        )
        assert count == 0

    def test_multiple_ingestions_accumulate_documents(self, store: RAGStore):
        store.ingest_incident("INC-A", description="First incident")
        store.ingest_incident("INC-B", description="Second incident")
        store.ingest_playbook("pb-1", content="Playbook content")
        stats = store.get_stats()
        assert stats.total_documents == 3

    def test_incident_chunks_stored_with_correct_source_type(self, store: RAGStore):
        store.ingest_incident("INC-100", description="test")
        results = store.search("test", source_type="incident")
        assert len(results) >= 1
        assert all(r.source_type == "incident" for r in results)

    def test_playbook_chunks_stored_with_correct_source_type(self, store: RAGStore):
        store.ingest_playbook("pb-restart", content="restart the pods")
        results = store.search("restart", source_type="playbook")
        assert len(results) >= 1
        assert all(r.source_type == "playbook" for r in results)


# ===========================================================================
# RAGStore — Search
# ===========================================================================


class TestRAGStoreSearch:
    """Tests for RAGStore.search()."""

    @pytest.fixture()
    def populated_store(self) -> RAGStore:
        store = RAGStore(chunk_size=500, chunk_overlap=50)
        store.ingest_incident(
            "INC-CPU",
            description="High CPU usage on web-server-01 caused by tight loop in request handler",
            root_cause="Infinite loop in /api/process endpoint",
            resolution="Deployed hotfix to break the loop condition",
        )
        store.ingest_incident(
            "INC-OOM",
            description="Out of memory kill on worker node due to memory leak in cache module",
            root_cause="Unbounded cache growth without eviction policy",
            resolution="Added LRU eviction and memory limits",
        )
        store.ingest_playbook(
            "restart-pod",
            content="To restart a pod: kubectl rollout restart deployment/<name>",
        )
        store.ingest_playbook(
            "scale-deployment",
            content="To scale deployment: kubectl scale --replicas=N deployment/<name>",
        )
        return store

    def test_search_returns_results(self, populated_store: RAGStore):
        results = populated_store.search("CPU usage")
        assert len(results) > 0

    def test_search_results_are_ranked_by_score(self, populated_store: RAGStore):
        results = populated_store.search("high CPU")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), "Results must be sorted by score descending"

    def test_search_top_k_limits_results(self, populated_store: RAGStore):
        results = populated_store.search("deployment", top_k=2)
        assert len(results) <= 2

    def test_search_top_k_one(self, populated_store: RAGStore):
        results = populated_store.search("memory leak", top_k=1)
        assert len(results) == 1

    def test_search_source_type_filter_incident(self, populated_store: RAGStore):
        results = populated_store.search("restart", source_type="incident")
        assert all(r.source_type == "incident" for r in results)

    def test_search_source_type_filter_playbook(self, populated_store: RAGStore):
        results = populated_store.search("restart", source_type="playbook")
        assert all(r.source_type == "playbook" for r in results)

    def test_search_min_score_filters_low_scoring(self, populated_store: RAGStore):
        results = populated_store.search("CPU", min_score=0.5)
        assert all(r.score >= 0.5 for r in results)

    def test_search_min_score_very_high_returns_empty(self, populated_store: RAGStore):
        results = populated_store.search("something", min_score=0.9999)
        # Most simple embeddings won't hit 0.9999 unless query == chunk
        # This just verifies min_score filtering works
        for r in results:
            assert r.score >= 0.9999

    def test_search_returns_search_result_objects(self, populated_store: RAGStore):
        results = populated_store.search("CPU")
        for r in results:
            assert isinstance(r, SearchResult)
            assert isinstance(r.chunk_id, str)
            assert isinstance(r.text, str)
            assert isinstance(r.score, float)
            assert isinstance(r.source, str)
            assert isinstance(r.source_type, str)

    def test_search_result_contains_source_info(self, populated_store: RAGStore):
        results = populated_store.search("memory leak", top_k=1)
        assert len(results) == 1
        assert results[0].source in ("INC-CPU", "INC-OOM", "restart-pod", "scale-deployment")

    def test_search_empty_store_returns_empty(self):
        empty_store = RAGStore()
        results = empty_store.search("anything")
        assert results == []

    def test_search_scores_rounded_to_four_decimals(self, populated_store: RAGStore):
        results = populated_store.search("CPU")
        for r in results:
            score_str = str(r.score)
            if "." in score_str:
                decimals = len(score_str.split(".")[1])
                assert decimals <= 4

    def test_search_relevant_incident_ranks_higher(self, populated_store: RAGStore):
        results = populated_store.search("out of memory kill")
        if len(results) >= 2:
            # The OOM incident should rank near the top
            top_sources = [r.source for r in results[:2]]
            assert "INC-OOM" in top_sources, f"Expected INC-OOM in top results, got {top_sources}"

    def test_search_relevant_playbook_ranks_higher(self, populated_store: RAGStore):
        results = populated_store.search("kubectl rollout restart", source_type="playbook")
        assert len(results) >= 1
        assert results[0].source == "restart-pod"


# ===========================================================================
# RAGStore — get_stats()
# ===========================================================================


class TestRAGStoreStats:
    """Tests for RAGStore.get_stats()."""

    def test_empty_store_stats(self):
        store = RAGStore()
        stats = store.get_stats()
        assert stats.total_documents == 0
        assert stats.total_chunks == 0
        assert stats.incident_chunks == 0
        assert stats.playbook_chunks == 0
        assert stats.last_updated is None
        assert stats.embedding_dimensions == 128

    def test_stats_after_incident_ingestion(self):
        store = RAGStore()
        store.ingest_incident("INC-1", description="test incident")
        stats = store.get_stats()
        assert stats.total_documents == 1
        assert stats.incident_chunks >= 1
        assert stats.total_chunks >= 1
        assert stats.last_updated is not None

    def test_stats_after_playbook_ingestion(self):
        store = RAGStore()
        store.ingest_playbook("pb-1", content="playbook content")
        stats = store.get_stats()
        assert stats.total_documents == 1
        assert stats.playbook_chunks >= 1

    def test_stats_reflects_custom_dimensions(self):
        store = RAGStore(embedding_dimensions=256)
        stats = store.get_stats()
        assert stats.embedding_dimensions == 256

    def test_stats_returns_index_stats_model(self):
        store = RAGStore()
        stats = store.get_stats()
        assert isinstance(stats, IndexStats)

    def test_stats_counts_mixed_ingestions(self):
        store = RAGStore()
        store.ingest_incident("INC-1", description="incident one")
        store.ingest_playbook("pb-1", content="playbook one")
        store.ingest_text("wiki", "runbook", text="runbook content")
        stats = store.get_stats()
        assert stats.total_documents == 3
        assert stats.incident_chunks >= 1
        assert stats.playbook_chunks >= 1
        # ingest_text does not increment incident or playbook counts
        assert stats.total_chunks == (stats.incident_chunks + stats.playbook_chunks + 1)


# ===========================================================================
# RAGStore — clear()
# ===========================================================================


class TestRAGStoreClear:
    """Tests for RAGStore.clear()."""

    def test_clear_removes_all_chunks(self):
        store = RAGStore()
        store.ingest_incident("INC-1", description="to be cleared")
        store.ingest_playbook("pb-1", content="to be cleared")
        assert store.get_stats().total_chunks > 0

        store.clear()

        stats = store.get_stats()
        assert stats.total_chunks == 0
        assert stats.total_documents == 0
        assert stats.incident_chunks == 0
        assert stats.playbook_chunks == 0

    def test_clear_makes_search_return_empty(self):
        store = RAGStore()
        store.ingest_incident("INC-1", description="clearing test")
        assert len(store.search("clearing")) > 0

        store.clear()
        assert store.search("clearing") == []

    def test_clear_allows_re_ingestion(self):
        store = RAGStore()
        store.ingest_incident("INC-1", description="first pass")
        store.clear()
        store.ingest_incident("INC-2", description="second pass")
        stats = store.get_stats()
        assert stats.total_documents == 1
        assert stats.total_chunks >= 1

    def test_clear_on_empty_store_is_safe(self):
        store = RAGStore()
        store.clear()  # Should not raise
        assert store.get_stats().total_chunks == 0


# ===========================================================================
# RAGStore — Constructor / Configuration
# ===========================================================================


class TestRAGStoreConfig:
    """Tests for RAGStore constructor parameters."""

    def test_default_configuration(self):
        store = RAGStore()
        stats = store.get_stats()
        assert stats.embedding_dimensions == 128

    def test_custom_embedding_dimensions(self):
        store = RAGStore(embedding_dimensions=64)
        store.ingest_text("src", "doc", text="test")
        results = store.search("test")
        assert len(results) >= 1

    def test_custom_chunk_size_affects_chunking(self):
        small_chunk_store = RAGStore(chunk_size=100, chunk_overlap=0)
        large_chunk_store = RAGStore(chunk_size=5000, chunk_overlap=0)

        text = _long_text(1000)

        small_count = small_chunk_store.ingest_text("src", "doc", text=text)
        large_count = large_chunk_store.ingest_text("src", "doc", text=text)

        assert small_count > large_count, "Smaller chunk size should produce more chunks"


# ===========================================================================
# Pydantic models
# ===========================================================================


class TestPydanticModels:
    """Tests for SearchResult, IndexStats, StoredChunk Pydantic models."""

    def test_search_result_defaults(self):
        sr = SearchResult(chunk_id="c1", text="hello")
        assert sr.source == ""
        assert sr.source_type == ""
        assert sr.score == 0.0
        assert sr.metadata == {}

    def test_stored_chunk_has_indexed_at(self):
        sc = StoredChunk(chunk_id="c1", text="data")
        assert sc.indexed_at is not None

    def test_index_stats_defaults(self):
        stats = IndexStats()
        assert stats.total_documents == 0
        assert stats.total_chunks == 0
        assert stats.last_updated is None
