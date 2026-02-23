"""On-Call Fatigue Analyzer — tracks page load, after-hours burden, burnout risk per engineer."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FatigueRisk(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    BURNOUT = "burnout"


class PageUrgency(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TimeOfDay(StrEnum):
    BUSINESS_HOURS = "business_hours"
    AFTER_HOURS = "after_hours"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


# --- Models ---


class PageEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    engineer: str
    service: str = ""
    urgency: PageUrgency = PageUrgency.MEDIUM
    time_of_day: TimeOfDay = TimeOfDay.BUSINESS_HOURS
    acknowledged: bool = False
    resolution_minutes: float = 0.0
    paged_at: float = Field(default_factory=time.time)


class FatigueReport(BaseModel):
    engineer: str
    total_pages: int = 0
    after_hours_pages: int = 0
    after_hours_ratio: float = 0.0
    avg_resolution_minutes: float = 0.0
    fatigue_score: float = 0.0
    risk: FatigueRisk = FatigueRisk.LOW


# --- Analyzer ---


class OnCallFatigueAnalyzer:
    """Tracks page load, after-hours burden, and burnout risk per engineer."""

    def __init__(
        self,
        max_events: int = 100000,
        burnout_threshold: float = 75.0,
    ) -> None:
        self._max_events = max_events
        self._burnout_threshold = burnout_threshold
        self._events: list[PageEvent] = []
        logger.info(
            "oncall_fatigue.initialized",
            max_events=max_events,
            burnout_threshold=burnout_threshold,
        )

    def record_page(
        self,
        engineer: str,
        service: str = "",
        urgency: PageUrgency = PageUrgency.MEDIUM,
        time_of_day: TimeOfDay = TimeOfDay.BUSINESS_HOURS,
        **kw: Any,
    ) -> PageEvent:
        """Record a page event."""
        event = PageEvent(
            engineer=engineer,
            service=service,
            urgency=urgency,
            time_of_day=time_of_day,
            **kw,
        )
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events :]
        logger.info(
            "oncall_fatigue.page_recorded",
            event_id=event.id,
            engineer=engineer,
            urgency=urgency,
            time_of_day=time_of_day,
        )
        return event

    def analyze_fatigue(self, engineer: str) -> FatigueReport:
        """Analyze fatigue for a specific engineer."""
        pages = [e for e in self._events if e.engineer == engineer]
        total = len(pages)
        after_hours = sum(
            1
            for p in pages
            if p.time_of_day in (TimeOfDay.AFTER_HOURS, TimeOfDay.WEEKEND, TimeOfDay.HOLIDAY)
        )
        ah_ratio = round(after_hours / total, 4) if total else 0.0
        resolutions = [p.resolution_minutes for p in pages if p.resolution_minutes > 0]
        avg_res = round(sum(resolutions) / len(resolutions), 2) if resolutions else 0.0
        critical_pages = sum(1 for p in pages if p.urgency == PageUrgency.CRITICAL)
        fatigue_score = min(100.0, total * 2.0 + after_hours * 3.0 + critical_pages * 5.0)
        if fatigue_score >= self._burnout_threshold:
            risk = FatigueRisk.BURNOUT
        elif fatigue_score >= 50.0:
            risk = FatigueRisk.HIGH
        elif fatigue_score >= 25.0:
            risk = FatigueRisk.MODERATE
        else:
            risk = FatigueRisk.LOW
        return FatigueReport(
            engineer=engineer,
            total_pages=total,
            after_hours_pages=after_hours,
            after_hours_ratio=ah_ratio,
            avg_resolution_minutes=avg_res,
            fatigue_score=round(fatigue_score, 2),
            risk=risk,
        )

    def get_team_report(self, engineers: list[str] | None = None) -> list[FatigueReport]:
        """Get fatigue reports for a team."""
        if engineers is None:
            engineers = sorted({e.engineer for e in self._events})
        return [self.analyze_fatigue(eng) for eng in engineers]

    def get_burnout_risks(self) -> list[FatigueReport]:
        """Get engineers at burnout risk."""
        engineers = {e.engineer for e in self._events}
        return [
            report
            for eng in engineers
            if (report := self.analyze_fatigue(eng)).risk in (FatigueRisk.HIGH, FatigueRisk.BURNOUT)
        ]

    def list_events(
        self,
        engineer: str | None = None,
        urgency: PageUrgency | None = None,
        limit: int = 100,
    ) -> list[PageEvent]:
        """List page events with optional filters."""
        results = list(self._events)
        if engineer is not None:
            results = [e for e in results if e.engineer == engineer]
        if urgency is not None:
            results = [e for e in results if e.urgency == urgency]
        return results[-limit:]

    def get_load_distribution(self) -> list[dict[str, Any]]:
        """Get page load distribution across engineers."""
        counts: dict[str, int] = {}
        for e in self._events:
            counts[e.engineer] = counts.get(e.engineer, 0) + 1
        total = len(self._events)
        return [
            {
                "engineer": eng,
                "page_count": count,
                "percentage": round(count / total * 100, 2) if total else 0.0,
            }
            for eng, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        ]

    def get_after_hours_ratio(self) -> dict[str, Any]:
        """Get overall after-hours page ratio."""
        total = len(self._events)
        after = sum(
            1
            for e in self._events
            if e.time_of_day in (TimeOfDay.AFTER_HOURS, TimeOfDay.WEEKEND, TimeOfDay.HOLIDAY)
        )
        return {
            "total_pages": total,
            "after_hours_pages": after,
            "ratio": round(after / total, 4) if total else 0.0,
        }

    def clear_events(self) -> int:
        """Clear all events. Returns count cleared."""
        count = len(self._events)
        self._events.clear()
        logger.info("oncall_fatigue.events_cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        urgency_counts: dict[str, int] = {}
        tod_counts: dict[str, int] = {}
        for e in self._events:
            urgency_counts[e.urgency] = urgency_counts.get(e.urgency, 0) + 1
            tod_counts[e.time_of_day] = tod_counts.get(e.time_of_day, 0) + 1
        unique_engineers = len({e.engineer for e in self._events})
        return {
            "total_events": len(self._events),
            "unique_engineers": unique_engineers,
            "urgency_distribution": urgency_counts,
            "time_of_day_distribution": tod_counts,
        }
