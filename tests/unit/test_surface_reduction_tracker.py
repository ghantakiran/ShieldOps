"""Tests for shieldops.security.surface_reduction_tracker — SurfaceReductionTracker."""

from __future__ import annotations

from shieldops.security.surface_reduction_tracker import (
    ReductionAction,
    ReductionAnalysis,
    ReductionCategory,
    ReductionImpact,
    ReductionRecord,
    ReductionReport,
    SurfaceReductionTracker,
)


def _engine(**kw) -> SurfaceReductionTracker:
    return SurfaceReductionTracker(**kw)


class TestEnums:
    def test_reductionaction_val1(self):
        assert ReductionAction.DECOMMISSION == "decommission"

    def test_reductionaction_val2(self):
        assert ReductionAction.PATCH == "patch"

    def test_reductionaction_val3(self):
        assert ReductionAction.RESTRICT == "restrict"

    def test_reductionaction_val4(self):
        assert ReductionAction.CONSOLIDATE == "consolidate"

    def test_reductionaction_val5(self):
        assert ReductionAction.MIGRATE == "migrate"

    def test_reductioncategory_val1(self):
        assert ReductionCategory.NETWORK == "network"

    def test_reductioncategory_val2(self):
        assert ReductionCategory.APPLICATION == "application"

    def test_reductioncategory_val3(self):
        assert ReductionCategory.CLOUD == "cloud"

    def test_reductioncategory_val4(self):
        assert ReductionCategory.IDENTITY == "identity"

    def test_reductioncategory_val5(self):
        assert ReductionCategory.DATA == "data"

    def test_reductionimpact_val1(self):
        assert ReductionImpact.CRITICAL == "critical"

    def test_reductionimpact_val2(self):
        assert ReductionImpact.HIGH == "high"

    def test_reductionimpact_val3(self):
        assert ReductionImpact.MEDIUM == "medium"

    def test_reductionimpact_val4(self):
        assert ReductionImpact.LOW == "low"

    def test_reductionimpact_val5(self):
        assert ReductionImpact.MINIMAL == "minimal"


class TestModels:
    def test_record_defaults(self):
        r = ReductionRecord()
        assert r.id
        assert r.reduction_name == ""

    def test_analysis_defaults(self):
        a = ReductionAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = ReductionReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_reduction(
            reduction_name="test",
            reduction_action=ReductionAction.PATCH,
            reduction_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.reduction_name == "test"
        assert r.reduction_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_reduction(reduction_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_reduction(reduction_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_reduction(reduction_name="a")
        eng.record_reduction(reduction_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_reduction(reduction_name="a", reduction_action=ReductionAction.DECOMMISSION)
        eng.record_reduction(reduction_name="b", reduction_action=ReductionAction.PATCH)
        assert len(eng.list_records(reduction_action=ReductionAction.DECOMMISSION)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_reduction(reduction_name="a", reduction_category=ReductionCategory.NETWORK)
        eng.record_reduction(reduction_name="b", reduction_category=ReductionCategory.APPLICATION)
        assert len(eng.list_records(reduction_category=ReductionCategory.NETWORK)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_reduction(reduction_name="a", team="sec")
        eng.record_reduction(reduction_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_reduction(reduction_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            reduction_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(reduction_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_reduction(
            reduction_name="a", reduction_action=ReductionAction.DECOMMISSION, reduction_score=90.0
        )
        eng.record_reduction(
            reduction_name="b", reduction_action=ReductionAction.DECOMMISSION, reduction_score=70.0
        )
        result = eng.analyze_distribution()
        assert ReductionAction.DECOMMISSION.value in result
        assert result[ReductionAction.DECOMMISSION.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_reduction(reduction_name="a", reduction_score=60.0)
        eng.record_reduction(reduction_name="b", reduction_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_reduction(reduction_name="a", reduction_score=50.0)
        eng.record_reduction(reduction_name="b", reduction_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["reduction_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_reduction(reduction_name="a", service="auth", reduction_score=90.0)
        eng.record_reduction(reduction_name="b", service="api", reduction_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(reduction_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(reduction_name="a", analysis_score=20.0)
        eng.add_analysis(reduction_name="b", analysis_score=20.0)
        eng.add_analysis(reduction_name="c", analysis_score=80.0)
        eng.add_analysis(reduction_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_reduction(reduction_name="test", reduction_score=50.0)
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
        eng.record_reduction(reduction_name="test")
        eng.add_analysis(reduction_name="test")
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
        eng.record_reduction(reduction_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
