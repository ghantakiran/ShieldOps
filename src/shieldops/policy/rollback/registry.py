"""Rollback event registry with pattern detection and success tracking.

Records rollback events, analyzes common triggers, and detects recurring
patterns to surface actionable recommendations for improving deployment
reliability.
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


class RollbackResult(enum.StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class RollbackType(enum.StrEnum):
    DEPLOYMENT = "deployment"
    CONFIG = "config"
    INFRASTRUCTURE = "infrastructure"
    DATABASE = "database"
    FEATURE_FLAG = "feature_flag"


# -- Models --------------------------------------------------------------------


class RollbackEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    service: str
    rollback_type: RollbackType
    result: RollbackResult = RollbackResult.SUCCESS
    trigger_reason: str = ""
    from_version: str = ""
    to_version: str = ""
    duration_seconds: float = 0.0
    initiated_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class RollbackTrigger(BaseModel):
    trigger_reason: str
    count: int
    services: list[str] = Field(default_factory=list)


class RollbackPattern(BaseModel):
    pattern: str
    frequency: int
    services: list[str] = Field(default_factory=list)
    avg_duration: float
    recommendation: str = ""


# -- Registry ------------------------------------------------------------------


class RollbackRegistry:
    """Track rollback events and detect recurring patterns.

    Parameters
    ----------
    max_events:
        Maximum rollback events to retain.
    pattern_lookback_days:
        Number of days to look back when detecting patterns.
    """

    def __init__(
        self,
        max_events: int = 10000,
        pattern_lookback_days: int = 90,
    ) -> None:
        self._events: dict[str, RollbackEvent] = {}
        self._max_events = max_events
        self._pattern_lookback_days = pattern_lookback_days

    def record_rollback(
        self,
        service: str,
        rollback_type: RollbackType,
        result: RollbackResult = RollbackResult.SUCCESS,
        trigger_reason: str = "",
        from_version: str = "",
        to_version: str = "",
        duration_seconds: float = 0.0,
        initiated_by: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> RollbackEvent:
        if len(self._events) >= self._max_events:
            raise ValueError(f"Maximum events limit reached: {self._max_events}")
        event = RollbackEvent(
            service=service,
            rollback_type=rollback_type,
            result=result,
            trigger_reason=trigger_reason,
            from_version=from_version,
            to_version=to_version,
            duration_seconds=duration_seconds,
            initiated_by=initiated_by,
            metadata=metadata or {},
        )
        self._events[event.id] = event
        logger.info(
            "rollback_recorded",
            event_id=event.id,
            service=service,
            rollback_type=rollback_type,
            result=result,
        )
        return event

    def get_rollback(self, event_id: str) -> RollbackEvent | None:
        return self._events.get(event_id)

    def list_rollbacks(
        self,
        service: str | None = None,
        rollback_type: RollbackType | None = None,
    ) -> list[RollbackEvent]:
        events = list(self._events.values())
        if service:
            events = [e for e in events if e.service == service]
        if rollback_type:
            events = [e for e in events if e.rollback_type == rollback_type]
        return events

    def delete_rollback(self, event_id: str) -> bool:
        return self._events.pop(event_id, None) is not None

    def analyze_triggers(self) -> list[RollbackTrigger]:
        trigger_map: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"services": set()})
        count_map: dict[str, int] = defaultdict(int)

        for event in self._events.values():
            if not event.trigger_reason:
                continue
            count_map[event.trigger_reason] += 1
            trigger_map[event.trigger_reason]["services"].add(event.service)

        triggers: list[RollbackTrigger] = []
        for reason, count in sorted(count_map.items(), key=lambda x: x[1], reverse=True):
            triggers.append(
                RollbackTrigger(
                    trigger_reason=reason,
                    count=count,
                    services=sorted(trigger_map[reason]["services"]),
                )
            )
        return triggers

    def detect_patterns(self) -> list[RollbackPattern]:
        cutoff = time.time() - (self._pattern_lookback_days * 86400)
        recent = [e for e in self._events.values() if e.created_at >= cutoff]

        # Group by service
        service_events: dict[str, list[RollbackEvent]] = defaultdict(list)
        for event in recent:
            service_events[event.service].append(event)

        patterns: list[RollbackPattern] = []
        for service, events in service_events.items():
            if len(events) < 2:
                continue
            avg_dur = sum(e.duration_seconds for e in events) / len(events)
            recommendation = ""
            if len(events) >= 5:
                recommendation = (
                    f"Service '{service}' has {len(events)} rollbacks in the lookback "
                    f"period. Consider reviewing deployment pipeline and testing."
                )
            elif len(events) >= 2:
                recommendation = (
                    f"Service '{service}' shows repeated rollbacks. "
                    f"Investigate root causes to improve stability."
                )
            patterns.append(
                RollbackPattern(
                    pattern=f"repeated_rollback:{service}",
                    frequency=len(events),
                    services=[service],
                    avg_duration=round(avg_dur, 2),
                    recommendation=recommendation,
                )
            )

        return sorted(patterns, key=lambda p: p.frequency, reverse=True)

    def get_success_rate(self, service: str | None = None) -> dict[str, Any]:
        events = list(self._events.values())
        if service:
            events = [e for e in events if e.service == service]
        total = len(events)
        if total == 0:
            return {
                "total": 0,
                "success_count": 0,
                "partial_count": 0,
                "failed_count": 0,
                "success_rate": 0.0,
            }
        success_count = sum(1 for e in events if e.result == RollbackResult.SUCCESS)
        partial_count = sum(1 for e in events if e.result == RollbackResult.PARTIAL)
        failed_count = sum(1 for e in events if e.result == RollbackResult.FAILED)
        return {
            "total": total,
            "success_count": success_count,
            "partial_count": partial_count,
            "failed_count": failed_count,
            "success_rate": round(success_count / total, 4),
        }

    def get_rollback_by_service(self, service: str) -> list[RollbackEvent]:
        return [e for e in self._events.values() if e.service == service]

    def get_stats(self) -> dict[str, Any]:
        success = sum(1 for e in self._events.values() if e.result == RollbackResult.SUCCESS)
        services = {e.service for e in self._events.values()}
        return {
            "total_events": len(self._events),
            "successful_rollbacks": success,
            "unique_services": len(services),
            "pattern_lookback_days": self._pattern_lookback_days,
        }
