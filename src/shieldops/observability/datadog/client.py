"""Datadog metric source implementation.

Queries Datadog via its API for metric data, anomaly detection,
and instant queries used by investigation agents.
"""

from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from shieldops.models.base import TimeRange
from shieldops.observability.base import MetricSource

logger = structlog.get_logger()


class DatadogSource(MetricSource):
    """Datadog metric querying via HTTP API."""

    source_name = "datadog"

    def __init__(
        self,
        api_key: str,
        app_key: str,
        site: str = "datadoghq.com",
    ) -> None:
        self._site = site
        self._base_url = f"https://api.{site}"
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "DD-API-KEY": api_key,
                "DD-APPLICATION-KEY": app_key,
                "Content-Type": "application/json",
            },
        )

    async def query_metric(
        self,
        metric_name: str,
        labels: dict[str, str],
        time_range: TimeRange,
        step: str = "1m",
    ) -> list[dict[str, Any]]:
        """Query a time-series metric from Datadog."""
        query = self._build_query(metric_name, labels)
        from_ts = int(time_range.start.timestamp())
        to_ts = int(time_range.end.timestamp())

        try:
            response = await self._client.get(
                f"{self._base_url}/api/v1/query",
                params={
                    "query": query,
                    "from": from_ts,
                    "to": to_ts,
                },
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for series in data.get("series", []):
                point_list = series.get("pointlist", [])
                tag_set = series.get("tag_set", [])
                series_labels = self._parse_tags(tag_set)
                for point in point_list:
                    if len(point) >= 2 and point[1] is not None:
                        ts_ms = point[0]
                        results.append(
                            {
                                "timestamp": datetime.fromtimestamp(
                                    ts_ms / 1000, tz=UTC
                                ).isoformat(),
                                "value": float(point[1]),
                                "labels": series_labels,
                            }
                        )
            return results

        except httpx.HTTPError as e:
            logger.error("datadog_query_failed", query=query, error=str(e))
            return []
        except Exception as e:
            logger.error("datadog_query_error", query=query, error=str(e))
            return []

    async def query_instant(self, query: str) -> list[dict[str, Any]]:
        """Execute an instant query (latest 5 minutes)."""
        now = int(datetime.now(UTC).timestamp())
        from_ts = now - 300  # 5 minutes ago

        try:
            response = await self._client.get(
                f"{self._base_url}/api/v1/query",
                params={
                    "query": query,
                    "from": from_ts,
                    "to": now,
                },
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for series in data.get("series", []):
                point_list = series.get("pointlist", [])
                tag_set = series.get("tag_set", [])
                series_labels = self._parse_tags(tag_set)
                # Take the last data point as the "instant" value
                if point_list and point_list[-1][1] is not None:
                    last = point_list[-1]
                    results.append(
                        {
                            "metric": series.get("metric", query),
                            "value": float(last[1]),
                            "labels": series_labels,
                            "timestamp": datetime.fromtimestamp(last[0] / 1000, tz=UTC).isoformat(),
                        }
                    )
            return results

        except httpx.HTTPError as e:
            logger.error("datadog_instant_query_failed", query=query, error=str(e))
            return []
        except Exception as e:
            logger.error("datadog_instant_query_error", query=query, error=str(e))
            return []

    async def detect_anomalies(
        self,
        metric_name: str,
        labels: dict[str, str],
        time_range: TimeRange,
        baseline_range: TimeRange,
        threshold_percent: float = 50.0,
    ) -> list[dict[str, Any]]:
        """Compare current metric values against a baseline period."""
        current_data = await self.query_metric(metric_name, labels, time_range)
        baseline_data = await self.query_metric(metric_name, labels, baseline_range)

        if not current_data or not baseline_data:
            return []

        baseline_values = [d["value"] for d in baseline_data if d["value"] is not None]
        if not baseline_values:
            return []
        baseline_avg = sum(baseline_values) / len(baseline_values)

        if baseline_avg == 0:
            return []

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
            "datadog_anomaly_detection",
            metric=metric_name,
            anomalies_found=len(anomalies),
            baseline_avg=round(baseline_avg, 2),
        )
        return anomalies

    @staticmethod
    def _build_query(metric_name: str, labels: dict[str, str]) -> str:
        """Build a Datadog query string from metric name and labels."""
        if labels:
            tag_filter = ",".join(f"{k}:{v}" for k, v in labels.items())
            return f"avg:{metric_name}{{{tag_filter}}}"
        return f"avg:{metric_name}{{*}}"

    @staticmethod
    def _parse_tags(tag_set: list[str]) -> dict[str, str]:
        """Parse Datadog tag_set list into a dict."""
        labels: dict[str, str] = {}
        for tag in tag_set:
            if ":" in tag:
                k, v = tag.split(":", 1)
                labels[k] = v
            else:
                labels[tag] = ""
        return labels

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
