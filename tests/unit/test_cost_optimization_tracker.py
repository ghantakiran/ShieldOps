"""Tests for shieldops.billing.cost_optimization_tracker — CostOptimizationTracker."""

from __future__ import annotations

from shieldops.billing.cost_optimization_tracker import (
    CostOptimizationReport,
    CostOptimizationTracker,
    OptimizationMetric,
    OptimizationRecord,
    OptimizationStatus,
    OptimizationType,
    SavingsCategory,
)


def _engine(**kw) -> CostOptimizationTracker:
    return CostOptimizationTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_right_sizing(self):
        assert OptimizationType.RIGHT_SIZING == "right_sizing"

    def test_type_reserved_instances(self):
        assert OptimizationType.RESERVED_INSTANCES == "reserved_instances"

    def test_type_spot_usage(self):
        assert OptimizationType.SPOT_USAGE == "spot_usage"

    def test_type_storage_tiering(self):
        assert OptimizationType.STORAGE_TIERING == "storage_tiering"

    def test_type_license_consolidation(self):
        assert OptimizationType.LICENSE_CONSOLIDATION == "license_consolidation"

    def test_status_identified(self):
        assert OptimizationStatus.IDENTIFIED == "identified"

    def test_status_in_progress(self):
        assert OptimizationStatus.IN_PROGRESS == "in_progress"

    def test_status_implemented(self):
        assert OptimizationStatus.IMPLEMENTED == "implemented"

    def test_status_validated(self):
        assert OptimizationStatus.VALIDATED == "validated"

    def test_status_expired(self):
        assert OptimizationStatus.EXPIRED == "expired"

    def test_category_compute(self):
        assert SavingsCategory.COMPUTE == "compute"

    def test_category_storage(self):
        assert SavingsCategory.STORAGE == "storage"

    def test_category_network(self):
        assert SavingsCategory.NETWORK == "network"

    def test_category_database(self):
        assert SavingsCategory.DATABASE == "database"

    def test_category_licensing(self):
        assert SavingsCategory.LICENSING == "licensing"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_optimization_record_defaults(self):
        r = OptimizationRecord()
        assert r.id
        assert r.optimization_id == ""
        assert r.optimization_type == OptimizationType.RIGHT_SIZING
        assert r.optimization_status == OptimizationStatus.IDENTIFIED
        assert r.savings_category == SavingsCategory.COMPUTE
        assert r.savings_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_optimization_metric_defaults(self):
        m = OptimizationMetric()
        assert m.id
        assert m.optimization_id == ""
        assert m.optimization_type == OptimizationType.RIGHT_SIZING
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_cost_optimization_report_defaults(self):
        r = CostOptimizationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.pending_count == 0
        assert r.avg_savings_pct == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_category == {}
        assert r.top_opportunities == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_optimization
# ---------------------------------------------------------------------------


class TestRecordOptimization:
    def test_basic(self):
        eng = _engine()
        r = eng.record_optimization(
            optimization_id="OPT-001",
            optimization_type=OptimizationType.RIGHT_SIZING,
            optimization_status=OptimizationStatus.IDENTIFIED,
            savings_category=SavingsCategory.COMPUTE,
            savings_pct=25.0,
            service="api-gateway",
            team="sre",
        )
        assert r.optimization_id == "OPT-001"
        assert r.optimization_type == OptimizationType.RIGHT_SIZING
        assert r.optimization_status == OptimizationStatus.IDENTIFIED
        assert r.savings_category == SavingsCategory.COMPUTE
        assert r.savings_pct == 25.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_optimization(optimization_id=f"OPT-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_optimization
# ---------------------------------------------------------------------------


class TestGetOptimization:
    def test_found(self):
        eng = _engine()
        r = eng.record_optimization(
            optimization_id="OPT-001",
            optimization_type=OptimizationType.RESERVED_INSTANCES,
        )
        result = eng.get_optimization(r.id)
        assert result is not None
        assert result.optimization_type == OptimizationType.RESERVED_INSTANCES

    def test_not_found(self):
        eng = _engine()
        assert eng.get_optimization("nonexistent") is None


# ---------------------------------------------------------------------------
# list_optimizations
# ---------------------------------------------------------------------------


class TestListOptimizations:
    def test_list_all(self):
        eng = _engine()
        eng.record_optimization(optimization_id="OPT-001")
        eng.record_optimization(optimization_id="OPT-002")
        assert len(eng.list_optimizations()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_optimization(
            optimization_id="OPT-001",
            optimization_type=OptimizationType.RIGHT_SIZING,
        )
        eng.record_optimization(
            optimization_id="OPT-002",
            optimization_type=OptimizationType.SPOT_USAGE,
        )
        results = eng.list_optimizations(
            optimization_type=OptimizationType.RIGHT_SIZING,
        )
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_optimization(
            optimization_id="OPT-001",
            optimization_status=OptimizationStatus.IDENTIFIED,
        )
        eng.record_optimization(
            optimization_id="OPT-002",
            optimization_status=OptimizationStatus.IMPLEMENTED,
        )
        results = eng.list_optimizations(
            optimization_status=OptimizationStatus.IDENTIFIED,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_optimization(
            optimization_id="OPT-001",
            service="api-gateway",
        )
        eng.record_optimization(
            optimization_id="OPT-002",
            service="auth",
        )
        results = eng.list_optimizations(service="api-gateway")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_optimization(optimization_id=f"OPT-{i}")
        assert len(eng.list_optimizations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            optimization_id="OPT-001",
            optimization_type=OptimizationType.RIGHT_SIZING,
            metric_score=65.0,
            threshold=50.0,
            breached=True,
            description="Savings above threshold",
        )
        assert m.optimization_id == "OPT-001"
        assert m.optimization_type == OptimizationType.RIGHT_SIZING
        assert m.metric_score == 65.0
        assert m.threshold == 50.0
        assert m.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(optimization_id=f"OPT-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_optimization_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeOptimizationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_optimization(
            optimization_id="OPT-001",
            optimization_type=OptimizationType.RIGHT_SIZING,
            savings_pct=20.0,
        )
        eng.record_optimization(
            optimization_id="OPT-002",
            optimization_type=OptimizationType.RIGHT_SIZING,
            savings_pct=30.0,
        )
        result = eng.analyze_optimization_distribution()
        assert "right_sizing" in result
        assert result["right_sizing"]["count"] == 2
        assert result["right_sizing"]["avg_savings_pct"] == 25.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_optimization_distribution() == {}


# ---------------------------------------------------------------------------
# identify_pending_optimizations
# ---------------------------------------------------------------------------


class TestIdentifyPendingOptimizations:
    def test_detects_identified(self):
        eng = _engine()
        eng.record_optimization(
            optimization_id="OPT-001",
            optimization_status=OptimizationStatus.IDENTIFIED,
        )
        eng.record_optimization(
            optimization_id="OPT-002",
            optimization_status=OptimizationStatus.IMPLEMENTED,
        )
        results = eng.identify_pending_optimizations()
        assert len(results) == 1
        assert results[0]["optimization_id"] == "OPT-001"

    def test_detects_in_progress(self):
        eng = _engine()
        eng.record_optimization(
            optimization_id="OPT-001",
            optimization_status=OptimizationStatus.IN_PROGRESS,
        )
        results = eng.identify_pending_optimizations()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_pending_optimizations() == []


# ---------------------------------------------------------------------------
# rank_by_savings
# ---------------------------------------------------------------------------


class TestRankBySavings:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_optimization(
            optimization_id="OPT-001",
            service="api-gateway",
            savings_pct=40.0,
        )
        eng.record_optimization(
            optimization_id="OPT-002",
            service="auth",
            savings_pct=15.0,
        )
        results = eng.rank_by_savings()
        assert len(results) == 2
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_savings_pct"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_savings() == []


# ---------------------------------------------------------------------------
# detect_optimization_trends
# ---------------------------------------------------------------------------


class TestDetectOptimizationTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_metric(optimization_id="OPT-001", metric_score=50.0)
        result = eng.detect_optimization_trends()
        assert result["trend"] == "stable"

    def test_growing(self):
        eng = _engine()
        eng.add_metric(optimization_id="OPT-001", metric_score=10.0)
        eng.add_metric(optimization_id="OPT-002", metric_score=10.0)
        eng.add_metric(optimization_id="OPT-003", metric_score=80.0)
        eng.add_metric(optimization_id="OPT-004", metric_score=80.0)
        result = eng.detect_optimization_trends()
        assert result["trend"] == "growing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_optimization_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_optimization(
            optimization_id="OPT-001",
            optimization_type=OptimizationType.RIGHT_SIZING,
            optimization_status=OptimizationStatus.IDENTIFIED,
            savings_pct=5.0,
        )
        report = eng.generate_report()
        assert isinstance(report, CostOptimizationReport)
        assert report.total_records == 1
        assert report.pending_count == 1
        assert len(report.top_opportunities) == 1
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
        eng.record_optimization(optimization_id="OPT-001")
        eng.add_metric(optimization_id="OPT-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["optimization_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_optimization(
            optimization_id="OPT-001",
            optimization_type=OptimizationType.RIGHT_SIZING,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "right_sizing" in stats["optimization_type_distribution"]
