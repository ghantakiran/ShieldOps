"""Tests for agent-level Prometheus metrics collector and LLM decorator.

Covers: counter increments, histogram bucketing, gauge updates, label
correctness, singleton pattern, Prometheus text exposition output,
LLM tracking decorator behaviour, exception handling, and independent
tracking across multiple agent types.
"""

from __future__ import annotations

import asyncio

import pytest

from shieldops.api.middleware.metrics import MetricsRegistry, get_metrics_registry
from shieldops.observability.agent_metrics import (
    AGENT_ACTIVE,
    CONFIDENCE_BUCKETS,
    CONFIDENCE_SCORE,
    EXECUTION_DURATION,
    EXECUTION_DURATION_BUCKETS,
    EXECUTIONS_TOTAL,
    LLM_CALLS_TOTAL,
    LLM_LATENCY,
    LLM_LATENCY_BUCKETS,
    LLM_TOKENS_TOTAL,
    AgentMetricsCollector,
    get_agent_metrics,
    reset_agent_metrics,
)
from shieldops.utils.llm_metrics import estimate_tokens, track_llm_call

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_state():
    """Ensure every test starts with a clean registry and collector."""
    MetricsRegistry.reset_instance()
    reset_agent_metrics()
    yield
    MetricsRegistry.reset_instance()
    reset_agent_metrics()


@pytest.fixture
def registry() -> MetricsRegistry:
    return get_metrics_registry()


@pytest.fixture
def collector(registry: MetricsRegistry) -> AgentMetricsCollector:
    return AgentMetricsCollector(registry=registry)


# ── record_execution tests ──────────────────────────────────────────


class TestRecordExecution:
    def test_increments_counter(self, collector, registry):
        collector.record_execution("investigation", "success", 5.0)
        key = registry._label_key(
            EXECUTIONS_TOTAL,
            {"agent_type": "investigation", "status": "success"},
        )
        assert registry.counters[key] == 1

    def test_increments_counter_multiple_times(self, collector, registry):
        collector.record_execution("investigation", "success", 5.0)
        collector.record_execution("investigation", "success", 10.0)
        collector.record_execution("investigation", "failure", 2.0)
        success_key = registry._label_key(
            EXECUTIONS_TOTAL,
            {"agent_type": "investigation", "status": "success"},
        )
        failure_key = registry._label_key(
            EXECUTIONS_TOTAL,
            {"agent_type": "investigation", "status": "failure"},
        )
        assert registry.counters[success_key] == 2
        assert registry.counters[failure_key] == 1

    def test_observes_duration_histogram(self, collector, registry):
        collector.record_execution("remediation", "success", 15.0)
        key = registry._label_key(
            EXECUTION_DURATION,
            {"agent_type": "remediation"},
        )
        assert key in registry.histograms
        assert registry._histogram_counts[key] == 1
        assert registry._histogram_sums[key] == pytest.approx(15.0)

    def test_duration_histogram_uses_correct_buckets(
        self,
        collector,
        registry,
    ):
        collector.record_execution("security", "success", 1.0)
        key = registry._label_key(
            EXECUTION_DURATION,
            {"agent_type": "security"},
        )
        buckets = registry.histograms[key]
        boundaries = [le for le, _ in buckets]
        expected = list(EXECUTION_DURATION_BUCKETS) + [float("inf")]
        assert boundaries == expected

    def test_timeout_status_tracked(self, collector, registry):
        collector.record_execution("learning", "timeout", 600.0)
        key = registry._label_key(
            EXECUTIONS_TOTAL,
            {"agent_type": "learning", "status": "timeout"},
        )
        assert registry.counters[key] == 1


# ── record_llm_call tests ──────────────────────────────────────────


class TestRecordLlmCall:
    def test_increments_call_counter(self, collector, registry):
        collector.record_llm_call(
            "investigation",
            "claude-sonnet-4-20250514",
            2.0,
            1000,
            500,
        )
        key = registry._label_key(
            LLM_CALLS_TOTAL,
            {"agent_type": "investigation", "model": "claude-sonnet-4-20250514"},
        )
        assert registry.counters[key] == 1

    def test_observes_latency_histogram(self, collector, registry):
        collector.record_llm_call(
            "investigation",
            "claude-sonnet-4-20250514",
            3.5,
            800,
            200,
        )
        key = registry._label_key(
            LLM_LATENCY,
            {"agent_type": "investigation", "model": "claude-sonnet-4-20250514"},
        )
        assert key in registry.histograms
        assert registry._histogram_sums[key] == pytest.approx(3.5)

    def test_latency_histogram_uses_correct_buckets(
        self,
        collector,
        registry,
    ):
        collector.record_llm_call(
            "security",
            "gpt-4o",
            1.0,
            500,
            100,
        )
        key = registry._label_key(
            LLM_LATENCY,
            {"agent_type": "security", "model": "gpt-4o"},
        )
        boundaries = [le for le, _ in registry.histograms[key]]
        expected = list(LLM_LATENCY_BUCKETS) + [float("inf")]
        assert boundaries == expected

    def test_tracks_input_tokens(self, collector, registry):
        collector.record_llm_call(
            "investigation",
            "claude-sonnet-4-20250514",
            2.0,
            1200,
            450,
        )
        key = registry._label_key(
            LLM_TOKENS_TOTAL,
            {
                "agent_type": "investigation",
                "model": "claude-sonnet-4-20250514",
                "direction": "input",
            },
        )
        assert registry.counters[key] == 1200

    def test_tracks_output_tokens(self, collector, registry):
        collector.record_llm_call(
            "investigation",
            "claude-sonnet-4-20250514",
            2.0,
            1200,
            450,
        )
        key = registry._label_key(
            LLM_TOKENS_TOTAL,
            {
                "agent_type": "investigation",
                "model": "claude-sonnet-4-20250514",
                "direction": "output",
            },
        )
        assert registry.counters[key] == 450

    def test_token_counts_accumulate(self, collector, registry):
        collector.record_llm_call("investigation", "m1", 1.0, 100, 50)
        collector.record_llm_call("investigation", "m1", 1.0, 200, 75)
        input_key = registry._label_key(
            LLM_TOKENS_TOTAL,
            {"agent_type": "investigation", "model": "m1", "direction": "input"},
        )
        output_key = registry._label_key(
            LLM_TOKENS_TOTAL,
            {"agent_type": "investigation", "model": "m1", "direction": "output"},
        )
        assert registry.counters[input_key] == 300
        assert registry.counters[output_key] == 125


# ── record_confidence tests ─────────────────────────────────────────


class TestRecordConfidence:
    def test_records_confidence_histogram(self, collector, registry):
        collector.record_confidence("investigation", 0.87)
        key = registry._label_key(
            CONFIDENCE_SCORE,
            {"agent_type": "investigation"},
        )
        assert key in registry.histograms
        assert registry._histogram_counts[key] == 1
        assert registry._histogram_sums[key] == pytest.approx(0.87)

    def test_confidence_histogram_uses_correct_buckets(
        self,
        collector,
        registry,
    ):
        collector.record_confidence("security", 0.5)
        key = registry._label_key(
            CONFIDENCE_SCORE,
            {"agent_type": "security"},
        )
        boundaries = [le for le, _ in registry.histograms[key]]
        expected = list(CONFIDENCE_BUCKETS) + [float("inf")]
        assert boundaries == expected

    def test_low_confidence_in_correct_buckets(self, collector, registry):
        collector.record_confidence("remediation", 0.15)
        key = registry._label_key(
            CONFIDENCE_SCORE,
            {"agent_type": "remediation"},
        )
        for le, count in registry.histograms[key]:
            if le < 0.15:
                assert count == 0, f"bucket le={le} should be 0"
            else:
                assert count == 1, f"bucket le={le} should be 1"


# ── set_active tests ────────────────────────────────────────────────


class TestSetActive:
    def test_sets_gauge_value(self, collector, registry):
        collector.set_active("investigation", 3)
        key = registry._label_key(
            AGENT_ACTIVE,
            {"agent_type": "investigation"},
        )
        assert registry.gauges[key] == 3

    def test_overwrites_previous_value(self, collector, registry):
        collector.set_active("investigation", 5)
        collector.set_active("investigation", 2)
        key = registry._label_key(
            AGENT_ACTIVE,
            {"agent_type": "investigation"},
        )
        assert registry.gauges[key] == 2

    def test_zero_active(self, collector, registry):
        collector.set_active("security", 3)
        collector.set_active("security", 0)
        key = registry._label_key(
            AGENT_ACTIVE,
            {"agent_type": "security"},
        )
        assert registry.gauges[key] == 0


# ── Label correctness ──────────────────────────────────────────────


class TestLabelCorrectness:
    def test_execution_labels(self, collector, registry):
        collector.record_execution("security", "failure", 1.0)
        output = registry.collect()
        assert 'agent_type="security"' in output
        assert 'status="failure"' in output

    def test_llm_labels_include_model(self, collector, registry):
        collector.record_llm_call("learning", "gpt-4o", 1.0, 100, 50)
        output = registry.collect()
        assert 'agent_type="learning"' in output
        assert 'model="gpt-4o"' in output

    def test_token_labels_include_direction(self, collector, registry):
        collector.record_llm_call("investigation", "m1", 1.0, 100, 50)
        output = registry.collect()
        assert 'direction="input"' in output
        assert 'direction="output"' in output


# ── Singleton pattern ──────────────────────────────────────────────


class TestSingletonPattern:
    def test_get_agent_metrics_returns_same_instance(self):
        a = get_agent_metrics()
        b = get_agent_metrics()
        assert a is b

    def test_reset_agent_metrics_clears_singleton(self):
        a = get_agent_metrics()
        reset_agent_metrics()
        b = get_agent_metrics()
        assert a is not b


# ── Prometheus text exposition ─────────────────────────────────────


class TestPrometheusOutput:
    def test_execution_counter_in_collect(self, collector, registry):
        collector.record_execution("investigation", "success", 5.0)
        output = registry.collect()
        assert EXECUTIONS_TOTAL in output
        assert "# TYPE" in output

    def test_histogram_buckets_in_collect(self, collector, registry):
        collector.record_execution("investigation", "success", 5.0)
        output = registry.collect()
        assert f"{EXECUTION_DURATION}_bucket" in output
        assert f"{EXECUTION_DURATION}_sum" in output
        assert f"{EXECUTION_DURATION}_count" in output

    def test_gauge_in_collect(self, collector, registry):
        collector.set_active("remediation", 2)
        output = registry.collect()
        assert AGENT_ACTIVE in output
        assert 'agent_type="remediation"' in output
        assert "} 2" in output

    def test_all_metric_types_in_collect(self, collector, registry):
        collector.record_execution("investigation", "success", 5.0)
        collector.record_llm_call("investigation", "m1", 1.0, 100, 50)
        collector.record_confidence("investigation", 0.9)
        collector.set_active("investigation", 1)
        output = registry.collect()
        assert EXECUTIONS_TOTAL in output
        assert EXECUTION_DURATION in output
        assert LLM_CALLS_TOTAL in output
        assert LLM_LATENCY in output
        assert LLM_TOKENS_TOTAL in output
        assert CONFIDENCE_SCORE in output
        assert AGENT_ACTIVE in output


# ── Multiple agent types tracked independently ──────────────────────


class TestMultipleAgentTypes:
    def test_independent_execution_counters(self, collector, registry):
        collector.record_execution("investigation", "success", 5.0)
        collector.record_execution("remediation", "success", 10.0)
        collector.record_execution("security", "failure", 3.0)

        inv_key = registry._label_key(
            EXECUTIONS_TOTAL,
            {"agent_type": "investigation", "status": "success"},
        )
        rem_key = registry._label_key(
            EXECUTIONS_TOTAL,
            {"agent_type": "remediation", "status": "success"},
        )
        sec_key = registry._label_key(
            EXECUTIONS_TOTAL,
            {"agent_type": "security", "status": "failure"},
        )
        assert registry.counters[inv_key] == 1
        assert registry.counters[rem_key] == 1
        assert registry.counters[sec_key] == 1

    def test_independent_active_gauges(self, collector, registry):
        collector.set_active("investigation", 2)
        collector.set_active("remediation", 5)
        collector.set_active("security", 1)

        inv_key = registry._label_key(
            AGENT_ACTIVE,
            {"agent_type": "investigation"},
        )
        rem_key = registry._label_key(
            AGENT_ACTIVE,
            {"agent_type": "remediation"},
        )
        sec_key = registry._label_key(
            AGENT_ACTIVE,
            {"agent_type": "security"},
        )
        assert registry.gauges[inv_key] == 2
        assert registry.gauges[rem_key] == 5
        assert registry.gauges[sec_key] == 1

    def test_independent_llm_token_counts(self, collector, registry):
        collector.record_llm_call("investigation", "m1", 1.0, 500, 100)
        collector.record_llm_call("remediation", "m1", 2.0, 800, 200)

        inv_input = registry._label_key(
            LLM_TOKENS_TOTAL,
            {"agent_type": "investigation", "model": "m1", "direction": "input"},
        )
        rem_input = registry._label_key(
            LLM_TOKENS_TOTAL,
            {"agent_type": "remediation", "model": "m1", "direction": "input"},
        )
        assert registry.counters[inv_input] == 500
        assert registry.counters[rem_input] == 800


# ── LLM tracking decorator tests ──────────────────────────────────


class TestTrackLlmCallDecorator:
    def test_decorator_records_metrics(self, registry):
        @track_llm_call(agent_type="investigation", model="test-model")
        async def fake_llm(prompt: str) -> dict:
            return {
                "content": "analysis result",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                },
            }

        asyncio.get_event_loop().run_until_complete(
            fake_llm("test prompt"),
        )

        calls_key = registry._label_key(
            LLM_CALLS_TOTAL,
            {"agent_type": "investigation", "model": "test-model"},
        )
        assert registry.counters[calls_key] == 1

    def test_decorator_records_latency(self, registry):
        @track_llm_call(agent_type="investigation", model="test-model")
        async def fake_llm(prompt: str) -> dict:
            return {"content": "result"}

        asyncio.get_event_loop().run_until_complete(
            fake_llm("test prompt"),
        )

        latency_key = registry._label_key(
            LLM_LATENCY,
            {"agent_type": "investigation", "model": "test-model"},
        )
        assert latency_key in registry.histograms
        assert registry._histogram_counts[latency_key] == 1

    def test_decorator_handles_exception_gracefully(self, registry):
        @track_llm_call(agent_type="investigation", model="test-model")
        async def failing_llm(prompt: str) -> dict:
            raise RuntimeError("LLM API error")

        with pytest.raises(RuntimeError, match="LLM API error"):
            asyncio.get_event_loop().run_until_complete(
                failing_llm("test prompt"),
            )

        # Call counter should still be recorded for the failed call
        calls_key = registry._label_key(
            LLM_CALLS_TOTAL,
            {"agent_type": "investigation", "model": "test-model"},
        )
        assert registry.counters[calls_key] == 1

    def test_decorator_returns_original_result(self, registry):
        expected = {"content": "hello", "score": 0.95}

        @track_llm_call(agent_type="security", model="m1")
        async def fake_llm() -> dict:
            return expected

        result = asyncio.get_event_loop().run_until_complete(fake_llm())
        assert result == expected

    def test_decorator_estimates_tokens_from_content(self, registry):
        @track_llm_call(agent_type="investigation", model="m1")
        async def fake_llm(prompt: str) -> dict:
            # No usage dict, so tokens are estimated from content
            return {"content": "x" * 400}  # ~100 tokens

        asyncio.get_event_loop().run_until_complete(
            fake_llm("y" * 200),
        )

        output_key = registry._label_key(
            LLM_TOKENS_TOTAL,
            {"agent_type": "investigation", "model": "m1", "direction": "output"},
        )
        assert registry.counters[output_key] == 100  # 400 / 4

    def test_decorator_uses_unknown_model_when_not_specified(self, registry):
        @track_llm_call(agent_type="learning")
        async def fake_llm() -> dict:
            return {"content": "result"}

        asyncio.get_event_loop().run_until_complete(fake_llm())

        calls_key = registry._label_key(
            LLM_CALLS_TOTAL,
            {"agent_type": "learning", "model": "unknown"},
        )
        assert registry.counters[calls_key] == 1


# ── Token estimation tests ─────────────────────────────────────────


class TestEstimateTokens:
    def test_empty_string_returns_one(self):
        assert estimate_tokens("") == 1

    def test_short_string(self):
        assert estimate_tokens("hi") == 1

    def test_known_length(self):
        # 400 chars / 4 = 100 tokens
        assert estimate_tokens("x" * 400) == 100

    def test_returns_integer(self):
        result = estimate_tokens("hello world")
        assert isinstance(result, int)
