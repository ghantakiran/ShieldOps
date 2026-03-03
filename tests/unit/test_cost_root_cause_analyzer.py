"""Tests for shieldops.billing.cost_root_cause_analyzer."""

from __future__ import annotations

from shieldops.billing.cost_root_cause_analyzer import (
    AnalysisDepth,
    CauseAnalysis,
    CostRootCauseAnalyzer,
    ImpactCategory,
    RootCause,
    RootCauseRecord,
    RootCauseReport,
)


def _engine(**kw) -> CostRootCauseAnalyzer:
    return CostRootCauseAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_rootcause_config_change(self):
        assert RootCause.CONFIG_CHANGE == "config_change"

    def test_rootcause_traffic_spike(self):
        assert RootCause.TRAFFIC_SPIKE == "traffic_spike"

    def test_rootcause_resource_leak(self):
        assert RootCause.RESOURCE_LEAK == "resource_leak"

    def test_rootcause_pricing_change(self):
        assert RootCause.PRICING_CHANGE == "pricing_change"

    def test_rootcause_misconfiguration(self):
        assert RootCause.MISCONFIGURATION == "misconfiguration"

    def test_analysisdepth_surface(self):
        assert AnalysisDepth.SURFACE == "surface"

    def test_analysisdepth_moderate(self):
        assert AnalysisDepth.MODERATE == "moderate"

    def test_analysisdepth_deep(self):
        assert AnalysisDepth.DEEP == "deep"

    def test_analysisdepth_exhaustive(self):
        assert AnalysisDepth.EXHAUSTIVE == "exhaustive"

    def test_analysisdepth_targeted(self):
        assert AnalysisDepth.TARGETED == "targeted"

    def test_impactcategory_compute(self):
        assert ImpactCategory.COMPUTE == "compute"

    def test_impactcategory_storage(self):
        assert ImpactCategory.STORAGE == "storage"

    def test_impactcategory_network(self):
        assert ImpactCategory.NETWORK == "network"

    def test_impactcategory_data_transfer(self):
        assert ImpactCategory.DATA_TRANSFER == "data_transfer"

    def test_impactcategory_licensing(self):
        assert ImpactCategory.LICENSING == "licensing"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_root_cause_record_defaults(self):
        r = RootCauseRecord()
        assert r.id
        assert r.root_cause == RootCause.MISCONFIGURATION
        assert r.analysis_depth == AnalysisDepth.MODERATE
        assert r.impact_category == ImpactCategory.COMPUTE
        assert r.cost_impact == 0.0
        assert r.confidence_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_cause_analysis_defaults(self):
        a = CauseAnalysis()
        assert a.id
        assert a.root_cause == RootCause.MISCONFIGURATION
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_root_cause_report_defaults(self):
        r = RootCauseReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_confidence_count == 0
        assert r.avg_cost_impact == 0.0
        assert r.by_root_cause == {}
        assert r.by_analysis_depth == {}
        assert r.by_impact_category == {}
        assert r.top_causes == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_root_cause
# ---------------------------------------------------------------------------


class TestRecordRootCause:
    def test_basic(self):
        eng = _engine()
        r = eng.record_root_cause(
            root_cause=RootCause.TRAFFIC_SPIKE,
            analysis_depth=AnalysisDepth.DEEP,
            impact_category=ImpactCategory.COMPUTE,
            cost_impact=2500.0,
            confidence_score=90.0,
            service="api-gw",
            team="platform",
        )
        assert r.root_cause == RootCause.TRAFFIC_SPIKE
        assert r.cost_impact == 2500.0
        assert r.confidence_score == 90.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for _i in range(5):
            eng.record_root_cause(root_cause=RootCause.CONFIG_CHANGE)
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_root_cause
# ---------------------------------------------------------------------------


class TestGetRootCause:
    def test_found(self):
        eng = _engine()
        r = eng.record_root_cause(
            root_cause=RootCause.RESOURCE_LEAK,
            cost_impact=500.0,
        )
        result = eng.get_root_cause(r.id)
        assert result is not None
        assert result.root_cause == RootCause.RESOURCE_LEAK

    def test_not_found(self):
        eng = _engine()
        assert eng.get_root_cause("nonexistent") is None


# ---------------------------------------------------------------------------
# list_root_causes
# ---------------------------------------------------------------------------


class TestListRootCauses:
    def test_list_all(self):
        eng = _engine()
        eng.record_root_cause(root_cause=RootCause.TRAFFIC_SPIKE)
        eng.record_root_cause(root_cause=RootCause.CONFIG_CHANGE)
        assert len(eng.list_root_causes()) == 2

    def test_filter_by_root_cause(self):
        eng = _engine()
        eng.record_root_cause(root_cause=RootCause.TRAFFIC_SPIKE)
        eng.record_root_cause(root_cause=RootCause.MISCONFIGURATION)
        results = eng.list_root_causes(root_cause=RootCause.TRAFFIC_SPIKE)
        assert len(results) == 1

    def test_filter_by_impact_category(self):
        eng = _engine()
        eng.record_root_cause(impact_category=ImpactCategory.COMPUTE)
        eng.record_root_cause(impact_category=ImpactCategory.STORAGE)
        results = eng.list_root_causes(impact_category=ImpactCategory.COMPUTE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_root_cause(team="security")
        eng.record_root_cause(team="platform")
        results = eng.list_root_causes(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for _i in range(10):
            eng.record_root_cause(root_cause=RootCause.MISCONFIGURATION)
        assert len(eng.list_root_causes(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            root_cause=RootCause.PRICING_CHANGE,
            analysis_score=92.0,
            threshold=80.0,
            breached=True,
            description="pricing change triggered spike",
        )
        assert a.root_cause == RootCause.PRICING_CHANGE
        assert a.analysis_score == 92.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _i in range(5):
            eng.add_analysis(root_cause=RootCause.CONFIG_CHANGE)
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_cause_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeCauseDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_root_cause(root_cause=RootCause.TRAFFIC_SPIKE, cost_impact=1000.0)
        eng.record_root_cause(root_cause=RootCause.TRAFFIC_SPIKE, cost_impact=500.0)
        result = eng.analyze_cause_distribution()
        assert "traffic_spike" in result
        assert result["traffic_spike"]["count"] == 2
        assert result["traffic_spike"]["avg_cost_impact"] == 750.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_cause_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_confidence_causes
# ---------------------------------------------------------------------------


class TestIdentifyHighConfidenceCauses:
    def test_detects_above_threshold(self):
        eng = _engine(confidence_threshold=80.0)
        eng.record_root_cause(root_cause=RootCause.TRAFFIC_SPIKE, confidence_score=90.0)
        eng.record_root_cause(root_cause=RootCause.CONFIG_CHANGE, confidence_score=50.0)
        results = eng.identify_high_confidence_causes()
        assert len(results) == 1

    def test_sorted_descending_by_cost(self):
        eng = _engine(confidence_threshold=50.0)
        eng.record_root_cause(confidence_score=90.0, cost_impact=5000.0)
        eng.record_root_cause(confidence_score=80.0, cost_impact=1000.0)
        results = eng.identify_high_confidence_causes()
        assert results[0]["cost_impact"] == 5000.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_confidence_causes() == []


# ---------------------------------------------------------------------------
# rank_by_cost_impact
# ---------------------------------------------------------------------------


class TestRankByCostImpact:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_root_cause(service="api-gw", cost_impact=3000.0)
        eng.record_root_cause(service="auth-svc", cost_impact=500.0)
        results = eng.rank_by_cost_impact()
        assert results[0]["service"] == "api-gw"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_cost_impact() == []


# ---------------------------------------------------------------------------
# detect_confidence_trends
# ---------------------------------------------------------------------------


class TestDetectConfidenceTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(root_cause=RootCause.TRAFFIC_SPIKE, analysis_score=50.0)
        result = eng.detect_confidence_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_confidence_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_confidence_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(confidence_threshold=70.0)
        eng.record_root_cause(
            root_cause=RootCause.TRAFFIC_SPIKE,
            analysis_depth=AnalysisDepth.DEEP,
            impact_category=ImpactCategory.COMPUTE,
            cost_impact=1000.0,
            confidence_score=85.0,
        )
        report = eng.generate_report()
        assert isinstance(report, RootCauseReport)
        assert report.total_records == 1
        assert report.high_confidence_count == 1

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
        eng.record_root_cause(root_cause=RootCause.TRAFFIC_SPIKE)
        eng.add_analysis(root_cause=RootCause.TRAFFIC_SPIKE)
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
        assert stats["root_cause_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_root_cause(
            root_cause=RootCause.TRAFFIC_SPIKE,
            service="api-gw",
            team="platform",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert "traffic_spike" in stats["root_cause_distribution"]
