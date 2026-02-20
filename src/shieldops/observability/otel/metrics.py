"""OpenTelemetry metrics pipeline for agent-level observability.

Provides a MeterProvider + OTLP exporter that ships counters and
histograms for agent executions alongside the existing TracerProvider.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()

_meter: Any = None


def init_metrics(
    exporter_endpoint: str = "http://localhost:4317",
) -> None:
    """Initialize OTel metrics with OTLP gRPC exporter."""
    global _meter  # noqa: PLW0603
    try:
        from opentelemetry import metrics
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import (
            PeriodicExportingMetricReader,
        )
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": "shieldops"})
        exporter = OTLPMetricExporter(endpoint=exporter_endpoint, insecure=True)
        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=30_000)
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(provider)
        _meter = metrics.get_meter("shieldops")
        logger.info("otel_metrics_initialized", endpoint=exporter_endpoint)
    except ImportError:
        logger.warning("otel_metrics_deps_missing")
    except Exception as e:
        logger.warning("otel_metrics_init_failed", error=str(e))


def get_meter() -> Any:
    """Return the global OTel meter (or None if not initialized)."""
    return _meter


class AgentMetrics:
    """Convenience wrapper for agent-level OTel metrics."""

    def __init__(self, agent_type: str) -> None:
        self._agent_type = agent_type
        self._execution_counter: Any = None
        self._duration_histogram: Any = None
        self._error_counter: Any = None
        self._setup()

    def _setup(self) -> None:
        meter = get_meter()
        if meter is None:
            return
        self._execution_counter = meter.create_counter(
            name=f"shieldops.agent.{self._agent_type}.executions",
            description=(f"Total executions of {self._agent_type} agent"),
        )
        self._duration_histogram = meter.create_histogram(
            name=(f"shieldops.agent.{self._agent_type}.duration_ms"),
            description=(f"Execution duration of {self._agent_type} agent in ms"),
            unit="ms",
        )
        self._error_counter = meter.create_counter(
            name=f"shieldops.agent.{self._agent_type}.errors",
            description=(f"Error count for {self._agent_type} agent"),
        )

    def record_execution(self, duration_ms: float, success: bool = True) -> None:
        """Record an agent execution with duration and outcome."""
        if self._execution_counter:
            self._execution_counter.add(1, {"success": str(success)})
        if self._duration_histogram:
            self._duration_histogram.record(duration_ms)
        if not success and self._error_counter:
            self._error_counter.add(1)
