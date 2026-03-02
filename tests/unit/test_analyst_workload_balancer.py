"""Tests for shieldops.operations.analyst_workload_balancer — AnalystWorkloadBalancer."""

from __future__ import annotations

from shieldops.operations.analyst_workload_balancer import (
    AnalystWorkloadBalancer,
    ShiftType,
    SkillLevel,
    WorkloadAnalysis,
    WorkloadLevel,
    WorkloadRecord,
    WorkloadReport,
)


def _engine(**kw) -> AnalystWorkloadBalancer:
    return AnalystWorkloadBalancer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_shift_day(self):
        assert ShiftType.DAY == "day"

    def test_shift_night(self):
        assert ShiftType.NIGHT == "night"

    def test_shift_swing(self):
        assert ShiftType.SWING == "swing"

    def test_shift_weekend(self):
        assert ShiftType.WEEKEND == "weekend"

    def test_shift_on_call(self):
        assert ShiftType.ON_CALL == "on_call"

    def test_workload_overloaded(self):
        assert WorkloadLevel.OVERLOADED == "overloaded"

    def test_workload_high(self):
        assert WorkloadLevel.HIGH == "high"

    def test_workload_balanced(self):
        assert WorkloadLevel.BALANCED == "balanced"

    def test_workload_low(self):
        assert WorkloadLevel.LOW == "low"

    def test_workload_idle(self):
        assert WorkloadLevel.IDLE == "idle"

    def test_skill_expert(self):
        assert SkillLevel.EXPERT == "expert"

    def test_skill_senior(self):
        assert SkillLevel.SENIOR == "senior"

    def test_skill_mid(self):
        assert SkillLevel.MID == "mid"

    def test_skill_junior(self):
        assert SkillLevel.JUNIOR == "junior"

    def test_skill_trainee(self):
        assert SkillLevel.TRAINEE == "trainee"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_workload_record_defaults(self):
        r = WorkloadRecord()
        assert r.id
        assert r.analyst_name == ""
        assert r.shift_type == ShiftType.DAY
        assert r.workload_level == WorkloadLevel.OVERLOADED
        assert r.skill_level == SkillLevel.EXPERT
        assert r.utilization_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_workload_analysis_defaults(self):
        c = WorkloadAnalysis()
        assert c.id
        assert c.analyst_name == ""
        assert c.shift_type == ShiftType.DAY
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_workload_report_defaults(self):
        r = WorkloadReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.overloaded_count == 0
        assert r.avg_utilization_score == 0.0
        assert r.by_shift == {}
        assert r.by_workload == {}
        assert r.by_skill == {}
        assert r.top_overloaded == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_workload
# ---------------------------------------------------------------------------


class TestRecordWorkload:
    def test_basic(self):
        eng = _engine()
        r = eng.record_workload(
            analyst_name="alice",
            shift_type=ShiftType.NIGHT,
            workload_level=WorkloadLevel.HIGH,
            skill_level=SkillLevel.SENIOR,
            utilization_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.analyst_name == "alice"
        assert r.shift_type == ShiftType.NIGHT
        assert r.workload_level == WorkloadLevel.HIGH
        assert r.skill_level == SkillLevel.SENIOR
        assert r.utilization_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_workload(analyst_name=f"analyst-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_workload
# ---------------------------------------------------------------------------


class TestGetWorkload:
    def test_found(self):
        eng = _engine()
        r = eng.record_workload(
            analyst_name="alice",
            workload_level=WorkloadLevel.OVERLOADED,
        )
        result = eng.get_workload(r.id)
        assert result is not None
        assert result.workload_level == WorkloadLevel.OVERLOADED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_workload("nonexistent") is None


# ---------------------------------------------------------------------------
# list_workloads
# ---------------------------------------------------------------------------


class TestListWorkloads:
    def test_list_all(self):
        eng = _engine()
        eng.record_workload(analyst_name="alice")
        eng.record_workload(analyst_name="bob")
        assert len(eng.list_workloads()) == 2

    def test_filter_by_shift(self):
        eng = _engine()
        eng.record_workload(
            analyst_name="alice",
            shift_type=ShiftType.DAY,
        )
        eng.record_workload(
            analyst_name="bob",
            shift_type=ShiftType.NIGHT,
        )
        results = eng.list_workloads(shift_type=ShiftType.DAY)
        assert len(results) == 1

    def test_filter_by_workload(self):
        eng = _engine()
        eng.record_workload(
            analyst_name="alice",
            workload_level=WorkloadLevel.OVERLOADED,
        )
        eng.record_workload(
            analyst_name="bob",
            workload_level=WorkloadLevel.LOW,
        )
        results = eng.list_workloads(
            workload_level=WorkloadLevel.OVERLOADED,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_workload(analyst_name="alice", team="security")
        eng.record_workload(analyst_name="bob", team="platform")
        results = eng.list_workloads(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_workload(analyst_name=f"analyst-{i}")
        assert len(eng.list_workloads(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        c = eng.add_analysis(
            analyst_name="alice",
            shift_type=ShiftType.ON_CALL,
            analysis_score=88.5,
        )
        assert c.analyst_name == "alice"
        assert c.shift_type == ShiftType.ON_CALL
        assert c.analysis_score == 88.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(analyst_name=f"analyst-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_workload_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_workload(
            analyst_name="alice",
            shift_type=ShiftType.DAY,
            utilization_score=90.0,
        )
        eng.record_workload(
            analyst_name="bob",
            shift_type=ShiftType.DAY,
            utilization_score=70.0,
        )
        result = eng.analyze_workload_distribution()
        assert "day" in result
        assert result["day"]["count"] == 2
        assert result["day"]["avg_utilization_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_workload_distribution() == {}


# ---------------------------------------------------------------------------
# identify_overloaded_analysts
# ---------------------------------------------------------------------------


class TestIdentifyOverloadedAnalysts:
    def test_detects_above_threshold(self):
        eng = _engine(utilization_threshold=65.0)
        eng.record_workload(analyst_name="alice", utilization_score=90.0)
        eng.record_workload(analyst_name="bob", utilization_score=40.0)
        results = eng.identify_overloaded_analysts()
        assert len(results) == 1
        assert results[0]["analyst_name"] == "alice"

    def test_sorted_descending(self):
        eng = _engine(utilization_threshold=65.0)
        eng.record_workload(analyst_name="alice", utilization_score=80.0)
        eng.record_workload(analyst_name="bob", utilization_score=95.0)
        results = eng.identify_overloaded_analysts()
        assert len(results) == 2
        assert results[0]["utilization_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_overloaded_analysts() == []


# ---------------------------------------------------------------------------
# rank_by_utilization
# ---------------------------------------------------------------------------


class TestRankByUtilization:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_workload(analyst_name="alice", service="auth-svc", utilization_score=50.0)
        eng.record_workload(analyst_name="bob", service="api-gw", utilization_score=90.0)
        results = eng.rank_by_utilization()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_utilization_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_utilization() == []


# ---------------------------------------------------------------------------
# detect_workload_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analyst_name="alice", analysis_score=50.0)
        result = eng.detect_workload_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analyst_name="alice", analysis_score=20.0)
        eng.add_analysis(analyst_name="bob", analysis_score=20.0)
        eng.add_analysis(analyst_name="carol", analysis_score=80.0)
        eng.add_analysis(analyst_name="dave", analysis_score=80.0)
        result = eng.detect_workload_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_workload_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(utilization_threshold=85.0)
        eng.record_workload(
            analyst_name="alice",
            shift_type=ShiftType.NIGHT,
            workload_level=WorkloadLevel.OVERLOADED,
            skill_level=SkillLevel.SENIOR,
            utilization_score=95.0,
        )
        report = eng.generate_report()
        assert isinstance(report, WorkloadReport)
        assert report.total_records == 1
        assert report.overloaded_count == 1
        assert len(report.top_overloaded) == 1
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
        eng.record_workload(analyst_name="alice")
        eng.add_analysis(analyst_name="alice")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["shift_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_workload(
            analyst_name="alice",
            shift_type=ShiftType.DAY,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "day" in stats["shift_distribution"]
