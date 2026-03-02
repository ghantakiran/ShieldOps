"""Tests for shieldops.sla.slo_threshold_optimizer — SloThresholdOptimizer."""

from __future__ import annotations

from shieldops.sla.slo_threshold_optimizer import (
    OptimizationBasis,
    SloThresholdOptimizer,
    SloThresholdReport,
    ThresholdAnalysis,
    ThresholdConfidence,
    ThresholdDirection,
    ThresholdRecord,
)


def _engine(**kw) -> SloThresholdOptimizer:
    return SloThresholdOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_direction_tighten(self):
        assert ThresholdDirection.TIGHTEN == "tighten"

    def test_direction_relax(self):
        assert ThresholdDirection.RELAX == "relax"

    def test_direction_maintain(self):
        assert ThresholdDirection.MAINTAIN == "maintain"

    def test_direction_split_tier(self):
        assert ThresholdDirection.SPLIT_TIER == "split_tier"

    def test_direction_consolidate(self):
        assert ThresholdDirection.CONSOLIDATE == "consolidate"

    def test_basis_historical_p99(self):
        assert OptimizationBasis.HISTORICAL_P99 == "historical_p99"

    def test_basis_cost_efficiency(self):
        assert OptimizationBasis.COST_EFFICIENCY == "cost_efficiency"

    def test_basis_customer_impact(self):
        assert OptimizationBasis.CUSTOMER_IMPACT == "customer_impact"

    def test_basis_engineering_effort(self):
        assert OptimizationBasis.ENGINEERING_EFFORT == "engineering_effort"

    def test_basis_competitive_benchmark(self):
        assert OptimizationBasis.COMPETITIVE_BENCHMARK == "competitive_benchmark"

    def test_confidence_very_high(self):
        assert ThresholdConfidence.VERY_HIGH == "very_high"

    def test_confidence_high(self):
        assert ThresholdConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert ThresholdConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert ThresholdConfidence.LOW == "low"

    def test_confidence_insufficient_data(self):
        assert ThresholdConfidence.INSUFFICIENT_DATA == "insufficient_data"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_threshold_record_defaults(self):
        r = ThresholdRecord()
        assert r.id
        assert r.slo_name == ""
        assert r.threshold_direction == ThresholdDirection.TIGHTEN
        assert r.optimization_basis == OptimizationBasis.HISTORICAL_P99
        assert r.threshold_confidence == ThresholdConfidence.VERY_HIGH
        assert r.adjustment_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_threshold_analysis_defaults(self):
        a = ThresholdAnalysis()
        assert a.id
        assert a.slo_name == ""
        assert a.threshold_direction == ThresholdDirection.TIGHTEN
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_slo_threshold_report_defaults(self):
        r = SloThresholdReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_confidence_count == 0
        assert r.avg_adjustment_score == 0.0
        assert r.by_direction == {}
        assert r.by_basis == {}
        assert r.by_confidence == {}
        assert r.top_adjustments == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_threshold
# ---------------------------------------------------------------------------


class TestRecordThreshold:
    def test_basic(self):
        eng = _engine()
        r = eng.record_threshold(
            slo_name="api-latency-p99",
            threshold_direction=ThresholdDirection.RELAX,
            optimization_basis=OptimizationBasis.COST_EFFICIENCY,
            threshold_confidence=ThresholdConfidence.HIGH,
            adjustment_score=15.0,
            service="api-gw",
            team="sre",
        )
        assert r.slo_name == "api-latency-p99"
        assert r.threshold_direction == ThresholdDirection.RELAX
        assert r.optimization_basis == OptimizationBasis.COST_EFFICIENCY
        assert r.threshold_confidence == ThresholdConfidence.HIGH
        assert r.adjustment_score == 15.0
        assert r.service == "api-gw"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_threshold(slo_name=f"SLO-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_threshold
# ---------------------------------------------------------------------------


class TestGetThreshold:
    def test_found(self):
        eng = _engine()
        r = eng.record_threshold(
            slo_name="api-latency-p99",
            threshold_confidence=ThresholdConfidence.LOW,
        )
        result = eng.get_threshold(r.id)
        assert result is not None
        assert result.threshold_confidence == ThresholdConfidence.LOW

    def test_not_found(self):
        eng = _engine()
        assert eng.get_threshold("nonexistent") is None


# ---------------------------------------------------------------------------
# list_thresholds
# ---------------------------------------------------------------------------


class TestListThresholds:
    def test_list_all(self):
        eng = _engine()
        eng.record_threshold(slo_name="SLO-001")
        eng.record_threshold(slo_name="SLO-002")
        assert len(eng.list_thresholds()) == 2

    def test_filter_by_direction(self):
        eng = _engine()
        eng.record_threshold(
            slo_name="SLO-001",
            threshold_direction=ThresholdDirection.TIGHTEN,
        )
        eng.record_threshold(
            slo_name="SLO-002",
            threshold_direction=ThresholdDirection.RELAX,
        )
        results = eng.list_thresholds(threshold_direction=ThresholdDirection.TIGHTEN)
        assert len(results) == 1

    def test_filter_by_basis(self):
        eng = _engine()
        eng.record_threshold(
            slo_name="SLO-001",
            optimization_basis=OptimizationBasis.HISTORICAL_P99,
        )
        eng.record_threshold(
            slo_name="SLO-002",
            optimization_basis=OptimizationBasis.COST_EFFICIENCY,
        )
        results = eng.list_thresholds(
            optimization_basis=OptimizationBasis.HISTORICAL_P99,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_threshold(slo_name="SLO-001", team="sre")
        eng.record_threshold(slo_name="SLO-002", team="platform")
        results = eng.list_thresholds(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_threshold(slo_name=f"SLO-{i}")
        assert len(eng.list_thresholds(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            slo_name="api-latency-p99",
            threshold_direction=ThresholdDirection.RELAX,
            analysis_score=72.5,
            threshold=60.0,
            breached=True,
            description="SLO too tight for cost",
        )
        assert a.slo_name == "api-latency-p99"
        assert a.threshold_direction == ThresholdDirection.RELAX
        assert a.analysis_score == 72.5
        assert a.threshold == 60.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(slo_name=f"SLO-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_threshold_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeThresholdDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_threshold(
            slo_name="SLO-001",
            threshold_direction=ThresholdDirection.TIGHTEN,
            adjustment_score=10.0,
        )
        eng.record_threshold(
            slo_name="SLO-002",
            threshold_direction=ThresholdDirection.TIGHTEN,
            adjustment_score=20.0,
        )
        result = eng.analyze_threshold_distribution()
        assert "tighten" in result
        assert result["tighten"]["count"] == 2
        assert result["tighten"]["avg_adjustment_score"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_threshold_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_confidence_thresholds
# ---------------------------------------------------------------------------


class TestIdentifyLowConfidenceThresholds:
    def test_detects_below_sensitivity(self):
        eng = _engine(adjustment_sensitivity=5.0)
        eng.record_threshold(slo_name="SLO-001", adjustment_score=3.0)
        eng.record_threshold(slo_name="SLO-002", adjustment_score=10.0)
        results = eng.identify_low_confidence_thresholds()
        assert len(results) == 1
        assert results[0]["slo_name"] == "SLO-001"

    def test_sorted_ascending(self):
        eng = _engine(adjustment_sensitivity=10.0)
        eng.record_threshold(slo_name="SLO-001", adjustment_score=5.0)
        eng.record_threshold(slo_name="SLO-002", adjustment_score=2.0)
        results = eng.identify_low_confidence_thresholds()
        assert len(results) == 2
        assert results[0]["adjustment_score"] == 2.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_confidence_thresholds() == []


# ---------------------------------------------------------------------------
# rank_by_adjustment
# ---------------------------------------------------------------------------


class TestRankByAdjustment:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_threshold(slo_name="SLO-001", service="api-gw", adjustment_score=20.0)
        eng.record_threshold(slo_name="SLO-002", service="auth", adjustment_score=5.0)
        results = eng.rank_by_adjustment()
        assert len(results) == 2
        assert results[0]["service"] == "auth"
        assert results[0]["avg_adjustment_score"] == 5.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_adjustment() == []


# ---------------------------------------------------------------------------
# detect_threshold_trends
# ---------------------------------------------------------------------------


class TestDetectThresholdTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(slo_name="SLO-001", analysis_score=50.0)
        result = eng.detect_threshold_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(slo_name="SLO-001", analysis_score=20.0)
        eng.add_analysis(slo_name="SLO-002", analysis_score=20.0)
        eng.add_analysis(slo_name="SLO-003", analysis_score=80.0)
        eng.add_analysis(slo_name="SLO-004", analysis_score=80.0)
        result = eng.detect_threshold_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_threshold_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(adjustment_sensitivity=5.0)
        eng.record_threshold(
            slo_name="api-latency-p99",
            threshold_direction=ThresholdDirection.TIGHTEN,
            optimization_basis=OptimizationBasis.HISTORICAL_P99,
            threshold_confidence=ThresholdConfidence.LOW,
            adjustment_score=2.0,
        )
        report = eng.generate_report()
        assert isinstance(report, SloThresholdReport)
        assert report.total_records == 1
        assert report.low_confidence_count == 1
        assert len(report.top_adjustments) == 1
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
        eng.record_threshold(slo_name="SLO-001")
        eng.add_analysis(slo_name="SLO-001")
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
        assert stats["direction_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_threshold(
            slo_name="SLO-001",
            threshold_direction=ThresholdDirection.TIGHTEN,
            service="api-gw",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "tighten" in stats["direction_distribution"]
