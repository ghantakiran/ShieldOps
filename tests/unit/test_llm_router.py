"""Tests for LLM Router — model routing by task complexity, usage tracking, cost breakdown.

Covers: TaskComplexity enum, ModelTier config, LLMRouter.classify_complexity heuristics,
LLMRouter.get_model tier selection, record_usage cost calculation, get_usage_stats
aggregation, get_cost_breakdown filtering, and edge cases (empty prompts, zero tokens,
unknown models, disabled router).
"""

from __future__ import annotations

import pytest

from shieldops.utils.llm_router import (
    DEFAULT_MODEL_TIERS,
    LLMRouter,
    ModelTier,
    TaskComplexity,
    UsageRecord,
    UsageStats,
)

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def router() -> LLMRouter:
    """Fresh LLMRouter with default tiers."""
    return LLMRouter()


@pytest.fixture
def custom_tiers() -> dict[TaskComplexity, ModelTier]:
    """Custom tier configuration for deterministic testing."""
    return {
        TaskComplexity.SIMPLE: ModelTier(
            provider="test-provider",
            model="test-simple-model",
            cost_per_1k_input=0.001,
            cost_per_1k_output=0.002,
            max_tokens=1024,
        ),
        TaskComplexity.MODERATE: ModelTier(
            provider="test-provider",
            model="test-moderate-model",
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.010,
            max_tokens=4096,
        ),
        TaskComplexity.COMPLEX: ModelTier(
            provider="test-provider",
            model="test-complex-model",
            cost_per_1k_input=0.020,
            cost_per_1k_output=0.080,
            max_tokens=8192,
        ),
    }


@pytest.fixture
def custom_router(custom_tiers: dict[TaskComplexity, ModelTier]) -> LLMRouter:
    """LLMRouter initialized with custom test tiers."""
    return LLMRouter(model_tiers=custom_tiers)


@pytest.fixture
def router_with_records(custom_router: LLMRouter) -> LLMRouter:
    """Router pre-populated with several usage records for stats testing."""
    custom_router.record_usage(
        request_id="req-1",
        complexity=TaskComplexity.SIMPLE,
        model="test-simple-model",
        provider="test-provider",
        input_tokens=100,
        output_tokens=50,
        latency_ms=120,
        agent_type="investigation",
    )
    custom_router.record_usage(
        request_id="req-2",
        complexity=TaskComplexity.MODERATE,
        model="test-moderate-model",
        provider="test-provider",
        input_tokens=500,
        output_tokens=200,
        latency_ms=350,
        agent_type="investigation",
    )
    custom_router.record_usage(
        request_id="req-3",
        complexity=TaskComplexity.COMPLEX,
        model="test-complex-model",
        provider="test-provider",
        input_tokens=2000,
        output_tokens=1000,
        latency_ms=1200,
        agent_type="remediation",
    )
    custom_router.record_usage(
        request_id="req-4",
        complexity=TaskComplexity.SIMPLE,
        model="test-simple-model",
        provider="test-provider",
        input_tokens=80,
        output_tokens=30,
        latency_ms=90,
        agent_type="security",
    )
    return custom_router


# ── TaskComplexity Enum ─────────────────────────────────────────────


class TestTaskComplexity:
    """Verify the TaskComplexity StrEnum values."""

    def test_simple_value(self):
        assert TaskComplexity.SIMPLE == "simple"
        assert TaskComplexity.SIMPLE.value == "simple"

    def test_moderate_value(self):
        assert TaskComplexity.MODERATE == "moderate"

    def test_complex_value(self):
        assert TaskComplexity.COMPLEX == "complex"

    def test_all_members_present(self):
        members = set(TaskComplexity)
        assert members == {TaskComplexity.SIMPLE, TaskComplexity.MODERATE, TaskComplexity.COMPLEX}

    def test_is_str_subclass(self):
        assert isinstance(TaskComplexity.SIMPLE, str)


# ── ModelTier Pydantic Model ───────────────────────────────────────


class TestModelTier:
    """Verify ModelTier defaults and field validation."""

    def test_default_costs_are_zero(self):
        tier = ModelTier(provider="test", model="test-model")
        assert tier.cost_per_1k_input == 0.0
        assert tier.cost_per_1k_output == 0.0

    def test_default_max_tokens(self):
        tier = ModelTier(provider="test", model="test-model")
        assert tier.max_tokens == 4096

    def test_custom_values(self):
        tier = ModelTier(
            provider="openai",
            model="gpt-4",
            cost_per_1k_input=0.03,
            cost_per_1k_output=0.06,
            max_tokens=8192,
        )
        assert tier.provider == "openai"
        assert tier.model == "gpt-4"
        assert tier.cost_per_1k_input == pytest.approx(0.03)
        assert tier.max_tokens == 8192


# ── UsageRecord Pydantic Model ─────────────────────────────────────


class TestUsageRecord:
    """Verify UsageRecord defaults and timestamp generation."""

    def test_defaults(self):
        record = UsageRecord()
        assert record.request_id == ""
        assert record.complexity == TaskComplexity.MODERATE
        assert record.input_tokens == 0
        assert record.output_tokens == 0
        assert record.estimated_cost == 0.0
        assert record.agent_type == ""

    def test_timestamp_auto_generated(self):
        record = UsageRecord()
        assert record.timestamp is not None


# ── classify_complexity ─────────────────────────────────────────────


class TestClassifyComplexity:
    """Tests for LLMRouter.classify_complexity heuristic classification."""

    def test_empty_prompt_returns_simple(self, router: LLMRouter):
        result = router.classify_complexity(prompt="")
        assert result == TaskComplexity.SIMPLE

    def test_short_prompt_returns_simple(self, router: LLMRouter):
        # 50 chars => ~12 tokens, well under SIMPLE_MAX_TOKENS (200)
        prompt = "What is the status of service X?"
        result = router.classify_complexity(prompt=prompt)
        assert result == TaskComplexity.SIMPLE

    def test_short_prompt_with_simple_keyword_returns_simple(self, router: LLMRouter):
        prompt = "Please classify this alert as critical or warning."
        result = router.classify_complexity(prompt=prompt)
        assert result == TaskComplexity.SIMPLE

    def test_short_prompt_with_extract_keyword_returns_simple(self, router: LLMRouter):
        prompt = "Extract the service name from this log entry."
        result = router.classify_complexity(prompt=prompt)
        assert result == TaskComplexity.SIMPLE

    def test_medium_prompt_without_keywords_returns_moderate(self, router: LLMRouter):
        # Between SIMPLE_MAX_TOKENS (200) and MODERATE_MAX_TOKENS (1000) in estimated tokens
        # 200 * 4 = 800 chars needed to exceed simple threshold
        prompt = "x" * 900  # ~225 estimated tokens, above SIMPLE_MAX_TOKENS
        result = router.classify_complexity(prompt=prompt)
        assert result == TaskComplexity.MODERATE

    def test_tool_use_with_short_prompt_returns_moderate(self, router: LLMRouter):
        prompt = "Check disk usage on host alpha."
        result = router.classify_complexity(prompt=prompt, requires_tool_use=True)
        assert result == TaskComplexity.MODERATE

    def test_structured_output_with_short_prompt_and_complex_keyword_returns_moderate(
        self, router: LLMRouter
    ):
        # Short prompt with complex keyword but no tool use => should not hit COMPLEX branch
        # But has complex keyword, so not SIMPLE either
        prompt = "Summarize the root cause."  # "root cause" is a complex keyword
        result = router.classify_complexity(prompt=prompt, requires_structured_output=True)
        assert result == TaskComplexity.MODERATE

    def test_long_prompt_returns_complex(self, router: LLMRouter):
        # Exceed MODERATE_MAX_TOKENS (1000). Need > 1000 * 4 = 4000 chars
        prompt = "a" * 4100  # ~1025 estimated tokens
        result = router.classify_complexity(prompt=prompt)
        assert result == TaskComplexity.COMPLEX

    def test_complex_keyword_with_tool_use_returns_complex(self, router: LLMRouter):
        prompt = "Analyze the root cause of this outage and correlate with recent deployments."
        result = router.classify_complexity(prompt=prompt, requires_tool_use=True)
        assert result == TaskComplexity.COMPLEX

    def test_hypothesis_keyword_with_tool_use_returns_complex(self, router: LLMRouter):
        prompt = "Form a hypothesis about why latency spiked across services."
        result = router.classify_complexity(prompt=prompt, requires_tool_use=True)
        assert result == TaskComplexity.COMPLEX

    def test_security_audit_keyword_with_tool_use_returns_complex(self, router: LLMRouter):
        prompt = "Run a security audit on the network policies."
        result = router.classify_complexity(prompt=prompt, requires_tool_use=True)
        assert result == TaskComplexity.COMPLEX

    def test_compliance_keyword_with_tool_use_returns_complex(self, router: LLMRouter):
        prompt = "Check compliance for PCI-DSS requirements."
        result = router.classify_complexity(prompt=prompt, requires_tool_use=True)
        assert result == TaskComplexity.COMPLEX

    def test_short_prompt_with_complex_keyword_no_tools_returns_moderate(self, router: LLMRouter):
        # Short prompt + complex keyword + no tool use => moderate (complex keyword
        # blocks SIMPLE, but no tool use blocks COMPLEX)
        prompt = "Analyze this short log."
        result = router.classify_complexity(prompt=prompt)
        assert result == TaskComplexity.MODERATE

    def test_case_insensitive_keyword_matching(self, router: LLMRouter):
        prompt = "ANALYZE the ROOT CAUSE with multi-step reasoning."
        result = router.classify_complexity(prompt=prompt, requires_tool_use=True)
        assert result == TaskComplexity.COMPLEX

    @pytest.mark.parametrize(
        "keyword",
        [
            "classify",
            "categorize",
            "extract",
            "summarize",
            "format",
            "parse",
            "validate",
        ],
    )
    def test_simple_keywords_yield_simple_for_short_prompts(self, router: LLMRouter, keyword: str):
        prompt = f"Please {keyword} this data."
        result = router.classify_complexity(prompt=prompt)
        assert result == TaskComplexity.SIMPLE

    @pytest.mark.parametrize(
        "keyword",
        [
            "analyze",
            "correlate",
            "hypothesis",
            "root cause",
            "diagnosis",
            "architectural",
            "security audit",
            "compliance",
            "multi-step",
        ],
    )
    def test_complex_keywords_with_tools_yield_complex(self, router: LLMRouter, keyword: str):
        prompt = f"Please {keyword} the system state."
        result = router.classify_complexity(prompt=prompt, requires_tool_use=True)
        assert result == TaskComplexity.COMPLEX

    def test_short_prompt_with_structured_output_no_keywords_returns_simple(
        self, router: LLMRouter
    ):
        # Short prompt, no complex keywords, structured output requested but
        # has_simple_keywords is false and requires_structured_output is True
        # => the inner condition checks has_simple_keywords or not requires_structured_output
        # Both False => falls through to MODERATE
        prompt = "Do something."
        result = router.classify_complexity(prompt=prompt, requires_structured_output=True)
        # "do something" has no simple or complex keywords
        # Short + no tool + no complex => enters inner if
        # has_simple_keywords=False, requires_structured_output=True => False or False => MODERATE
        assert result == TaskComplexity.MODERATE

    def test_short_prompt_no_structured_output_no_keywords_returns_simple(self, router: LLMRouter):
        # Short, no keywords, no structured output => simple
        prompt = "Hello world."
        result = router.classify_complexity(prompt=prompt, requires_structured_output=False)
        assert result == TaskComplexity.SIMPLE


# ── get_model ───────────────────────────────────────────────────────


class TestGetModel:
    """Tests for LLMRouter.get_model tier selection."""

    def test_explicit_simple_complexity_returns_simple_tier(self, custom_router: LLMRouter):
        tier = custom_router.get_model(complexity=TaskComplexity.SIMPLE)
        assert tier.model == "test-simple-model"

    def test_explicit_moderate_complexity_returns_moderate_tier(self, custom_router: LLMRouter):
        tier = custom_router.get_model(complexity=TaskComplexity.MODERATE)
        assert tier.model == "test-moderate-model"

    def test_explicit_complex_complexity_returns_complex_tier(self, custom_router: LLMRouter):
        tier = custom_router.get_model(complexity=TaskComplexity.COMPLEX)
        assert tier.model == "test-complex-model"

    def test_no_complexity_classifies_from_prompt(self, custom_router: LLMRouter):
        # Short prompt, no tools => SIMPLE
        tier = custom_router.get_model(prompt="Summarize this log entry.")
        assert tier.model == "test-simple-model"

    def test_no_complexity_long_prompt_returns_complex_tier(self, custom_router: LLMRouter):
        # Long prompt => COMPLEX
        tier = custom_router.get_model(prompt="a" * 4100)
        assert tier.model == "test-complex-model"

    def test_no_complexity_with_tool_use_returns_moderate_or_higher(self, custom_router: LLMRouter):
        tier = custom_router.get_model(prompt="Check this short task.", requires_tool_use=True)
        # Tool use bumps short prompt to MODERATE
        assert tier.model == "test-moderate-model"

    def test_default_tiers_match_expected_models(self, router: LLMRouter):
        simple = router.get_model(complexity=TaskComplexity.SIMPLE)
        moderate = router.get_model(complexity=TaskComplexity.MODERATE)
        complex_ = router.get_model(complexity=TaskComplexity.COMPLEX)
        assert simple.model == "claude-haiku-4-5-20251001"
        assert moderate.model == "claude-sonnet-4-20250514"
        assert complex_.model == "claude-opus-4-20250514"

    def test_default_tier_providers_are_anthropic(self, router: LLMRouter):
        for complexity in TaskComplexity:
            tier = router.get_model(complexity=complexity)
            assert tier.provider == "anthropic"


# ── route (get_model end-to-end with prompt) ────────────────────────


class TestRouteEndToEnd:
    """End-to-end routing tests: prompt in, model tier out."""

    def test_route_simple_prompt(self, router: LLMRouter):
        tier = router.get_model(prompt="Parse this JSON.")
        assert tier.model == DEFAULT_MODEL_TIERS[TaskComplexity.SIMPLE].model

    def test_route_complex_tool_prompt(self, router: LLMRouter):
        tier = router.get_model(
            prompt="Analyze root cause of this incident and correlate logs.",
            requires_tool_use=True,
        )
        assert tier.model == DEFAULT_MODEL_TIERS[TaskComplexity.COMPLEX].model

    def test_route_moderate_prompt(self, router: LLMRouter):
        # Medium-length prompt, no keywords
        tier = router.get_model(prompt="x" * 900)
        assert tier.model == DEFAULT_MODEL_TIERS[TaskComplexity.MODERATE].model


# ── record_usage ────────────────────────────────────────────────────


class TestRecordUsage:
    """Tests for LLMRouter.record_usage cost calculation and record creation."""

    def test_returns_usage_record(self, custom_router: LLMRouter):
        record = custom_router.record_usage(
            request_id="r1",
            complexity=TaskComplexity.SIMPLE,
            model="test-simple-model",
            provider="test-provider",
            input_tokens=1000,
            output_tokens=500,
        )
        assert isinstance(record, UsageRecord)

    def test_cost_calculation_simple_model(self, custom_router: LLMRouter):
        record = custom_router.record_usage(
            request_id="r1",
            complexity=TaskComplexity.SIMPLE,
            model="test-simple-model",
            provider="test-provider",
            input_tokens=1000,
            output_tokens=500,
        )
        # cost = (1000/1000 * 0.001) + (500/1000 * 0.002) = 0.001 + 0.001 = 0.002
        assert record.estimated_cost == pytest.approx(0.002)

    def test_cost_calculation_complex_model(self, custom_router: LLMRouter):
        record = custom_router.record_usage(
            request_id="r2",
            complexity=TaskComplexity.COMPLEX,
            model="test-complex-model",
            provider="test-provider",
            input_tokens=2000,
            output_tokens=1000,
        )
        # cost = (2000/1000 * 0.020) + (1000/1000 * 0.080) = 0.040 + 0.080 = 0.120
        assert record.estimated_cost == pytest.approx(0.12)

    def test_zero_tokens_yields_zero_cost(self, custom_router: LLMRouter):
        record = custom_router.record_usage(
            request_id="r3",
            complexity=TaskComplexity.SIMPLE,
            model="test-simple-model",
            provider="test-provider",
            input_tokens=0,
            output_tokens=0,
        )
        assert record.estimated_cost == pytest.approx(0.0)

    def test_unknown_model_yields_zero_cost(self, custom_router: LLMRouter):
        record = custom_router.record_usage(
            request_id="r4",
            complexity=TaskComplexity.MODERATE,
            model="unknown-model-xyz",
            provider="unknown",
            input_tokens=5000,
            output_tokens=2000,
        )
        # Model not in tiers => tier is None => cost is 0
        assert record.estimated_cost == pytest.approx(0.0)

    def test_record_fields_match_inputs(self, custom_router: LLMRouter):
        record = custom_router.record_usage(
            request_id="req-abc",
            complexity=TaskComplexity.MODERATE,
            model="test-moderate-model",
            provider="test-provider",
            input_tokens=300,
            output_tokens=150,
            latency_ms=450,
            agent_type="security",
        )
        assert record.request_id == "req-abc"
        assert record.complexity == TaskComplexity.MODERATE
        assert record.model == "test-moderate-model"
        assert record.provider == "test-provider"
        assert record.input_tokens == 300
        assert record.output_tokens == 150
        assert record.latency_ms == 450
        assert record.agent_type == "security"

    def test_record_appended_to_internal_list(self, custom_router: LLMRouter):
        assert len(custom_router._usage_records) == 0
        custom_router.record_usage(
            request_id="r1",
            complexity=TaskComplexity.SIMPLE,
            model="test-simple-model",
            provider="test-provider",
        )
        assert len(custom_router._usage_records) == 1
        custom_router.record_usage(
            request_id="r2",
            complexity=TaskComplexity.MODERATE,
            model="test-moderate-model",
            provider="test-provider",
        )
        assert len(custom_router._usage_records) == 2

    def test_record_has_timestamp(self, custom_router: LLMRouter):
        record = custom_router.record_usage(
            request_id="r1",
            complexity=TaskComplexity.SIMPLE,
            model="test-simple-model",
            provider="test-provider",
        )
        assert record.timestamp is not None


# ── get_usage_stats ─────────────────────────────────────────────────


class TestGetUsageStats:
    """Tests for LLMRouter.get_usage_stats aggregation."""

    def test_empty_router_returns_zero_stats(self, custom_router: LLMRouter):
        stats = custom_router.get_usage_stats()
        assert isinstance(stats, UsageStats)
        assert stats.total_requests == 0
        assert stats.total_input_tokens == 0
        assert stats.total_output_tokens == 0
        assert stats.total_estimated_cost == pytest.approx(0.0)
        assert stats.by_model == {}
        assert stats.by_complexity == {}
        assert stats.by_agent == {}

    def test_total_requests_count(self, router_with_records: LLMRouter):
        stats = router_with_records.get_usage_stats()
        assert stats.total_requests == 4

    def test_total_input_tokens(self, router_with_records: LLMRouter):
        stats = router_with_records.get_usage_stats()
        # 100 + 500 + 2000 + 80 = 2680
        assert stats.total_input_tokens == 2680

    def test_total_output_tokens(self, router_with_records: LLMRouter):
        stats = router_with_records.get_usage_stats()
        # 50 + 200 + 1000 + 30 = 1280
        assert stats.total_output_tokens == 1280

    def test_total_estimated_cost(self, router_with_records: LLMRouter):
        stats = router_with_records.get_usage_stats()
        # Simple model (req-1): (100/1000*0.001) + (50/1000*0.002) = 0.0001 + 0.0001 = 0.0002
        # Moderate model (req-2): (500/1000*0.005) + (200/1000*0.010) = 0.0025 + 0.002 = 0.0045
        # Complex model (req-3): (2000/1000*0.020) + (1000/1000*0.080) = 0.04 + 0.08 = 0.12
        # Simple model (req-4): (80/1000*0.001) + (30/1000*0.002) = 0.00008 + 0.00006 = 0.00014
        # Total: 0.0002 + 0.0045 + 0.12 + 0.00014 = 0.12484
        assert stats.total_estimated_cost == pytest.approx(0.12484, abs=1e-6)

    def test_by_model_keys(self, router_with_records: LLMRouter):
        stats = router_with_records.get_usage_stats()
        assert set(stats.by_model.keys()) == {
            "test-simple-model",
            "test-moderate-model",
            "test-complex-model",
        }

    def test_by_model_request_counts(self, router_with_records: LLMRouter):
        stats = router_with_records.get_usage_stats()
        assert stats.by_model["test-simple-model"]["requests"] == 2
        assert stats.by_model["test-moderate-model"]["requests"] == 1
        assert stats.by_model["test-complex-model"]["requests"] == 1

    def test_by_model_token_aggregation(self, router_with_records: LLMRouter):
        stats = router_with_records.get_usage_stats()
        simple = stats.by_model["test-simple-model"]
        assert simple["input_tokens"] == 180  # 100 + 80
        assert simple["output_tokens"] == 80  # 50 + 30

    def test_by_complexity_keys(self, router_with_records: LLMRouter):
        stats = router_with_records.get_usage_stats()
        assert set(stats.by_complexity.keys()) == {"simple", "moderate", "complex"}

    def test_by_complexity_request_counts(self, router_with_records: LLMRouter):
        stats = router_with_records.get_usage_stats()
        assert stats.by_complexity["simple"]["requests"] == 2
        assert stats.by_complexity["moderate"]["requests"] == 1
        assert stats.by_complexity["complex"]["requests"] == 1

    def test_by_agent_keys(self, router_with_records: LLMRouter):
        stats = router_with_records.get_usage_stats()
        assert set(stats.by_agent.keys()) == {"investigation", "remediation", "security"}

    def test_by_agent_request_counts(self, router_with_records: LLMRouter):
        stats = router_with_records.get_usage_stats()
        assert stats.by_agent["investigation"]["requests"] == 2
        assert stats.by_agent["remediation"]["requests"] == 1
        assert stats.by_agent["security"]["requests"] == 1

    def test_empty_agent_type_excluded_from_by_agent(self, custom_router: LLMRouter):
        custom_router.record_usage(
            request_id="r1",
            complexity=TaskComplexity.SIMPLE,
            model="test-simple-model",
            provider="test-provider",
            input_tokens=100,
            output_tokens=50,
            agent_type="",  # empty string
        )
        stats = custom_router.get_usage_stats()
        assert stats.by_agent == {}
        assert stats.total_requests == 1


# ── get_cost_breakdown ──────────────────────────────────────────────


class TestGetCostBreakdown:
    """Tests for LLMRouter.get_cost_breakdown filtering and aggregation."""

    def test_empty_router_returns_zero_breakdown(self, custom_router: LLMRouter):
        breakdown = custom_router.get_cost_breakdown()
        assert breakdown["total_cost"] == pytest.approx(0.0)
        assert breakdown["total_requests"] == 0
        assert breakdown["by_model"] == {}

    def test_total_cost_all_records(self, router_with_records: LLMRouter):
        breakdown = router_with_records.get_cost_breakdown()
        assert breakdown["total_cost"] == pytest.approx(0.12484, abs=1e-6)

    def test_total_requests_all_records(self, router_with_records: LLMRouter):
        breakdown = router_with_records.get_cost_breakdown()
        assert breakdown["total_requests"] == 4

    def test_by_model_keys_all_records(self, router_with_records: LLMRouter):
        breakdown = router_with_records.get_cost_breakdown()
        assert set(breakdown["by_model"].keys()) == {
            "test-simple-model",
            "test-moderate-model",
            "test-complex-model",
        }

    def test_by_model_request_counts(self, router_with_records: LLMRouter):
        breakdown = router_with_records.get_cost_breakdown()
        assert breakdown["by_model"]["test-simple-model"]["requests"] == 2
        assert breakdown["by_model"]["test-moderate-model"]["requests"] == 1

    def test_filter_by_agent_type_investigation(self, router_with_records: LLMRouter):
        breakdown = router_with_records.get_cost_breakdown(agent_type="investigation")
        assert breakdown["total_requests"] == 2
        # Only investigation records: req-1 (simple) + req-2 (moderate)
        assert "test-simple-model" in breakdown["by_model"]
        assert "test-moderate-model" in breakdown["by_model"]
        assert "test-complex-model" not in breakdown["by_model"]

    def test_filter_by_agent_type_remediation(self, router_with_records: LLMRouter):
        breakdown = router_with_records.get_cost_breakdown(agent_type="remediation")
        assert breakdown["total_requests"] == 1
        assert "test-complex-model" in breakdown["by_model"]
        assert breakdown["total_cost"] == pytest.approx(0.12, abs=1e-6)

    def test_filter_by_nonexistent_agent_type_returns_empty(self, router_with_records: LLMRouter):
        breakdown = router_with_records.get_cost_breakdown(agent_type="nonexistent-agent")
        assert breakdown["total_requests"] == 0
        assert breakdown["total_cost"] == pytest.approx(0.0)
        assert breakdown["by_model"] == {}

    def test_avg_latency_calculation(self, router_with_records: LLMRouter):
        breakdown = router_with_records.get_cost_breakdown()
        # simple model: two records with latency 120 and 90 => avg = (120 + 90) / 2 = 105
        assert breakdown["by_model"]["test-simple-model"]["avg_latency_ms"] == pytest.approx(105.0)

    def test_avg_latency_single_record(self, router_with_records: LLMRouter):
        breakdown = router_with_records.get_cost_breakdown()
        assert breakdown["by_model"]["test-complex-model"]["avg_latency_ms"] == pytest.approx(
            1200.0
        )


# ── Router initialization & properties ──────────────────────────────


class TestRouterInitialization:
    """Tests for LLMRouter constructor and properties."""

    def test_default_tiers_loaded(self, router: LLMRouter):
        for complexity in TaskComplexity:
            tier = router.get_model(complexity=complexity)
            assert tier.model == DEFAULT_MODEL_TIERS[complexity].model

    def test_custom_tiers_override_defaults(self, custom_router: LLMRouter):
        tier = custom_router.get_model(complexity=TaskComplexity.SIMPLE)
        assert tier.model == "test-simple-model"

    def test_enabled_property_default_true(self, router: LLMRouter):
        assert router.enabled is True

    def test_enabled_property_when_disabled(self):
        disabled_router = LLMRouter(enabled=False)
        assert disabled_router.enabled is False

    def test_usage_records_initially_empty(self, router: LLMRouter):
        assert len(router._usage_records) == 0

    def test_custom_tiers_do_not_mutate_defaults(self, custom_tiers):
        _ = LLMRouter(model_tiers=custom_tiers)
        # Verify the global DEFAULT_MODEL_TIERS is untouched
        assert DEFAULT_MODEL_TIERS[TaskComplexity.SIMPLE].model == "claude-haiku-4-5-20251001"


# ── Edge cases & boundary conditions ────────────────────────────────


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_prompt_exactly_at_simple_boundary(self, router: LLMRouter):
        # SIMPLE_MAX_TOKENS = 200, so 200 * 4 = 800 chars => exactly 200 tokens
        prompt = "x" * 800
        result = router.classify_complexity(prompt=prompt)
        # estimated_tokens = 800 // 4 = 200, which is <= 200 => enters simple branch
        assert result == TaskComplexity.SIMPLE

    def test_prompt_one_over_simple_boundary(self, router: LLMRouter):
        # 201 * 4 = 804 chars => 201 tokens, above SIMPLE_MAX_TOKENS
        prompt = "x" * 804
        result = router.classify_complexity(prompt=prompt)
        assert result == TaskComplexity.MODERATE

    def test_prompt_exactly_at_moderate_boundary(self, router: LLMRouter):
        # MODERATE_MAX_TOKENS = 1000, so 1000 * 4 = 4000 chars => exactly 1000 tokens
        prompt = "x" * 4000
        result = router.classify_complexity(prompt=prompt)
        # estimated_tokens = 1000, not > 1000 => moderate
        assert result == TaskComplexity.MODERATE

    def test_prompt_one_over_moderate_boundary(self, router: LLMRouter):
        # 1001 * 4 = 4004 chars => 1001 tokens, above MODERATE_MAX_TOKENS
        prompt = "x" * 4004
        result = router.classify_complexity(prompt=prompt)
        assert result == TaskComplexity.COMPLEX

    def test_very_large_token_counts(self, custom_router: LLMRouter):
        record = custom_router.record_usage(
            request_id="r-large",
            complexity=TaskComplexity.COMPLEX,
            model="test-complex-model",
            provider="test-provider",
            input_tokens=1_000_000,
            output_tokens=500_000,
        )
        # (1000000/1000 * 0.020) + (500000/1000 * 0.080) = 20.0 + 40.0 = 60.0
        assert record.estimated_cost == pytest.approx(60.0)

    def test_multiple_records_then_stats_consistency(self, custom_router: LLMRouter):
        """Verify stats totals match sum of individual records."""
        records = []
        for i in range(10):
            r = custom_router.record_usage(
                request_id=f"r-{i}",
                complexity=TaskComplexity.SIMPLE,
                model="test-simple-model",
                provider="test-provider",
                input_tokens=100 * (i + 1),
                output_tokens=50 * (i + 1),
                agent_type="test-agent",
            )
            records.append(r)

        stats = custom_router.get_usage_stats()
        assert stats.total_requests == 10
        assert stats.total_input_tokens == sum(r.input_tokens for r in records)
        assert stats.total_output_tokens == sum(r.output_tokens for r in records)
        assert stats.total_estimated_cost == pytest.approx(
            sum(r.estimated_cost for r in records), abs=1e-6
        )

    def test_cost_breakdown_matches_usage_stats(self, router_with_records: LLMRouter):
        """Cross-check that cost_breakdown total matches usage_stats total."""
        stats = router_with_records.get_usage_stats()
        breakdown = router_with_records.get_cost_breakdown()
        assert breakdown["total_cost"] == pytest.approx(stats.total_estimated_cost, abs=1e-6)
        assert breakdown["total_requests"] == stats.total_requests
