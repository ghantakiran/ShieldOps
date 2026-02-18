"""Prometheus metric source implementation.

Queries Prometheus via its HTTP API for metric data, anomaly detection,
and instant queries used by investigation agents.
"""

from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from shieldops.models.base import TimeRange
from shieldops.observability.base import MetricSource

logger = structlog.get_logger()


class PrometheusSource(MetricSource):
    """Prometheus metric querying via HTTP API."""

    source_name = "prometheus"

    def __init__(self, url: str = "http://localhost:9090") -> None:
        self._url = url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def query_metric(
        self,
        metric_name: str,
        labels: dict[str, str],
        time_range: TimeRange,
        step: str = "1m",
    ) -> list[dict[str, Any]]:
        """Query a range of metric data points."""
        label_selector = ",".join(f'{k}="{v}"' for k, v in labels.items())
        query = f"{metric_name}{{{label_selector}}}" if labels else metric_name

        try:
            response = await self._client.get(
                f"{self._url}/api/v1/query_range",
                params={
                    "query": query,
                    "start": time_range.start.timestamp(),
                    "end": time_range.end.timestamp(),
                    "step": step,
                },
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for series in data.get("data", {}).get("result", []):
                for timestamp, value in series.get("values", []):
                    results.append(
                        {
                            "timestamp": datetime.fromtimestamp(timestamp, tz=UTC).isoformat(),
                            "value": float(value),
                            "labels": series.get("metric", {}),
                        }
                    )
            return results

        except httpx.HTTPError as e:
            logger.error("prometheus_query_failed", query=query, error=str(e))
            return []

    async def query_instant(self, query: str) -> list[dict[str, Any]]:
        """Execute an instant PromQL query."""
        try:
            response = await self._client.get(
                f"{self._url}/api/v1/query",
                params={"query": query},
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for series in data.get("data", {}).get("result", []):
                value = series.get("value", [None, None])
                results.append(
                    {
                        "metric": series.get("metric", {}),
                        "value": float(value[1]) if value[1] is not None else None,
                        "timestamp": datetime.fromtimestamp(float(value[0]), tz=UTC).isoformat()
                        if value[0]
                        else None,
                    }
                )
            return results

        except httpx.HTTPError as e:
            logger.error("prometheus_instant_query_failed", query=query, error=str(e))
            return []

    async def detect_anomalies(
        self,
        metric_name: str,
        labels: dict[str, str],
        time_range: TimeRange,
        baseline_range: TimeRange,
        threshold_percent: float = 50.0,
    ) -> list[dict[str, Any]]:
        """Compare current values against baseline to detect anomalies."""
        current_data = await self.query_metric(metric_name, labels, time_range)
        baseline_data = await self.query_metric(metric_name, labels, baseline_range)

        if not current_data or not baseline_data:
            return []

        # Calculate baseline average
        baseline_values = [d["value"] for d in baseline_data if d["value"] is not None]
        if not baseline_values:
            return []
        baseline_avg = sum(baseline_values) / len(baseline_values)

        if baseline_avg == 0:
            return []

        # Find data points that deviate beyond threshold
        anomalies = []
        for point in current_data:
            if point["value"] is None:
                continue
            deviation = ((point["value"] - baseline_avg) / baseline_avg) * 100
            if abs(deviation) >= threshold_percent:
                anomalies.append(
                    {
                        "timestamp": point["timestamp"],
                        "current_value": point["value"],
                        "baseline_value": baseline_avg,
                        "deviation_percent": round(deviation, 2),
                        "labels": point.get("labels", {}),
                        "metric_name": metric_name,
                    }
                )

        logger.info(
            "prometheus_anomaly_detection",
            metric=metric_name,
            anomalies_found=len(anomalies),
            baseline_avg=round(baseline_avg, 2),
        )
        return anomalies

    async def close(self) -> None:
        await self._client.aclose()
