"""Tests for shieldops.changes.change_coordination_planner — ChangeCoordinationPlanner."""

from __future__ import annotations

from shieldops.changes.change_coordination_planner import (
    ChangeCoordinationPlanner,
    ChangeCoordinationReport,
    ConflictSeverity,
    CoordinationAssessment,
    CoordinationRecord,
    CoordinationStatus,
    ScheduleWindow,
)


def _engine(**kw) -> ChangeCoordinationPlanner:
    return ChangeCoordinationPlanner(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_aligned(self):
        assert CoordinationStatus.ALIGNED == "aligned"

    def test_status_conflicting(self):
        assert CoordinationStatus.CONFLICTING == "conflicting"

    def test_status_overlapping(self):
        assert CoordinationStatus.OVERLAPPING == "overlapping"

    def test_status_sequenced(self):
        assert CoordinationStatus.SEQUENCED == "sequenced"

    def test_status_independent(self):
        assert CoordinationStatus.INDEPENDENT == "independent"

    def test_severity_blocking(self):
        assert ConflictSeverity.BLOCKING == "blocking"

    def test_severity_major(self):
        assert ConflictSeverity.MAJOR == "major"

    def test_severity_moderate(self):
        assert ConflictSeverity.MODERATE == "moderate"

    def test_severity_minor(self):
        assert ConflictSeverity.MINOR == "minor"

    def test_severity_none(self):
        assert ConflictSeverity.NONE == "none"

    def test_window_peak_hours(self):
        assert ScheduleWindow.PEAK_HOURS == "peak_hours"

    def test_window_off_peak(self):
        assert ScheduleWindow.OFF_PEAK == "off_peak"

    def test_window_maintenance(self):
        assert ScheduleWindow.MAINTENANCE == "maintenance"

    def test_window_weekend(self):
        assert ScheduleWindow.WEEKEND == "weekend"

    def test_window_emergency(self):
        assert ScheduleWindow.EMERGENCY == "emergency"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_coordination_record_defaults(self):
        r = CoordinationRecord()
        assert r.id
        assert r.change_id == ""
        assert r.coordination_status == CoordinationStatus.ALIGNED
        assert r.conflict_severity == ConflictSeverity.NONE
        assert r.schedule_window == ScheduleWindow.OFF_PEAK
        assert r.risk_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_coordination_assessment_defaults(self):
        a = CoordinationAssessment()
        assert a.id
        assert a.change_id == ""
        assert a.coordination_status == CoordinationStatus.ALIGNED
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_change_coordination_report_defaults(self):
        r = ChangeCoordinationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.high_risk_count == 0
        assert r.avg_risk_score == 0.0
        assert r.by_status == {}
        assert r.by_severity == {}
        assert r.by_window == {}
        assert r.top_conflicts == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_coordination
# ---------------------------------------------------------------------------


class TestRecordCoordination:
    def test_basic(self):
        eng = _engine()
        r = eng.record_coordination(
            change_id="CHG-001",
            coordination_status=CoordinationStatus.CONFLICTING,
            conflict_severity=ConflictSeverity.MAJOR,
            schedule_window=ScheduleWindow.PEAK_HOURS,
            risk_score=75.0,
            service="api-gw",
            team="sre",
        )
        assert r.change_id == "CHG-001"
        assert r.coordination_status == CoordinationStatus.CONFLICTING
        assert r.conflict_severity == ConflictSeverity.MAJOR
        assert r.schedule_window == ScheduleWindow.PEAK_HOURS
        assert r.risk_score == 75.0
        assert r.service == "api-gw"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_coordination(change_id=f"CHG-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_coordination
# ---------------------------------------------------------------------------


class TestGetCoordination:
    def test_found(self):
        eng = _engine()
        r = eng.record_coordination(
            change_id="CHG-001",
            conflict_severity=ConflictSeverity.BLOCKING,
        )
        result = eng.get_coordination(r.id)
        assert result is not None
        assert result.conflict_severity == ConflictSeverity.BLOCKING

    def test_not_found(self):
        eng = _engine()
        assert eng.get_coordination("nonexistent") is None


# ---------------------------------------------------------------------------
# list_coordinations
# ---------------------------------------------------------------------------


class TestListCoordinations:
    def test_list_all(self):
        eng = _engine()
        eng.record_coordination(change_id="CHG-001")
        eng.record_coordination(change_id="CHG-002")
        assert len(eng.list_coordinations()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_coordination(
            change_id="CHG-001",
            coordination_status=CoordinationStatus.ALIGNED,
        )
        eng.record_coordination(
            change_id="CHG-002",
            coordination_status=CoordinationStatus.CONFLICTING,
        )
        results = eng.list_coordinations(coordination_status=CoordinationStatus.ALIGNED)
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_coordination(
            change_id="CHG-001",
            conflict_severity=ConflictSeverity.BLOCKING,
        )
        eng.record_coordination(
            change_id="CHG-002",
            conflict_severity=ConflictSeverity.NONE,
        )
        results = eng.list_coordinations(conflict_severity=ConflictSeverity.BLOCKING)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_coordination(change_id="CHG-001", team="sre")
        eng.record_coordination(change_id="CHG-002", team="platform")
        results = eng.list_coordinations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_coordination(change_id=f"CHG-{i}")
        assert len(eng.list_coordinations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            change_id="CHG-001",
            coordination_status=CoordinationStatus.CONFLICTING,
            assessment_score=88.5,
            threshold=80.0,
            breached=True,
            description="conflict threshold exceeded",
        )
        assert a.change_id == "CHG-001"
        assert a.coordination_status == CoordinationStatus.CONFLICTING
        assert a.assessment_score == 88.5
        assert a.threshold == 80.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(change_id=f"CHG-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_coordination_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeCoordinationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_coordination(
            change_id="CHG-001",
            coordination_status=CoordinationStatus.ALIGNED,
            risk_score=40.0,
        )
        eng.record_coordination(
            change_id="CHG-002",
            coordination_status=CoordinationStatus.ALIGNED,
            risk_score=60.0,
        )
        result = eng.analyze_coordination_distribution()
        assert "aligned" in result
        assert result["aligned"]["count"] == 2
        assert result["aligned"]["avg_risk_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_coordination_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_risk_coordinations
# ---------------------------------------------------------------------------


class TestIdentifyHighRiskCoordinations:
    def test_detects_above_threshold(self):
        eng = _engine(coordination_risk_threshold=60.0)
        eng.record_coordination(change_id="CHG-001", risk_score=80.0)
        eng.record_coordination(change_id="CHG-002", risk_score=40.0)
        results = eng.identify_high_risk_coordinations()
        assert len(results) == 1
        assert results[0]["change_id"] == "CHG-001"

    def test_sorted_descending(self):
        eng = _engine(coordination_risk_threshold=30.0)
        eng.record_coordination(change_id="CHG-001", risk_score=50.0)
        eng.record_coordination(change_id="CHG-002", risk_score=90.0)
        results = eng.identify_high_risk_coordinations()
        assert len(results) == 2
        assert results[0]["risk_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_risk_coordinations() == []


# ---------------------------------------------------------------------------
# rank_by_risk
# ---------------------------------------------------------------------------


class TestRankByRisk:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_coordination(change_id="CHG-001", service="api-gw", risk_score=40.0)
        eng.record_coordination(change_id="CHG-002", service="auth", risk_score=90.0)
        results = eng.rank_by_risk()
        assert len(results) == 2
        assert results[0]["service"] == "auth"
        assert results[0]["avg_risk_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk() == []


# ---------------------------------------------------------------------------
# detect_coordination_trends
# ---------------------------------------------------------------------------


class TestDetectCoordinationTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(change_id="CHG-001", assessment_score=50.0)
        result = eng.detect_coordination_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(change_id="CHG-001", assessment_score=20.0)
        eng.add_assessment(change_id="CHG-002", assessment_score=20.0)
        eng.add_assessment(change_id="CHG-003", assessment_score=80.0)
        eng.add_assessment(change_id="CHG-004", assessment_score=80.0)
        result = eng.detect_coordination_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_coordination_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(coordination_risk_threshold=60.0)
        eng.record_coordination(
            change_id="CHG-001",
            coordination_status=CoordinationStatus.CONFLICTING,
            conflict_severity=ConflictSeverity.MAJOR,
            schedule_window=ScheduleWindow.PEAK_HOURS,
            risk_score=80.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ChangeCoordinationReport)
        assert report.total_records == 1
        assert report.high_risk_count == 1
        assert len(report.top_conflicts) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_coordination(change_id="CHG-001")
        eng.add_assessment(change_id="CHG-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_coordination(
            change_id="CHG-001",
            coordination_status=CoordinationStatus.ALIGNED,
            service="api-gw",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "aligned" in stats["status_distribution"]
