"""Tests for DistributedQueryAccelerator."""

from __future__ import annotations

from shieldops.observability.distributed_query_accelerator import (
    CacheStrategy,
    DataLocality,
    DistributedQueryAccelerator,
    QueryComplexity,
)


def _engine(**kw) -> DistributedQueryAccelerator:
    return DistributedQueryAccelerator(**kw)


class TestEnums:
    def test_query_complexity(self):
        assert QueryComplexity.SIMPLE == "simple"
        assert QueryComplexity.EXTREME == "extreme"

    def test_cache_strategy(self):
        assert CacheStrategy.LRU == "lru"
        assert CacheStrategy.ADAPTIVE == "adaptive"

    def test_data_locality(self):
        assert DataLocality.LOCAL == "local"
        assert DataLocality.GLOBAL == "global"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(name="q-1", service="api")
        assert rec.name == "q-1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"q-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(name="q-1", score=60.0)
        result = eng.process("q-1")
        assert result["key"] == "q-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(name="q1", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated(self):
        eng = _engine()
        eng.add_record(name="q1", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(name="q1", service="api")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestAnalyzeQueryPatterns:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="q1",
            complexity=QueryComplexity.COMPLEX,
            query_time_ms=500.0,
        )
        result = eng.analyze_query_patterns()
        assert isinstance(result, dict)
        assert "complex" in result


class TestComputeCacheEfficiency:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="q1",
            cache_strategy=CacheStrategy.LRU,
            cache_hit_rate=0.85,
        )
        result = eng.compute_cache_efficiency()
        assert "overall_hit_rate" in result

    def test_empty(self):
        eng = _engine()
        result = eng.compute_cache_efficiency()
        assert result["status"] == "no_data"


class TestOptimizeQueryRouting:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="q1",
            service="api",
            query_time_ms=600.0,
            data_locality=DataLocality.GLOBAL,
        )
        result = eng.optimize_query_routing()
        assert isinstance(result, list)
        assert len(result) >= 1
