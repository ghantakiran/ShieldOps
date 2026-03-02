"""Tests for shieldops.analytics.analyst_efficiency_tracker — AnalystEfficiencyTracker."""

from __future__ import annotations

from shieldops.analytics.analyst_efficiency_tracker import (
    AnalystEfficiencyTracker,
    AnalystTier,
    EfficiencyAnalysis,
    EfficiencyMetric,
    EfficiencyRecord,
    EfficiencyReport,
    PerformanceBand,
)


def _engine(**kw) -> AnalystEfficiencyTracker:
    return AnalystEfficiencyTracker(**kw)


class TestEnums:
    def test_efficiencymetric_val1(self):
        assert EfficiencyMetric.MEAN_TIME_TO_TRIAGE == "mean_time_to_triage"

    def test_efficiencymetric_val2(self):
        assert EfficiencyMetric.MEAN_TIME_TO_RESOLVE == "mean_time_to_resolve"

    def test_efficiencymetric_val3(self):
        assert EfficiencyMetric.ALERTS_PER_ANALYST == "alerts_per_analyst"

    def test_efficiencymetric_val4(self):
        assert EfficiencyMetric.FALSE_POSITIVE_RATE == "false_positive_rate"

    def test_efficiencymetric_val5(self):
        assert EfficiencyMetric.ESCALATION_RATE == "escalation_rate"

    def test_analysttier_val1(self):
        assert AnalystTier.TIER_1 == "tier_1"

    def test_analysttier_val2(self):
        assert AnalystTier.TIER_2 == "tier_2"

    def test_analysttier_val3(self):
        assert AnalystTier.TIER_3 == "tier_3"

    def test_analysttier_val4(self):
        assert AnalystTier.LEAD == "lead"

    def test_analysttier_val5(self):
        assert AnalystTier.MANAGER == "manager"

    def test_performanceband_val1(self):
        assert PerformanceBand.EXCEPTIONAL == "exceptional"

    def test_performanceband_val2(self):
        assert PerformanceBand.ABOVE_AVERAGE == "above_average"

    def test_performanceband_val3(self):
        assert PerformanceBand.AVERAGE == "average"

    def test_performanceband_val4(self):
        assert PerformanceBand.BELOW_AVERAGE == "below_average"

    def test_performanceband_val5(self):
        assert PerformanceBand.NEEDS_IMPROVEMENT == "needs_improvement"


class TestModels:
    def test_record_defaults(self):
        r = EfficiencyRecord()
        assert r.id
        assert r.analyst_name == ""

    def test_analysis_defaults(self):
        a = EfficiencyAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = EfficiencyReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_efficiency(
            analyst_name="test",
            efficiency_metric=EfficiencyMetric.MEAN_TIME_TO_RESOLVE,
            efficiency_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.analyst_name == "test"
        assert r.efficiency_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_efficiency(analyst_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_efficiency(analyst_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_efficiency(analyst_name="a")
        eng.record_efficiency(analyst_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_efficiency(
            analyst_name="a", efficiency_metric=EfficiencyMetric.MEAN_TIME_TO_TRIAGE
        )
        eng.record_efficiency(
            analyst_name="b", efficiency_metric=EfficiencyMetric.MEAN_TIME_TO_RESOLVE
        )
        assert len(eng.list_records(efficiency_metric=EfficiencyMetric.MEAN_TIME_TO_TRIAGE)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_efficiency(analyst_name="a", analyst_tier=AnalystTier.TIER_1)
        eng.record_efficiency(analyst_name="b", analyst_tier=AnalystTier.TIER_2)
        assert len(eng.list_records(analyst_tier=AnalystTier.TIER_1)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_efficiency(analyst_name="a", team="sec")
        eng.record_efficiency(analyst_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_efficiency(analyst_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            analyst_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(analyst_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_efficiency(
            analyst_name="a",
            efficiency_metric=EfficiencyMetric.MEAN_TIME_TO_TRIAGE,
            efficiency_score=90.0,
        )
        eng.record_efficiency(
            analyst_name="b",
            efficiency_metric=EfficiencyMetric.MEAN_TIME_TO_TRIAGE,
            efficiency_score=70.0,
        )
        result = eng.analyze_distribution()
        assert EfficiencyMetric.MEAN_TIME_TO_TRIAGE.value in result
        assert result[EfficiencyMetric.MEAN_TIME_TO_TRIAGE.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_efficiency(analyst_name="a", efficiency_score=60.0)
        eng.record_efficiency(analyst_name="b", efficiency_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_efficiency(analyst_name="a", efficiency_score=50.0)
        eng.record_efficiency(analyst_name="b", efficiency_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["efficiency_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_efficiency(analyst_name="a", service="auth", efficiency_score=90.0)
        eng.record_efficiency(analyst_name="b", service="api", efficiency_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analyst_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analyst_name="a", analysis_score=20.0)
        eng.add_analysis(analyst_name="b", analysis_score=20.0)
        eng.add_analysis(analyst_name="c", analysis_score=80.0)
        eng.add_analysis(analyst_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_efficiency(analyst_name="test", efficiency_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert (
            "healthy" in report.recommendations[0].lower()
            or "within" in report.recommendations[0].lower()
        )


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_efficiency(analyst_name="test")
        eng.add_analysis(analyst_name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_efficiency(analyst_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
