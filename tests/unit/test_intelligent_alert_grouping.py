"""Tests for shieldops.observability.intelligent_alert_grouping — IntelligentAlertGrouping."""

from __future__ import annotations

from shieldops.observability.intelligent_alert_grouping import (
    AlertGroupRecord,
    AlertPriority,
    GroupingStrategy,
    GroupStatus,
    IntelligentAlertGrouping,
)


def _engine(**kw) -> IntelligentAlertGrouping:
    return IntelligentAlertGrouping(**kw)


class TestEnums:
    def test_strategy_temporal(self):
        assert GroupingStrategy.TEMPORAL == "temporal"

    def test_priority_critical(self):
        assert AlertPriority.CRITICAL == "critical"

    def test_group_status(self):
        assert GroupStatus.OPEN == "open"


class TestModels:
    def test_record_defaults(self):
        r = AlertGroupRecord()
        assert r.id
        assert r.created_at > 0


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(alert_name="HighCPU", fingerprint="fp-1")
        assert rec.alert_name == "HighCPU"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(alert_name=f"alert-{i}", fingerprint=f"fp-{i}")
        assert len(eng._records) == 3


class TestGroupStatistics:
    def test_basic(self):
        eng = _engine()
        eng.add_record(alert_name="HighCPU", fingerprint="fp-1", group_id="g1")
        eng.add_record(alert_name="HighMem", fingerprint="fp-2", group_id="g1")
        result = eng.compute_group_statistics()
        assert isinstance(result, list)


class TestNoiseReduction:
    def test_basic(self):
        eng = _engine()
        eng.add_record(alert_name="HighCPU", fingerprint="fp-1", group_id="g1")
        result = eng.calculate_noise_reduction()
        assert isinstance(result, dict)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(alert_name="HighCPU", fingerprint="fp-1", service="api")
        result = eng.process("HighCPU")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(alert_name="HighCPU", fingerprint="fp-1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(alert_name="HighCPU", fingerprint="fp-1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(alert_name="HighCPU", fingerprint="fp-1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
