"""Tests for EventSourcingPatternEngine."""

from __future__ import annotations

from shieldops.analytics.event_sourcing_pattern_engine import (
    EventSourcingPatternEngine,
    EventType,
    ProjectionStatus,
    StoreGrowth,
)


def _engine(**kw) -> EventSourcingPatternEngine:
    return EventSourcingPatternEngine(**kw)


class TestEnums:
    def test_event_type_values(self):
        for v in EventType:
            assert isinstance(v.value, str)

    def test_projection_status_values(self):
        for v in ProjectionStatus:
            assert isinstance(v.value, str)

    def test_store_growth_values(self):
        for v in StoreGrowth:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(aggregate_id="a1")
        assert r.aggregate_id == "a1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(aggregate_id=f"a-{i}")
        assert len(eng._records) == 5

    def test_defaults(self):
        r = _engine().add_record()
        assert r.event_type == EventType.DOMAIN


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            aggregate_id="a1",
            event_count=100,
            store_size_mb=50.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "aggregate_id")
        assert a.aggregate_id == "a1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(aggregate_id="a1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0

    def test_lagging_aggregates(self):
        eng = _engine()
        eng.add_record(
            aggregate_id="a1",
            projection_status=(ProjectionStatus.LAGGING),
        )
        rpt = eng.generate_report()
        assert len(rpt.lagging_aggregates) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(aggregate_id="a1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(aggregate_id="a1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestAnalyzeEventStoreGrowth:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            aggregate_id="a1",
            store_size_mb=100.0,
            event_count=500,
        )
        result = eng.analyze_event_store_growth()
        assert len(result) == 1
        assert result[0]["total_size_mb"] == 100.0

    def test_empty(self):
        r = _engine().analyze_event_store_growth()
        assert r == []


class TestDetectProjectionLag:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            aggregate_id="a1",
            projection_status=(ProjectionStatus.STALE),
            projection_lag_ms=5000.0,
        )
        result = eng.detect_projection_lag()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_projection_lag() == []


class TestRankAggregatesByComplexity:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            aggregate_id="a1",
            event_count=1000,
            store_size_mb=500.0,
        )
        eng.add_record(
            aggregate_id="a2",
            event_count=10,
            store_size_mb=5.0,
        )
        result = eng.rank_aggregates_by_complexity()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_aggregates_by_complexity()
        assert r == []
