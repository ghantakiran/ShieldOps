"""Tests for shieldops.incidents.incident_timeline — IncidentTimelineAnalyzer.

Covers TimelinePhase, BottleneckType, and ResponseQuality enums,
TimelineEntry / BottleneckAnalysis / TimelineReport models, and all
IncidentTimelineAnalyzer operations including phase recording, duration
calculation, bottleneck detection, response quality analysis, timeline
comparison, improvement identification, and report generation.
"""

from __future__ import annotations

from shieldops.incidents.incident_timeline import (
    BottleneckAnalysis,
    BottleneckType,
    IncidentTimelineAnalyzer,
    ResponseQuality,
    TimelineEntry,
    TimelinePhase,
    TimelineReport,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(**kw) -> IncidentTimelineAnalyzer:
    return IncidentTimelineAnalyzer(**kw)


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    """Validate every member of all three enums."""

    # -- TimelinePhase (5 members) ----------------------------------

    def test_phase_detection(self):
        assert TimelinePhase.DETECTION == "detection"

    def test_phase_triage(self):
        assert TimelinePhase.TRIAGE == "triage"

    def test_phase_investigation(self):
        assert TimelinePhase.INVESTIGATION == "investigation"

    def test_phase_mitigation(self):
        assert TimelinePhase.MITIGATION == "mitigation"

    def test_phase_resolution(self):
        assert TimelinePhase.RESOLUTION == "resolution"

    # -- BottleneckType (5 members) ---------------------------------

    def test_bn_slow_detection(self):
        assert BottleneckType.SLOW_DETECTION == "slow_detection"

    def test_bn_delayed_triage(self):
        assert BottleneckType.DELAYED_TRIAGE == "delayed_triage"

    def test_bn_long_investigation(self):
        assert BottleneckType.LONG_INVESTIGATION == "long_investigation"

    def test_bn_failed_mitigation(self):
        assert BottleneckType.FAILED_MITIGATION == "failed_mitigation"

    def test_bn_extended_resolution(self):
        assert BottleneckType.EXTENDED_RESOLUTION == "extended_resolution"

    # -- ResponseQuality (5 members) --------------------------------

    def test_quality_excellent(self):
        assert ResponseQuality.EXCELLENT == "excellent"

    def test_quality_good(self):
        assert ResponseQuality.GOOD == "good"

    def test_quality_acceptable(self):
        assert ResponseQuality.ACCEPTABLE == "acceptable"

    def test_quality_below_target(self):
        assert ResponseQuality.BELOW_TARGET == "below_target"

    def test_quality_critical(self):
        assert ResponseQuality.CRITICAL == "critical"


# ===========================================================================
# Model defaults
# ===========================================================================


class TestModels:
    """Verify default field values for each Pydantic model."""

    def test_timeline_entry_defaults(self):
        e = TimelineEntry()
        assert e.id
        assert e.incident_id == ""
        assert e.phase == TimelinePhase.DETECTION
        assert e.started_at > 0
        assert e.ended_at == 0.0
        assert e.duration_minutes == 0.0
        assert e.assignee == ""
        assert e.notes == ""
        assert e.created_at > 0

    def test_bottleneck_analysis_defaults(self):
        b = BottleneckAnalysis()
        assert b.incident_id == ""
        assert b.bottleneck_type == BottleneckType.SLOW_DETECTION
        assert b.phase == TimelinePhase.DETECTION
        assert b.duration_minutes == 0.0
        assert b.target_minutes == 0.0
        assert b.overshoot_pct == 0.0
        assert b.created_at > 0

    def test_timeline_report_defaults(self):
        r = TimelineReport()
        assert r.total_incidents == 0
        assert r.total_entries == 0
        assert r.avg_resolution_minutes == 0.0
        assert r.by_phase == {}
        assert r.by_quality == {}
        assert r.bottlenecks == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ===========================================================================
# RecordPhase
# ===========================================================================


class TestRecordPhase:
    """Test IncidentTimelineAnalyzer.record_phase."""

    def test_basic_record(self):
        eng = _engine()
        e = eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.DETECTION,
            duration_minutes=3.0,
            assignee="alice",
        )
        assert e.id
        assert e.incident_id == "INC-001"
        assert e.phase == TimelinePhase.DETECTION
        assert e.duration_minutes == 3.0
        assert e.assignee == "alice"

    def test_custom_fields(self):
        eng = _engine()
        e = eng.record_phase(
            incident_id="INC-002",
            phase=TimelinePhase.MITIGATION,
            duration_minutes=25.0,
            notes="Rolled back deployment",
        )
        assert e.phase == TimelinePhase.MITIGATION
        assert e.notes == "Rolled back deployment"

    def test_eviction_on_overflow(self):
        eng = _engine(max_entries=3)
        eng.record_phase(incident_id="a")
        eng.record_phase(incident_id="b")
        eng.record_phase(incident_id="c")
        e4 = eng.record_phase(incident_id="d")
        items = eng.list_entries(limit=100)
        assert len(items) == 3
        assert items[-1].id == e4.id


# ===========================================================================
# GetEntry
# ===========================================================================


class TestGetEntry:
    """Test IncidentTimelineAnalyzer.get_entry."""

    def test_found(self):
        eng = _engine()
        e = eng.record_phase(incident_id="INC-001")
        assert eng.get_entry(e.id) is e

    def test_not_found(self):
        eng = _engine()
        assert eng.get_entry("missing") is None


# ===========================================================================
# ListEntries
# ===========================================================================


class TestListEntries:
    """Test IncidentTimelineAnalyzer.list_entries."""

    def test_all(self):
        eng = _engine()
        eng.record_phase(incident_id="INC-001")
        eng.record_phase(incident_id="INC-002")
        assert len(eng.list_entries()) == 2

    def test_filter_by_incident(self):
        eng = _engine()
        eng.record_phase(incident_id="INC-001")
        eng.record_phase(incident_id="INC-002")
        eng.record_phase(incident_id="INC-001")
        results = eng.list_entries(incident_id="INC-001")
        assert len(results) == 2
        assert all(e.incident_id == "INC-001" for e in results)

    def test_filter_by_phase(self):
        eng = _engine()
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.DETECTION,
        )
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.TRIAGE,
        )
        results = eng.list_entries(
            phase=TimelinePhase.TRIAGE,
        )
        assert len(results) == 1
        assert results[0].phase == TimelinePhase.TRIAGE

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_phase(incident_id=f"INC-{i}")
        assert len(eng.list_entries(limit=3)) == 3


# ===========================================================================
# CalculatePhaseDurations
# ===========================================================================


class TestCalculatePhaseDurations:
    """Test IncidentTimelineAnalyzer.calculate_phase_durations."""

    def test_basic(self):
        eng = _engine()
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.DETECTION,
            duration_minutes=5.0,
        )
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.TRIAGE,
            duration_minutes=10.0,
        )
        durations = eng.calculate_phase_durations("INC-001")
        assert durations["detection"] == 5.0
        assert durations["triage"] == 10.0

    def test_empty_incident(self):
        eng = _engine()
        assert eng.calculate_phase_durations("none") == {}

    def test_multiple_same_phase(self):
        eng = _engine()
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.INVESTIGATION,
            duration_minutes=20.0,
        )
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.INVESTIGATION,
            duration_minutes=15.0,
        )
        durations = eng.calculate_phase_durations("INC-001")
        assert durations["investigation"] == 35.0


# ===========================================================================
# DetectBottlenecks
# ===========================================================================


class TestDetectBottlenecks:
    """Test IncidentTimelineAnalyzer.detect_bottlenecks."""

    def test_over_target(self):
        eng = _engine()
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.DETECTION,
            duration_minutes=20.0,
        )
        bns = eng.detect_bottlenecks("INC-001")
        assert len(bns) >= 1
        assert bns[0].bottleneck_type == BottleneckType.SLOW_DETECTION
        assert bns[0].overshoot_pct > 0

    def test_under_target(self):
        eng = _engine()
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.DETECTION,
            duration_minutes=2.0,
        )
        bns = eng.detect_bottlenecks("INC-001")
        assert len(bns) == 0

    def test_custom_targets(self):
        eng = _engine()
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.TRIAGE,
            duration_minutes=5.0,
        )
        bns = eng.detect_bottlenecks(
            "INC-001",
            targets={TimelinePhase.TRIAGE: 2.0},
        )
        assert len(bns) == 1
        assert bns[0].phase == TimelinePhase.TRIAGE


# ===========================================================================
# AnalyzeResponseQuality
# ===========================================================================


class TestAnalyzeResponseQuality:
    """Test IncidentTimelineAnalyzer.analyze_response_quality."""

    def test_excellent(self):
        eng = _engine(target_resolution_minutes=60)
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.DETECTION,
            duration_minutes=5.0,
        )
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.RESOLUTION,
            duration_minutes=10.0,
        )
        quality = eng.analyze_response_quality("INC-001")
        assert quality == ResponseQuality.EXCELLENT

    def test_critical(self):
        eng = _engine(target_resolution_minutes=10)
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.INVESTIGATION,
            duration_minutes=100.0,
        )
        quality = eng.analyze_response_quality("INC-001")
        assert quality == ResponseQuality.CRITICAL

    def test_good(self):
        eng = _engine(target_resolution_minutes=60)
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.DETECTION,
            duration_minutes=50.0,
        )
        quality = eng.analyze_response_quality("INC-001")
        assert quality == ResponseQuality.GOOD


# ===========================================================================
# CompareIncidentTimelines
# ===========================================================================


class TestCompareIncidentTimelines:
    """Test IncidentTimelineAnalyzer.compare_incident_timelines."""

    def test_compare_two(self):
        eng = _engine(target_resolution_minutes=60)
        eng.record_phase(
            incident_id="INC-001",
            duration_minutes=10.0,
        )
        eng.record_phase(
            incident_id="INC-002",
            duration_minutes=50.0,
        )
        results = eng.compare_incident_timelines(
            ["INC-001", "INC-002"],
        )
        assert len(results) == 2
        assert results[0]["total_minutes"] <= results[1]["total_minutes"]

    def test_empty_list(self):
        eng = _engine()
        assert eng.compare_incident_timelines([]) == []


# ===========================================================================
# IdentifyImprovementAreas
# ===========================================================================


class TestIdentifyImprovementAreas:
    """Test IncidentTimelineAnalyzer.identify_improvement_areas."""

    def test_with_slow_phases(self):
        eng = _engine()
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.DETECTION,
            duration_minutes=20.0,
        )
        eng.record_phase(
            incident_id="INC-002",
            phase=TimelinePhase.DETECTION,
            duration_minutes=25.0,
        )
        areas = eng.identify_improvement_areas()
        assert len(areas) >= 1
        assert areas[0]["phase"] == "detection"
        assert areas[0]["overshoot_pct"] > 0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_improvement_areas() == []


# ===========================================================================
# GenerateTimelineReport
# ===========================================================================


class TestGenerateTimelineReport:
    """Test IncidentTimelineAnalyzer.generate_timeline_report."""

    def test_basic_report(self):
        eng = _engine(target_resolution_minutes=60)
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.DETECTION,
            duration_minutes=5.0,
        )
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.RESOLUTION,
            duration_minutes=20.0,
        )
        eng.record_phase(
            incident_id="INC-002",
            phase=TimelinePhase.DETECTION,
            duration_minutes=100.0,
        )
        report = eng.generate_timeline_report()
        assert isinstance(report, TimelineReport)
        assert report.total_incidents == 2
        assert report.total_entries == 3
        assert report.avg_resolution_minutes > 0
        assert report.generated_at > 0
        assert len(report.by_phase) >= 1

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_timeline_report()
        assert report.total_incidents == 0
        assert report.total_entries == 0

    def test_report_recommendations(self):
        eng = _engine(target_resolution_minutes=10)
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.INVESTIGATION,
            duration_minutes=100.0,
        )
        report = eng.generate_timeline_report()
        assert len(report.recommendations) >= 1


# ===========================================================================
# ClearData
# ===========================================================================


class TestClearData:
    """Test IncidentTimelineAnalyzer.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        eng.record_phase(incident_id="INC-001")
        eng.clear_data()
        assert len(eng.list_entries()) == 0
        stats = eng.get_stats()
        assert stats["total_entries"] == 0


# ===========================================================================
# GetStats
# ===========================================================================


class TestGetStats:
    """Test IncidentTimelineAnalyzer.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_entries"] == 0
        assert stats["unique_incidents"] == 0
        assert stats["unique_assignees"] == 0
        assert stats["total_duration_minutes"] == 0.0
        assert stats["avg_duration_minutes"] == 0.0
        assert stats["phase_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_phase(
            incident_id="INC-001",
            phase=TimelinePhase.DETECTION,
            duration_minutes=5.0,
            assignee="alice",
        )
        eng.record_phase(
            incident_id="INC-002",
            phase=TimelinePhase.TRIAGE,
            duration_minutes=15.0,
            assignee="bob",
        )
        stats = eng.get_stats()
        assert stats["total_entries"] == 2
        assert stats["unique_incidents"] == 2
        assert stats["unique_assignees"] == 2
        assert stats["total_duration_minutes"] == 20.0
        assert stats["avg_duration_minutes"] == 10.0
        assert stats["phase_distribution"]["detection"] == 1
        assert stats["phase_distribution"]["triage"] == 1
