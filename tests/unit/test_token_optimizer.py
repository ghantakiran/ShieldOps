"""Tests for shieldops.agents.token_optimizer — AgentTokenOptimizer."""

from __future__ import annotations

from shieldops.agents.token_optimizer import (
    AgentTokenOptimizer,
    CostTier,
    OptimizationResult,
    OptimizationStrategy,
    TokenOptimizerReport,
    TokenSavingsLevel,
    TokenUsageRecord,
)


def _engine(**kw) -> AgentTokenOptimizer:
    return AgentTokenOptimizer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # OptimizationStrategy (5)
    def test_strategy_prompt_compression(self):
        assert OptimizationStrategy.PROMPT_COMPRESSION == "prompt_compression"

    def test_strategy_response_caching(self):
        assert OptimizationStrategy.RESPONSE_CACHING == "response_caching"

    def test_strategy_semantic_dedup(self):
        assert OptimizationStrategy.SEMANTIC_DEDUP == "semantic_dedup"

    def test_strategy_model_downgrade(self):
        assert OptimizationStrategy.MODEL_DOWNGRADE == "model_downgrade"

    def test_strategy_context_pruning(self):
        assert OptimizationStrategy.CONTEXT_PRUNING == "context_pruning"

    # TokenSavingsLevel (5)
    def test_savings_excellent(self):
        assert TokenSavingsLevel.EXCELLENT == "excellent"

    def test_savings_good(self):
        assert TokenSavingsLevel.GOOD == "good"

    def test_savings_moderate(self):
        assert TokenSavingsLevel.MODERATE == "moderate"

    def test_savings_low(self):
        assert TokenSavingsLevel.LOW == "low"

    def test_savings_none(self):
        assert TokenSavingsLevel.NONE == "none"

    # CostTier (5)
    def test_tier_premium(self):
        assert CostTier.PREMIUM == "premium"

    def test_tier_standard(self):
        assert CostTier.STANDARD == "standard"

    def test_tier_economy(self):
        assert CostTier.ECONOMY == "economy"

    def test_tier_free_tier(self):
        assert CostTier.FREE_TIER == "free_tier"

    def test_tier_cached(self):
        assert CostTier.CACHED == "cached"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_token_usage_record_defaults(self):
        r = TokenUsageRecord()
        assert r.id
        assert r.agent_name == ""
        assert r.optimization_strategy == OptimizationStrategy.PROMPT_COMPRESSION
        assert r.savings_level == TokenSavingsLevel.MODERATE
        assert r.cost_tier == CostTier.STANDARD
        assert r.tokens_saved == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_optimization_result_defaults(self):
        r = OptimizationResult()
        assert r.id
        assert r.result_label == ""
        assert r.optimization_strategy == OptimizationStrategy.PROMPT_COMPRESSION
        assert r.savings_level == TokenSavingsLevel.GOOD
        assert r.savings_pct == 0.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = TokenOptimizerReport()
        assert r.total_records == 0
        assert r.total_results == 0
        assert r.avg_savings_pct == 0.0
        assert r.by_strategy == {}
        assert r.by_savings_level == {}
        assert r.low_savings_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_usage
# -------------------------------------------------------------------


class TestRecordUsage:
    def test_basic(self):
        eng = _engine()
        r = eng.record_usage(
            "agent-a",
            optimization_strategy=OptimizationStrategy.RESPONSE_CACHING,
            savings_level=TokenSavingsLevel.EXCELLENT,
        )
        assert r.agent_name == "agent-a"
        assert r.optimization_strategy == OptimizationStrategy.RESPONSE_CACHING

    def test_with_tokens(self):
        eng = _engine()
        r = eng.record_usage(
            "agent-b",
            cost_tier=CostTier.PREMIUM,
            tokens_saved=5000,
        )
        assert r.cost_tier == CostTier.PREMIUM
        assert r.tokens_saved == 5000

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_usage(f"agent-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_usage
# -------------------------------------------------------------------


class TestGetUsage:
    def test_found(self):
        eng = _engine()
        r = eng.record_usage("agent-a")
        assert eng.get_usage(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_usage("nonexistent") is None


# -------------------------------------------------------------------
# list_usages
# -------------------------------------------------------------------


class TestListUsages:
    def test_list_all(self):
        eng = _engine()
        eng.record_usage("agent-a")
        eng.record_usage("agent-b")
        assert len(eng.list_usages()) == 2

    def test_filter_by_agent(self):
        eng = _engine()
        eng.record_usage("agent-a")
        eng.record_usage("agent-b")
        results = eng.list_usages(agent_name="agent-a")
        assert len(results) == 1

    def test_filter_by_strategy(self):
        eng = _engine()
        eng.record_usage("agent-a", optimization_strategy=OptimizationStrategy.SEMANTIC_DEDUP)
        eng.record_usage("agent-b", optimization_strategy=OptimizationStrategy.PROMPT_COMPRESSION)
        results = eng.list_usages(optimization_strategy=OptimizationStrategy.SEMANTIC_DEDUP)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_result
# -------------------------------------------------------------------


class TestAddResult:
    def test_basic(self):
        eng = _engine()
        r = eng.add_result(
            "result-1",
            optimization_strategy=OptimizationStrategy.MODEL_DOWNGRADE,
            savings_level=TokenSavingsLevel.EXCELLENT,
            savings_pct=45.0,
        )
        assert r.result_label == "result-1"
        assert r.savings_pct == 45.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_result(f"result-{i}")
        assert len(eng._results) == 2


# -------------------------------------------------------------------
# analyze_agent_savings
# -------------------------------------------------------------------


class TestAnalyzeAgentSavings:
    def test_with_data(self):
        eng = _engine()
        eng.record_usage("agent-a", savings_level=TokenSavingsLevel.EXCELLENT, tokens_saved=1000)
        eng.record_usage("agent-a", savings_level=TokenSavingsLevel.NONE, tokens_saved=0)
        result = eng.analyze_agent_savings("agent-a")
        assert result["agent_name"] == "agent-a"
        assert result["total_records"] == 2
        assert result["avg_tokens_saved"] == 500.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_agent_savings("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(target_savings_pct=50.0)
        eng.record_usage("agent-a", savings_level=TokenSavingsLevel.EXCELLENT)
        result = eng.analyze_agent_savings("agent-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_low_savings_agents
# -------------------------------------------------------------------


class TestIdentifyLowSavingsAgents:
    def test_with_low_savings(self):
        eng = _engine()
        eng.record_usage("agent-a", savings_level=TokenSavingsLevel.NONE)
        eng.record_usage("agent-a", savings_level=TokenSavingsLevel.LOW)
        eng.record_usage("agent-b", savings_level=TokenSavingsLevel.EXCELLENT)
        results = eng.identify_low_savings_agents()
        assert len(results) == 1
        assert results[0]["agent_name"] == "agent-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_savings_agents() == []


# -------------------------------------------------------------------
# rank_by_tokens_saved
# -------------------------------------------------------------------


class TestRankByTokensSaved:
    def test_with_data(self):
        eng = _engine()
        eng.record_usage("agent-a", tokens_saved=5000)
        eng.record_usage("agent-a", tokens_saved=3000)
        eng.record_usage("agent-b", tokens_saved=1000)
        results = eng.rank_by_tokens_saved()
        assert results[0]["agent_name"] == "agent-a"
        assert results[0]["total_tokens_saved"] == 8000

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_tokens_saved() == []


# -------------------------------------------------------------------
# detect_savings_regression
# -------------------------------------------------------------------


class TestDetectSavingsRegression:
    def test_with_regression(self):
        eng = _engine()
        for _ in range(5):
            eng.record_usage("agent-a", savings_level=TokenSavingsLevel.NONE)
        eng.record_usage("agent-b", savings_level=TokenSavingsLevel.EXCELLENT)
        results = eng.detect_savings_regression()
        assert len(results) == 1
        assert results[0]["agent_name"] == "agent-a"
        assert results[0]["regressing"] is True

    def test_no_regression(self):
        eng = _engine()
        eng.record_usage("agent-a", savings_level=TokenSavingsLevel.EXCELLENT)
        assert eng.detect_savings_regression() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_usage("agent-a", savings_level=TokenSavingsLevel.EXCELLENT)
        eng.record_usage("agent-b", savings_level=TokenSavingsLevel.NONE)
        eng.add_result("result-1", savings_pct=40.0)
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_results == 1
        assert report.by_strategy != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert report.recommendations[0] == "Token optimization meets targets"

    def test_low_savings(self):
        eng = _engine()
        eng.record_usage("agent-a", savings_level=TokenSavingsLevel.NONE)
        report = eng.generate_report()
        assert any("low or no" in r for r in report.recommendations)


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_usage("agent-a")
        eng.add_result("result-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._results) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_results"] == 0
        assert stats["strategy_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_usage("agent-a", optimization_strategy=OptimizationStrategy.PROMPT_COMPRESSION)
        eng.record_usage("agent-b", optimization_strategy=OptimizationStrategy.RESPONSE_CACHING)
        eng.add_result("r1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_results"] == 1
        assert stats["unique_agents"] == 2
