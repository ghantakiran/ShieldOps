"""Base interface for observability data sources.

All observability integrations (Splunk, Prometheus, Datadog, etc.) implement
this interface so investigation agents can query telemetry uniformly.
"""

from abc import ABC, abstractmethod
from typing import Any

from shieldops.models.base import TimeRange


class LogSource(ABC):
    """Abstract interface for log querying."""

    source_name: str

    @abstractmethod
    async def query_logs(
        self,
        query: str,
        time_range: TimeRange,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Execute a log query and return matching entries.

        Returns list of dicts with at minimum: timestamp, message, level.
        """

    @abstractmethod
    async def search_patterns(
        self,
        resource_id: str,
        patterns: list[str],
        time_range: TimeRange,
    ) -> dict[str, list[dict[str, Any]]]:
        """Search logs for specific patterns (error signatures, keywords).

        Returns dict mapping pattern → list of matching log entries.
        """


class MetricSource(ABC):
    """Abstract interface for metric querying."""

    source_name: str

    @abstractmethod
    async def query_metric(
        self,
        metric_name: str,
        labels: dict[str, str],
        time_range: TimeRange,
        step: str = "1m",
    ) -> list[dict[str, Any]]:
        """Query a time-series metric.

        Returns list of {timestamp, value} data points.
        """

    @abstractmethod
    async def query_instant(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        """Execute an instant query (current value).

        Returns list of {metric, value, labels} results.
        """

    @abstractmethod
    async def detect_anomalies(
        self,
        metric_name: str,
        labels: dict[str, str],
        time_range: TimeRange,
        baseline_range: TimeRange,
        threshold_percent: float = 50.0,
    ) -> list[dict[str, Any]]:
        """Compare current metric values against a baseline period.

        Returns list of anomalies where deviation exceeds threshold.
        """


class TraceSource(ABC):
    """Abstract interface for distributed trace querying."""

    source_name: str

    @abstractmethod
    async def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        """Get a single trace by ID with all spans."""

    @abstractmethod
    async def search_traces(
        self,
        service: str,
        time_range: TimeRange,
        min_duration_ms: float | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search traces by service, duration, or error status."""

    @abstractmethod
    async def find_bottleneck(
        self,
        service: str,
        time_range: TimeRange,
    ) -> dict[str, Any] | None:
        """Identify the slowest span/service in recent traces for a service."""
