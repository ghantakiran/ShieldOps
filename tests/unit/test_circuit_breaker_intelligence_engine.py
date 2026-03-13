"""Tests for CircuitBreakerIntelligenceEngine."""

from __future__ import annotations

from shieldops.topology.circuit_breaker_intelligence_engine import (
    BreakerState,
    CircuitBreakerIntelligenceEngine,
    FlappingStatus,
    TripCause,
)


def _engine(**kw) -> CircuitBreakerIntelligenceEngine:
    return CircuitBreakerIntelligenceEngine(**kw)


class TestEnums:
    def test_breaker_state_values(self):
        for v in BreakerState:
            assert isinstance(v.value, str)

    def test_trip_cause_values(self):
        for v in TripCause:
            assert isinstance(v.value, str)

    def test_flapping_status_values(self):
        for v in FlappingStatus:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(service="svc-a")
        assert r.service == "svc-a"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(service=f"svc-{i}")
        assert len(eng._records) == 5

    def test_all_fields(self):
        eng = _engine()
        r = eng.record_item(
            service="svc-a",
            breaker_name="cb-1",
            breaker_state=BreakerState.OPEN,
            trip_count=10,
        )
        assert r.trip_count == 10


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(breaker_name="cb-1", trip_count=5)
        a = eng.process(r.id)
        assert a.breaker_name == "cb-1"

    def test_flapping(self):
        eng = _engine()
        r = eng.record_item(
            breaker_name="cb-1",
            flapping_status=FlappingStatus.CRITICAL,
        )
        a = eng.process(r.id)
        assert a.is_flapping is True

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(service="svc-a")
        rpt = eng.generate_report()
        assert rpt.total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_flapping_breakers(self):
        eng = _engine()
        eng.record_item(
            breaker_name="cb-1",
            flapping_status=FlappingStatus.FREQUENT,
        )
        rpt = eng.generate_report()
        assert len(rpt.flapping_breakers) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(service="svc-a")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(service="svc-a")
        eng.clear_data()
        assert len(eng._records) == 0


class TestAnalyzeTripFrequency:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(breaker_name="cb-1", trip_count=10)
        result = eng.analyze_trip_frequency()
        assert len(result) == 1
        assert result[0]["total_trips"] == 10

    def test_empty(self):
        assert _engine().analyze_trip_frequency() == []


class TestDetectFlappingBreakers:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            breaker_name="cb-1",
            flapping_status=FlappingStatus.CRITICAL,
            trip_count=50,
        )
        result = eng.detect_flapping_breakers()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_flapping_breakers() == []


class TestRecommendThresholdTuning:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            breaker_name="cb-1",
            error_threshold=50.0,
            current_error_rate=48.0,
        )
        result = eng.recommend_threshold_tuning()
        assert len(result) == 1
        assert "Increase" in result[0]["recommendation"]

    def test_empty(self):
        assert _engine().recommend_threshold_tuning() == []
