"""Tests for SelfTuningAlertEngine."""

from __future__ import annotations

from shieldops.observability.self_tuning_alert_engine import (
    AlertSignalQuality,
    SelfTuningAlertEngine,
    TuningAction,
    TuningOutcome,
)


def _engine(**kw) -> SelfTuningAlertEngine:
    return SelfTuningAlertEngine(**kw)


class TestEnums:
    def test_signal_quality(self):
        assert AlertSignalQuality.HIGH_SIGNAL == "high_signal"

    def test_tuning_action(self):
        assert TuningAction.TIGHTEN_THRESHOLD == "tighten_threshold"

    def test_tuning_outcome(self):
        assert TuningOutcome.IMPROVED == "improved"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(alert_rule_id="r-1", service="api")
        assert rec.alert_rule_id == "r-1"
        assert rec.service == "api"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(
                alert_rule_id=f"r-{i}",
                service="svc",
            )
        assert len(eng._records) == 3


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(alert_rule_id="r-1", service="api")
        result = eng.process("r-1")
        assert isinstance(result, dict)
        assert result["alert_rule_id"] == "r-1"

    def test_not_found(self):
        eng = _engine()
        result = eng.process("missing")
        assert result["status"] == "no_data"


class TestRecommendTuning:
    def test_basic(self):
        eng = _engine()
        eng.add_record(alert_rule_id="r-1", service="api")
        result = eng.recommend_tuning("r-1")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(alert_rule_id="r-1", service="api")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(alert_rule_id="r-1", service="api")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(alert_rule_id="r-1", service="api")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert eng.get_stats()["total_records"] == 0
