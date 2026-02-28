"""Tests for shieldops.billing.optimization_planner — CostOptimizationPlanner."""

from __future__ import annotations

from shieldops.billing.optimization_planner import (
    CostOptimizationPlanner,
    ImplementationEffort,
    OptimizationAction,
    OptimizationPlannerReport,
    OptimizationPriority,
    OptimizationRecord,
    OptimizationType,
)


def _engine(**kw) -> CostOptimizationPlanner:
    return CostOptimizationPlanner(**kw)


class TestEnums:
    def test_type_right_sizing(self):
        assert OptimizationType.RIGHT_SIZING == "right_sizing"

    def test_type_reserved_instance(self):
        assert OptimizationType.RESERVED_INSTANCE == "reserved_instance"

    def test_type_spot_instance(self):
        assert OptimizationType.SPOT_INSTANCE == "spot_instance"

    def test_type_storage_tiering(self):
        assert OptimizationType.STORAGE_TIERING == "storage_tiering"

    def test_type_license_optimization(self):
        assert OptimizationType.LICENSE_OPTIMIZATION == "license_optimization"

    def test_priority_critical(self):
        assert OptimizationPriority.CRITICAL == "critical"

    def test_priority_high(self):
        assert OptimizationPriority.HIGH == "high"

    def test_priority_medium(self):
        assert OptimizationPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert OptimizationPriority.LOW == "low"

    def test_priority_optional(self):
        assert OptimizationPriority.OPTIONAL == "optional"

    def test_effort_trivial(self):
        assert ImplementationEffort.TRIVIAL == "trivial"

    def test_effort_low(self):
        assert ImplementationEffort.LOW == "low"

    def test_effort_moderate(self):
        assert ImplementationEffort.MODERATE == "moderate"

    def test_effort_high(self):
        assert ImplementationEffort.HIGH == "high"

    def test_effort_complex(self):
        assert ImplementationEffort.COMPLEX == "complex"


class TestModels:
    def test_optimization_record_defaults(self):
        r = OptimizationRecord()
        assert r.id
        assert r.resource_id == ""
        assert r.optimization_type == OptimizationType.RIGHT_SIZING
        assert r.priority == OptimizationPriority.MEDIUM
        assert r.effort == ImplementationEffort.MODERATE
        assert r.savings_pct == 0.0
        assert r.estimated_savings_usd == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_optimization_action_defaults(self):
        a = OptimizationAction()
        assert a.id
        assert a.resource_id == ""
        assert a.optimization_type == OptimizationType.RIGHT_SIZING
        assert a.action_description == ""
        assert a.effort == ImplementationEffort.LOW
        assert a.estimated_savings_usd == 0.0
        assert a.notes == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = OptimizationPlannerReport()
        assert r.total_optimizations == 0
        assert r.total_actions == 0
        assert r.avg_savings_pct == 0.0
        assert r.total_estimated_savings_usd == 0.0
        assert r.by_optimization_type == {}
        assert r.by_priority == {}
        assert r.quick_wins_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordOptimization:
    def test_basic(self):
        eng = _engine()
        r = eng.record_optimization(
            resource_id="ec2-001", savings_pct=25.0, estimated_savings_usd=500.0
        )
        assert r.resource_id == "ec2-001"
        assert r.savings_pct == 25.0
        assert r.estimated_savings_usd == 500.0

    def test_with_type(self):
        eng = _engine()
        r = eng.record_optimization(optimization_type=OptimizationType.SPOT_INSTANCE)
        assert r.optimization_type == OptimizationType.SPOT_INSTANCE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_optimization(resource_id=f"res-{i}")
        assert len(eng._records) == 3


class TestGetOptimization:
    def test_found(self):
        eng = _engine()
        r = eng.record_optimization(resource_id="ec2-001")
        assert eng.get_optimization(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_optimization("nonexistent") is None


class TestListOptimizations:
    def test_list_all(self):
        eng = _engine()
        eng.record_optimization(resource_id="res-a")
        eng.record_optimization(resource_id="res-b")
        assert len(eng.list_optimizations()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_optimization(optimization_type=OptimizationType.RIGHT_SIZING)
        eng.record_optimization(optimization_type=OptimizationType.SPOT_INSTANCE)
        results = eng.list_optimizations(optimization_type=OptimizationType.RIGHT_SIZING)
        assert len(results) == 1

    def test_filter_by_priority(self):
        eng = _engine()
        eng.record_optimization(priority=OptimizationPriority.CRITICAL)
        eng.record_optimization(priority=OptimizationPriority.LOW)
        results = eng.list_optimizations(priority=OptimizationPriority.CRITICAL)
        assert len(results) == 1


class TestAddAction:
    def test_basic(self):
        eng = _engine()
        a = eng.add_action(
            resource_id="ec2-001",
            optimization_type=OptimizationType.RIGHT_SIZING,
            action_description="Downsize from m5.xlarge to m5.large",
            estimated_savings_usd=200.0,
        )
        assert a.resource_id == "ec2-001"
        assert a.action_description == "Downsize from m5.xlarge to m5.large"
        assert a.estimated_savings_usd == 200.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_action(resource_id=f"res-{i}")
        assert len(eng._actions) == 2


class TestAnalyzeOptimizationByType:
    def test_with_data(self):
        eng = _engine()
        eng.record_optimization(
            optimization_type=OptimizationType.RESERVED_INSTANCE,
            savings_pct=30.0,
            estimated_savings_usd=1000.0,
        )
        eng.record_optimization(
            optimization_type=OptimizationType.RESERVED_INSTANCE,
            savings_pct=20.0,
            estimated_savings_usd=500.0,
        )
        result = eng.analyze_optimization_by_type(OptimizationType.RESERVED_INSTANCE)
        assert result["optimization_type"] == "reserved_instance"
        assert result["total"] == 2
        assert result["avg_savings_pct"] == 25.0
        assert result["total_estimated_savings_usd"] == 1500.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_optimization_by_type(OptimizationType.SPOT_INSTANCE)
        assert result["status"] == "no_data"


class TestIdentifyQuickWins:
    def test_with_quick_wins(self):
        eng = _engine()
        eng.record_optimization(effort=ImplementationEffort.TRIVIAL, savings_pct=20.0)
        eng.record_optimization(effort=ImplementationEffort.COMPLEX, savings_pct=50.0)
        results = eng.identify_quick_wins()
        assert len(results) == 1
        assert results[0]["effort"] == "trivial"

    def test_below_threshold(self):
        eng = _engine(min_savings_pct=15.0)
        eng.record_optimization(effort=ImplementationEffort.LOW, savings_pct=5.0)
        assert eng.identify_quick_wins() == []

    def test_empty(self):
        eng = _engine()
        assert eng.identify_quick_wins() == []


class TestRankBySavingsPotential:
    def test_with_data(self):
        eng = _engine()
        eng.record_optimization(resource_id="res-a", estimated_savings_usd=100.0)
        eng.record_optimization(resource_id="res-b", estimated_savings_usd=500.0)
        results = eng.rank_by_savings_potential()
        assert results[0]["resource_id"] == "res-b"
        assert results[0]["estimated_savings_usd"] == 500.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_savings_potential() == []


class TestDetectOptimizationTrends:
    def test_improving(self):
        eng = _engine()
        for i in range(5):
            eng.record_optimization(resource_id="res-001", savings_pct=float(5 + i * 5))
        results = eng.detect_optimization_trends()
        assert len(results) == 1
        assert results[0]["resource_id"] == "res-001"
        assert results[0]["savings_trend"] == "improving"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_optimization_trends() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_optimization(
            effort=ImplementationEffort.TRIVIAL,
            savings_pct=20.0,
            estimated_savings_usd=300.0,
        )
        eng.record_optimization(
            effort=ImplementationEffort.COMPLEX,
            savings_pct=5.0,
            estimated_savings_usd=50.0,
        )
        eng.add_action(resource_id="res-001")
        report = eng.generate_report()
        assert report.total_optimizations == 2
        assert report.total_actions == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_optimizations == 0
        assert "expected" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_optimization(resource_id="res-001")
        eng.add_action(resource_id="res-001")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._actions) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_optimizations"] == 0
        assert stats["total_actions"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_optimization(
            resource_id="res-a", optimization_type=OptimizationType.RIGHT_SIZING
        )
        eng.record_optimization(
            resource_id="res-b", optimization_type=OptimizationType.SPOT_INSTANCE
        )
        eng.add_action(resource_id="res-a")
        stats = eng.get_stats()
        assert stats["total_optimizations"] == 2
        assert stats["total_actions"] == 1
        assert stats["unique_resources"] == 2
