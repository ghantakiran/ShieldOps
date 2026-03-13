"""Tests for AlertQualityLifecycleScorer."""

from __future__ import annotations

from shieldops.observability.alert_quality_lifecycle_scorer import (
    ActionabilityLevel,
    AlertPhase,
    AlertQualityLifecycleScorer,
    QualityGrade,
)


def _engine(**kw) -> AlertQualityLifecycleScorer:
    return AlertQualityLifecycleScorer(**kw)


class TestEnums:
    def test_quality_grade_values(self):
        for v in QualityGrade:
            assert isinstance(v.value, str)

    def test_alert_phase_values(self):
        for v in AlertPhase:
            assert isinstance(v.value, str)

    def test_actionability_level_values(self):
        for v in ActionabilityLevel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(alert_name="cpu_high")
        assert r.alert_name == "cpu_high"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(alert_name=f"a-{i}")
        assert len(eng._records) == 5

    def test_with_params(self):
        eng = _engine()
        r = eng.add_record(
            alert_name="cpu_high",
            quality_score=85.0,
            action_taken=True,
        )
        assert r.quality_score == 85.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            alert_name="cpu_high",
            quality_score=90.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "alert_name")
        assert a.alert_name == "cpu_high"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(alert_name="cpu_high")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(alert_name="cpu_high")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(alert_name="cpu_high")
        eng.clear_data()
        assert len(eng._records) == 0


class TestScoreAlertActionability:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_name="cpu_high",
            action_taken=True,
        )
        result = eng.score_alert_actionability()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().score_alert_actionability()
        assert r == []


class TestIdentifyLowValueAlerts:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_name="noisy",
            quality_score=10.0,
            action_taken=False,
        )
        result = eng.identify_low_value_alerts()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().identify_low_value_alerts()
        assert r == []


class TestTrackAlertQualityTrend:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_name="cpu_high",
            quality_score=80.0,
        )
        eng.add_record(
            alert_name="cpu_high",
            quality_score=90.0,
        )
        result = eng.track_alert_quality_trend()
        assert len(result) == 1
        assert "trend" in result[0]

    def test_empty(self):
        r = _engine().track_alert_quality_trend()
        assert r == []
