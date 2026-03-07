"""Prometheus data source for metric queries and anomaly detection.

Queries Prometheus HTTP API for time-series metrics and performs lightweight
anomaly detection by comparing current values against a 7-day historical
baseline.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Pre-built PromQL queries keyed by short name
# ---------------------------------------------------------------------------

BUILTIN_QUERIES: dict[str, str] = {
    "cpu": (
        'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"'
        "{service_filter}}}[5m])) by (pod)"
    ),
    "memory": (
        'sum(container_memory_working_set_bytes{{namespace="{namespace}"'
        "{service_filter}}}) by (pod)"
    ),
    "error_rate": (
        'sum(rate(http_requests_total{{namespace="{namespace}"'
        '{service_filter},status_code=~"5.."}}[5m]))'
        " / "
        'sum(rate(http_requests_total{{namespace="{namespace}"'
        "{service_filter}}}[5m]))"
    ),
    "latency_p99": (
        "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket"
        '{{namespace="{namespace}"{service_filter}}}[5m])) by (le))'
    ),
    "restarts": (
        "sum(increase(kube_pod_container_status_restarts_total"
        '{{namespace="{namespace}"{service_filter}}}[1h])) by (pod)'
    ),
}


def _service_filter(service: str | None) -> str:
    """Return a PromQL label matcher fragment for a service, or empty string."""
    if service:
        return f',service="{service}"'
    return ""


class TimeSeries:
    """A single Prometheus time series with helper methods."""

    def __init__(self, metric: dict[str, str], values: list[tuple[float, str]]) -> None:
        self.metric = metric
        self.values = [(ts, float(v)) for ts, v in values if v != "NaN"]

    @property
    def latest(self) -> float | None:
        """Return the most recent value, or None if empty."""
        return self.values[-1][1] if self.values else None

    @property
    def mean(self) -> float:
        """Arithmetic mean of all values."""
        if not self.values:
            return 0.0
        return sum(v for _, v in self.values) / len(self.values)

    @property
    def stddev(self) -> float:
        """Population standard deviation."""
        if len(self.values) < 2:
            return 0.0
        m = self.mean
        return math.sqrt(sum((v - m) ** 2 for _, v in self.values) / len(self.values))


class PrometheusSource:
    """Async client for querying Prometheus and detecting anomalies.

    Args:
        base_url: Prometheus server URL (e.g. ``http://prometheus:9090``).
        timeout: HTTP request timeout in seconds.
    """

    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Core query methods
    # ------------------------------------------------------------------

    async def query_instant(self, query: str) -> list[TimeSeries]:
        """Execute an instant query against ``/api/v1/query``.

        Returns a list of :class:`TimeSeries`, each containing a single
        data point.
        """
        resp = await self._client.get("/api/v1/query", params={"query": query})
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "success":
            logger.warning("prometheus_query_failed", query=query, response=data)
            return []

        results: list[TimeSeries] = []
        for item in data.get("data", {}).get("result", []):
            ts_val = item.get("value", [])
            results.append(TimeSeries(item.get("metric", {}), [tuple(ts_val)] if ts_val else []))
        return results

    async def query_range(
        self,
        query: str,
        start: datetime | None = None,
        end: datetime | None = None,
        step: str = "60s",
    ) -> list[TimeSeries]:
        """Execute a range query against ``/api/v1/query_range``.

        Defaults to the last hour if *start*/*end* are not provided.
        """
        now = datetime.now(tz=UTC)
        end = end or now
        start = start or (now - timedelta(hours=1))

        params: dict[str, Any] = {
            "query": query,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step,
        }
        resp = await self._client.get("/api/v1/query_range", params=params)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "success":
            logger.warning("prometheus_range_query_failed", query=query, response=data)
            return []

        return [
            TimeSeries(item.get("metric", {}), item.get("values", []))
            for item in data.get("data", {}).get("result", [])
        ]

    # ------------------------------------------------------------------
    # High-level investigation helpers
    # ------------------------------------------------------------------

    async def collect_signals(
        self,
        namespace: str,
        service: str | None = None,
    ) -> dict[str, list[TimeSeries]]:
        """Run all built-in queries and return results keyed by signal name."""
        svc = _service_filter(service)
        signals: dict[str, list[TimeSeries]] = {}

        for name, template in BUILTIN_QUERIES.items():
            query = template.format(namespace=namespace, service_filter=svc)
            try:
                signals[name] = await self.query_range(query)
            except httpx.HTTPError as exc:
                logger.warning("prometheus_signal_failed", signal=name, error=str(exc))
                signals[name] = []

        return signals

    async def detect_anomalies(
        self,
        query: str,
        namespace: str,
        service: str | None = None,
        *,
        threshold_stddev: float = 2.0,
    ) -> tuple[float | None, float]:
        """Compare the current value to a 7-day baseline.

        Returns ``(current_value, anomaly_score)`` where anomaly_score is
        a float from 0 to 1 (fraction of threshold breached, capped at 1).
        """
        svc = _service_filter(service)
        formatted = query.format(namespace=namespace, service_filter=svc)

        # Current value
        instant = await self.query_instant(formatted)
        current = instant[0].latest if instant else None

        if current is None:
            return None, 0.0

        # 7-day baseline
        now = datetime.now(tz=UTC)
        baseline = await self.query_range(
            formatted,
            start=now - timedelta(days=7),
            end=now - timedelta(hours=1),
            step="3600s",
        )

        if not baseline or not baseline[0].values:
            return current, 0.0

        series = baseline[0]
        mean = series.mean
        std = series.stddev

        if std == 0:
            return current, 0.0

        z_score = abs(current - mean) / std
        anomaly_score = min(z_score / (threshold_stddev * 2), 1.0)

        if z_score > threshold_stddev:
            logger.info(
                "anomaly_detected",
                query=formatted,
                current=current,
                mean=mean,
                stddev=std,
                z_score=round(z_score, 2),
            )

        return current, round(anomaly_score, 4)
