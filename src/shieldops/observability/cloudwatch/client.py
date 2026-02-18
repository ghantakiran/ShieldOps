"""CloudWatch Logs observability source."""

import asyncio
from functools import partial
from typing import Any

import structlog

from shieldops.models.base import TimeRange
from shieldops.observability.base import LogSource

logger = structlog.get_logger()


class CloudWatchLogsSource(LogSource):
    """CloudWatch Logs integration for log querying."""

    source_name = "cloudwatch"

    def __init__(self, log_group: str, region: str = "us-east-1") -> None:
        self._log_group = log_group
        self._region = region
        self._client: Any = None

    def _ensure_client(self) -> None:
        if self._client is None:
            import boto3

            self._client = boto3.client("logs", region_name=self._region)

    async def _run_sync(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def query_logs(
        self,
        query: str,
        time_range: TimeRange,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Execute a CloudWatch Logs Insights query."""
        self._ensure_client()

        start_resp = await self._run_sync(
            self._client.start_query,
            logGroupName=self._log_group,
            startTime=int(time_range.start.timestamp()),
            endTime=int(time_range.end.timestamp()),
            queryString=query,
            limit=limit,
        )
        query_id = start_resp["queryId"]

        # Poll for results
        for _ in range(60):
            resp = await self._run_sync(self._client.get_query_results, queryId=query_id)
            if resp["status"] == "Complete":
                return [
                    {field["field"]: field["value"] for field in row}
                    for row in resp.get("results", [])
                ]
            await asyncio.sleep(1)

        logger.warning("cloudwatch_query_timeout", query_id=query_id)
        return []

    async def search_patterns(
        self,
        resource_id: str,
        patterns: list[str],
        time_range: TimeRange,
    ) -> dict[str, list[dict[str, Any]]]:
        """Search CloudWatch logs for specific patterns using filter_log_events."""
        self._ensure_client()
        results: dict[str, list[dict[str, Any]]] = {}

        for pattern in patterns:
            resp = await self._run_sync(
                self._client.filter_log_events,
                logGroupName=self._log_group,
                startTime=int(time_range.start.timestamp() * 1000),
                endTime=int(time_range.end.timestamp() * 1000),
                filterPattern=pattern,
                limit=50,
            )
            results[pattern] = [
                {
                    "timestamp": evt.get("timestamp"),
                    "message": evt.get("message", ""),
                    "level": "error" if "error" in evt.get("message", "").lower() else "info",
                    "log_stream": evt.get("logStreamName"),
                }
                for evt in resp.get("events", [])
            ]

        return results

    async def close(self) -> None:
        """No persistent connection to close for boto3."""
        pass
