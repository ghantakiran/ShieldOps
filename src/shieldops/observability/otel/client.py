"""Jaeger trace source implementation.

Queries Jaeger via its HTTP API for distributed trace data used by
investigation agents for latency analysis and bottleneck detection.
"""

from datetime import UTC
from typing import Any

import httpx
import structlog

from shieldops.models.base import TimeRange
from shieldops.observability.base import TraceSource

logger = structlog.get_logger()


class JaegerSource(TraceSource):
    """Jaeger distributed trace querying via HTTP API."""

    source_name = "jaeger"

    def __init__(self, url: str) -> None:
        self._url = url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        """Get a single trace by ID with all spans."""
        try:
            response = await self._client.get(
                f"{self._url}/api/traces/{trace_id}",
            )
            response.raise_for_status()
            data = response.json()

            traces = data.get("data", [])
            if not traces:
                return None

            trace = traces[0]
            spans = self._parse_spans(trace)
            root_service = self._find_root_service(trace)

            return {
                "trace_id": trace.get("traceID", trace_id),
                "root_service": root_service,
                "spans": spans,
                "span_count": len(spans),
            }

        except httpx.HTTPError as e:
            logger.error("jaeger_get_trace_failed", trace_id=trace_id, error=str(e))
            return None
        except Exception as e:
            logger.error("jaeger_get_trace_error", trace_id=trace_id, error=str(e))
            return None

    async def search_traces(
        self,
        service: str,
        time_range: TimeRange,
        min_duration_ms: float | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search traces by service, duration, or error status."""
        # Jaeger uses microseconds for timestamps
        start_us = int(time_range.start.astimezone(UTC).timestamp() * 1_000_000)
        end_us = int(time_range.end.astimezone(UTC).timestamp() * 1_000_000)

        params: dict[str, Any] = {
            "service": service,
            "start": start_us,
            "end": end_us,
            "limit": limit,
        }
        if min_duration_ms is not None:
            params["minDuration"] = f"{int(min_duration_ms)}ms"
        if status == "error":
            params["tags"] = '{"error":"true"}'

        try:
            response = await self._client.get(
                f"{self._url}/api/traces",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            summaries = []
            for trace in data.get("data", []):
                spans = self._parse_spans(trace)
                root_service = self._find_root_service(trace)
                total_duration = max((s["duration_ms"] for s in spans), default=0)
                has_error = any(s.get("status") == "error" for s in spans)

                summaries.append(
                    {
                        "trace_id": trace.get("traceID", ""),
                        "root_service": root_service,
                        "span_count": len(spans),
                        "total_duration_ms": total_duration,
                        "has_error": has_error,
                        "services": list({s["service"] for s in spans}),
                    }
                )
            return summaries

        except httpx.HTTPError as e:
            logger.error("jaeger_search_failed", service=service, error=str(e))
            return []
        except Exception as e:
            logger.error("jaeger_search_error", service=service, error=str(e))
            return []

    async def find_bottleneck(
        self,
        service: str,
        time_range: TimeRange,
    ) -> dict[str, Any] | None:
        """Identify the slowest span/service in recent traces."""
        traces = await self.search_traces(service, time_range, limit=10)
        if not traces:
            return None

        # Get the trace with the longest duration and fetch full details
        slowest_trace = max(traces, key=lambda t: t["total_duration_ms"])
        trace_detail = await self.get_trace(slowest_trace["trace_id"])
        if not trace_detail or not trace_detail["spans"]:
            return None

        # Find the slowest individual span
        slowest_span = max(trace_detail["spans"], key=lambda s: s["duration_ms"])

        return {
            "trace_id": slowest_trace["trace_id"],
            "service": slowest_span["service"],
            "operation": slowest_span["operation"],
            "duration_ms": slowest_span["duration_ms"],
            "span_count": trace_detail["span_count"],
        }

    def _parse_spans(self, trace: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse spans from Jaeger trace format."""
        # Build process map: processID -> serviceName
        processes = trace.get("processes", {})
        process_map: dict[str, str] = {}
        for pid, proc in processes.items():
            process_map[pid] = proc.get("serviceName", "unknown")

        spans = []
        for span in trace.get("spans", []):
            # Duration in Jaeger is in microseconds
            duration_us = span.get("duration", 0)
            has_error = any(
                tag.get("key") == "error" and tag.get("value") is True
                for tag in span.get("tags", [])
            )
            references = span.get("references", [])
            parent_span_id = None
            for ref in references:
                if ref.get("refType") == "CHILD_OF":
                    parent_span_id = ref.get("spanID")
                    break

            spans.append(
                {
                    "span_id": span.get("spanID", ""),
                    "service": process_map.get(span.get("processID", ""), "unknown"),
                    "operation": span.get("operationName", ""),
                    "duration_ms": round(duration_us / 1000, 2),
                    "status": "error" if has_error else "ok",
                    "parent_span_id": parent_span_id,
                }
            )
        return spans

    @staticmethod
    def _find_root_service(trace: dict[str, Any]) -> str:
        """Find the root service (span with no parent) in a trace."""
        processes = trace.get("processes", {})
        process_map: dict[str, str] = {}
        for pid, proc in processes.items():
            process_map[pid] = proc.get("serviceName", "unknown")

        for span in trace.get("spans", []):
            references = span.get("references", [])
            if not references:
                return process_map.get(span.get("processID", ""), "unknown")

        # Fallback: return first span's service
        if trace.get("spans"):
            first = trace["spans"][0]
            return process_map.get(first.get("processID", ""), "unknown")
        return "unknown"

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
