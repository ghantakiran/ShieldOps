"""Tool functions for the Investigation Agent.

These bridge observability connectors and infrastructure connectors to the
agent's LangGraph nodes. Each tool is a self-contained async function that
queries external systems and returns structured data.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from shieldops.connectors.base import ConnectorRouter
from shieldops.models.base import TimeRange
from shieldops.observability.base import LogSource, MetricSource, TraceSource

logger = structlog.get_logger()


class InvestigationToolkit:
    """Collection of tools available to the investigation agent.

    Injected into nodes at graph construction time to decouple agent logic
    from specific connector implementations.
    """

    def __init__(
        self,
        connector_router: ConnectorRouter | None = None,
        log_sources: list[LogSource] | None = None,
        metric_sources: list[MetricSource] | None = None,
        trace_sources: list[TraceSource] | None = None,
    ) -> None:
        self._router = connector_router
        self._log_sources = log_sources or []
        self._metric_sources = metric_sources or []
        self._trace_sources = trace_sources or []

    async def query_logs(
        self,
        resource_id: str,
        time_range: TimeRange | None = None,
        patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Query logs across all registered log sources.

        Returns aggregated log entries and pattern matches.
        """
        if time_range is None:
            now = datetime.now(UTC)
            time_range = TimeRange(start=now - timedelta(hours=1), end=now)

        all_entries: list[dict[str, Any]] = []
        pattern_matches: dict[str, list[dict[str, Any]]] = {}

        for source in self._log_sources:
            try:
                entries = await source.query_logs(resource_id, time_range)
                all_entries.extend(entries)

                if patterns:
                    matches = await source.search_patterns(resource_id, patterns, time_range)
                    for pattern, hits in matches.items():
                        pattern_matches.setdefault(pattern, []).extend(hits)
            except Exception as e:
                logger.error(
                    "log_query_failed",
                    source=source.source_name,
                    resource_id=resource_id,
                    error=str(e),
                )

        # Classify entries by severity
        error_entries = [e for e in all_entries if e.get("level") in ("error", "fatal")]
        warning_entries = [e for e in all_entries if e.get("level") == "warning"]

        return {
            "total_entries": len(all_entries),
            "error_count": len(error_entries),
            "warning_count": len(warning_entries),
            "entries": all_entries[:100],  # Cap at 100 for LLM context
            "error_entries": error_entries[:30],
            "warning_entries": warning_entries[:20],
            "pattern_matches": {k: v[:10] for k, v in pattern_matches.items()},
            "sources_queried": [s.source_name for s in self._log_sources],
        }

    async def query_metrics(
        self,
        resource_id: str,
        metric_names: list[str] | None = None,
        time_range: TimeRange | None = None,
    ) -> dict[str, Any]:
        """Query metrics across all registered metric sources.

        If metric_names not provided, queries standard SRE metrics:
        CPU, memory, error rate, latency, restarts.
        """
        if time_range is None:
            now = datetime.now(UTC)
            time_range = TimeRange(start=now - timedelta(hours=1), end=now)

        baseline_range = TimeRange(
            start=time_range.start - timedelta(hours=24),
            end=time_range.start - timedelta(hours=23),
        )

        # Default SRE metrics to check if none specified
        if metric_names is None:
            metric_names = self._default_metrics_for_resource(resource_id)

        labels = self._labels_from_resource_id(resource_id)
        all_anomalies: list[dict[str, Any]] = []
        current_values: dict[str, Any] = {}

        for source in self._metric_sources:
            for metric in metric_names:
                try:
                    # Get current value
                    instant = await source.query_instant(
                        f"{metric}{{{self._format_labels(labels)}}}"
                    )
                    if instant:
                        current_values[metric] = instant[0].get("value")

                    # Detect anomalies against baseline
                    anomalies = await source.detect_anomalies(
                        metric_name=metric,
                        labels=labels,
                        time_range=time_range,
                        baseline_range=baseline_range,
                        threshold_percent=50.0,
                    )
                    all_anomalies.extend(anomalies)
                except Exception as e:
                    logger.error(
                        "metric_query_failed",
                        source=source.source_name,
                        metric=metric,
                        error=str(e),
                    )

        return {
            "current_values": current_values,
            "anomalies": all_anomalies,
            "anomaly_count": len(all_anomalies),
            "metrics_checked": metric_names,
            "sources_queried": [s.source_name for s in self._metric_sources],
        }

    async def query_traces(
        self,
        service_name: str,
        time_range: TimeRange | None = None,
    ) -> dict[str, Any]:
        """Query distributed traces for a service to find bottlenecks."""
        if time_range is None:
            now = datetime.now(UTC)
            time_range = TimeRange(start=now - timedelta(hours=1), end=now)

        results: dict[str, Any] = {
            "traces": [],
            "bottleneck": None,
            "error_traces": [],
            "sources_queried": [],
        }

        for source in self._trace_sources:
            try:
                results["sources_queried"].append(source.source_name)

                # Find slow traces
                slow = await source.search_traces(
                    service=service_name,
                    time_range=time_range,
                    min_duration_ms=1000,
                    limit=10,
                )
                results["traces"].extend(slow)

                # Find error traces
                errors = await source.search_traces(
                    service=service_name,
                    time_range=time_range,
                    status="error",
                    limit=10,
                )
                results["error_traces"].extend(errors)

                # Identify bottleneck
                bottleneck = await source.find_bottleneck(service_name, time_range)
                if bottleneck:
                    results["bottleneck"] = bottleneck
            except Exception as e:
                logger.error(
                    "trace_query_failed",
                    source=source.source_name,
                    service=service_name,
                    error=str(e),
                )

        return results

    async def get_k8s_events(
        self,
        resource_id: str,
        time_range: TimeRange | None = None,
    ) -> list[dict[str, Any]]:
        """Get Kubernetes events for a resource."""
        if self._router is None:
            return []

        if time_range is None:
            now = datetime.now(UTC)
            time_range = TimeRange(start=now - timedelta(hours=1), end=now)

        try:
            connector = self._router.get("kubernetes")
            return await connector.get_events(resource_id, time_range)
        except (ValueError, Exception) as e:
            logger.error("k8s_events_failed", resource_id=resource_id, error=str(e))
            return []

    async def get_resource_health(self, resource_id: str, provider: str = "kubernetes") -> dict:
        """Get health status of a specific resource."""
        if self._router is None:
            return {"healthy": None, "status": "unknown", "message": "No connector available"}

        try:
            connector = self._router.get(provider)
            health = await connector.get_health(resource_id)
            return health.model_dump()
        except (ValueError, Exception) as e:
            logger.error("health_check_failed", resource_id=resource_id, error=str(e))
            return {"healthy": None, "status": "error", "message": str(e)}

    # --- Private helpers ---

    @staticmethod
    def _default_metrics_for_resource(resource_id: str) -> list[str]:
        """Standard SRE metrics to check for any resource."""
        return [
            "container_cpu_usage_seconds_total",
            "container_memory_usage_bytes",
            "kube_pod_container_status_restarts_total",
            "container_network_receive_bytes_total",
        ]

    @staticmethod
    def _labels_from_resource_id(resource_id: str) -> dict[str, str]:
        """Extract Prometheus labels from a resource ID like 'namespace/pod'."""
        parts = resource_id.split("/", 1)
        if len(parts) == 2:
            return {"namespace": parts[0], "pod": parts[1]}
        return {"pod": parts[0]}

    @staticmethod
    def _format_labels(labels: dict[str, str]) -> str:
        """Format labels dict as PromQL selector string."""
        return ",".join(f'{k}="{v}"' for k, v in labels.items())
