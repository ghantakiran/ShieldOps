"""Agent-level Prometheus metrics collector for ShieldOps.

Registers agent-specific counters, histograms, and gauges on the shared
``MetricsRegistry`` so they are exposed alongside HTTP metrics at
``GET /metrics`` in Prometheus text exposition format.

Usage::

    from shieldops.observability.agent_metrics import get_agent_metrics

    metrics = get_agent_metrics()
    metrics.record_execution("investigation", "success", duration_seconds=12.5)
    metrics.record_llm_call("investigation", "claude-sonnet-4-20250514", 2.3, 1200, 450)
    metrics.record_confidence("investigation", 0.87)
    metrics.set_active("investigation", 3)
"""

from __future__ import annotations

import structlog

from shieldops.api.middleware.metrics import MetricsRegistry, get_metrics_registry

logger = structlog.get_logger()

# ── Histogram bucket definitions ─────────────────────────────────

# Agent execution: spans seconds to minutes (remediation can be long)
EXECUTION_DURATION_BUCKETS: tuple[float, ...] = (
    1.0,
    5.0,
    10.0,
    30.0,
    60.0,
    120.0,
    300.0,
    600.0,
)

# LLM call latency: sub-second to tens of seconds
LLM_LATENCY_BUCKETS: tuple[float, ...] = (
    0.5,
    1.0,
    2.0,
    5.0,
    10.0,
    30.0,
)

# Confidence scores: 0.1 to 1.0 in 0.1 increments
CONFIDENCE_BUCKETS: tuple[float, ...] = (
    0.1,
    0.2,
    0.3,
    0.4,
    0.5,
    0.6,
    0.7,
    0.8,
    0.9,
    1.0,
)

# ── Metric names ─────────────────────────────────────────────────

EXECUTIONS_TOTAL = "shieldops_agent_executions_total"
EXECUTION_DURATION = "shieldops_agent_execution_duration_seconds"
LLM_CALLS_TOTAL = "shieldops_agent_llm_calls_total"
LLM_LATENCY = "shieldops_agent_llm_latency_seconds"
LLM_TOKENS_TOTAL = "shieldops_agent_llm_tokens_total"
CONFIDENCE_SCORE = "shieldops_agent_confidence_score"
AGENT_ACTIVE = "shieldops_agent_active"


class AgentMetricsCollector:
    """Records agent-level metrics on the shared ``MetricsRegistry``.

    Each method corresponds to a specific instrumentation point in the
    agent lifecycle.  All operations are thread-safe (delegated to the
    registry's internal lock).
    """

    def __init__(self, registry: MetricsRegistry | None = None) -> None:
        self._registry = registry or get_metrics_registry()

    # ── Public recording methods ─────────────────────────────────

    def record_execution(
        self,
        agent_type: str,
        status: str,
        duration_seconds: float,
    ) -> None:
        """Record a completed agent execution.

        Args:
            agent_type: Agent kind
                (investigation, remediation, security, learning).
            status: Outcome -- ``success``, ``failure``, or ``timeout``.
            duration_seconds: Wall-clock execution time.
        """
        self._registry.inc_counter(
            EXECUTIONS_TOTAL,
            {"agent_type": agent_type, "status": status},
        )
        self._registry.observe_histogram(
            EXECUTION_DURATION,
            {"agent_type": agent_type},
            duration_seconds,
            buckets=EXECUTION_DURATION_BUCKETS,
        )
        logger.debug(
            "agent_execution_recorded",
            agent_type=agent_type,
            status=status,
            duration_seconds=duration_seconds,
        )

    def record_llm_call(
        self,
        agent_type: str,
        model: str,
        latency_seconds: float,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record an LLM invocation with token usage.

        Args:
            agent_type: Agent kind that made the call.
            model: LLM model identifier (e.g. ``claude-sonnet-4-20250514``).
            latency_seconds: Round-trip latency of the LLM call.
            input_tokens: Number of input (prompt) tokens.
            output_tokens: Number of output (completion) tokens.
        """
        call_labels = {"agent_type": agent_type, "model": model}

        self._registry.inc_counter(LLM_CALLS_TOTAL, call_labels)
        self._registry.observe_histogram(
            LLM_LATENCY,
            call_labels,
            latency_seconds,
            buckets=LLM_LATENCY_BUCKETS,
        )

        # Token counters -- use amount parameter for bulk increments
        self._registry.inc_counter(
            LLM_TOKENS_TOTAL,
            {
                "agent_type": agent_type,
                "model": model,
                "direction": "input",
            },
            amount=input_tokens,
        )
        self._registry.inc_counter(
            LLM_TOKENS_TOTAL,
            {
                "agent_type": agent_type,
                "model": model,
                "direction": "output",
            },
            amount=output_tokens,
        )

        logger.debug(
            "agent_llm_call_recorded",
            agent_type=agent_type,
            model=model,
            latency_seconds=latency_seconds,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def record_confidence(self, agent_type: str, score: float) -> None:
        """Record an agent confidence score observation.

        Args:
            agent_type: Agent kind that produced the score.
            score: Confidence value between 0.0 and 1.0.
        """
        self._registry.observe_histogram(
            CONFIDENCE_SCORE,
            {"agent_type": agent_type},
            score,
            buckets=CONFIDENCE_BUCKETS,
        )
        logger.debug(
            "agent_confidence_recorded",
            agent_type=agent_type,
            score=score,
        )

    def set_active(self, agent_type: str, count: int) -> None:
        """Set the number of currently active agents of a given type.

        Args:
            agent_type: Agent kind.
            count: Number of currently running agents.
        """
        self._registry.set_gauge(
            AGENT_ACTIVE,
            {"agent_type": agent_type},
            count,
        )
        logger.debug(
            "agent_active_updated",
            agent_type=agent_type,
            count=count,
        )


# ── Module-level singleton ───────────────────────────────────────

_collector: AgentMetricsCollector | None = None


def get_agent_metrics() -> AgentMetricsCollector:
    """Return the module-level singleton ``AgentMetricsCollector``."""
    global _collector
    if _collector is None:
        _collector = AgentMetricsCollector()
    return _collector


def reset_agent_metrics() -> None:
    """Destroy the singleton (useful in tests)."""
    global _collector
    _collector = None
