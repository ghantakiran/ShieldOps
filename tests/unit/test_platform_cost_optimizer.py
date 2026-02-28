"""Tests for shieldops.billing.platform_cost_optimizer — PlatformCostOptimizer."""

from __future__ import annotations

from shieldops.billing.platform_cost_optimizer import (
    CostDomain,
    OptimizationAction,
    OptimizationRecord,
    OptimizationRule,
    OptimizationStatus,
    PlatformCostOptimizer,
    PlatformCostReport,
)


def _engine(**kw) -> PlatformCostOptimizer:
    return PlatformCostOptimizer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # CostDomain (5)
    def test_domain_compute(self):
        assert CostDomain.COMPUTE == "compute"

    def test_domain_storage(self):
        assert CostDomain.STORAGE == "storage"

    def test_domain_network(self):
        assert CostDomain.NETWORK == "network"

    def test_domain_observability(self):
        assert CostDomain.OBSERVABILITY == "observability"

    def test_domain_licensing(self):
        assert CostDomain.LICENSING == "licensing"

    # OptimizationAction (5)
    def test_action_rightsize(self):
        assert OptimizationAction.RIGHTSIZE == "rightsize"

    def test_action_consolidate(self):
        assert OptimizationAction.CONSOLIDATE == "consolidate"

    def test_action_eliminate(self):
        assert OptimizationAction.ELIMINATE == "eliminate"

    def test_action_negotiate(self):
        assert OptimizationAction.NEGOTIATE == "negotiate"

    def test_action_migrate(self):
        assert OptimizationAction.MIGRATE == "migrate"

    # OptimizationStatus (5)
    def test_status_identified(self):
        assert OptimizationStatus.IDENTIFIED == "identified"

    def test_status_in_progress(self):
        assert OptimizationStatus.IN_PROGRESS == "in_progress"

    def test_status_implemented(self):
        assert OptimizationStatus.IMPLEMENTED == "implemented"

    def test_status_rejected(self):
        assert OptimizationStatus.REJECTED == "rejected"

    def test_status_deferred(self):
        assert OptimizationStatus.DEFERRED == "deferred"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_optimization_record_defaults(self):
        r = OptimizationRecord()
        assert r.id
        assert r.domain_name == ""
        assert r.cost_domain == CostDomain.COMPUTE
        assert r.action == OptimizationAction.RIGHTSIZE
        assert r.status == OptimizationStatus.IDENTIFIED
        assert r.savings_amount == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_optimization_rule_defaults(self):
        r = OptimizationRule()
        assert r.id
        assert r.rule_name == ""
        assert r.cost_domain == CostDomain.COMPUTE
        assert r.action == OptimizationAction.RIGHTSIZE
        assert r.min_savings_threshold == 100.0
        assert r.auto_implement is False
        assert r.created_at > 0

    def test_platform_cost_report_defaults(self):
        r = PlatformCostReport()
        assert r.total_optimizations == 0
        assert r.total_rules == 0
        assert r.implementation_rate_pct == 0.0
        assert r.by_domain == {}
        assert r.by_status == {}
        assert r.total_savings == 0.0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_optimization
# -------------------------------------------------------------------


class TestRecordOptimization:
    def test_basic(self):
        eng = _engine()
        r = eng.record_optimization(
            "compute-pool",
            cost_domain=CostDomain.COMPUTE,
            action=OptimizationAction.RIGHTSIZE,
        )
        assert r.domain_name == "compute-pool"
        assert r.cost_domain == CostDomain.COMPUTE

    def test_with_status(self):
        eng = _engine()
        r = eng.record_optimization(
            "storage-tier",
            status=OptimizationStatus.IMPLEMENTED,
        )
        assert r.status == OptimizationStatus.IMPLEMENTED

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_optimization(f"dom-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_optimization
# -------------------------------------------------------------------


class TestGetOptimization:
    def test_found(self):
        eng = _engine()
        r = eng.record_optimization("dom-a")
        assert eng.get_optimization(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_optimization("nonexistent") is None


# -------------------------------------------------------------------
# list_optimizations
# -------------------------------------------------------------------


class TestListOptimizations:
    def test_list_all(self):
        eng = _engine()
        eng.record_optimization("dom-a")
        eng.record_optimization("dom-b")
        assert len(eng.list_optimizations()) == 2

    def test_filter_by_domain_name(self):
        eng = _engine()
        eng.record_optimization("dom-a")
        eng.record_optimization("dom-b")
        results = eng.list_optimizations(
            domain_name="dom-a",
        )
        assert len(results) == 1

    def test_filter_by_cost_domain(self):
        eng = _engine()
        eng.record_optimization(
            "dom-a",
            cost_domain=CostDomain.STORAGE,
        )
        eng.record_optimization(
            "dom-b",
            cost_domain=CostDomain.NETWORK,
        )
        results = eng.list_optimizations(
            cost_domain=CostDomain.STORAGE,
        )
        assert len(results) == 1


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        p = eng.add_rule(
            "rightsize-compute",
            cost_domain=CostDomain.COMPUTE,
            action=OptimizationAction.RIGHTSIZE,
            min_savings_threshold=500.0,
            auto_implement=True,
        )
        assert p.rule_name == "rightsize-compute"
        assert p.min_savings_threshold == 500.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rule(f"rule-{i}")
        assert len(eng._rules) == 2


# -------------------------------------------------------------------
# analyze_cost_efficiency
# -------------------------------------------------------------------


class TestAnalyzeCostEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_optimization(
            "dom-a",
            status=OptimizationStatus.IMPLEMENTED,
            savings_amount=200.0,
        )
        eng.record_optimization(
            "dom-a",
            status=OptimizationStatus.IDENTIFIED,
            savings_amount=100.0,
        )
        result = eng.analyze_cost_efficiency("dom-a")
        assert result["domain_name"] == "dom-a"
        assert result["optimization_count"] == 2
        assert result["implementation_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_cost_efficiency("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_rejected_optimizations
# -------------------------------------------------------------------


class TestIdentifyRejectedOptimizations:
    def test_with_rejections(self):
        eng = _engine()
        eng.record_optimization(
            "dom-a",
            status=OptimizationStatus.REJECTED,
        )
        eng.record_optimization(
            "dom-a",
            status=OptimizationStatus.REJECTED,
        )
        eng.record_optimization(
            "dom-b",
            status=OptimizationStatus.IMPLEMENTED,
        )
        results = eng.identify_rejected_optimizations()
        assert len(results) == 1
        assert results[0]["domain_name"] == "dom-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_rejected_optimizations() == []


# -------------------------------------------------------------------
# rank_by_savings
# -------------------------------------------------------------------


class TestRankBySavings:
    def test_with_data(self):
        eng = _engine()
        eng.record_optimization(
            "dom-a",
            savings_amount=500.0,
        )
        eng.record_optimization(
            "dom-a",
            savings_amount=300.0,
        )
        eng.record_optimization(
            "dom-b",
            savings_amount=100.0,
        )
        results = eng.rank_by_savings()
        assert results[0]["domain_name"] == "dom-a"
        assert results[0]["avg_savings"] == 400.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_savings() == []


# -------------------------------------------------------------------
# detect_cost_anomalies
# -------------------------------------------------------------------


class TestDetectCostAnomalies:
    def test_with_anomalies(self):
        eng = _engine()
        for _ in range(5):
            eng.record_optimization(
                "dom-a",
                status=OptimizationStatus.IDENTIFIED,
            )
        eng.record_optimization(
            "dom-b",
            status=OptimizationStatus.IMPLEMENTED,
        )
        results = eng.detect_cost_anomalies()
        assert len(results) == 1
        assert results[0]["domain_name"] == "dom-a"
        assert results[0]["anomaly_detected"] is True

    def test_no_anomalies(self):
        eng = _engine()
        eng.record_optimization(
            "dom-a",
            status=OptimizationStatus.IDENTIFIED,
        )
        assert eng.detect_cost_anomalies() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_optimization(
            "dom-a",
            status=OptimizationStatus.IMPLEMENTED,
        )
        eng.record_optimization(
            "dom-b",
            status=OptimizationStatus.REJECTED,
        )
        eng.record_optimization(
            "dom-b",
            status=OptimizationStatus.REJECTED,
        )
        eng.add_rule("rule-1")
        report = eng.generate_report()
        assert report.total_optimizations == 3
        assert report.total_rules == 1
        assert report.by_domain != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_optimizations == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_optimization("dom-a")
        eng.add_rule("rule-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_optimizations"] == 0
        assert stats["total_rules"] == 0
        assert stats["domain_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_optimization(
            "dom-a",
            cost_domain=CostDomain.COMPUTE,
        )
        eng.record_optimization(
            "dom-b",
            cost_domain=CostDomain.STORAGE,
        )
        eng.add_rule("r1")
        stats = eng.get_stats()
        assert stats["total_optimizations"] == 2
        assert stats["total_rules"] == 1
        assert stats["unique_domains"] == 2
