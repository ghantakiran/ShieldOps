"""Tests for RiskAlertCorrelationEngine."""

from __future__ import annotations

from shieldops.incidents.risk_alert_correlation_engine import (
    AlertRelation,
    CorrelationStrength,
    CorrelationType,
    RiskAlertCorrelationEngine,
)


def _engine(**kw) -> RiskAlertCorrelationEngine:
    return RiskAlertCorrelationEngine(**kw)


class TestEnums:
    def test_correlation_type_values(self):
        for v in CorrelationType:
            assert isinstance(v.value, str)

    def test_correlation_strength_values(self):
        for v in CorrelationStrength:
            assert isinstance(v.value, str)

    def test_alert_relation_values(self):
        for v in AlertRelation:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(correlation_id="c1")
        assert r.correlation_id == "c1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(correlation_id=f"c-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            correlation_id="c1",
            confidence=0.85,
        )
        a = eng.process(r.id)
        assert hasattr(a, "correlation_id")
        assert a.correlation_id == "c1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(correlation_id="c1")
        assert eng.generate_report().total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(correlation_id="c1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(correlation_id="c1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestCorrelateRiskAlerts:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            correlation_id="c1",
            entity_id="e1",
            alert_id_a="a1",
            alert_id_b="a2",
        )
        result = eng.correlate_risk_alerts()
        assert len(result) == 1
        assert result[0]["alert_count"] == 2

    def test_empty(self):
        assert _engine().correlate_risk_alerts() == []


class TestBuildAttackTimeline:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            correlation_id="c1",
            entity_id="e1",
        )
        result = eng.build_attack_timeline()
        assert len(result) == 1
        assert result[0]["event_count"] == 1

    def test_empty(self):
        assert _engine().build_attack_timeline() == []


class TestComputeCorrelationConfidence:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            correlation_id="c1",
            confidence=0.9,
        )
        result = eng.compute_correlation_confidence()
        assert result["avg_confidence"] == 0.9

    def test_empty(self):
        result = _engine().compute_correlation_confidence()
        assert result["avg_confidence"] == 0.0
