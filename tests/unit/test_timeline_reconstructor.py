"""Tests for shieldops.incidents.timeline_reconstructor — IncidentTimelineReconstructor."""

from __future__ import annotations

import time

from shieldops.incidents.timeline_reconstructor import (
    CorrelationConfidence,
    EventSource,
    IncidentTimelineReconstructor,
    ReconstructedTimeline,
    TimelineAnalysisReport,
    TimelineEvent,
    TimelinePhase,
)


def _engine(**kw) -> IncidentTimelineReconstructor:
    return IncidentTimelineReconstructor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # EventSource (6)
    def test_source_log(self):
        assert EventSource.LOG == "log"

    def test_source_metric(self):
        assert EventSource.METRIC == "metric"

    def test_source_alert(self):
        assert EventSource.ALERT == "alert"

    def test_source_deployment(self):
        assert EventSource.DEPLOYMENT == "deployment"

    def test_source_configuration_change(self):
        assert EventSource.CONFIGURATION_CHANGE == "configuration_change"

    def test_source_manual_note(self):
        assert EventSource.MANUAL_NOTE == "manual_note"

    # TimelinePhase (6)
    def test_phase_pre_incident(self):
        assert TimelinePhase.PRE_INCIDENT == "pre_incident"

    def test_phase_trigger(self):
        assert TimelinePhase.TRIGGER == "trigger"

    def test_phase_detection(self):
        assert TimelinePhase.DETECTION == "detection"

    def test_phase_escalation(self):
        assert TimelinePhase.ESCALATION == "escalation"

    def test_phase_mitigation(self):
        assert TimelinePhase.MITIGATION == "mitigation"

    def test_phase_resolution(self):
        assert TimelinePhase.RESOLUTION == "resolution"

    # CorrelationConfidence (5)
    def test_confidence_high(self):
        assert CorrelationConfidence.HIGH == "high"

    def test_confidence_medium(self):
        assert CorrelationConfidence.MEDIUM == "medium"

    def test_confidence_low(self):
        assert CorrelationConfidence.LOW == "low"

    def test_confidence_speculative(self):
        assert CorrelationConfidence.SPECULATIVE == "speculative"

    def test_confidence_unrelated(self):
        assert CorrelationConfidence.UNRELATED == "unrelated"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_event_defaults(self):
        e = TimelineEvent()
        assert e.id
        assert e.incident_id == ""
        assert e.source == EventSource.LOG
        assert e.phase == TimelinePhase.PRE_INCIDENT
        assert e.timestamp == 0.0
        assert e.description == ""
        assert e.service_name == ""
        assert e.correlation_confidence == CorrelationConfidence.MEDIUM

    def test_timeline_defaults(self):
        t = ReconstructedTimeline()
        assert t.incident_id == ""
        assert t.events == []
        assert t.root_cause_candidates == []
        assert t.detection_delay_seconds == 0.0
        assert t.total_duration_seconds == 0.0
        assert t.phase_durations == {}

    def test_report_defaults(self):
        r = TimelineAnalysisReport()
        assert r.total_events == 0
        assert r.incidents_analyzed == 0
        assert r.avg_detection_delay == 0.0
        assert r.avg_resolution_time == 0.0
        assert r.source_distribution == {}
        assert r.phase_distribution == {}
        assert r.recommendations == []


# ---------------------------------------------------------------------------
# record_event
# ---------------------------------------------------------------------------


class TestRecordEvent:
    def test_basic_record(self):
        eng = _engine()
        base = time.time()
        e = eng.record_event(
            incident_id="INC-001",
            source=EventSource.ALERT,
            phase=TimelinePhase.TRIGGER,
            timestamp=base,
            description="CPU spike detected",
            service_name="api-gateway",
            correlation_confidence=CorrelationConfidence.HIGH,
        )
        assert e.incident_id == "INC-001"
        assert e.source == EventSource.ALERT
        assert e.phase == TimelinePhase.TRIGGER
        assert e.timestamp == base
        assert e.description == "CPU spike detected"
        assert e.service_name == "api-gateway"
        assert e.correlation_confidence == CorrelationConfidence.HIGH

    def test_eviction_at_max(self):
        eng = _engine(max_events=3)
        for i in range(5):
            eng.record_event(incident_id=f"INC-{i}")
        assert len(eng._events) == 3


# ---------------------------------------------------------------------------
# get_event
# ---------------------------------------------------------------------------


class TestGetEvent:
    def test_found(self):
        eng = _engine()
        e = eng.record_event(incident_id="INC-001", description="test event")
        assert eng.get_event(e.id) is not None
        assert eng.get_event(e.id).description == "test event"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_event("nonexistent") is None


# ---------------------------------------------------------------------------
# list_events
# ---------------------------------------------------------------------------


class TestListEvents:
    def test_list_all(self):
        eng = _engine()
        eng.record_event(incident_id="INC-001")
        eng.record_event(incident_id="INC-002")
        assert len(eng.list_events()) == 2

    def test_filter_by_incident_id(self):
        eng = _engine()
        eng.record_event(incident_id="INC-001")
        eng.record_event(incident_id="INC-002")
        results = eng.list_events(incident_id="INC-001")
        assert len(results) == 1
        assert results[0].incident_id == "INC-001"

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_event(incident_id="INC-001", source=EventSource.ALERT)
        eng.record_event(incident_id="INC-001", source=EventSource.LOG)
        results = eng.list_events(source=EventSource.ALERT)
        assert len(results) == 1
        assert results[0].source == EventSource.ALERT

    def test_filter_by_phase(self):
        eng = _engine()
        eng.record_event(incident_id="INC-001", phase=TimelinePhase.TRIGGER)
        eng.record_event(incident_id="INC-001", phase=TimelinePhase.DETECTION)
        results = eng.list_events(phase=TimelinePhase.TRIGGER)
        assert len(results) == 1
        assert results[0].phase == TimelinePhase.TRIGGER


# ---------------------------------------------------------------------------
# reconstruct_timeline
# ---------------------------------------------------------------------------


class TestReconstructTimeline:
    def test_with_events(self):
        eng = _engine()
        base = 1000.0
        eng.record_event(
            incident_id="INC-001",
            phase=TimelinePhase.TRIGGER,
            timestamp=base,
            source=EventSource.ALERT,
            description="alert fired",
            service_name="api",
            correlation_confidence=CorrelationConfidence.HIGH,
        )
        eng.record_event(
            incident_id="INC-001",
            phase=TimelinePhase.DETECTION,
            timestamp=base + 60,
            source=EventSource.METRIC,
            description="anomaly detected",
            service_name="api",
        )
        eng.record_event(
            incident_id="INC-001",
            phase=TimelinePhase.RESOLUTION,
            timestamp=base + 300,
            source=EventSource.LOG,
            description="service restarted",
            service_name="api",
        )
        timeline = eng.reconstruct_timeline("INC-001")
        assert timeline.incident_id == "INC-001"
        assert len(timeline.events) == 3
        assert timeline.total_duration_seconds == 300.0
        assert len(timeline.root_cause_candidates) >= 1

    def test_detection_delay_calculation(self):
        eng = _engine()
        base = 2000.0
        eng.record_event(
            incident_id="INC-002",
            phase=TimelinePhase.TRIGGER,
            timestamp=base,
        )
        eng.record_event(
            incident_id="INC-002",
            phase=TimelinePhase.DETECTION,
            timestamp=base + 120,
        )
        timeline = eng.reconstruct_timeline("INC-002")
        assert timeline.detection_delay_seconds == 120.0


# ---------------------------------------------------------------------------
# identify_root_cause_candidates
# ---------------------------------------------------------------------------


class TestIdentifyRootCauseCandidates:
    def test_with_trigger_high_events(self):
        eng = _engine()
        base = 1000.0
        eng.record_event(
            incident_id="INC-001",
            phase=TimelinePhase.TRIGGER,
            timestamp=base,
            source=EventSource.DEPLOYMENT,
            description="bad deploy",
            service_name="api",
            correlation_confidence=CorrelationConfidence.HIGH,
        )
        eng.record_event(
            incident_id="INC-001",
            phase=TimelinePhase.DETECTION,
            timestamp=base + 30,
            source=EventSource.ALERT,
            description="alert",
            service_name="api",
            correlation_confidence=CorrelationConfidence.MEDIUM,
        )
        candidates = eng.identify_root_cause_candidates("INC-001")
        assert len(candidates) >= 1
        assert "bad deploy" in candidates[0]
        assert "[deployment]" in candidates[0]


# ---------------------------------------------------------------------------
# calculate_detection_delay
# ---------------------------------------------------------------------------


class TestCalculateDetectionDelay:
    def test_delay_between_trigger_and_detection(self):
        eng = _engine()
        base = 5000.0
        eng.record_event(
            incident_id="INC-010",
            phase=TimelinePhase.TRIGGER,
            timestamp=base,
        )
        eng.record_event(
            incident_id="INC-010",
            phase=TimelinePhase.DETECTION,
            timestamp=base + 90,
        )
        delay = eng.calculate_detection_delay("INC-010")
        assert delay == 90.0


# ---------------------------------------------------------------------------
# analyze_phase_transitions
# ---------------------------------------------------------------------------


class TestAnalyzePhaseTransitions:
    def test_phase_transitions(self):
        eng = _engine()
        base = 1000.0
        eng.record_event(
            incident_id="INC-001",
            phase=TimelinePhase.TRIGGER,
            timestamp=base,
        )
        eng.record_event(
            incident_id="INC-001",
            phase=TimelinePhase.DETECTION,
            timestamp=base + 60,
        )
        eng.record_event(
            incident_id="INC-001",
            phase=TimelinePhase.MITIGATION,
            timestamp=base + 180,
        )
        transitions = eng.analyze_phase_transitions("INC-001")
        assert len(transitions) == 2
        assert transitions[0]["from_phase"] == "trigger"
        assert transitions[0]["to_phase"] == "detection"
        assert transitions[0]["gap_seconds"] == 60.0
        assert transitions[1]["from_phase"] == "detection"
        assert transitions[1]["to_phase"] == "mitigation"
        assert transitions[1]["gap_seconds"] == 120.0


# ---------------------------------------------------------------------------
# find_correlated_events
# ---------------------------------------------------------------------------


class TestFindCorrelatedEvents:
    def test_within_window(self):
        eng = _engine(correlation_window_seconds=300)
        base = 1000.0
        e1 = eng.record_event(
            incident_id="INC-001",
            timestamp=base,
            description="event-a",
        )
        eng.record_event(
            incident_id="INC-001",
            timestamp=base + 100,
            description="event-b",
        )
        correlated = eng.find_correlated_events(e1.id)
        assert len(correlated) == 1
        assert correlated[0].description == "event-b"

    def test_outside_window(self):
        eng = _engine(correlation_window_seconds=60)
        base = 1000.0
        e1 = eng.record_event(
            incident_id="INC-001",
            timestamp=base,
            description="event-a",
        )
        eng.record_event(
            incident_id="INC-001",
            timestamp=base + 500,
            description="event-far",
        )
        correlated = eng.find_correlated_events(e1.id)
        assert len(correlated) == 0


# ---------------------------------------------------------------------------
# generate_analysis_report
# ---------------------------------------------------------------------------


class TestGenerateAnalysisReport:
    def test_basic_report(self):
        eng = _engine()
        base = 1000.0
        eng.record_event(
            incident_id="INC-001",
            source=EventSource.ALERT,
            phase=TimelinePhase.TRIGGER,
            timestamp=base,
        )
        eng.record_event(
            incident_id="INC-001",
            source=EventSource.METRIC,
            phase=TimelinePhase.DETECTION,
            timestamp=base + 60,
        )
        eng.record_event(
            incident_id="INC-001",
            source=EventSource.LOG,
            phase=TimelinePhase.RESOLUTION,
            timestamp=base + 600,
        )
        report = eng.generate_analysis_report()
        assert report.total_events == 3
        assert report.incidents_analyzed == 1
        assert report.avg_detection_delay == 60.0
        assert report.avg_resolution_time == 600.0
        assert "alert" in report.source_distribution
        assert "trigger" in report.phase_distribution


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_event(incident_id="INC-001")
        eng.record_event(incident_id="INC-002")
        assert len(eng._events) == 2
        eng.clear_data()
        assert len(eng._events) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_events"] == 0
        assert stats["unique_incidents"] == 0
        assert stats["event_sources"] == []
        assert stats["event_phases"] == []

    def test_populated(self):
        eng = _engine()
        eng.record_event(
            incident_id="INC-001",
            source=EventSource.ALERT,
            phase=TimelinePhase.TRIGGER,
            timestamp=1000.0,
        )
        eng.record_event(
            incident_id="INC-002",
            source=EventSource.LOG,
            phase=TimelinePhase.DETECTION,
            timestamp=2000.0,
        )
        stats = eng.get_stats()
        assert stats["total_events"] == 2
        assert stats["unique_incidents"] == 2
        assert "alert" in stats["event_sources"]
        assert "log" in stats["event_sources"]
        assert "trigger" in stats["event_phases"]
        assert "detection" in stats["event_phases"]
