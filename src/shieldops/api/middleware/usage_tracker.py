"""API usage tracking middleware -- records per-endpoint call counts."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import structlog
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()

# Paths that should not be tracked (infrastructure / observability)
_SKIP_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/ready",
        "/metrics",
    }
)


class UsageTracker:
    """In-memory, thread-safe API usage tracker.

    Stores per-org, per-endpoint, per-hour call counts and latencies.
    Designed for lightweight analytics without external dependencies.
    """

    _instance: ClassVar[UsageTracker | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        self._mu = threading.Lock()
        # {org_key: {endpoint: {hour_key: count}}}
        self._counts: dict[str, dict[str, dict[str, int]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(int))
        )
        # {org_key: {endpoint: {hour_key: total_ms}}}
        self._latencies: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        self._total_calls: dict[str, int] = defaultdict(int)

    # -- Singleton access --------------------------------------------------

    @classmethod
    def get_instance(cls) -> UsageTracker:
        """Return the global singleton, creating it on first call."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Destroy the singleton (useful in tests)."""
        with cls._lock:
            cls._instance = None

    # -- Recording ---------------------------------------------------------

    def record(
        self,
        org_id: str | None,
        method: str,
        path: str,
        duration_ms: float = 0.0,
    ) -> None:
        """Record a single API call."""
        key = org_id or "_anonymous"
        endpoint = f"{method} {path}"
        hour = datetime.now(UTC).strftime("%Y-%m-%dT%H")
        with self._mu:
            self._counts[key][endpoint][hour] += 1
            self._latencies[key][endpoint][hour] += duration_ms
            self._total_calls[key] += 1

    # -- Query helpers -----------------------------------------------------

    def _hour_keys_in_range(
        self,
        hours: int,
    ) -> set[str]:
        """Return the set of hour-key strings within the window."""
        now = datetime.now(UTC)
        return {(now - timedelta(hours=i)).strftime("%Y-%m-%dT%H") for i in range(hours)}

    def get_usage(
        self,
        org_id: str | None = None,
        hours: int = 24,
    ) -> dict[str, Any]:
        """Get aggregated usage stats, optionally filtered by org."""
        valid_hours = self._hour_keys_in_range(hours)
        with self._mu:
            orgs = [org_id or "_anonymous"] if org_id is not None else list(self._counts.keys())
            total = 0
            endpoint_count = 0
            seen_endpoints: set[str] = set()
            for org in orgs:
                for ep, hour_map in self._counts.get(org, {}).items():
                    for h, cnt in hour_map.items():
                        if h in valid_hours:
                            total += cnt
                            seen_endpoints.add(ep)
                    endpoint_count = len(seen_endpoints)

        return {
            "period_hours": hours,
            "total_calls": total,
            "unique_endpoints": endpoint_count,
            "org_id": org_id,
        }

    def get_top_endpoints(
        self,
        org_id: str | None = None,
        limit: int = 10,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Get the most-called endpoints within the time window."""
        valid_hours = self._hour_keys_in_range(hours)
        # {endpoint: (count, total_latency_ms)}
        agg: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        with self._mu:
            orgs = [org_id or "_anonymous"] if org_id is not None else list(self._counts.keys())
            for org in orgs:
                for ep, hour_map in self._counts.get(org, {}).items():
                    for h, cnt in hour_map.items():
                        if h in valid_hours:
                            agg[ep][0] += cnt
                            lat_map = self._latencies.get(org, {}).get(ep, {})
                            agg[ep][1] += lat_map.get(h, 0.0)

        ranked = sorted(
            agg.items(),
            key=lambda x: x[1][0],
            reverse=True,
        )[:limit]

        results: list[dict[str, Any]] = []
        for ep, (count, total_lat) in ranked:
            avg_latency = round(total_lat / count, 2) if count else 0.0
            results.append(
                {
                    "endpoint": ep,
                    "count": int(count),
                    "avg_latency_ms": avg_latency,
                }
            )
        return results

    def get_hourly_breakdown(
        self,
        org_id: str | None = None,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Get call volume broken down by hour."""
        valid_hours = self._hour_keys_in_range(hours)
        # {hour_key: count}
        hourly: dict[str, int] = defaultdict(int)
        with self._mu:
            orgs = [org_id or "_anonymous"] if org_id is not None else list(self._counts.keys())
            for org in orgs:
                for _ep, hour_map in self._counts.get(org, {}).items():
                    for h, cnt in hour_map.items():
                        if h in valid_hours:
                            hourly[h] += cnt

        # Return sorted by hour ascending
        return [{"hour": h, "count": hourly[h]} for h in sorted(valid_hours)]

    def get_usage_by_org(
        self,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Get per-organization usage breakdown (admin view)."""
        valid_hours = self._hour_keys_in_range(hours)
        org_totals: dict[str, int] = defaultdict(int)
        with self._mu:
            for org, ep_map in self._counts.items():
                for _ep, hour_map in ep_map.items():
                    for h, cnt in hour_map.items():
                        if h in valid_hours:
                            org_totals[org] += cnt

        ranked = sorted(
            org_totals.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return [{"org_id": org, "total_calls": cnt} for org, cnt in ranked]

    def reset(self) -> None:
        """Clear all stored data (useful in tests)."""
        with self._mu:
            self._counts.clear()
            self._latencies.clear()
            self._total_calls.clear()


def get_usage_tracker() -> UsageTracker:
    """Convenience accessor for the global usage tracker."""
    return UsageTracker.get_instance()


# -- Starlette Middleware --------------------------------------------------


class UsageTrackerMiddleware(BaseHTTPMiddleware):
    """Middleware that records API call counts and latencies."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path

        # Skip infrastructure endpoints
        if path in _SKIP_PATHS:
            return await call_next(request)

        method = request.method
        org_id: str | None = getattr(
            request.state,
            "organization_id",
            None,
        )

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0

        tracker = get_usage_tracker()
        tracker.record(
            org_id=org_id,
            method=method,
            path=path,
            duration_ms=duration_ms,
        )

        return response
