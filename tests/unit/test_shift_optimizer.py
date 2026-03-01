"""Tests for shieldops.operations.shift_optimizer — ShiftScheduleOptimizer."""

from __future__ import annotations

from shieldops.operations.shift_optimizer import (
    CoverageGap,
    CoverageStatus,
    ScheduleIssue,
    ShiftRecord,
    ShiftScheduleOptimizer,
    ShiftScheduleReport,
    ShiftType,
)


def _engine(**kw) -> ShiftScheduleOptimizer:
    return ShiftScheduleOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_shift_type_primary(self):
        assert ShiftType.PRIMARY == "primary"

    def test_shift_type_secondary(self):
        assert ShiftType.SECONDARY == "secondary"

    def test_shift_type_backup(self):
        assert ShiftType.BACKUP == "backup"

    def test_shift_type_follow_the_sun(self):
        assert ShiftType.FOLLOW_THE_SUN == "follow_the_sun"

    def test_shift_type_split(self):
        assert ShiftType.SPLIT == "split"

    def test_coverage_full(self):
        assert CoverageStatus.FULL == "full"

    def test_coverage_partial(self):
        assert CoverageStatus.PARTIAL == "partial"

    def test_coverage_gap(self):
        assert CoverageStatus.GAP == "gap"

    def test_coverage_overlap(self):
        assert CoverageStatus.OVERLAP == "overlap"

    def test_coverage_understaffed(self):
        assert CoverageStatus.UNDERSTAFFED == "understaffed"

    def test_issue_fatigue_risk(self):
        assert ScheduleIssue.FATIGUE_RISK == "fatigue_risk"

    def test_issue_timezone_mismatch(self):
        assert ScheduleIssue.TIMEZONE_MISMATCH == "timezone_mismatch"

    def test_issue_skill_gap(self):
        assert ScheduleIssue.SKILL_GAP == "skill_gap"

    def test_issue_understaffed(self):
        assert ScheduleIssue.UNDERSTAFFED == "understaffed"

    def test_issue_overloaded(self):
        assert ScheduleIssue.OVERLOADED == "overloaded"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_shift_record_defaults(self):
        r = ShiftRecord()
        assert r.id
        assert r.schedule_id == ""
        assert r.shift_type == ShiftType.PRIMARY
        assert r.coverage_status == CoverageStatus.FULL
        assert r.schedule_issue == ScheduleIssue.FATIGUE_RISK
        assert r.coverage_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_coverage_gap_defaults(self):
        g = CoverageGap()
        assert g.id
        assert g.schedule_id == ""
        assert g.shift_type == ShiftType.PRIMARY
        assert g.gap_duration_hours == 0.0
        assert g.severity == 0
        assert g.auto_fill is False
        assert g.description == ""
        assert g.created_at > 0

    def test_shift_schedule_report_defaults(self):
        r = ShiftScheduleReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_gaps == 0
        assert r.coverage_gap_count == 0
        assert r.avg_coverage_score == 0.0
        assert r.by_shift_type == {}
        assert r.by_coverage_status == {}
        assert r.by_schedule_issue == {}
        assert r.top_teams == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_shift
# ---------------------------------------------------------------------------


class TestRecordShift:
    def test_basic(self):
        eng = _engine()
        r = eng.record_shift(
            schedule_id="SCHED-001",
            shift_type=ShiftType.FOLLOW_THE_SUN,
            coverage_status=CoverageStatus.PARTIAL,
            schedule_issue=ScheduleIssue.TIMEZONE_MISMATCH,
            coverage_score=75.0,
            service="api-gateway",
            team="sre",
        )
        assert r.schedule_id == "SCHED-001"
        assert r.shift_type == ShiftType.FOLLOW_THE_SUN
        assert r.coverage_status == CoverageStatus.PARTIAL
        assert r.schedule_issue == ScheduleIssue.TIMEZONE_MISMATCH
        assert r.coverage_score == 75.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_shift(schedule_id=f"SCHED-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_shift
# ---------------------------------------------------------------------------


class TestGetShift:
    def test_found(self):
        eng = _engine()
        r = eng.record_shift(
            schedule_id="SCHED-001",
            coverage_status=CoverageStatus.GAP,
        )
        result = eng.get_shift(r.id)
        assert result is not None
        assert result.coverage_status == CoverageStatus.GAP

    def test_not_found(self):
        eng = _engine()
        assert eng.get_shift("nonexistent") is None


# ---------------------------------------------------------------------------
# list_shifts
# ---------------------------------------------------------------------------


class TestListShifts:
    def test_list_all(self):
        eng = _engine()
        eng.record_shift(schedule_id="SCHED-001")
        eng.record_shift(schedule_id="SCHED-002")
        assert len(eng.list_shifts()) == 2

    def test_filter_by_shift_type(self):
        eng = _engine()
        eng.record_shift(
            schedule_id="SCHED-001",
            shift_type=ShiftType.BACKUP,
        )
        eng.record_shift(
            schedule_id="SCHED-002",
            shift_type=ShiftType.PRIMARY,
        )
        results = eng.list_shifts(shift_type=ShiftType.BACKUP)
        assert len(results) == 1

    def test_filter_by_coverage_status(self):
        eng = _engine()
        eng.record_shift(
            schedule_id="SCHED-001",
            coverage_status=CoverageStatus.GAP,
        )
        eng.record_shift(
            schedule_id="SCHED-002",
            coverage_status=CoverageStatus.FULL,
        )
        results = eng.list_shifts(coverage_status=CoverageStatus.GAP)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_shift(schedule_id="SCHED-001", service="api")
        eng.record_shift(schedule_id="SCHED-002", service="web")
        results = eng.list_shifts(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_shift(schedule_id="SCHED-001", team="sre")
        eng.record_shift(schedule_id="SCHED-002", team="platform")
        results = eng.list_shifts(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_shift(schedule_id=f"SCHED-{i}")
        assert len(eng.list_shifts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_gap
# ---------------------------------------------------------------------------


class TestAddGap:
    def test_basic(self):
        eng = _engine()
        g = eng.add_gap(
            schedule_id="SCHED-001",
            shift_type=ShiftType.SECONDARY,
            gap_duration_hours=4.0,
            severity=3,
            auto_fill=True,
            description="Weekend coverage gap",
        )
        assert g.schedule_id == "SCHED-001"
        assert g.shift_type == ShiftType.SECONDARY
        assert g.gap_duration_hours == 4.0
        assert g.severity == 3
        assert g.auto_fill is True
        assert g.description == "Weekend coverage gap"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_gap(schedule_id=f"SCHED-{i}")
        assert len(eng._gaps) == 2


# ---------------------------------------------------------------------------
# analyze_coverage_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeCoveragePatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_shift(
            schedule_id="SCHED-001",
            shift_type=ShiftType.PRIMARY,
            coverage_score=80.0,
        )
        eng.record_shift(
            schedule_id="SCHED-002",
            shift_type=ShiftType.PRIMARY,
            coverage_score=90.0,
        )
        result = eng.analyze_coverage_patterns()
        assert "primary" in result
        assert result["primary"]["count"] == 2
        assert result["primary"]["avg_coverage_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_coverage_patterns() == {}


# ---------------------------------------------------------------------------
# identify_coverage_gaps
# ---------------------------------------------------------------------------


class TestIdentifyCoverageGaps:
    def test_detects_gaps(self):
        eng = _engine()
        eng.record_shift(
            schedule_id="SCHED-001",
            coverage_status=CoverageStatus.GAP,
        )
        eng.record_shift(
            schedule_id="SCHED-002",
            coverage_status=CoverageStatus.FULL,
        )
        results = eng.identify_coverage_gaps()
        assert len(results) == 1
        assert results[0]["schedule_id"] == "SCHED-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_coverage_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_coverage_score
# ---------------------------------------------------------------------------


class TestRankByCoverageScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_shift(schedule_id="SCHED-001", team="sre", coverage_score=90.0)
        eng.record_shift(schedule_id="SCHED-002", team="sre", coverage_score=80.0)
        eng.record_shift(schedule_id="SCHED-003", team="platform", coverage_score=50.0)
        results = eng.rank_by_coverage_score()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["avg_coverage_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_coverage_score() == []


# ---------------------------------------------------------------------------
# detect_schedule_issues
# ---------------------------------------------------------------------------


class TestDetectScheduleIssues:
    def test_stable(self):
        eng = _engine()
        for sev in [10, 10, 10, 10]:
            eng.add_gap(schedule_id="SCHED-001", severity=sev)
        result = eng.detect_schedule_issues()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for sev in [5, 5, 20, 20]:
            eng.add_gap(schedule_id="SCHED-001", severity=sev)
        result = eng.detect_schedule_issues()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_schedule_issues()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_shift(
            schedule_id="SCHED-001",
            shift_type=ShiftType.PRIMARY,
            coverage_status=CoverageStatus.GAP,
            coverage_score=40.0,
            service="api",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, ShiftScheduleReport)
        assert report.total_records == 1
        assert report.coverage_gap_count == 1
        assert report.avg_coverage_score == 40.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_shift(schedule_id="SCHED-001")
        eng.add_gap(schedule_id="SCHED-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._gaps) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_gaps"] == 0
        assert stats["shift_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_shift(
            schedule_id="SCHED-001",
            shift_type=ShiftType.BACKUP,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_teams"] == 1
        assert "backup" in stats["shift_type_distribution"]
