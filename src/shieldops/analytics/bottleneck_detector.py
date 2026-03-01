"""Capacity Bottleneck Detector — track and analyze infrastructure capacity bottlenecks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BottleneckType(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK_IO = "disk_io"
    NETWORK = "network"
    CONNECTION_POOL = "connection_pool"


class BottleneckSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NONE = "none"


class BottleneckTrend(StrEnum):
    WORSENING = "worsening"
    STABLE = "stable"
    IMPROVING = "improving"
    RESOLVED = "resolved"
    RECURRING = "recurring"


# --- Models ---


class BottleneckRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    bottleneck_type: BottleneckType = BottleneckType.CPU
    severity: BottleneckSeverity = BottleneckSeverity.NONE
    utilization_pct: float = 0.0
    duration_minutes: float = 0.0
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class BottleneckEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    record_id: str = ""
    event_type: str = ""
    impact_score: float = 0.0
    affected_users: int = 0
    created_at: float = Field(default_factory=time.time)


class CapacityBottleneckReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_events: int = 0
    critical_bottlenecks: int = 0
    avg_utilization_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    most_constrained: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityBottleneckDetector:
    """Track and analyze infrastructure capacity bottlenecks."""

    def __init__(
        self,
        max_records: int = 200000,
        critical_utilization_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._critical_utilization_pct = critical_utilization_pct
        self._records: list[BottleneckRecord] = []
        self._events: list[BottleneckEvent] = []
        logger.info(
            "bottleneck_detector.initialized",
            max_records=max_records,
            critical_utilization_pct=critical_utilization_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_bottleneck(
        self,
        service: str,
        bottleneck_type: BottleneckType = BottleneckType.CPU,
        severity: BottleneckSeverity = BottleneckSeverity.NONE,
        utilization_pct: float = 0.0,
        duration_minutes: float = 0.0,
        team: str = "",
        details: str = "",
    ) -> BottleneckRecord:
        record = BottleneckRecord(
            service=service,
            bottleneck_type=bottleneck_type,
            severity=severity,
            utilization_pct=utilization_pct,
            duration_minutes=duration_minutes,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "bottleneck_detector.recorded",
            record_id=record.id,
            service=service,
            severity=severity.value,
        )
        return record

    def get_bottleneck(self, record_id: str) -> BottleneckRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_bottlenecks(
        self,
        bottleneck_type: BottleneckType | None = None,
        severity: BottleneckSeverity | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[BottleneckRecord]:
        results = list(self._records)
        if bottleneck_type is not None:
            results = [r for r in results if r.bottleneck_type == bottleneck_type]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def add_event(
        self,
        record_id: str,
        event_type: str = "",
        impact_score: float = 0.0,
        affected_users: int = 0,
    ) -> BottleneckEvent:
        event = BottleneckEvent(
            record_id=record_id,
            event_type=event_type,
            impact_score=impact_score,
            affected_users=affected_users,
        )
        self._events.append(event)
        if len(self._events) > self._max_records:
            self._events = self._events[-self._max_records :]
        logger.info(
            "bottleneck_detector.event_added",
            event_id=event.id,
            record_id=record_id,
            impact_score=impact_score,
        )
        return event

    # -- domain operations -----------------------------------------------

    def analyze_bottleneck_patterns(self) -> dict[str, Any]:
        """Group by bottleneck_type, compute avg utilization_pct and count."""
        groups: dict[str, list[float]] = {}
        for r in self._records:
            groups.setdefault(r.bottleneck_type.value, []).append(r.utilization_pct)
        result: dict[str, Any] = {}
        for bt, utils in groups.items():
            result[bt] = {
                "count": len(utils),
                "avg_utilization_pct": round(sum(utils) / len(utils), 2),
            }
        return result

    def identify_critical_bottlenecks(self) -> list[dict[str, Any]]:
        """Find records where utilization_pct exceeds critical_utilization_pct."""
        critical = [r for r in self._records if r.utilization_pct > self._critical_utilization_pct]
        return [
            {
                "record_id": r.id,
                "service": r.service,
                "utilization_pct": r.utilization_pct,
                "bottleneck_type": r.bottleneck_type.value,
                "severity": r.severity.value,
            }
            for r in critical
        ]

    def rank_by_utilization(self) -> list[dict[str, Any]]:
        """Group by service, compute avg utilization_pct, sort descending."""
        service_utils: dict[str, list[float]] = {}
        for r in self._records:
            service_utils.setdefault(r.service, []).append(r.utilization_pct)
        results: list[dict[str, Any]] = []
        for svc, utils in service_utils.items():
            results.append(
                {"service": svc, "avg_utilization_pct": round(sum(utils) / len(utils), 2)}
            )
        results.sort(key=lambda x: x["avg_utilization_pct"], reverse=True)
        return results

    def detect_bottleneck_trends(self) -> dict[str, Any]:
        """Split records in half and compute delta in avg utilization_pct; threshold 5.0."""
        if len(self._records) < 2:
            return {"status": "insufficient_data"}
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]
        avg_first = sum(r.utilization_pct for r in first_half) / len(first_half)
        avg_second = sum(r.utilization_pct for r in second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        trend = "worsening" if delta > 5.0 else ("improving" if delta < -5.0 else "stable")
        return {
            "avg_utilization_first_half": round(avg_first, 2),
            "avg_utilization_second_half": round(avg_second, 2),
            "delta": delta,
            "trend": trend,
        }

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> CapacityBottleneckReport:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_type[r.bottleneck_type.value] = by_type.get(r.bottleneck_type.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
        critical_bottlenecks = sum(
            1 for r in self._records if r.severity == BottleneckSeverity.CRITICAL
        )
        avg_util = (
            round(
                sum(r.utilization_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        sorted_records = sorted(self._records, key=lambda r: r.utilization_pct, reverse=True)
        most_constrained = [r.service for r in sorted_records[:5]]
        recs: list[str] = []
        over_threshold = sum(
            1 for r in self._records if r.utilization_pct > self._critical_utilization_pct
        )
        if over_threshold > 0:
            recs.append(
                f"{over_threshold} service(s) exceed "
                f"{self._critical_utilization_pct}% utilization threshold"
            )
        if critical_bottlenecks > 0:
            recs.append(f"{critical_bottlenecks} critical bottleneck(s) require immediate action")
        if not recs:
            recs.append("Capacity utilization within acceptable limits")
        return CapacityBottleneckReport(
            total_records=len(self._records),
            total_events=len(self._events),
            critical_bottlenecks=critical_bottlenecks,
            avg_utilization_pct=avg_util,
            by_type=by_type,
            by_severity=by_severity,
            most_constrained=most_constrained,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._events.clear()
        logger.info("bottleneck_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.bottleneck_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_events": len(self._events),
            "critical_utilization_pct": self._critical_utilization_pct,
            "type_distribution": type_dist,
            "unique_services": len({r.service for r in self._records}),
        }
