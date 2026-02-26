"""Resource Contention Detector — detect and analyze resource contention patterns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ContentionType(StrEnum):
    CPU_THROTTLING = "cpu_throttling"
    MEMORY_PRESSURE = "memory_pressure"
    IO_SATURATION = "io_saturation"
    NETWORK_CONGESTION = "network_congestion"
    LOCK_CONTENTION = "lock_contention"


class ContentionSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NONE_SEV = "none"


class ContentionSource(StrEnum):
    NOISY_NEIGHBOR = "noisy_neighbor"
    RESOURCE_LIMIT = "resource_limit"
    BURST_TRAFFIC = "burst_traffic"
    MEMORY_LEAK = "memory_leak"
    MISCONFIGURATION = "misconfiguration"


# --- Models ---


class ContentionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    contention_type: ContentionType = ContentionType.CPU_THROTTLING
    severity: ContentionSeverity = ContentionSeverity.LOW
    source: ContentionSource = ContentionSource.RESOURCE_LIMIT
    impact_duration_hours: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ContentionEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_name: str = ""
    contention_type: ContentionType = ContentionType.CPU_THROTTLING
    severity: ContentionSeverity = ContentionSeverity.LOW
    duration_hours: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ResourceContentionReport(BaseModel):
    total_contentions: int = 0
    total_events: int = 0
    avg_duration_hours: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ResourceContentionDetector:
    """Detect and analyze resource contention patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        critical_threshold_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._critical_threshold_pct = critical_threshold_pct
        self._records: list[ContentionRecord] = []
        self._events: list[ContentionEvent] = []
        logger.info(
            "resource_contention.initialized",
            max_records=max_records,
            critical_threshold_pct=critical_threshold_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_contention(
        self,
        service_name: str,
        contention_type: ContentionType = ContentionType.CPU_THROTTLING,
        severity: ContentionSeverity = ContentionSeverity.LOW,
        source: ContentionSource = ContentionSource.RESOURCE_LIMIT,
        impact_duration_hours: float = 0.0,
        details: str = "",
    ) -> ContentionRecord:
        record = ContentionRecord(
            service_name=service_name,
            contention_type=contention_type,
            severity=severity,
            source=source,
            impact_duration_hours=impact_duration_hours,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "resource_contention.recorded",
            record_id=record.id,
            service_name=service_name,
            severity=severity.value,
        )
        return record

    def get_contention(self, record_id: str) -> ContentionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_contentions(
        self,
        service_name: str | None = None,
        contention_type: ContentionType | None = None,
        limit: int = 50,
    ) -> list[ContentionRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if contention_type is not None:
            results = [r for r in results if r.contention_type == contention_type]
        return results[-limit:]

    def add_event(
        self,
        event_name: str,
        contention_type: ContentionType = ContentionType.CPU_THROTTLING,
        severity: ContentionSeverity = ContentionSeverity.LOW,
        duration_hours: float = 0.0,
        description: str = "",
    ) -> ContentionEvent:
        event = ContentionEvent(
            event_name=event_name,
            contention_type=contention_type,
            severity=severity,
            duration_hours=duration_hours,
            description=description,
        )
        self._events.append(event)
        if len(self._events) > self._max_records:
            self._events = self._events[-self._max_records :]
        logger.info(
            "resource_contention.event_added",
            event_name=event_name,
            duration_hours=duration_hours,
        )
        return event

    # -- domain operations -----------------------------------------------

    def analyze_contention_patterns(self, service_name: str) -> dict[str, Any]:
        """Analyze contention patterns for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_duration = round(sum(r.impact_duration_hours for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "total": len(records),
            "avg_duration": avg_duration,
            "meets_threshold": avg_duration <= self._critical_threshold_pct,
        }

    def identify_critical_contentions(self) -> list[dict[str, Any]]:
        """Find services with critical or high severity contentions."""
        critical_sevs = {ContentionSeverity.CRITICAL, ContentionSeverity.HIGH}
        service_counts: dict[str, int] = {}
        for r in self._records:
            if r.severity in critical_sevs:
                service_counts[r.service_name] = service_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for name, count in service_counts.items():
            if count > 1:
                results.append({"service_name": name, "critical_count": count})
        results.sort(key=lambda x: x["critical_count"], reverse=True)
        return results

    def rank_by_impact_duration(self) -> list[dict[str, Any]]:
        """Rank services by average impact duration descending."""
        service_durations: dict[str, list[float]] = {}
        for r in self._records:
            service_durations.setdefault(r.service_name, []).append(r.impact_duration_hours)
        results: list[dict[str, Any]] = []
        for name, durations in service_durations.items():
            avg = round(sum(durations) / len(durations), 2)
            results.append({"service_name": name, "avg_duration_hours": avg})
        results.sort(key=lambda x: x["avg_duration_hours"], reverse=True)
        return results

    def detect_recurring_contentions(self) -> list[dict[str, Any]]:
        """Detect recurring contentions for services with sufficient data."""
        service_records: dict[str, list[ContentionRecord]] = {}
        for r in self._records:
            service_records.setdefault(r.service_name, []).append(r)
        results: list[dict[str, Any]] = []
        for name, records in service_records.items():
            if len(records) > 3:
                durations = [r.impact_duration_hours for r in records]
                pattern = "worsening" if durations[-1] > durations[0] else "improving"
                results.append(
                    {
                        "service_name": name,
                        "record_count": len(records),
                        "pattern": pattern,
                    }
                )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ResourceContentionReport:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_type[r.contention_type.value] = by_type.get(r.contention_type.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
        avg_duration = (
            round(
                sum(r.impact_duration_hours for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        critical_sevs = {ContentionSeverity.CRITICAL, ContentionSeverity.HIGH}
        critical_count = sum(1 for r in self._records if r.severity in critical_sevs)
        recs: list[str] = []
        if critical_count > 0:
            recs.append(f"{critical_count} contention(s) with critical/high severity")
        long_duration = sum(1 for r in self._records if r.impact_duration_hours > 4.0)
        if long_duration > 0:
            recs.append(f"{long_duration} contention(s) with extended duration")
        if not recs:
            recs.append("Resource contention within acceptable limits")
        return ResourceContentionReport(
            total_contentions=len(self._records),
            total_events=len(self._events),
            avg_duration_hours=avg_duration,
            by_type=by_type,
            by_severity=by_severity,
            critical_count=critical_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._events.clear()
        logger.info("resource_contention.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.contention_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_contentions": len(self._records),
            "total_events": len(self._events),
            "critical_threshold_pct": self._critical_threshold_pct,
            "type_distribution": type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
