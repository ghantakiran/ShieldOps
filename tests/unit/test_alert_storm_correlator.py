"""Tests for shieldops.observability.alert_storm_correlator — AlertStormCorrelator."""

from __future__ import annotations

import time

from shieldops.observability.alert_storm_correlator import (
    AlertStorm,
    AlertStormCorrelator,
    CorrelationMethod,
    StormAlert,
    StormPhase,
    StormReport,
    StormSeverity,
)


def _engine(**kw) -> AlertStormCorrelator:
    return AlertStormCorrelator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # StormSeverity (5)
    def test_severity_minor(self):
        assert StormSeverity.MINOR == "minor"

    def test_severity_moderate(self):
        assert StormSeverity.MODERATE == "moderate"

    def test_severity_major(self):
        assert StormSeverity.MAJOR == "major"

    def test_severity_severe(self):
        assert StormSeverity.SEVERE == "severe"

    def test_severity_catastrophic(self):
        assert StormSeverity.CATASTROPHIC == "catastrophic"

    # CorrelationMethod (5)
    def test_method_temporal(self):
        assert CorrelationMethod.TEMPORAL == "temporal"

    def test_method_topological(self):
        assert CorrelationMethod.TOPOLOGICAL == "topological"

    def test_method_causal(self):
        assert CorrelationMethod.CAUSAL == "causal"

    def test_method_symptom(self):
        assert CorrelationMethod.SYMPTOM_BASED == "symptom_based"

    def test_method_hybrid(self):
        assert CorrelationMethod.HYBRID == "hybrid"

    # StormPhase (5)
    def test_phase_building(self):
        assert StormPhase.BUILDING == "building"

    def test_phase_peak(self):
        assert StormPhase.PEAK == "peak"

    def test_phase_subsiding(self):
        assert StormPhase.SUBSIDING == "subsiding"

    def test_phase_resolved(self):
        assert StormPhase.RESOLVED == "resolved"

    def test_phase_recurring(self):
        assert StormPhase.RECURRING == "recurring"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_storm_alert_defaults(self):
        r = StormAlert()
        assert r.id
        assert r.alert_name == ""
        assert r.service == ""
        assert r.severity == ""
        assert r.timestamp > 0
        assert r.is_root_cause is False

    def test_alert_storm_defaults(self):
        r = AlertStorm()
        assert r.id
        assert r.storm_name == ""
        assert r.severity == StormSeverity.MINOR
        assert r.phase == StormPhase.BUILDING
        assert r.method == CorrelationMethod.TEMPORAL
        assert r.alerts == []
        assert r.root_cause_alert_id == ""
        assert r.affected_services == []
        assert r.resolved_at == 0.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = StormReport()
        assert r.total_storms == 0
        assert r.active_storms == 0
        assert r.avg_alerts_per_storm == 0.0
        assert r.by_severity == {}
        assert r.by_phase == {}
        assert r.by_method == {}
        assert r.frequent_root_causes == []
        assert r.recommendations == []


# -------------------------------------------------------------------
# record_storm
# -------------------------------------------------------------------


class TestRecordStorm:
    def test_basic(self):
        eng = _engine()
        s = eng.record_storm("db-cascade")
        assert s.storm_name == "db-cascade"
        assert s.severity == StormSeverity.MINOR

    def test_with_params(self):
        eng = _engine()
        s = eng.record_storm(
            "network-outage",
            severity=StormSeverity.SEVERE,
            method=CorrelationMethod.CAUSAL,
        )
        assert s.severity == StormSeverity.SEVERE
        assert s.method == CorrelationMethod.CAUSAL

    def test_unique_ids(self):
        eng = _engine()
        s1 = eng.record_storm("storm-a")
        s2 = eng.record_storm("storm-b")
        assert s1.id != s2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_storm(f"storm-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_storm
# -------------------------------------------------------------------


class TestGetStorm:
    def test_found(self):
        eng = _engine()
        s = eng.record_storm("test-storm")
        assert eng.get_storm(s.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_storm("nonexistent") is None


# -------------------------------------------------------------------
# list_storms
# -------------------------------------------------------------------


class TestListStorms:
    def test_list_all(self):
        eng = _engine()
        eng.record_storm("storm-a")
        eng.record_storm("storm-b")
        assert len(eng.list_storms()) == 2

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_storm("storm-a", severity=StormSeverity.MINOR)
        eng.record_storm("storm-b", severity=StormSeverity.CATASTROPHIC)
        results = eng.list_storms(severity=StormSeverity.CATASTROPHIC)
        assert len(results) == 1
        assert results[0].severity == StormSeverity.CATASTROPHIC

    def test_filter_by_phase(self):
        eng = _engine()
        s = eng.record_storm("storm-a")
        eng.update_storm_phase(s.id, StormPhase.RESOLVED)
        eng.record_storm("storm-b")  # default phase=BUILDING
        results = eng.list_storms(phase=StormPhase.RESOLVED)
        assert len(results) == 1


# -------------------------------------------------------------------
# detect_storm
# -------------------------------------------------------------------


class TestDetectStorm:
    def _make_alerts(self, count: int, base_ts: float, window: float) -> list[dict]:
        step = window / max(count - 1, 1)
        alerts = []
        for i in range(count):
            alerts.append(
                {
                    "alert_name": f"alert-{i}",
                    "service": f"svc-{i % 3}",
                    "severity": "critical",
                    "timestamp": base_ts + i * step,
                }
            )
        return alerts

    def test_enough_alerts_creates_storm(self):
        eng = _engine(storm_window_seconds=300.0)
        base = time.time()
        alerts = self._make_alerts(6, base, 200.0)
        result = eng.detect_storm(alerts)
        assert result["storm_detected"] is True
        assert result["alert_count"] == 6
        assert result["root_cause_alert_id"]

    def test_too_few_alerts(self):
        eng = _engine()
        alerts = [
            {"alert_name": "a1", "service": "svc", "severity": "warning", "timestamp": 1.0},
            {"alert_name": "a2", "service": "svc", "severity": "warning", "timestamp": 2.0},
        ]
        result = eng.detect_storm(alerts)
        assert result["storm_detected"] is False
        assert result["reason"] == "fewer_than_5_alerts"

    def test_outside_window(self):
        eng = _engine(storm_window_seconds=300.0)
        base = time.time()
        # 6 alerts spread over 600s (> 300s window)
        alerts = self._make_alerts(6, base, 600.0)
        result = eng.detect_storm(alerts)
        assert result["storm_detected"] is False
        assert result["reason"] == "alerts_outside_window"


# -------------------------------------------------------------------
# add_alert_to_storm
# -------------------------------------------------------------------


class TestAddAlertToStorm:
    def test_valid_storm(self):
        eng = _engine()
        s = eng.record_storm("test-storm")
        result = eng.add_alert_to_storm(s.id, "cpu-high", "api-svc", "critical")
        assert result["total_alerts"] == 1
        assert result["storm_id"] == s.id

    def test_not_found(self):
        eng = _engine()
        result = eng.add_alert_to_storm("bad-id", "alert", "svc")
        assert result["error"] == "storm_not_found"


# -------------------------------------------------------------------
# identify_root_cause
# -------------------------------------------------------------------


class TestIdentifyRootCause:
    def test_valid_storm_with_alerts(self):
        eng = _engine()
        s = eng.record_storm("test-storm")
        eng.add_alert_to_storm(s.id, "db-slow", "db-svc", "warning")
        eng.add_alert_to_storm(s.id, "api-timeout", "api-svc", "critical")
        result = eng.identify_root_cause(s.id)
        assert result["storm_id"] == s.id
        assert result["root_cause_alert_id"]
        assert result["alert_name"]

    def test_not_found(self):
        eng = _engine()
        result = eng.identify_root_cause("bad-id")
        assert result["error"] == "storm_not_found"


# -------------------------------------------------------------------
# calculate_storm_frequency
# -------------------------------------------------------------------


class TestCalculateStormFrequency:
    def test_with_storms(self):
        eng = _engine()
        eng.record_storm("storm-a")
        eng.record_storm("storm-b")
        result = eng.calculate_storm_frequency()
        assert result["total"] == 2
        assert result["storms_per_day"] >= 0

    def test_empty(self):
        eng = _engine()
        result = eng.calculate_storm_frequency()
        assert result["total"] == 0
        assert result["storms_per_day"] == 0.0


# -------------------------------------------------------------------
# update_storm_phase
# -------------------------------------------------------------------


class TestUpdateStormPhase:
    def test_valid(self):
        eng = _engine()
        s = eng.record_storm("test-storm")
        result = eng.update_storm_phase(s.id, StormPhase.PEAK)
        assert result["old_phase"] == "building"
        assert result["new_phase"] == "peak"

    def test_not_found(self):
        eng = _engine()
        result = eng.update_storm_phase("bad-id", StormPhase.RESOLVED)
        assert result["error"] == "storm_not_found"


# -------------------------------------------------------------------
# generate_storm_report
# -------------------------------------------------------------------


class TestGenerateStormReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_storm_report()
        assert report.total_storms == 0
        assert report.active_storms == 0

    def test_with_data(self):
        eng = _engine()
        s1 = eng.record_storm("storm-a", severity=StormSeverity.MAJOR)
        eng.add_alert_to_storm(s1.id, "root-alert", "svc-a", "critical")
        eng.identify_root_cause(s1.id)
        s2 = eng.record_storm("storm-b", severity=StormSeverity.MINOR)
        eng.update_storm_phase(s2.id, StormPhase.RESOLVED)
        report = eng.generate_storm_report()
        assert report.total_storms == 2
        assert report.active_storms == 1  # storm-a is BUILDING
        assert report.by_severity != {}


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_storm("storm-a")
        eng.record_storm("storm-b")
        eng.clear_data()
        assert len(eng._records) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_storms"] == 0
        assert stats["total_alerts"] == 0

    def test_populated(self):
        eng = _engine()
        s = eng.record_storm("storm-a", severity=StormSeverity.MAJOR)
        eng.add_alert_to_storm(s.id, "cpu-high", "api-svc", "critical")
        eng.add_alert_to_storm(s.id, "mem-high", "api-svc", "warning")
        stats = eng.get_stats()
        assert stats["total_storms"] == 1
        assert stats["total_alerts"] == 2
        assert stats["storm_window_seconds"] == 300.0
