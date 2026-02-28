"""Tests for shieldops.incidents.prevention_engine — IncidentPreventionEngine."""

from __future__ import annotations

from shieldops.incidents.prevention_engine import (
    IncidentPreventionEngine,
    PrecursorSignal,
    PrecursorType,
    PreventionAction,
    PreventionEngineReport,
    PreventionOutcome,
    PreventionRecord,
)


def _engine(**kw) -> IncidentPreventionEngine:
    return IncidentPreventionEngine(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # PrecursorType (5)
    def test_precursor_metric_anomaly(self):
        assert PrecursorType.METRIC_ANOMALY == "metric_anomaly"

    def test_precursor_log_pattern(self):
        assert PrecursorType.LOG_PATTERN == "log_pattern"

    def test_precursor_dependency_degradation(self):
        assert PrecursorType.DEPENDENCY_DEGRADATION == "dependency_degradation"

    def test_precursor_capacity_trend(self):
        assert PrecursorType.CAPACITY_TREND == "capacity_trend"

    def test_precursor_security_signal(self):
        assert PrecursorType.SECURITY_SIGNAL == "security_signal"

    # PreventionAction (5)
    def test_action_auto_scale(self):
        assert PreventionAction.AUTO_SCALE == "auto_scale"

    def test_action_circuit_break(self):
        assert PreventionAction.CIRCUIT_BREAK == "circuit_break"

    def test_action_traffic_shift(self):
        assert PreventionAction.TRAFFIC_SHIFT == "traffic_shift"

    def test_action_alert_team(self):
        assert PreventionAction.ALERT_TEAM == "alert_team"

    def test_action_rollback(self):
        assert PreventionAction.ROLLBACK == "rollback"

    # PreventionOutcome (5)
    def test_outcome_prevented(self):
        assert PreventionOutcome.PREVENTED == "prevented"

    def test_outcome_mitigated(self):
        assert PreventionOutcome.MITIGATED == "mitigated"

    def test_outcome_false_alarm(self):
        assert PreventionOutcome.FALSE_ALARM == "false_alarm"

    def test_outcome_missed(self):
        assert PreventionOutcome.MISSED == "missed"

    def test_outcome_inconclusive(self):
        assert PreventionOutcome.INCONCLUSIVE == "inconclusive"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_prevention_record_defaults(self):
        r = PreventionRecord()
        assert r.id
        assert r.service_name == ""
        assert r.precursor_type == PrecursorType.METRIC_ANOMALY
        assert r.prevention_action == PreventionAction.ALERT_TEAM
        assert r.prevention_outcome == PreventionOutcome.PREVENTED
        assert r.lead_time_minutes == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_precursor_signal_defaults(self):
        r = PrecursorSignal()
        assert r.id
        assert r.signal_name == ""
        assert r.precursor_type == PrecursorType.LOG_PATTERN
        assert r.prevention_action == PreventionAction.AUTO_SCALE
        assert r.confidence_score == 0.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = PreventionEngineReport()
        assert r.total_preventions == 0
        assert r.total_signals == 0
        assert r.prevention_rate_pct == 0.0
        assert r.by_precursor == {}
        assert r.by_outcome == {}
        assert r.missed_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_prevention
# -------------------------------------------------------------------


class TestRecordPrevention:
    def test_basic(self):
        eng = _engine()
        r = eng.record_prevention(
            "svc-a",
            precursor_type=PrecursorType.CAPACITY_TREND,
            prevention_action=PreventionAction.AUTO_SCALE,
        )
        assert r.service_name == "svc-a"
        assert r.precursor_type == PrecursorType.CAPACITY_TREND

    def test_with_lead_time(self):
        eng = _engine()
        r = eng.record_prevention("svc-b", lead_time_minutes=30.0)
        assert r.lead_time_minutes == 30.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_prevention(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_prevention
# -------------------------------------------------------------------


class TestGetPrevention:
    def test_found(self):
        eng = _engine()
        r = eng.record_prevention("svc-a")
        assert eng.get_prevention(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_prevention("nonexistent") is None


# -------------------------------------------------------------------
# list_preventions
# -------------------------------------------------------------------


class TestListPreventions:
    def test_list_all(self):
        eng = _engine()
        eng.record_prevention("svc-a")
        eng.record_prevention("svc-b")
        assert len(eng.list_preventions()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_prevention("svc-a")
        eng.record_prevention("svc-b")
        results = eng.list_preventions(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_precursor_type(self):
        eng = _engine()
        eng.record_prevention("svc-a", precursor_type=PrecursorType.LOG_PATTERN)
        eng.record_prevention("svc-b", precursor_type=PrecursorType.METRIC_ANOMALY)
        results = eng.list_preventions(precursor_type=PrecursorType.LOG_PATTERN)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_signal
# -------------------------------------------------------------------


class TestAddSignal:
    def test_basic(self):
        eng = _engine()
        r = eng.add_signal(
            "sig-1",
            precursor_type=PrecursorType.SECURITY_SIGNAL,
            prevention_action=PreventionAction.CIRCUIT_BREAK,
            confidence_score=85.0,
        )
        assert r.signal_name == "sig-1"
        assert r.confidence_score == 85.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_signal(f"sig-{i}")
        assert len(eng._signals) == 2


# -------------------------------------------------------------------
# analyze_prevention_effectiveness
# -------------------------------------------------------------------


class TestAnalyzePreventionEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.record_prevention("svc-a", prevention_outcome=PreventionOutcome.PREVENTED)
        eng.record_prevention("svc-a", prevention_outcome=PreventionOutcome.MISSED)
        result = eng.analyze_prevention_effectiveness("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_records"] == 2
        assert result["prevented_count"] == 1
        assert result["prevention_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_prevention_effectiveness("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_confidence_pct=50.0)
        eng.record_prevention("svc-a", prevention_outcome=PreventionOutcome.PREVENTED)
        result = eng.analyze_prevention_effectiveness("svc-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_missed_preventions
# -------------------------------------------------------------------


class TestIdentifyMissedPreventions:
    def test_with_missed(self):
        eng = _engine()
        eng.record_prevention("svc-a", prevention_outcome=PreventionOutcome.MISSED)
        eng.record_prevention("svc-a", prevention_outcome=PreventionOutcome.MISSED)
        eng.record_prevention("svc-b", prevention_outcome=PreventionOutcome.PREVENTED)
        results = eng.identify_missed_preventions()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_missed_preventions() == []


# -------------------------------------------------------------------
# rank_by_lead_time
# -------------------------------------------------------------------


class TestRankByLeadTime:
    def test_with_data(self):
        eng = _engine()
        eng.record_prevention("svc-a", lead_time_minutes=50.0)
        eng.record_prevention("svc-a", lead_time_minutes=30.0)
        eng.record_prevention("svc-b", lead_time_minutes=10.0)
        results = eng.rank_by_lead_time()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["avg_lead_time_min"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_lead_time() == []


# -------------------------------------------------------------------
# detect_false_alarm_patterns
# -------------------------------------------------------------------


class TestDetectFalseAlarmPatterns:
    def test_with_recurring(self):
        eng = _engine()
        for _ in range(5):
            eng.record_prevention("svc-a", prevention_outcome=PreventionOutcome.FALSE_ALARM)
        eng.record_prevention("svc-b", prevention_outcome=PreventionOutcome.FALSE_ALARM)
        results = eng.detect_false_alarm_patterns()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["recurring"] is True

    def test_no_recurring(self):
        eng = _engine()
        eng.record_prevention("svc-a", prevention_outcome=PreventionOutcome.FALSE_ALARM)
        assert eng.detect_false_alarm_patterns() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_prevention("svc-a", prevention_outcome=PreventionOutcome.MISSED)
        eng.record_prevention("svc-b", prevention_outcome=PreventionOutcome.PREVENTED)
        eng.add_signal("sig-1")
        report = eng.generate_report()
        assert report.total_preventions == 2
        assert report.total_signals == 1
        assert report.by_precursor != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_preventions == 0
        assert report.recommendations[0] == "Prevention engine performance meets targets"

    def test_missed_recommendation(self):
        eng = _engine()
        eng.record_prevention("svc-a", prevention_outcome=PreventionOutcome.MISSED)
        report = eng.generate_report()
        assert "missed" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_prevention("svc-a")
        eng.add_signal("sig-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._signals) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_signals"] == 0
        assert stats["precursor_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_prevention("svc-a", precursor_type=PrecursorType.METRIC_ANOMALY)
        eng.record_prevention("svc-b", precursor_type=PrecursorType.LOG_PATTERN)
        eng.add_signal("sig-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_signals"] == 1
        assert stats["unique_services"] == 2
