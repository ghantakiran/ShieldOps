"""Tests for shieldops.incidents.timeline_correlator."""

from __future__ import annotations

from shieldops.incidents.timeline_correlator import (
    CorrelationRecord,
    CorrelationRule,
    CorrelationStrength,
    EventType,
    IncidentTimelineCorrelator,
    TimelineCorrelatorReport,
    TimelinePhase,
)


def _engine(**kw) -> IncidentTimelineCorrelator:
    return IncidentTimelineCorrelator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # EventType (5)
    def test_event_alert_fired(self):
        assert EventType.ALERT_FIRED == "alert_fired"

    def test_event_deployment(self):
        assert EventType.DEPLOYMENT == "deployment"

    def test_event_config_change(self):
        assert EventType.CONFIG_CHANGE == "config_change"

    def test_event_scaling_event(self):
        assert EventType.SCALING_EVENT == "scaling_event"

    def test_event_human_action(self):
        assert EventType.HUMAN_ACTION == "human_action"

    # CorrelationStrength (5)
    def test_strength_strong(self):
        assert CorrelationStrength.STRONG == "strong"

    def test_strength_moderate(self):
        assert CorrelationStrength.MODERATE == "moderate"

    def test_strength_weak(self):
        assert CorrelationStrength.WEAK == "weak"

    def test_strength_coincidental(self):
        assert CorrelationStrength.COINCIDENTAL == "coincidental"

    def test_strength_none(self):
        assert CorrelationStrength.NONE == "none"

    # TimelinePhase (5)
    def test_phase_detection(self):
        assert TimelinePhase.DETECTION == "detection"

    def test_phase_triage(self):
        assert TimelinePhase.TRIAGE == "triage"

    def test_phase_investigation(self):
        assert TimelinePhase.INVESTIGATION == "investigation"

    def test_phase_remediation(self):
        assert TimelinePhase.REMEDIATION == "remediation"

    def test_phase_recovery(self):
        assert TimelinePhase.RECOVERY == "recovery"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_correlation_record_defaults(self):
        r = CorrelationRecord()
        assert r.id
        assert r.incident_name == ""
        assert r.event_type == EventType.ALERT_FIRED
        assert r.strength == CorrelationStrength.MODERATE
        assert r.phase == TimelinePhase.DETECTION
        assert r.confidence_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_correlation_rule_defaults(self):
        r = CorrelationRule()
        assert r.id
        assert r.rule_name == ""
        assert r.event_type == EventType.ALERT_FIRED
        assert r.phase == TimelinePhase.DETECTION
        assert r.min_confidence_pct == 60.0
        assert r.time_window_minutes == 30.0
        assert r.created_at > 0

    def test_correlator_report_defaults(self):
        r = TimelineCorrelatorReport()
        assert r.total_correlations == 0
        assert r.total_rules == 0
        assert r.strong_rate_pct == 0.0
        assert r.by_event_type == {}
        assert r.by_strength == {}
        assert r.weak_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_correlation
# -------------------------------------------------------------------


class TestRecordCorrelation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_correlation(
            "inc-001",
            event_type=EventType.ALERT_FIRED,
            strength=CorrelationStrength.STRONG,
        )
        assert r.incident_name == "inc-001"
        assert r.event_type == EventType.ALERT_FIRED

    def test_with_phase(self):
        eng = _engine()
        r = eng.record_correlation(
            "inc-002",
            phase=TimelinePhase.REMEDIATION,
        )
        assert r.phase == TimelinePhase.REMEDIATION

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_correlation(f"inc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_correlation
# -------------------------------------------------------------------


class TestGetCorrelation:
    def test_found(self):
        eng = _engine()
        r = eng.record_correlation("inc-001")
        assert eng.get_correlation(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_correlation("nonexistent") is None


# -------------------------------------------------------------------
# list_correlations
# -------------------------------------------------------------------


class TestListCorrelations:
    def test_list_all(self):
        eng = _engine()
        eng.record_correlation("inc-001")
        eng.record_correlation("inc-002")
        assert len(eng.list_correlations()) == 2

    def test_filter_by_incident(self):
        eng = _engine()
        eng.record_correlation("inc-001")
        eng.record_correlation("inc-002")
        results = eng.list_correlations(incident_name="inc-001")
        assert len(results) == 1

    def test_filter_by_event_type(self):
        eng = _engine()
        eng.record_correlation(
            "inc-001",
            event_type=EventType.DEPLOYMENT,
        )
        eng.record_correlation(
            "inc-002",
            event_type=EventType.CONFIG_CHANGE,
        )
        results = eng.list_correlations(event_type=EventType.DEPLOYMENT)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        p = eng.add_rule(
            "alert-deploy-rule",
            event_type=EventType.ALERT_FIRED,
            phase=TimelinePhase.DETECTION,
            min_confidence_pct=70.0,
            time_window_minutes=15.0,
        )
        assert p.rule_name == "alert-deploy-rule"
        assert p.min_confidence_pct == 70.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rule(f"rule-{i}")
        assert len(eng._policies) == 2


# -------------------------------------------------------------------
# analyze_correlation_quality
# -------------------------------------------------------------------


class TestAnalyzeCorrelationQuality:
    def test_with_data(self):
        eng = _engine()
        eng.record_correlation(
            "inc-001",
            strength=CorrelationStrength.STRONG,
            confidence_pct=80.0,
        )
        eng.record_correlation(
            "inc-001",
            strength=CorrelationStrength.WEAK,
            confidence_pct=30.0,
        )
        result = eng.analyze_correlation_quality("inc-001")
        assert result["incident_name"] == "inc-001"
        assert result["correlation_count"] == 2
        assert result["strong_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_correlation_quality("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_confidence_pct=50.0)
        eng.record_correlation(
            "inc-001",
            strength=CorrelationStrength.STRONG,
            confidence_pct=80.0,
        )
        result = eng.analyze_correlation_quality("inc-001")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_weak_correlations
# -------------------------------------------------------------------


class TestIdentifyWeakCorrelations:
    def test_with_weak(self):
        eng = _engine()
        eng.record_correlation(
            "inc-001",
            strength=CorrelationStrength.WEAK,
        )
        eng.record_correlation(
            "inc-001",
            strength=CorrelationStrength.WEAK,
        )
        eng.record_correlation(
            "inc-002",
            strength=CorrelationStrength.STRONG,
        )
        results = eng.identify_weak_correlations()
        assert len(results) == 1
        assert results[0]["incident_name"] == "inc-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_weak_correlations() == []


# -------------------------------------------------------------------
# rank_by_confidence
# -------------------------------------------------------------------


class TestRankByConfidence:
    def test_with_data(self):
        eng = _engine()
        eng.record_correlation("inc-001", confidence_pct=90.0)
        eng.record_correlation("inc-001", confidence_pct=90.0)
        eng.record_correlation("inc-002", confidence_pct=20.0)
        results = eng.rank_by_confidence()
        assert results[0]["incident_name"] == "inc-001"
        assert results[0]["avg_confidence_pct"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_confidence() == []


# -------------------------------------------------------------------
# detect_correlation_gaps
# -------------------------------------------------------------------


class TestDetectCorrelationGaps:
    def test_with_gaps(self):
        eng = _engine()
        for _ in range(5):
            eng.record_correlation(
                "inc-001",
                strength=CorrelationStrength.WEAK,
            )
        eng.record_correlation(
            "inc-002",
            strength=CorrelationStrength.STRONG,
        )
        results = eng.detect_correlation_gaps()
        assert len(results) == 1
        assert results[0]["incident_name"] == "inc-001"
        assert results[0]["gap_detected"] is True

    def test_no_gaps(self):
        eng = _engine()
        eng.record_correlation(
            "inc-001",
            strength=CorrelationStrength.WEAK,
        )
        assert eng.detect_correlation_gaps() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_correlation(
            "inc-001",
            strength=CorrelationStrength.STRONG,
        )
        eng.record_correlation(
            "inc-002",
            strength=CorrelationStrength.WEAK,
        )
        eng.record_correlation(
            "inc-002",
            strength=CorrelationStrength.WEAK,
        )
        eng.add_rule("rule-1")
        report = eng.generate_report()
        assert report.total_correlations == 3
        assert report.total_rules == 1
        assert report.by_event_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_correlations == 0
        assert "optimal" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_correlation("inc-001")
        eng.add_rule("rule-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._policies) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_correlations"] == 0
        assert stats["total_rules"] == 0
        assert stats["event_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_correlation(
            "inc-001",
            event_type=EventType.ALERT_FIRED,
        )
        eng.record_correlation(
            "inc-002",
            event_type=EventType.DEPLOYMENT,
        )
        eng.add_rule("r1")
        stats = eng.get_stats()
        assert stats["total_correlations"] == 2
        assert stats["total_rules"] == 1
        assert stats["unique_incidents"] == 2
