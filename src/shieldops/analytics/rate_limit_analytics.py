"""Rate limit analytics for tracking API usage patterns and abuse detection.

Collects rate-limit events across endpoints, identifies top offenders,
computes quota utilization, detects burst patterns, and provides trend
analysis over configurable time windows.
"""

from __future__ import annotations

import enum
import time
import uuid
from collections import defaultdict
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class LimitAction(enum.StrEnum):
    ALLOWED = "allowed"
    THROTTLED = "throttled"
    BLOCKED = "blocked"
    WARNED = "warned"


class AnalyticsPeriod(enum.StrEnum):
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"


# -- Models --------------------------------------------------------------------


class RateLimitEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    client_id: str
    endpoint: str
    action: LimitAction
    request_count: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)
    recorded_at: float = Field(default_factory=time.time)


class OffenderProfile(BaseModel):
    client_id: str
    total_violations: int
    blocked_count: int
    throttled_count: int
    top_endpoints: list[str] = Field(default_factory=list)
    first_seen: float
    last_seen: float


class QuotaUtilization(BaseModel):
    endpoint: str
    total_requests: int
    allowed: int
    throttled: int
    blocked: int
    utilization_pct: float = 0.0


class TrendBucket(BaseModel):
    period: str
    timestamp: float
    total_events: int
    blocked_events: int


# -- Constants ----------------------------------------------------------------

_PERIOD_SECONDS: dict[AnalyticsPeriod, int] = {
    AnalyticsPeriod.MINUTE: 60,
    AnalyticsPeriod.HOUR: 3600,
    AnalyticsPeriod.DAY: 86400,
    AnalyticsPeriod.WEEK: 604800,
}


# -- Engine --------------------------------------------------------------------


class RateLimitAnalyticsEngine:
    """Track and analyse rate-limit events for API abuse detection.

    Parameters
    ----------
    max_events:
        Maximum events retained in memory.
    retention_hours:
        How long events are kept before being eligible for eviction.
    """

    def __init__(
        self,
        max_events: int = 100000,
        retention_hours: int = 168,
    ) -> None:
        self._events: list[RateLimitEvent] = []
        self._max_events = max_events
        self._retention_hours = retention_hours

    # -- helpers --------------------------------------------------------------

    def _trim_events(self) -> None:
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events :]

    def _retention_cutoff(self) -> float:
        return time.time() - self._retention_hours * 3600

    # -- public API -----------------------------------------------------------

    def record_event(
        self,
        client_id: str,
        endpoint: str,
        action: LimitAction,
        request_count: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> RateLimitEvent:
        event = RateLimitEvent(
            client_id=client_id,
            endpoint=endpoint,
            action=action,
            request_count=request_count,
            metadata=metadata or {},
        )
        self._events.append(event)
        self._trim_events()
        logger.info(
            "rate_limit_event_recorded",
            event_id=event.id,
            client_id=client_id,
            endpoint=endpoint,
            action=action,
        )
        return event

    def get_top_offenders(self, limit: int = 10) -> list[OffenderProfile]:
        client_map: dict[str, list[RateLimitEvent]] = defaultdict(list)
        for ev in self._events:
            if ev.action in (LimitAction.BLOCKED, LimitAction.THROTTLED):
                client_map[ev.client_id].append(ev)

        profiles: list[OffenderProfile] = []
        for client_id, events in client_map.items():
            blocked = sum(1 for e in events if e.action == LimitAction.BLOCKED)
            throttled = sum(1 for e in events if e.action == LimitAction.THROTTLED)
            endpoint_counts: dict[str, int] = defaultdict(int)
            for e in events:
                endpoint_counts[e.endpoint] += 1
            top_eps = sorted(endpoint_counts, key=endpoint_counts.get, reverse=True)[:5]  # type: ignore[arg-type]
            timestamps = [e.recorded_at for e in events]
            profiles.append(
                OffenderProfile(
                    client_id=client_id,
                    total_violations=len(events),
                    blocked_count=blocked,
                    throttled_count=throttled,
                    top_endpoints=top_eps,
                    first_seen=min(timestamps),
                    last_seen=max(timestamps),
                )
            )

        profiles.sort(key=lambda p: p.total_violations, reverse=True)
        return profiles[:limit]

    def get_utilization(
        self,
        endpoint: str | None = None,
    ) -> list[QuotaUtilization]:
        ep_map: dict[str, list[RateLimitEvent]] = defaultdict(list)
        for ev in self._events:
            if endpoint and ev.endpoint != endpoint:
                continue
            ep_map[ev.endpoint].append(ev)

        results: list[QuotaUtilization] = []
        for ep, events in ep_map.items():
            total = sum(e.request_count for e in events)
            allowed = sum(e.request_count for e in events if e.action == LimitAction.ALLOWED)
            throttled = sum(e.request_count for e in events if e.action == LimitAction.THROTTLED)
            blocked = sum(e.request_count for e in events if e.action == LimitAction.BLOCKED)
            util_pct = ((throttled + blocked) / total * 100) if total > 0 else 0.0
            results.append(
                QuotaUtilization(
                    endpoint=ep,
                    total_requests=total,
                    allowed=allowed,
                    throttled=throttled,
                    blocked=blocked,
                    utilization_pct=round(util_pct, 2),
                )
            )
        return results

    def get_trends(
        self,
        period: AnalyticsPeriod = AnalyticsPeriod.HOUR,
        hours: int = 24,
    ) -> list[TrendBucket]:
        cutoff = time.time() - hours * 3600
        bucket_size = _PERIOD_SECONDS[period]

        buckets: dict[float, list[RateLimitEvent]] = defaultdict(list)
        for ev in self._events:
            if ev.recorded_at < cutoff:
                continue
            bucket_ts = (ev.recorded_at // bucket_size) * bucket_size
            buckets[bucket_ts].append(ev)

        results: list[TrendBucket] = []
        for ts in sorted(buckets):
            events = buckets[ts]
            blocked = sum(1 for e in events if e.action == LimitAction.BLOCKED)
            results.append(
                TrendBucket(
                    period=period.value,
                    timestamp=ts,
                    total_events=len(events),
                    blocked_events=blocked,
                )
            )
        return results

    def get_burst_detection(
        self,
        window_seconds: int = 60,
        threshold: int = 100,
    ) -> list[dict[str, Any]]:
        now = time.time()
        window_start = now - window_seconds

        client_counts: dict[str, int] = defaultdict(int)
        for ev in self._events:
            if ev.recorded_at >= window_start:
                client_counts[ev.client_id] += 1

        bursts: list[dict[str, Any]] = []
        for client_id, count in client_counts.items():
            if count > threshold:
                bursts.append(
                    {
                        "client_id": client_id,
                        "event_count": count,
                        "window_seconds": window_seconds,
                        "threshold": threshold,
                        "detected_at": now,
                    }
                )

        bursts.sort(key=lambda b: b["event_count"], reverse=True)
        return bursts

    def list_events(
        self,
        client_id: str | None = None,
        endpoint: str | None = None,
        limit: int = 100,
    ) -> list[RateLimitEvent]:
        events = list(self._events)
        if client_id:
            events = [e for e in events if e.client_id == client_id]
        if endpoint:
            events = [e for e in events if e.endpoint == endpoint]
        return events[-limit:]

    def get_endpoint_analytics(self, path: str) -> dict[str, Any]:
        events = [e for e in self._events if e.endpoint == path]
        if not events:
            return {
                "endpoint": path,
                "total_events": 0,
                "unique_clients": 0,
                "action_breakdown": {},
                "requests_total": 0,
            }

        action_counts: dict[str, int] = defaultdict(int)
        clients: set[str] = set()
        total_requests = 0
        for ev in events:
            action_counts[ev.action.value] += 1
            clients.add(ev.client_id)
            total_requests += ev.request_count

        return {
            "endpoint": path,
            "total_events": len(events),
            "unique_clients": len(clients),
            "action_breakdown": dict(action_counts),
            "requests_total": total_requests,
        }

    def get_stats(self) -> dict[str, Any]:
        blocked = sum(1 for e in self._events if e.action == LimitAction.BLOCKED)
        throttled = sum(1 for e in self._events if e.action == LimitAction.THROTTLED)
        unique_clients = len({e.client_id for e in self._events})
        unique_endpoints = len({e.endpoint for e in self._events})
        return {
            "total_events": len(self._events),
            "blocked_events": blocked,
            "throttled_events": throttled,
            "unique_clients": unique_clients,
            "unique_endpoints": unique_endpoints,
            "max_events": self._max_events,
            "retention_hours": self._retention_hours,
        }
