"""Tests for shieldops.sla.reliability_scorecard — PlatformReliabilityScorecard."""

from __future__ import annotations

from shieldops.sla.reliability_scorecard import (
    CategoryScore,
    PlatformReliabilityScorecard,
    ReliabilityScorecardReport,
    ScorecardRecord,
    ScoreCategory,
    ScoreGrade,
    ScoreTrend,
)


def _engine(**kw) -> PlatformReliabilityScorecard:
    return PlatformReliabilityScorecard(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ScoreCategory (5)
    def test_category_slo(self):
        assert ScoreCategory.SLO_COMPLIANCE == "slo_compliance"

    def test_category_incident(self):
        assert ScoreCategory.INCIDENT_FREQUENCY == "incident_frequency"

    def test_category_change(self):
        assert ScoreCategory.CHANGE_SUCCESS == "change_success"

    def test_category_monitoring(self):
        assert ScoreCategory.MONITORING_COVERAGE == "monitoring_coverage"

    def test_category_recovery(self):
        assert ScoreCategory.RECOVERY_SPEED == "recovery_speed"

    # ScoreGrade (5)
    def test_grade_a(self):
        assert ScoreGrade.A_EXCELLENT == "a_excellent"

    def test_grade_b(self):
        assert ScoreGrade.B_GOOD == "b_good"

    def test_grade_c(self):
        assert ScoreGrade.C_ADEQUATE == "c_adequate"

    def test_grade_d(self):
        assert ScoreGrade.D_POOR == "d_poor"

    def test_grade_f(self):
        assert ScoreGrade.F_FAILING == "f_failing"

    # ScoreTrend (5)
    def test_trend_improving(self):
        assert ScoreTrend.IMPROVING == "improving"

    def test_trend_stable(self):
        assert ScoreTrend.STABLE == "stable"

    def test_trend_declining(self):
        assert ScoreTrend.DECLINING == "declining"

    def test_trend_volatile(self):
        assert ScoreTrend.VOLATILE == "volatile"

    def test_trend_new(self):
        assert ScoreTrend.NEW == "new"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_scorecard_record_defaults(self):
        r = ScorecardRecord()
        assert r.id
        assert r.service_name == ""
        assert r.category == ScoreCategory.SLO_COMPLIANCE
        assert r.grade == ScoreGrade.C_ADEQUATE
        assert r.trend == ScoreTrend.NEW
        assert r.overall_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_category_score_defaults(self):
        c = CategoryScore()
        assert c.id
        assert c.category_name == ""
        assert c.category == ScoreCategory.SLO_COMPLIANCE
        assert c.grade == ScoreGrade.C_ADEQUATE
        assert c.score == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_report_defaults(self):
        r = ReliabilityScorecardReport()
        assert r.total_scorecards == 0
        assert r.total_categories == 0
        assert r.avg_score_pct == 0.0
        assert r.by_category == {}
        assert r.by_grade == {}
        assert r.low_score_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_scorecard
# -------------------------------------------------------------------


class TestRecordScorecard:
    def test_basic(self):
        eng = _engine()
        r = eng.record_scorecard(
            "svc-a",
            category=ScoreCategory.INCIDENT_FREQUENCY,
            grade=ScoreGrade.A_EXCELLENT,
            overall_score=95.0,
        )
        assert r.service_name == "svc-a"
        assert r.category == ScoreCategory.INCIDENT_FREQUENCY
        assert r.overall_score == 95.0

    def test_with_trend(self):
        eng = _engine()
        r = eng.record_scorecard("svc-b", trend=ScoreTrend.IMPROVING)
        assert r.trend == ScoreTrend.IMPROVING

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_scorecard(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_scorecard
# -------------------------------------------------------------------


class TestGetScorecard:
    def test_found(self):
        eng = _engine()
        r = eng.record_scorecard("svc-a")
        assert eng.get_scorecard(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_scorecard("nonexistent") is None


# -------------------------------------------------------------------
# list_scorecards
# -------------------------------------------------------------------


class TestListScorecards:
    def test_list_all(self):
        eng = _engine()
        eng.record_scorecard("svc-a")
        eng.record_scorecard("svc-b")
        assert len(eng.list_scorecards()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_scorecard("svc-a")
        eng.record_scorecard("svc-b")
        results = eng.list_scorecards(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_scorecard("svc-a", category=ScoreCategory.SLO_COMPLIANCE)
        eng.record_scorecard("svc-b", category=ScoreCategory.RECOVERY_SPEED)
        results = eng.list_scorecards(category=ScoreCategory.SLO_COMPLIANCE)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_category_score
# -------------------------------------------------------------------


class TestAddCategoryScore:
    def test_basic(self):
        eng = _engine()
        c = eng.add_category_score("slo-score", score=88.0)
        assert c.category_name == "slo-score"
        assert c.score == 88.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_category_score(f"cat-{i}")
        assert len(eng._categories) == 2


# -------------------------------------------------------------------
# analyze_service_reliability
# -------------------------------------------------------------------


class TestAnalyzeServiceReliability:
    def test_with_data(self):
        eng = _engine(min_grade_score=70.0)
        eng.record_scorecard("svc-a", overall_score=80.0)
        eng.record_scorecard("svc-a", overall_score=90.0)
        result = eng.analyze_service_reliability("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total"] == 2
        assert result["avg_score"] == 85.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_service_reliability("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_low_scoring_services
# -------------------------------------------------------------------


class TestIdentifyLowScoringServices:
    def test_with_low_grades(self):
        eng = _engine()
        eng.record_scorecard("svc-a", grade=ScoreGrade.D_POOR)
        eng.record_scorecard("svc-a", grade=ScoreGrade.F_FAILING)
        eng.record_scorecard("svc-b", grade=ScoreGrade.A_EXCELLENT)
        results = eng.identify_low_scoring_services()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_scoring_services() == []


# -------------------------------------------------------------------
# rank_by_overall_score
# -------------------------------------------------------------------


class TestRankByOverallScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_scorecard("svc-a", overall_score=10.0)
        eng.record_scorecard("svc-b", overall_score=90.0)
        results = eng.rank_by_overall_score()
        assert results[0]["avg_overall_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_overall_score() == []


# -------------------------------------------------------------------
# detect_score_trends
# -------------------------------------------------------------------


class TestDetectScoreTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(4):
            eng.record_scorecard("svc-trending")
        eng.record_scorecard("svc-stable")
        results = eng.detect_score_trends()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-trending"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_score_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_grade_score=70.0)
        eng.record_scorecard("svc-a", grade=ScoreGrade.F_FAILING, overall_score=30.0)
        eng.record_scorecard("svc-b", grade=ScoreGrade.D_POOR, overall_score=50.0)
        eng.add_category_score("cat-1")
        report = eng.generate_report()
        assert isinstance(report, ReliabilityScorecardReport)
        assert report.total_scorecards == 2
        assert report.total_categories == 1
        assert report.low_score_count == 2
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "healthy" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_scorecard("svc-a")
        eng.add_category_score("cat-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._categories) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_scorecards"] == 0
        assert stats["total_categories"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_scorecard("svc-a", category=ScoreCategory.SLO_COMPLIANCE)
        eng.record_scorecard("svc-b", category=ScoreCategory.RECOVERY_SPEED)
        eng.add_category_score("cat-1")
        stats = eng.get_stats()
        assert stats["total_scorecards"] == 2
        assert stats["total_categories"] == 1
        assert stats["unique_services"] == 2
