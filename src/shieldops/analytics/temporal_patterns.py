"""Temporal pattern discovery for time-based incident correlation.

Analyzes incident event streams to detect recurring hourly, daily, weekly, and
seasonal patterns, enabling proactive risk-window identification.
"""

from __future__ import annotations

import enum
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class PatternType(enum.StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    SEASONAL = "seasonal"


class PatternConfidence(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# -- Models --------------------------------------------------------------------


class IncidentEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    service: str
    incident_type: str
    severity: str = "warning"
    timestamp: float = Field(default_factory=time.time)
    day_of_week: int = 0
    hour_of_day: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    recorded_at: float = Field(default_factory=time.time)


class TemporalPattern(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    service: str
    pattern_type: PatternType
    description: str
    occurrences: int = 0
    confidence: PatternConfidence = PatternConfidence.LOW
    peak_hour: int | None = None
    peak_day: int | None = None
    recommendation: str = ""
    detected_at: float = Field(default_factory=time.time)


class PatternSummary(BaseModel):
    service: str
    total_events: int = 0
    patterns_found: int = 0
    top_pattern: str = ""
    risk_windows: list[str] = Field(default_factory=list)


# -- Engine --------------------------------------------------------------------

_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class TemporalPatternEngine:
    """Discover recurring temporal patterns in incident event streams.

    Parameters
    ----------
    max_events:
        Maximum number of incident events to retain.
    min_occurrences:
        Minimum occurrences required to classify a grouping as a pattern.
    """

    def __init__(
        self,
        max_events: int = 100000,
        min_occurrences: int = 3,
    ) -> None:
        self._events: list[IncidentEvent] = []
        self._max_events = max_events
        self._min_occurrences = min_occurrences

    def record_event(
        self,
        service: str,
        incident_type: str,
        severity: str = "warning",
        timestamp: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> IncidentEvent:
        ts = timestamp if timestamp is not None else time.time()

        # Derive day_of_week (0=Monday) and hour_of_day from timestamp
        dt = datetime.fromtimestamp(ts, tz=UTC)
        day_of_week = dt.weekday()
        hour_of_day = dt.hour

        event = IncidentEvent(
            service=service,
            incident_type=incident_type,
            severity=severity,
            timestamp=ts,
            day_of_week=day_of_week,
            hour_of_day=hour_of_day,
            metadata=metadata or {},
        )
        self._events.append(event)

        # Trim to max_events
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events :]

        logger.info(
            "incident_event_recorded",
            event_id=event.id,
            service=service,
            incident_type=incident_type,
        )
        return event

    def _compute_confidence(self, occurrences: int) -> PatternConfidence:
        if occurrences >= 20:
            return PatternConfidence.VERY_HIGH
        if occurrences >= 10:
            return PatternConfidence.HIGH
        if occurrences >= 5:
            return PatternConfidence.MEDIUM
        return PatternConfidence.LOW

    def detect_patterns(
        self,
        service: str | None = None,
    ) -> list[TemporalPattern]:
        events = self._events
        if service:
            events = [e for e in events if e.service == service]

        patterns: list[TemporalPattern] = []

        # Group by service for pattern detection
        service_events: dict[str, list[IncidentEvent]] = {}
        for event in events:
            service_events.setdefault(event.service, []).append(event)

        for svc, svc_events in service_events.items():
            # Hourly patterns: group by service + hour_of_day
            hour_counter: Counter[int] = Counter()
            for e in svc_events:
                hour_counter[e.hour_of_day] += 1

            for hour, count in hour_counter.items():
                if count >= self._min_occurrences:
                    confidence = self._compute_confidence(count)
                    patterns.append(
                        TemporalPattern(
                            service=svc,
                            pattern_type=PatternType.HOURLY,
                            description=(f"{count} incidents at hour {hour:02d}:00 UTC for {svc}"),
                            occurrences=count,
                            confidence=confidence,
                            peak_hour=hour,
                            recommendation=(
                                f"Schedule proactive monitoring for {svc} around {hour:02d}:00 UTC"
                            ),
                        )
                    )

            # Daily patterns: group by service + day_of_week
            day_counter: Counter[int] = Counter()
            for e in svc_events:
                day_counter[e.day_of_week] += 1

            for day, count in day_counter.items():
                if count >= self._min_occurrences:
                    day_name = _DAY_NAMES[day] if day < len(_DAY_NAMES) else str(day)
                    confidence = self._compute_confidence(count)
                    patterns.append(
                        TemporalPattern(
                            service=svc,
                            pattern_type=PatternType.DAILY,
                            description=(f"{count} incidents on {day_name}s for {svc}"),
                            occurrences=count,
                            confidence=confidence,
                            peak_day=day,
                            recommendation=(
                                f"Increase staffing or alerting for {svc} on {day_name}s"
                            ),
                        )
                    )

        logger.info("patterns_detected", count=len(patterns))
        return patterns

    def get_service_summary(self, service: str) -> PatternSummary:
        events = [e for e in self._events if e.service == service]
        patterns = self.detect_patterns(service=service)

        top_pattern = ""
        if patterns:
            best = max(patterns, key=lambda p: p.occurrences)
            top_pattern = best.description

        risk_windows = self.get_risk_windows(service)
        risk_labels = [w.get("label", "") for w in risk_windows if w.get("label")]

        return PatternSummary(
            service=service,
            total_events=len(events),
            patterns_found=len(patterns),
            top_pattern=top_pattern,
            risk_windows=risk_labels,
        )

    def get_risk_windows(
        self,
        service: str,
    ) -> list[dict[str, Any]]:
        events = [e for e in self._events if e.service == service]
        if not events:
            return []

        # Find hour windows with highest incident frequency
        hour_counter: Counter[int] = Counter()
        for e in events:
            hour_counter[e.hour_of_day] += 1

        windows: list[dict[str, Any]] = []
        for hour, count in hour_counter.most_common(5):
            if count >= self._min_occurrences:
                windows.append(
                    {
                        "hour": hour,
                        "label": f"{hour:02d}:00-{(hour + 1) % 24:02d}:00 UTC",
                        "incident_count": count,
                        "service": service,
                    }
                )
        return windows

    def list_events(
        self,
        service: str | None = None,
        limit: int = 100,
    ) -> list[IncidentEvent]:
        events = self._events
        if service:
            events = [e for e in events if e.service == service]
        return events[-limit:]

    def get_patterns(
        self,
        service: str | None = None,
        pattern_type: PatternType | None = None,
    ) -> list[TemporalPattern]:
        patterns = self.detect_patterns(service=service)
        if pattern_type:
            patterns = [p for p in patterns if p.pattern_type == pattern_type]
        return patterns

    def clear_events(self, before_timestamp: float | None = None) -> int:
        if before_timestamp is None:
            count = len(self._events)
            self._events.clear()
            logger.info("events_cleared", count=count)
            return count
        original = len(self._events)
        self._events = [e for e in self._events if e.timestamp >= before_timestamp]
        removed = original - len(self._events)
        logger.info("events_cleared", count=removed, before=before_timestamp)
        return removed

    def get_stats(self) -> dict[str, Any]:
        services = {e.service for e in self._events}
        patterns = self.detect_patterns()
        return {
            "total_events": len(self._events),
            "services": len(services),
            "patterns_detected": len(patterns),
        }
