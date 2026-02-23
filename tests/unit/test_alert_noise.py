"""Tests for shieldops.observability.alert_noise — AlertNoiseAnalyzer."""

from __future__ import annotations

import pytest

from shieldops.observability.alert_noise import (
    AlertNoiseAnalyzer,
    AlertOutcome,
    AlertRecord,
    AlertSource,
    NoiseLevel,
    NoiseReport,
)


def _analyzer(**kw) -> AlertNoiseAnalyzer:
    return AlertNoiseAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # AlertOutcome (5 values)

    def test_alert_outcome_actioned(self):
        assert AlertOutcome.ACTIONED == "actioned"

    def test_alert_outcome_ignored(self):
        assert AlertOutcome.IGNORED == "ignored"

    def test_alert_outcome_auto_resolved(self):
        assert AlertOutcome.AUTO_RESOLVED == "auto_resolved"

    def test_alert_outcome_escalated(self):
        assert AlertOutcome.ESCALATED == "escalated"

    def test_alert_outcome_duplicate(self):
        assert AlertOutcome.DUPLICATE == "duplicate"

    # NoiseLevel (4 values)

    def test_noise_level_low(self):
        assert NoiseLevel.LOW == "low"

    def test_noise_level_moderate(self):
        assert NoiseLevel.MODERATE == "moderate"

    def test_noise_level_high(self):
        assert NoiseLevel.HIGH == "high"

    def test_noise_level_critical(self):
        assert NoiseLevel.CRITICAL == "critical"

    # AlertSource (5 values)

    def test_alert_source_prometheus(self):
        assert AlertSource.PROMETHEUS == "prometheus"

    def test_alert_source_datadog(self):
        assert AlertSource.DATADOG == "datadog"

    def test_alert_source_cloudwatch(self):
        assert AlertSource.CLOUDWATCH == "cloudwatch"

    def test_alert_source_custom(self):
        assert AlertSource.CUSTOM == "custom"

    def test_alert_source_synthetic(self):
        assert AlertSource.SYNTHETIC == "synthetic"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_alert_record_defaults(self):
        record = AlertRecord(alert_name="HighCPU")
        assert record.id
        assert record.alert_name == "HighCPU"
        assert record.source == AlertSource.CUSTOM
        assert record.service == ""
        assert record.outcome is None
        assert record.responder == ""
        assert record.fired_at > 0
        assert record.resolved_at is None
        assert record.tags == []

    def test_noise_report_defaults(self):
        report = NoiseReport(alert_name="HighCPU")
        assert report.alert_name == "HighCPU"
        assert report.total_fires == 0
        assert report.actioned_count == 0
        assert report.ignored_count == 0
        assert report.auto_resolved_count == 0
        assert report.duplicate_count == 0
        assert report.noise_level == NoiseLevel.LOW
        assert report.signal_to_noise == 0.0


# ---------------------------------------------------------------------------
# record_alert
# ---------------------------------------------------------------------------


class TestRecordAlert:
    def test_basic_record(self):
        ana = _analyzer()
        rec = ana.record_alert("HighCPU")
        assert rec.alert_name == "HighCPU"
        assert rec.source == AlertSource.CUSTOM
        assert len(ana.list_alerts()) == 1

    def test_record_assigns_unique_ids(self):
        ana = _analyzer()
        r1 = ana.record_alert("HighCPU")
        r2 = ana.record_alert("HighMem")
        assert r1.id != r2.id

    def test_record_with_extra_fields(self):
        ana = _analyzer()
        rec = ana.record_alert(
            "HighCPU",
            source=AlertSource.PROMETHEUS,
            service="api-gateway",
            responder="oncall-1",
            tags=["infra", "cpu"],
        )
        assert rec.source == AlertSource.PROMETHEUS
        assert rec.service == "api-gateway"
        assert rec.responder == "oncall-1"
        assert rec.tags == ["infra", "cpu"]

    def test_evicts_at_max_records(self):
        ana = _analyzer(max_records=3)
        ids = []
        for i in range(4):
            rec = ana.record_alert(f"Alert-{i}")
            ids.append(rec.id)
        alerts = ana.list_alerts()
        assert len(alerts) == 3
        found_ids = {a.id for a in alerts}
        assert ids[0] not in found_ids
        assert ids[3] in found_ids


# ---------------------------------------------------------------------------
# resolve_alert
# ---------------------------------------------------------------------------


class TestResolveAlert:
    def test_basic_resolve(self):
        ana = _analyzer()
        rec = ana.record_alert("HighCPU")
        resolved = ana.resolve_alert(rec.id, AlertOutcome.ACTIONED)
        assert resolved is not None
        assert resolved.outcome == AlertOutcome.ACTIONED
        assert resolved.resolved_at is not None

    def test_resolve_not_found(self):
        ana = _analyzer()
        result = ana.resolve_alert("nonexistent", AlertOutcome.IGNORED)
        assert result is None


# ---------------------------------------------------------------------------
# analyze_noise
# ---------------------------------------------------------------------------


class TestAnalyzeNoise:
    def test_basic_analysis(self):
        ana = _analyzer()
        r1 = ana.record_alert("HighCPU")
        r2 = ana.record_alert("HighCPU")
        ana.resolve_alert(r1.id, AlertOutcome.ACTIONED)
        ana.resolve_alert(r2.id, AlertOutcome.IGNORED)
        reports = ana.analyze_noise()
        assert len(reports) == 1
        assert reports[0].alert_name == "HighCPU"
        assert reports[0].total_fires == 2
        assert reports[0].actioned_count == 1
        assert reports[0].ignored_count == 1

    def test_noise_levels_mapping(self):
        ana = _analyzer(noise_threshold=0.3)
        # Create 10 alerts: 0 actioned -> stn = 0.0 -> CRITICAL
        for _ in range(10):
            rec = ana.record_alert("NoisyAlert")
            ana.resolve_alert(rec.id, AlertOutcome.IGNORED)
        reports = ana.analyze_noise()
        assert len(reports) == 1
        assert reports[0].noise_level == NoiseLevel.CRITICAL
        assert reports[0].signal_to_noise == pytest.approx(0.0, abs=1e-4)

    def test_analyze_empty(self):
        ana = _analyzer()
        reports = ana.analyze_noise()
        assert reports == []


# ---------------------------------------------------------------------------
# get_signal_to_noise
# ---------------------------------------------------------------------------


class TestGetSignalToNoise:
    def test_basic_signal_to_noise(self):
        ana = _analyzer()
        r1 = ana.record_alert("A")
        r2 = ana.record_alert("B")
        r3 = ana.record_alert("C")
        r4 = ana.record_alert("D")
        ana.resolve_alert(r1.id, AlertOutcome.ACTIONED)
        ana.resolve_alert(r2.id, AlertOutcome.ESCALATED)
        ana.resolve_alert(r3.id, AlertOutcome.IGNORED)
        ana.resolve_alert(r4.id, AlertOutcome.IGNORED)
        # signal = 2 (actioned + escalated), total = 4 -> 0.5
        stn = ana.get_signal_to_noise()
        assert stn == pytest.approx(0.5, abs=1e-4)

    def test_signal_to_noise_empty(self):
        ana = _analyzer()
        assert ana.get_signal_to_noise() == 0.0


# ---------------------------------------------------------------------------
# get_top_noisy_alerts
# ---------------------------------------------------------------------------


class TestGetTopNoisyAlerts:
    def test_basic_top_noisy(self):
        ana = _analyzer()
        # Create a noisy alert (all ignored)
        for _ in range(5):
            rec = ana.record_alert("NoisyAlert")
            ana.resolve_alert(rec.id, AlertOutcome.IGNORED)
        # Create a signal alert (all actioned)
        for _ in range(5):
            rec = ana.record_alert("GoodAlert")
            ana.resolve_alert(rec.id, AlertOutcome.ACTIONED)
        top = ana.get_top_noisy_alerts()
        assert len(top) == 2
        # NoisyAlert should be first (lowest stn)
        assert top[0].alert_name == "NoisyAlert"

    def test_top_noisy_with_limit(self):
        ana = _analyzer()
        for name in ["A", "B", "C"]:
            rec = ana.record_alert(name)
            ana.resolve_alert(rec.id, AlertOutcome.IGNORED)
        top = ana.get_top_noisy_alerts(limit=2)
        assert len(top) == 2


# ---------------------------------------------------------------------------
# list_alerts
# ---------------------------------------------------------------------------


class TestListAlerts:
    def test_list_all(self):
        ana = _analyzer()
        ana.record_alert("A")
        ana.record_alert("B")
        ana.record_alert("C")
        assert len(ana.list_alerts()) == 3

    def test_filter_by_name(self):
        ana = _analyzer()
        ana.record_alert("HighCPU")
        ana.record_alert("HighMem")
        ana.record_alert("HighCPU")
        results = ana.list_alerts(alert_name="HighCPU")
        assert len(results) == 2
        assert all(r.alert_name == "HighCPU" for r in results)

    def test_filter_by_source(self):
        ana = _analyzer()
        ana.record_alert("A", source=AlertSource.PROMETHEUS)
        ana.record_alert("B", source=AlertSource.DATADOG)
        ana.record_alert("C", source=AlertSource.PROMETHEUS)
        results = ana.list_alerts(source=AlertSource.PROMETHEUS)
        assert len(results) == 2
        assert all(r.source == AlertSource.PROMETHEUS for r in results)

    def test_filter_by_outcome(self):
        ana = _analyzer()
        r1 = ana.record_alert("A")
        r2 = ana.record_alert("B")
        ana.resolve_alert(r1.id, AlertOutcome.ACTIONED)
        ana.resolve_alert(r2.id, AlertOutcome.IGNORED)
        results = ana.list_alerts(outcome=AlertOutcome.ACTIONED)
        assert len(results) == 1
        assert results[0].outcome == AlertOutcome.ACTIONED


# ---------------------------------------------------------------------------
# get_fatigue_score
# ---------------------------------------------------------------------------


class TestGetFatigueScore:
    def test_basic_fatigue(self):
        ana = _analyzer()
        r1 = ana.record_alert("A", responder="oncall-1")
        r2 = ana.record_alert("B", responder="oncall-1")
        r3 = ana.record_alert("C", responder="oncall-1")
        ana.resolve_alert(r1.id, AlertOutcome.ACTIONED)
        ana.resolve_alert(r2.id, AlertOutcome.IGNORED)
        ana.resolve_alert(r3.id, AlertOutcome.IGNORED)
        score = ana.get_fatigue_score("oncall-1")
        assert score["responder"] == "oncall-1"
        assert score["total_alerts"] == 3
        assert score["ignored_count"] == 2
        assert score["fatigue_score"] == pytest.approx(2 / 3, abs=1e-4)

    def test_fatigue_no_alerts(self):
        ana = _analyzer()
        score = ana.get_fatigue_score("oncall-2")
        assert score["total_alerts"] == 0
        assert score["fatigue_score"] == 0.0


# ---------------------------------------------------------------------------
# clear_records
# ---------------------------------------------------------------------------


class TestClearRecords:
    def test_clears_all(self):
        ana = _analyzer()
        ana.record_alert("A")
        ana.record_alert("B")
        count = ana.clear_records()
        assert count == 2
        assert len(ana.list_alerts()) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        ana = _analyzer()
        stats = ana.get_stats()
        assert stats["total_records"] == 0
        assert stats["signal_to_noise"] == 0.0
        assert stats["source_distribution"] == {}
        assert stats["outcome_distribution"] == {}

    def test_stats_populated(self):
        ana = _analyzer()
        r1 = ana.record_alert("A", source=AlertSource.PROMETHEUS)
        r2 = ana.record_alert("B", source=AlertSource.DATADOG)
        ana.resolve_alert(r1.id, AlertOutcome.ACTIONED)
        ana.resolve_alert(r2.id, AlertOutcome.IGNORED)

        stats = ana.get_stats()
        assert stats["total_records"] == 2
        assert stats["signal_to_noise"] == pytest.approx(0.5, abs=1e-4)
        assert stats["source_distribution"][AlertSource.PROMETHEUS] == 1
        assert stats["source_distribution"][AlertSource.DATADOG] == 1
        assert stats["outcome_distribution"][AlertOutcome.ACTIONED] == 1
        assert stats["outcome_distribution"][AlertOutcome.IGNORED] == 1
