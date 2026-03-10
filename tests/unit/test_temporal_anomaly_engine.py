"""Tests for TemporalAnomalyEngine."""

from __future__ import annotations

from shieldops.observability.temporal_anomaly_engine import (
    RiskLevel,
    TemporalAnomalyEngine,
    TemporalContext,
    TemporalViolation,
)


def _engine(**kw) -> TemporalAnomalyEngine:
    return TemporalAnomalyEngine(**kw)


class TestEnums:
    def test_temporal_context(self):
        assert TemporalContext.BUSINESS_HOURS == "business_hours"

    def test_temporal_violation(self):
        assert TemporalViolation.OFF_HOURS_DEPLOY == "off_hours_deploy"

    def test_risk_level(self):
        assert RiskLevel.CRITICAL == "critical"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(event_type="deploy", service="api")
        assert rec.event_type == "deploy"
        assert rec.service == "api"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(event_type=f"e-{i}", service="svc")
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(event_type="deploy", service="api")
        result = eng.process("api")
        assert isinstance(result, dict)
        assert result["service"] == "api"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestDetectTemporalViolations:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            event_type="deploy",
            service="api",
            risk_level=RiskLevel.HIGH,
        )
        result = eng.detect_temporal_violations("api")
        assert isinstance(result, list)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(event_type="deploy", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(event_type="deploy", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(event_type="deploy", service="api")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert eng.get_stats()["total_records"] == 0
