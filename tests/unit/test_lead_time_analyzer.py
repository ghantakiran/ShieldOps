"""Tests for shieldops.changes.lead_time_analyzer — ChangeLeadTimeAnalyzer."""

from __future__ import annotations

from shieldops.changes.lead_time_analyzer import (
    ChangeLeadTimeAnalyzer,
    LeadTimePhase,
    LeadTimeRecord,
    LeadTimeReport,
    LeadTimeTrend,
    PhaseBreakdown,
    VelocityGrade,
)


def _engine(**kw) -> ChangeLeadTimeAnalyzer:
    return ChangeLeadTimeAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # LeadTimePhase (5)
    def test_phase_coding(self):
        assert LeadTimePhase.CODING == "coding"

    def test_phase_review(self):
        assert LeadTimePhase.REVIEW == "review"

    def test_phase_testing(self):
        assert LeadTimePhase.TESTING == "testing"

    def test_phase_staging(self):
        assert LeadTimePhase.STAGING == "staging"

    def test_phase_production(self):
        assert LeadTimePhase.PRODUCTION == "production"

    # VelocityGrade (5)
    def test_grade_elite(self):
        assert VelocityGrade.ELITE == "elite"

    def test_grade_high(self):
        assert VelocityGrade.HIGH == "high"

    def test_grade_medium(self):
        assert VelocityGrade.MEDIUM == "medium"

    def test_grade_low(self):
        assert VelocityGrade.LOW == "low"

    def test_grade_critical(self):
        assert VelocityGrade.CRITICAL == "critical"

    # LeadTimeTrend (5)
    def test_trend_improving(self):
        assert LeadTimeTrend.IMPROVING == "improving"

    def test_trend_stable(self):
        assert LeadTimeTrend.STABLE == "stable"

    def test_trend_degrading(self):
        assert LeadTimeTrend.DEGRADING == "degrading"

    def test_trend_volatile(self):
        assert LeadTimeTrend.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert LeadTimeTrend.INSUFFICIENT_DATA == "insufficient_data"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_lead_time_record_defaults(self):
        r = LeadTimeRecord()
        assert r.id
        assert r.service_name == ""
        assert r.phase == LeadTimePhase.CODING
        assert r.grade == VelocityGrade.MEDIUM
        assert r.lead_time_hours == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_phase_breakdown_defaults(self):
        b = PhaseBreakdown()
        assert b.id
        assert b.phase_name == ""
        assert b.phase == LeadTimePhase.CODING
        assert b.grade == VelocityGrade.MEDIUM
        assert b.avg_hours == 0.0
        assert b.description == ""
        assert b.created_at > 0

    def test_report_defaults(self):
        r = LeadTimeReport()
        assert r.total_records == 0
        assert r.total_breakdowns == 0
        assert r.avg_lead_time_hours == 0.0
        assert r.by_phase == {}
        assert r.by_grade == {}
        assert r.slow_service_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_lead_time
# ---------------------------------------------------------------------------


class TestRecordLeadTime:
    def test_basic(self):
        eng = _engine()
        r = eng.record_lead_time(
            "web-api",
            phase=LeadTimePhase.REVIEW,
            grade=VelocityGrade.HIGH,
            lead_time_hours=4.5,
        )
        assert r.service_name == "web-api"
        assert r.lead_time_hours == 4.5
        assert r.grade == VelocityGrade.HIGH

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_lead_time(f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_lead_time
# ---------------------------------------------------------------------------


class TestGetLeadTime:
    def test_found(self):
        eng = _engine()
        r = eng.record_lead_time("web-api", lead_time_hours=8.0)
        assert eng.get_lead_time(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_lead_time("nonexistent") is None


# ---------------------------------------------------------------------------
# list_lead_times
# ---------------------------------------------------------------------------


class TestListLeadTimes:
    def test_list_all(self):
        eng = _engine()
        eng.record_lead_time("svc-a")
        eng.record_lead_time("svc-b")
        assert len(eng.list_lead_times()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_lead_time("svc-a")
        eng.record_lead_time("svc-b")
        results = eng.list_lead_times(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_phase(self):
        eng = _engine()
        eng.record_lead_time("s1", phase=LeadTimePhase.CODING)
        eng.record_lead_time("s2", phase=LeadTimePhase.TESTING)
        results = eng.list_lead_times(phase=LeadTimePhase.CODING)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# add_breakdown
# ---------------------------------------------------------------------------


class TestAddBreakdown:
    def test_basic(self):
        eng = _engine()
        b = eng.add_breakdown(
            "code-review-phase",
            phase=LeadTimePhase.REVIEW,
            grade=VelocityGrade.HIGH,
            avg_hours=2.5,
        )
        assert b.phase_name == "code-review-phase"
        assert b.avg_hours == 2.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_breakdown(f"phase-{i}")
        assert len(eng._breakdowns) == 2


# ---------------------------------------------------------------------------
# analyze_service_lead_time
# ---------------------------------------------------------------------------


class TestAnalyzeServiceLeadTime:
    def test_with_data(self):
        eng = _engine(max_lead_time_hours=72.0)
        eng.record_lead_time("web-api", lead_time_hours=24.0)
        eng.record_lead_time("web-api", lead_time_hours=36.0)
        result = eng.analyze_service_lead_time("web-api")
        assert result["service_name"] == "web-api"
        assert result["avg_lead_time_hours"] == 30.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_service_lead_time("ghost")
        assert result["status"] == "no_data"


# ---------------------------------------------------------------------------
# identify_slow_services
# ---------------------------------------------------------------------------


class TestIdentifySlowServices:
    def test_with_slow(self):
        eng = _engine()
        eng.record_lead_time("svc-a", grade=VelocityGrade.LOW)
        eng.record_lead_time("svc-a", grade=VelocityGrade.CRITICAL)
        eng.record_lead_time("svc-b", grade=VelocityGrade.ELITE)
        results = eng.identify_slow_services()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_slow_services() == []


# ---------------------------------------------------------------------------
# rank_by_lead_time
# ---------------------------------------------------------------------------


class TestRankByLeadTime:
    def test_with_data(self):
        eng = _engine()
        eng.record_lead_time("svc-a", lead_time_hours=10.0)
        eng.record_lead_time("svc-b", lead_time_hours=50.0)
        results = eng.rank_by_lead_time()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_lead_time_hours"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_lead_time() == []


# ---------------------------------------------------------------------------
# detect_lead_time_trends
# ---------------------------------------------------------------------------


class TestDetectLeadTimeTrends:
    def test_with_enough_data_improving(self):
        eng = _engine()
        eng.record_lead_time("svc-a", lead_time_hours=50.0)
        eng.record_lead_time("svc-a", lead_time_hours=48.0)
        eng.record_lead_time("svc-a", lead_time_hours=20.0)
        eng.record_lead_time("svc-a", lead_time_hours=18.0)
        results = eng.detect_lead_time_trends()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["trend"] == LeadTimeTrend.IMPROVING.value

    def test_insufficient_data(self):
        eng = _engine()
        eng.record_lead_time("svc-a", lead_time_hours=10.0)
        eng.record_lead_time("svc-a", lead_time_hours=12.0)
        results = eng.detect_lead_time_trends()
        assert len(results) == 0


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(max_lead_time_hours=72.0)
        eng.record_lead_time(
            "svc-a",
            lead_time_hours=100.0,
            grade=VelocityGrade.LOW,
        )
        eng.add_breakdown("review-phase")
        report = eng.generate_report()
        assert isinstance(report, LeadTimeReport)
        assert report.total_records == 1
        assert report.total_breakdowns == 1
        assert report.slow_service_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "within acceptable bounds" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_lead_time("svc-a")
        eng.add_breakdown("phase-a")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._breakdowns) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_breakdowns"] == 0
        assert stats["phase_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_lead_time("svc-a", phase=LeadTimePhase.CODING)
        eng.record_lead_time("svc-b", phase=LeadTimePhase.TESTING)
        eng.add_breakdown("review-phase")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_breakdowns"] == 1
        assert stats["unique_services"] == 2
