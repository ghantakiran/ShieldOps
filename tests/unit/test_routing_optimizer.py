"""Tests for shieldops.agents.routing_optimizer — AgentRoutingOptimizer."""

from __future__ import annotations

from shieldops.agents.routing_optimizer import (
    AgentRoutingOptimizer,
    ModelTier,
    RoutingCriteria,
    RoutingDecision,
    RoutingOptimizerReport,
    RoutingOutcome,
    RoutingRecord,
)


def _engine(**kw) -> AgentRoutingOptimizer:
    return AgentRoutingOptimizer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ModelTier (5)
    def test_tier_flagship(self):
        assert ModelTier.FLAGSHIP == "flagship"

    def test_tier_standard(self):
        assert ModelTier.STANDARD == "standard"

    def test_tier_fast(self):
        assert ModelTier.FAST == "fast"

    def test_tier_mini(self):
        assert ModelTier.MINI == "mini"

    def test_tier_cached(self):
        assert ModelTier.CACHED == "cached"

    # RoutingCriteria (5)
    def test_criteria_complexity(self):
        assert RoutingCriteria.COMPLEXITY == "complexity"

    def test_criteria_urgency(self):
        assert RoutingCriteria.URGENCY == "urgency"

    def test_criteria_cost_budget(self):
        assert RoutingCriteria.COST_BUDGET == "cost_budget"

    def test_criteria_accuracy_needed(self):
        assert RoutingCriteria.ACCURACY_NEEDED == "accuracy_needed"

    def test_criteria_latency(self):
        assert RoutingCriteria.LATENCY == "latency"

    # RoutingOutcome (5)
    def test_outcome_optimal(self):
        assert RoutingOutcome.OPTIMAL == "optimal"

    def test_outcome_acceptable(self):
        assert RoutingOutcome.ACCEPTABLE == "acceptable"

    def test_outcome_over_provisioned(self):
        assert RoutingOutcome.OVER_PROVISIONED == "over_provisioned"

    def test_outcome_under_provisioned(self):
        assert RoutingOutcome.UNDER_PROVISIONED == "under_provisioned"

    def test_outcome_fallback(self):
        assert RoutingOutcome.FALLBACK == "fallback"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_routing_record_defaults(self):
        r = RoutingRecord()
        assert r.id
        assert r.task_name == ""
        assert r.model_tier == ModelTier.STANDARD
        assert r.routing_criteria == RoutingCriteria.COMPLEXITY
        assert r.routing_outcome == RoutingOutcome.OPTIMAL
        assert r.cost_dollars == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_routing_decision_defaults(self):
        r = RoutingDecision()
        assert r.id
        assert r.decision_label == ""
        assert r.model_tier == ModelTier.STANDARD
        assert r.routing_outcome == RoutingOutcome.OPTIMAL
        assert r.latency_ms == 0.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = RoutingOptimizerReport()
        assert r.total_routings == 0
        assert r.total_decisions == 0
        assert r.optimal_rate_pct == 0.0
        assert r.by_tier == {}
        assert r.by_outcome == {}
        assert r.fallback_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_routing
# -------------------------------------------------------------------


class TestRecordRouting:
    def test_basic(self):
        eng = _engine()
        r = eng.record_routing(
            "task-a",
            model_tier=ModelTier.FLAGSHIP,
            routing_criteria=RoutingCriteria.URGENCY,
        )
        assert r.task_name == "task-a"
        assert r.model_tier == ModelTier.FLAGSHIP

    def test_with_cost(self):
        eng = _engine()
        r = eng.record_routing(
            "task-b",
            routing_outcome=RoutingOutcome.FALLBACK,
            cost_dollars=5.50,
        )
        assert r.routing_outcome == RoutingOutcome.FALLBACK
        assert r.cost_dollars == 5.50

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_routing(f"task-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_routing
# -------------------------------------------------------------------


class TestGetRouting:
    def test_found(self):
        eng = _engine()
        r = eng.record_routing("task-a")
        assert eng.get_routing(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_routing("nonexistent") is None


# -------------------------------------------------------------------
# list_routings
# -------------------------------------------------------------------


class TestListRoutings:
    def test_list_all(self):
        eng = _engine()
        eng.record_routing("task-a")
        eng.record_routing("task-b")
        assert len(eng.list_routings()) == 2

    def test_filter_by_task(self):
        eng = _engine()
        eng.record_routing("task-a")
        eng.record_routing("task-b")
        results = eng.list_routings(task_name="task-a")
        assert len(results) == 1

    def test_filter_by_tier(self):
        eng = _engine()
        eng.record_routing("task-a", model_tier=ModelTier.MINI)
        eng.record_routing("task-b", model_tier=ModelTier.STANDARD)
        results = eng.list_routings(model_tier=ModelTier.MINI)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_decision
# -------------------------------------------------------------------


class TestAddDecision:
    def test_basic(self):
        eng = _engine()
        d = eng.add_decision(
            "decision-1",
            model_tier=ModelTier.FAST,
            routing_outcome=RoutingOutcome.ACCEPTABLE,
            latency_ms=12.5,
        )
        assert d.decision_label == "decision-1"
        assert d.latency_ms == 12.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_decision(f"decision-{i}")
        assert len(eng._decisions) == 2


# -------------------------------------------------------------------
# analyze_routing_efficiency
# -------------------------------------------------------------------


class TestAnalyzeRoutingEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_routing("task-a", routing_outcome=RoutingOutcome.OPTIMAL, cost_dollars=2.0)
        eng.record_routing("task-a", routing_outcome=RoutingOutcome.FALLBACK, cost_dollars=8.0)
        result = eng.analyze_routing_efficiency("task-a")
        assert result["task_name"] == "task-a"
        assert result["total_routings"] == 2
        assert result["optimal_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_routing_efficiency("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(cost_limit=10.0)
        eng.record_routing("task-a", cost_dollars=5.0)
        result = eng.analyze_routing_efficiency("task-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_suboptimal_routings
# -------------------------------------------------------------------


class TestIdentifySuboptimalRoutings:
    def test_with_suboptimal(self):
        eng = _engine()
        eng.record_routing("task-a", routing_outcome=RoutingOutcome.OVER_PROVISIONED)
        eng.record_routing("task-a", routing_outcome=RoutingOutcome.UNDER_PROVISIONED)
        eng.record_routing("task-b", routing_outcome=RoutingOutcome.OPTIMAL)
        results = eng.identify_suboptimal_routings()
        assert len(results) == 1
        assert results[0]["task_name"] == "task-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_suboptimal_routings() == []


# -------------------------------------------------------------------
# rank_by_cost_efficiency
# -------------------------------------------------------------------


class TestRankByCostEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_routing("task-a", cost_dollars=10.0)
        eng.record_routing("task-a", cost_dollars=5.0)
        eng.record_routing("task-b", cost_dollars=2.0)
        results = eng.rank_by_cost_efficiency()
        assert results[0]["task_name"] == "task-b"
        assert results[0]["total_cost_dollars"] == 2.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_cost_efficiency() == []


# -------------------------------------------------------------------
# detect_routing_failures
# -------------------------------------------------------------------


class TestDetectRoutingFailures:
    def test_with_failures(self):
        eng = _engine()
        for _ in range(5):
            eng.record_routing("task-a", routing_outcome=RoutingOutcome.FALLBACK)
        eng.record_routing("task-b", routing_outcome=RoutingOutcome.OPTIMAL)
        results = eng.detect_routing_failures()
        assert len(results) == 1
        assert results[0]["task_name"] == "task-a"
        assert results[0]["failing"] is True

    def test_no_failures(self):
        eng = _engine()
        eng.record_routing("task-a", routing_outcome=RoutingOutcome.OPTIMAL)
        assert eng.detect_routing_failures() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_routing("task-a", routing_outcome=RoutingOutcome.OPTIMAL)
        eng.record_routing("task-b", routing_outcome=RoutingOutcome.FALLBACK)
        eng.add_decision("decision-1")
        report = eng.generate_report()
        assert report.total_routings == 2
        assert report.total_decisions == 1
        assert report.by_tier != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_routings == 0
        assert report.recommendations[0] == "Routing optimization meets targets"

    def test_below_target(self):
        eng = _engine()
        eng.record_routing("task-a", routing_outcome=RoutingOutcome.FALLBACK)
        report = eng.generate_report()
        assert any("fallback" in r for r in report.recommendations)


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_routing("task-a")
        eng.add_decision("decision-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._decisions) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_decisions"] == 0
        assert stats["tier_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_routing("task-a", model_tier=ModelTier.STANDARD)
        eng.record_routing("task-b", model_tier=ModelTier.FLAGSHIP)
        eng.add_decision("d1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_decisions"] == 1
        assert stats["unique_tasks"] == 2
