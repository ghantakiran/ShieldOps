"""Tests for shieldops.billing.llm_cost_tracker — LLMTokenCostTracker."""

from __future__ import annotations

from shieldops.billing.llm_cost_tracker import (
    CostTrend,
    LLMCostRecord,
    LLMCostReport,
    LLMProvider,
    LLMTokenCostTracker,
    ProviderCostBreakdown,
    TokenCategory,
)


def _engine(**kw) -> LLMTokenCostTracker:
    return LLMTokenCostTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # LLMProvider (5)
    def test_provider_anthropic(self):
        assert LLMProvider.ANTHROPIC == "anthropic"

    def test_provider_openai(self):
        assert LLMProvider.OPENAI == "openai"

    def test_provider_google(self):
        assert LLMProvider.GOOGLE == "google"

    def test_provider_cohere(self):
        assert LLMProvider.COHERE == "cohere"

    def test_provider_local(self):
        assert LLMProvider.LOCAL == "local"

    # TokenCategory (5)
    def test_category_input(self):
        assert TokenCategory.INPUT == "input"

    def test_category_output(self):
        assert TokenCategory.OUTPUT == "output"

    def test_category_embedding(self):
        assert TokenCategory.EMBEDDING == "embedding"

    def test_category_fine_tuning(self):
        assert TokenCategory.FINE_TUNING == "fine_tuning"

    def test_category_cached(self):
        assert TokenCategory.CACHED == "cached"

    # CostTrend (5)
    def test_trend_increasing(self):
        assert CostTrend.INCREASING == "increasing"

    def test_trend_stable(self):
        assert CostTrend.STABLE == "stable"

    def test_trend_decreasing(self):
        assert CostTrend.DECREASING == "decreasing"

    def test_trend_volatile(self):
        assert CostTrend.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert CostTrend.INSUFFICIENT_DATA == "insufficient_data"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_cost_record_defaults(self):
        r = LLMCostRecord()
        assert r.id
        assert r.agent_name == ""
        assert r.provider == LLMProvider.ANTHROPIC
        assert r.category == TokenCategory.INPUT
        assert r.token_count == 0
        assert r.cost_usd == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_breakdown_defaults(self):
        b = ProviderCostBreakdown()
        assert b.id
        assert b.provider_name == ""
        assert b.provider == LLMProvider.ANTHROPIC
        assert b.category == TokenCategory.INPUT
        assert b.total_tokens == 0
        assert b.description == ""
        assert b.created_at > 0

    def test_report_defaults(self):
        r = LLMCostReport()
        assert r.total_records == 0
        assert r.total_breakdowns == 0
        assert r.avg_cost_usd == 0.0
        assert r.by_provider == {}
        assert r.by_category == {}
        assert r.high_cost_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_cost
# ---------------------------------------------------------------------------


class TestRecordCost:
    def test_basic(self):
        eng = _engine()
        r = eng.record_cost(
            "investigation-agent",
            provider=LLMProvider.ANTHROPIC,
            category=TokenCategory.INPUT,
            token_count=5000,
            cost_usd=0.50,
        )
        assert r.agent_name == "investigation-agent"
        assert r.token_count == 5000
        assert r.cost_usd == 0.50

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_cost(f"agent-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_cost
# ---------------------------------------------------------------------------


class TestGetCost:
    def test_found(self):
        eng = _engine()
        r = eng.record_cost("agent-a", cost_usd=10.0)
        assert eng.get_cost(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_cost("nonexistent") is None


# ---------------------------------------------------------------------------
# list_costs
# ---------------------------------------------------------------------------


class TestListCosts:
    def test_list_all(self):
        eng = _engine()
        eng.record_cost("agent-a")
        eng.record_cost("agent-b")
        assert len(eng.list_costs()) == 2

    def test_filter_by_agent(self):
        eng = _engine()
        eng.record_cost("agent-a")
        eng.record_cost("agent-b")
        results = eng.list_costs(agent_name="agent-a")
        assert len(results) == 1

    def test_filter_by_provider(self):
        eng = _engine()
        eng.record_cost("a1", provider=LLMProvider.ANTHROPIC)
        eng.record_cost("a2", provider=LLMProvider.OPENAI)
        results = eng.list_costs(provider=LLMProvider.ANTHROPIC)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# add_breakdown
# ---------------------------------------------------------------------------


class TestAddBreakdown:
    def test_basic(self):
        eng = _engine()
        b = eng.add_breakdown(
            "anthropic-main",
            provider=LLMProvider.ANTHROPIC,
            total_tokens=100000,
        )
        assert b.provider_name == "anthropic-main"
        assert b.total_tokens == 100000

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_breakdown(f"p-{i}")
        assert len(eng._breakdowns) == 2


# ---------------------------------------------------------------------------
# analyze_agent_costs
# ---------------------------------------------------------------------------


class TestAnalyzeAgentCosts:
    def test_with_data(self):
        eng = _engine(high_cost_threshold=100.0)
        eng.record_cost("agent-a", cost_usd=50.0)
        eng.record_cost("agent-a", cost_usd=30.0)
        result = eng.analyze_agent_costs("agent-a")
        assert result["agent_name"] == "agent-a"
        assert result["avg_cost_usd"] == 40.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_agent_costs("ghost")
        assert result["status"] == "no_data"


# ---------------------------------------------------------------------------
# identify_high_cost_agents
# ---------------------------------------------------------------------------


class TestIdentifyHighCostAgents:
    def test_with_high(self):
        eng = _engine(high_cost_threshold=50.0)
        eng.record_cost("agent-a", cost_usd=100.0)
        eng.record_cost("agent-a", cost_usd=80.0)
        eng.record_cost("agent-b", cost_usd=10.0)
        results = eng.identify_high_cost_agents()
        assert len(results) == 1
        assert results[0]["agent_name"] == "agent-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_cost_agents() == []


# ---------------------------------------------------------------------------
# rank_by_total_cost
# ---------------------------------------------------------------------------


class TestRankByTotalCost:
    def test_with_data(self):
        eng = _engine()
        eng.record_cost("agent-a", cost_usd=100.0)
        eng.record_cost("agent-b", cost_usd=200.0)
        results = eng.rank_by_total_cost()
        assert results[0]["agent_name"] == "agent-b"
        assert results[0]["avg_cost_usd"] == 200.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_total_cost() == []


# ---------------------------------------------------------------------------
# detect_cost_trends
# ---------------------------------------------------------------------------


class TestDetectCostTrends:
    def test_with_enough_data(self):
        eng = _engine()
        eng.record_cost("agent-a", cost_usd=10.0)
        eng.record_cost("agent-a", cost_usd=12.0)
        eng.record_cost("agent-a", cost_usd=50.0)
        eng.record_cost("agent-a", cost_usd=55.0)
        results = eng.detect_cost_trends()
        assert len(results) == 1
        assert results[0]["agent_name"] == "agent-a"
        assert results[0]["trend"] == CostTrend.INCREASING.value

    def test_insufficient_data(self):
        eng = _engine()
        eng.record_cost("agent-a", cost_usd=10.0)
        eng.record_cost("agent-a", cost_usd=12.0)
        results = eng.detect_cost_trends()
        assert len(results) == 0


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(high_cost_threshold=50.0)
        eng.record_cost("agent-a", cost_usd=100.0, provider=LLMProvider.ANTHROPIC)
        eng.add_breakdown("anthropic-main")
        report = eng.generate_report()
        assert isinstance(report, LLMCostReport)
        assert report.total_records == 1
        assert report.total_breakdowns == 1
        assert report.high_cost_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "within acceptable bounds" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_cost("agent-a")
        eng.add_breakdown("anthropic-main")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._breakdowns) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_breakdowns"] == 0
        assert stats["provider_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_cost("agent-a", provider=LLMProvider.ANTHROPIC)
        eng.record_cost("agent-b", provider=LLMProvider.OPENAI)
        eng.add_breakdown("anthropic-main")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_breakdowns"] == 1
        assert stats["unique_agents"] == 2
