"""Tests for RealtimeSliCalculator."""

from __future__ import annotations

from shieldops.observability.realtime_sli_calculator import (
    CalculationWindow,
    RealtimeSliCalculator,
    SliHealth,
    SliType,
)


def _engine(**kw) -> RealtimeSliCalculator:
    return RealtimeSliCalculator(**kw)


class TestEnums:
    def test_sli_type(self):
        assert SliType.AVAILABILITY == "availability"
        assert SliType.ERROR_RATE == "error_rate"

    def test_calculation_window(self):
        assert CalculationWindow.MINUTES_1 == "minutes_1"
        assert CalculationWindow.HOUR_1 == "hour_1"

    def test_sli_health(self):
        assert SliHealth.HEALTHY == "healthy"
        assert SliHealth.CRITICAL == "critical"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(name="sli-1", service="api")
        assert rec.name == "sli-1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"s-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(name="sli-1", score=99.0)
        result = eng.process("sli-1")
        assert result["key"] == "sli-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(name="s1", service="api")
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
        eng.add_record(name="s1", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(name="s1", service="api")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0


class TestComputeCompositeSli:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="s1",
            service="api",
            sli_type=SliType.AVAILABILITY,
            value=99.9,
        )
        result = eng.compute_composite_sli(service="api")
        assert "composite_sli" in result

    def test_empty(self):
        eng = _engine()
        result = eng.compute_composite_sli()
        assert result["status"] == "no_data"


class TestDetectSliDegradation:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="s1",
            service="api",
            value=98.0,
            target=99.9,
        )
        result = eng.detect_sli_degradation()
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_no_degradation(self):
        eng = _engine()
        eng.add_record(name="s1", value=99.99, target=99.9)
        result = eng.detect_sli_degradation()
        assert len(result) == 0


class TestForecastSliBreach:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            name="s1",
            service="api",
            sli_type=SliType.AVAILABILITY,
            value=99.5,
            target=99.9,
        )
        eng.add_record(
            name="s2",
            service="api",
            sli_type=SliType.AVAILABILITY,
            value=99.0,
            target=99.9,
        )
        result = eng.forecast_sli_breach()
        assert "at_risk_count" in result

    def test_insufficient(self):
        eng = _engine()
        result = eng.forecast_sli_breach()
        assert result["status"] == "insufficient_data"
