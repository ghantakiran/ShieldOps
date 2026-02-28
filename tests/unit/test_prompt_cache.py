"""Tests for shieldops.agents.prompt_cache — PromptCacheManager."""

from __future__ import annotations

from shieldops.agents.prompt_cache import (
    CacheEntry,
    CacheHitEvent,
    CacheOutcome,
    CacheStrategy,
    EvictionPolicy,
    PromptCacheManager,
    PromptCacheReport,
)


def _engine(**kw) -> PromptCacheManager:
    return PromptCacheManager(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # CacheStrategy (5)
    def test_strategy_exact_match(self):
        assert CacheStrategy.EXACT_MATCH == "exact_match"

    def test_strategy_semantic_similarity(self):
        assert CacheStrategy.SEMANTIC_SIMILARITY == "semantic_similarity"

    def test_strategy_template_match(self):
        assert CacheStrategy.TEMPLATE_MATCH == "template_match"

    def test_strategy_embedding_based(self):
        assert CacheStrategy.EMBEDDING_BASED == "embedding_based"

    def test_strategy_hybrid(self):
        assert CacheStrategy.HYBRID == "hybrid"

    # CacheOutcome (5)
    def test_outcome_hit(self):
        assert CacheOutcome.HIT == "hit"

    def test_outcome_miss(self):
        assert CacheOutcome.MISS == "miss"

    def test_outcome_partial_hit(self):
        assert CacheOutcome.PARTIAL_HIT == "partial_hit"

    def test_outcome_stale(self):
        assert CacheOutcome.STALE == "stale"

    def test_outcome_evicted(self):
        assert CacheOutcome.EVICTED == "evicted"

    # EvictionPolicy (5)
    def test_eviction_lru(self):
        assert EvictionPolicy.LRU == "lru"

    def test_eviction_lfu(self):
        assert EvictionPolicy.LFU == "lfu"

    def test_eviction_ttl_based(self):
        assert EvictionPolicy.TTL_BASED == "ttl_based"

    def test_eviction_size_based(self):
        assert EvictionPolicy.SIZE_BASED == "size_based"

    def test_eviction_priority(self):
        assert EvictionPolicy.PRIORITY == "priority"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_cache_entry_defaults(self):
        r = CacheEntry()
        assert r.id
        assert r.cache_key == ""
        assert r.cache_strategy == CacheStrategy.EXACT_MATCH
        assert r.cache_outcome == CacheOutcome.MISS
        assert r.eviction_policy == EvictionPolicy.LRU
        assert r.entry_size_bytes == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_cache_hit_event_defaults(self):
        r = CacheHitEvent()
        assert r.id
        assert r.event_label == ""
        assert r.cache_strategy == CacheStrategy.EXACT_MATCH
        assert r.cache_outcome == CacheOutcome.HIT
        assert r.latency_ms == 0.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = PromptCacheReport()
        assert r.total_entries == 0
        assert r.total_events == 0
        assert r.hit_rate_pct == 0.0
        assert r.by_strategy == {}
        assert r.by_outcome == {}
        assert r.eviction_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_entry
# -------------------------------------------------------------------


class TestRecordEntry:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            "key-a",
            cache_strategy=CacheStrategy.SEMANTIC_SIMILARITY,
            cache_outcome=CacheOutcome.HIT,
        )
        assert r.cache_key == "key-a"
        assert r.cache_strategy == CacheStrategy.SEMANTIC_SIMILARITY

    def test_with_size(self):
        eng = _engine()
        r = eng.record_entry(
            "key-b",
            eviction_policy=EvictionPolicy.LFU,
            entry_size_bytes=4096,
        )
        assert r.eviction_policy == EvictionPolicy.LFU
        assert r.entry_size_bytes == 4096

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(f"key-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_entry
# -------------------------------------------------------------------


class TestGetEntry:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry("key-a")
        assert eng.get_entry(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_entry("nonexistent") is None


# -------------------------------------------------------------------
# list_entries
# -------------------------------------------------------------------


class TestListEntries:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry("key-a")
        eng.record_entry("key-b")
        assert len(eng.list_entries()) == 2

    def test_filter_by_key(self):
        eng = _engine()
        eng.record_entry("key-a")
        eng.record_entry("key-b")
        results = eng.list_entries(cache_key="key-a")
        assert len(results) == 1

    def test_filter_by_strategy(self):
        eng = _engine()
        eng.record_entry("key-a", cache_strategy=CacheStrategy.HYBRID)
        eng.record_entry("key-b", cache_strategy=CacheStrategy.EXACT_MATCH)
        results = eng.list_entries(cache_strategy=CacheStrategy.HYBRID)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_event
# -------------------------------------------------------------------


class TestAddEvent:
    def test_basic(self):
        eng = _engine()
        e = eng.add_event(
            "event-1",
            cache_strategy=CacheStrategy.TEMPLATE_MATCH,
            cache_outcome=CacheOutcome.HIT,
            latency_ms=5.5,
        )
        assert e.event_label == "event-1"
        assert e.latency_ms == 5.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_event(f"event-{i}")
        assert len(eng._events) == 2


# -------------------------------------------------------------------
# analyze_cache_performance
# -------------------------------------------------------------------


class TestAnalyzeCachePerformance:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry("key-a", cache_outcome=CacheOutcome.HIT, entry_size_bytes=100)
        eng.record_entry("key-a", cache_outcome=CacheOutcome.MISS, entry_size_bytes=200)
        result = eng.analyze_cache_performance("key-a")
        assert result["cache_key"] == "key-a"
        assert result["total_entries"] == 2
        assert result["hit_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_cache_performance("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine()
        eng.record_entry("key-a", cache_outcome=CacheOutcome.HIT)
        result = eng.analyze_cache_performance("key-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_low_hit_keys
# -------------------------------------------------------------------


class TestIdentifyLowHitKeys:
    def test_with_misses(self):
        eng = _engine()
        eng.record_entry("key-a", cache_outcome=CacheOutcome.MISS)
        eng.record_entry("key-a", cache_outcome=CacheOutcome.STALE)
        eng.record_entry("key-b", cache_outcome=CacheOutcome.HIT)
        results = eng.identify_low_hit_keys()
        assert len(results) == 1
        assert results[0]["cache_key"] == "key-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_hit_keys() == []


# -------------------------------------------------------------------
# rank_by_hit_rate
# -------------------------------------------------------------------


class TestRankByHitRate:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry("key-a", cache_outcome=CacheOutcome.HIT)
        eng.record_entry("key-a", cache_outcome=CacheOutcome.HIT)
        eng.record_entry("key-b", cache_outcome=CacheOutcome.MISS)
        results = eng.rank_by_hit_rate()
        assert results[0]["cache_key"] == "key-a"
        assert results[0]["hit_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_hit_rate() == []


# -------------------------------------------------------------------
# detect_cache_thrashing
# -------------------------------------------------------------------


class TestDetectCacheThrashing:
    def test_with_thrashing(self):
        eng = _engine()
        for _ in range(5):
            eng.record_entry("key-a", cache_outcome=CacheOutcome.EVICTED)
        eng.record_entry("key-b", cache_outcome=CacheOutcome.HIT)
        results = eng.detect_cache_thrashing()
        assert len(results) == 1
        assert results[0]["cache_key"] == "key-a"
        assert results[0]["thrashing"] is True

    def test_no_thrashing(self):
        eng = _engine()
        eng.record_entry("key-a", cache_outcome=CacheOutcome.HIT)
        assert eng.detect_cache_thrashing() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry("key-a", cache_outcome=CacheOutcome.HIT)
        eng.record_entry("key-b", cache_outcome=CacheOutcome.EVICTED)
        eng.add_event("event-1")
        report = eng.generate_report()
        assert report.total_entries == 2
        assert report.total_events == 1
        assert report.by_strategy != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_entries == 0
        assert report.recommendations[0] == "Prompt cache performance meets targets"

    def test_low_hit_rate(self):
        eng = _engine()
        eng.record_entry("key-a", cache_outcome=CacheOutcome.MISS)
        report = eng.generate_report()
        assert any("below" in r for r in report.recommendations)


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_entry("key-a")
        eng.add_event("event-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._events) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_events"] == 0
        assert stats["strategy_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_entry("key-a", cache_strategy=CacheStrategy.EXACT_MATCH)
        eng.record_entry("key-b", cache_strategy=CacheStrategy.HYBRID)
        eng.add_event("e1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_events"] == 1
        assert stats["unique_keys"] == 2
