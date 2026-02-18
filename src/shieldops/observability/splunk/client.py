"""Splunk log source implementation.

Queries Splunk via its REST API for log data using SPL (Search Processing Language).
Used by investigation agents for log analysis and pattern searching.
"""

import asyncio
from datetime import timezone
from typing import Any

import httpx
import structlog

from shieldops.models.base import TimeRange
from shieldops.observability.base import LogSource

logger = structlog.get_logger()


class SplunkSource(LogSource):
    """Splunk log querying via REST API."""

    source_name = "splunk"

    def __init__(
        self,
        url: str,
        token: str,
        index: str = "main",
        verify_ssl: bool = True,
    ) -> None:
        self._url = url.rstrip("/")
        self._index = index
        self._client = httpx.AsyncClient(
            timeout=60.0,
            verify=verify_ssl,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )

    async def query_logs(
        self,
        query: str,
        time_range: TimeRange,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Execute a log query against Splunk.

        `query` is used as the source filter (e.g. 'namespace/pod_name').
        Translates to SPL: search index=<idx> source=<query> earliest=<start> latest=<end>
        """
        earliest = time_range.start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        latest = time_range.end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        spl = (
            f'search index={self._index} source="{query}" '
            f"earliest={earliest} latest={latest} "
            f"| head {limit}"
        )

        try:
            results = await self._run_search(spl)
            return self._normalize_results(results)
        except httpx.HTTPError as e:
            logger.error("splunk_query_failed", query=spl, error=str(e))
            return []
        except Exception as e:
            logger.error("splunk_query_error", query=spl, error=str(e))
            return []

    async def search_patterns(
        self,
        resource_id: str,
        patterns: list[str],
        time_range: TimeRange,
    ) -> dict[str, list[dict[str, Any]]]:
        """Search Splunk logs for specific patterns."""
        earliest = time_range.start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        latest = time_range.end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        results: dict[str, list[dict[str, Any]]] = {p: [] for p in patterns}

        for pattern in patterns:
            spl = (
                f'search index={self._index} source="{resource_id}" '
                f"earliest={earliest} latest={latest} "
                f'"{pattern}"'
            )
            try:
                raw = await self._run_search(spl)
                results[pattern] = self._normalize_results(raw)
            except httpx.HTTPError as e:
                logger.error(
                    "splunk_pattern_search_failed",
                    pattern=pattern,
                    error=str(e),
                )
            except Exception as e:
                logger.error(
                    "splunk_pattern_search_error",
                    pattern=pattern,
                    error=str(e),
                )

        logger.info(
            "splunk_pattern_search",
            resource_id=resource_id,
            patterns=patterns,
            matches={p: len(v) for p, v in results.items()},
        )
        return results

    async def _run_search(self, spl: str) -> list[dict[str, Any]]:
        """Create a Splunk search job, poll for completion, and return results."""
        # Create search job
        response = await self._client.post(
            f"{self._url}/services/search/jobs",
            data={"search": spl, "output_mode": "json", "exec_mode": "oneshot"},
        )
        response.raise_for_status()
        data = response.json()

        # oneshot mode returns results directly
        return data.get("results", [])

    async def _run_search_async_job(self, spl: str) -> list[dict[str, Any]]:
        """Create a normal (non-oneshot) search job and poll for results."""
        # Create search job
        response = await self._client.post(
            f"{self._url}/services/search/jobs",
            data={"search": spl, "output_mode": "json"},
        )
        response.raise_for_status()
        sid = response.json().get("sid")
        if not sid:
            return []

        # Poll for completion
        for _ in range(60):
            status_resp = await self._client.get(
                f"{self._url}/services/search/jobs/{sid}",
                params={"output_mode": "json"},
            )
            status_resp.raise_for_status()
            job = status_resp.json().get("entry", [{}])[0].get("content", {})
            if job.get("isDone") == "1" or job.get("isDone") is True:
                break
            await asyncio.sleep(1)

        # Fetch results
        results_resp = await self._client.get(
            f"{self._url}/services/search/jobs/{sid}/results",
            params={"output_mode": "json", "count": 1000},
        )
        results_resp.raise_for_status()
        return results_resp.json().get("results", [])

    def _normalize_results(self, raw_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize Splunk results to standard log entry format."""
        entries = []
        for result in raw_results:
            entries.append({
                "timestamp": result.get("_time", ""),
                "message": result.get("_raw", result.get("message", "")),
                "level": self._detect_level(result),
                "source": result.get("source", "splunk"),
            })
        return entries

    @staticmethod
    def _detect_level(result: dict[str, Any]) -> str:
        """Detect log level from Splunk result fields."""
        # Check explicit level fields first
        for field in ("log_level", "level", "severity"):
            if field in result:
                return result[field].lower()

        # Fall back to content analysis
        raw = result.get("_raw", "").upper()
        if "FATAL" in raw or "PANIC" in raw:
            return "fatal"
        if "ERROR" in raw or "ERR " in raw:
            return "error"
        if "WARN" in raw:
            return "warning"
        if "DEBUG" in raw:
            return "debug"
        return "info"

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
