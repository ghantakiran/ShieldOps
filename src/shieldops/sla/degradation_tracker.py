"""Service Degradation Tracker — track service degradations, events, and trends."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DegradationType(StrEnum):
    LATENCY_SPIKE = "latency_spike"
    ERROR_RATE_INCREASE = "error_rate_increase"
    THROUGHPUT_DROP = "throughput_drop"
    PARTIAL_OUTAGE = "partial_outage"
    CAPACITY_LIMIT = "capacity_limit"


class DegradationSeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    COSMETIC = "cosmetic"


class RecoveryMethod(StrEnum):
    AUTO_HEAL = "auto_heal"
    MANUAL_FIX = "manual_fix"
    ROLLBACK = "rollback"
    FAILOVER = "failover"
    SCALING = "scaling"


# --- Models ---


class DegradationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    degradation_id: str = ""
    degradation_type: DegradationType = DegradationType.LATENCY_SPIKE
    degradation_severity: DegradationSeverity = DegradationSeverity.MINOR
    recovery_method: RecoveryMethod = RecoveryMethod.AUTO_HEAL
    duration_minutes: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DegradationEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    degradation_id: str = ""
    degradation_type: DegradationType = DegradationType.LATENCY_SPIKE
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ServiceDegradationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_events: int = 0
    critical_degradations: int = 0
    avg_duration_minutes: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_recovery: dict[str, int] = Field(default_factory=dict)
    top_degraded: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceDegradationTracker:
    """Track service degradations, identify patterns, and detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        max_degradation_minutes: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._max_degradation_minutes = max_degradation_minutes
        self._records: list[DegradationRecord] = []
        self._events: list[DegradationEvent] = []
        logger.info(
            "degradation_tracker.initialized",
            max_records=max_records,
            max_degradation_minutes=max_degradation_minutes,
        )

    # -- record / get / list ------------------------------------------------

    def record_degradation(
        self,
        degradation_id: str,
        degradation_type: DegradationType = DegradationType.LATENCY_SPIKE,
        degradation_severity: DegradationSeverity = DegradationSeverity.MINOR,
        recovery_method: RecoveryMethod = RecoveryMethod.AUTO_HEAL,
        duration_minutes: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DegradationRecord:
        record = DegradationRecord(
            degradation_id=degradation_id,
            degradation_type=degradation_type,
            degradation_severity=degradation_severity,
            recovery_method=recovery_method,
            duration_minutes=duration_minutes,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "degradation_tracker.degradation_recorded",
            record_id=record.id,
            degradation_id=degradation_id,
            degradation_type=degradation_type.value,
            degradation_severity=degradation_severity.value,
        )
        return record

    def get_degradation(self, record_id: str) -> DegradationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_degradations(
        self,
        dtype: DegradationType | None = None,
        severity: DegradationSeverity | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DegradationRecord]:
        results = list(self._records)
        if dtype is not None:
            results = [r for r in results if r.degradation_type == dtype]
        if severity is not None:
            results = [r for r in results if r.degradation_severity == severity]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_event(
        self,
        degradation_id: str,
        degradation_type: DegradationType = DegradationType.LATENCY_SPIKE,
        value: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DegradationEvent:
        event = DegradationEvent(
            degradation_id=degradation_id,
            degradation_type=degradation_type,
            value=value,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._events.append(event)
        if len(self._events) > self._max_records:
            self._events = self._events[-self._max_records :]
        logger.info(
            "degradation_tracker.event_added",
            degradation_id=degradation_id,
            degradation_type=degradation_type.value,
            value=value,
        )
        return event

    # -- domain operations --------------------------------------------------

    def analyze_degradation_patterns(self) -> dict[str, Any]:
        """Group by type; return count and avg duration per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.degradation_type.value
            type_data.setdefault(key, []).append(r.duration_minutes)
        result: dict[str, Any] = {}
        for dtype, durations in type_data.items():
            result[dtype] = {
                "count": len(durations),
                "avg_duration_minutes": round(sum(durations) / len(durations), 2),
            }
        return result

    def identify_frequent_degradations(self) -> list[dict[str, Any]]:
        """Return records where severity == CRITICAL or MAJOR."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.degradation_severity in (
                DegradationSeverity.CRITICAL,
                DegradationSeverity.MAJOR,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "degradation_id": r.degradation_id,
                        "degradation_type": r.degradation_type.value,
                        "degradation_severity": r.degradation_severity.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_duration(self) -> list[dict[str, Any]]:
        """Group by service, total records, sort descending by avg duration."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.duration_minutes)
        results: list[dict[str, Any]] = []
        for service, durations in service_data.items():
            results.append(
                {
                    "service": service,
                    "record_count": len(durations),
                    "avg_duration_minutes": round(sum(durations) / len(durations), 2),
                }
            )
        results.sort(key=lambda x: x["avg_duration_minutes"], reverse=True)
        return results

    def detect_degradation_trends(self) -> dict[str, Any]:
        """Split-half on value; delta threshold 5.0."""
        if len(self._events) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [e.value for e in self._events]
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ServiceDegradationReport:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_recovery: dict[str, int] = {}
        for r in self._records:
            by_type[r.degradation_type.value] = by_type.get(r.degradation_type.value, 0) + 1
            by_severity[r.degradation_severity.value] = (
                by_severity.get(r.degradation_severity.value, 0) + 1
            )
            by_recovery[r.recovery_method.value] = by_recovery.get(r.recovery_method.value, 0) + 1
        critical_count = sum(
            1
            for r in self._records
            if r.degradation_severity in (DegradationSeverity.CRITICAL, DegradationSeverity.MAJOR)
        )
        durations = [r.duration_minutes for r in self._records]
        avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0
        rankings = self.rank_by_duration()
        top_degraded = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        above_threshold = sum(
            1 for r in self._records if r.duration_minutes > self._max_degradation_minutes
        )
        above_rate = round(above_threshold / len(self._records) * 100, 2) if self._records else 0.0
        if above_rate > 20.0:
            recs.append(
                f"Long degradation rate {above_rate}% exceeds threshold"
                f" ({self._max_degradation_minutes}min)"
            )
        if critical_count > 0:
            recs.append(f"{critical_count} critical degradation(s) detected — review degradations")
        if not recs:
            recs.append("Service degradation levels are acceptable")
        return ServiceDegradationReport(
            total_records=len(self._records),
            total_events=len(self._events),
            critical_degradations=critical_count,
            avg_duration_minutes=avg_duration,
            by_type=by_type,
            by_severity=by_severity,
            by_recovery=by_recovery,
            top_degraded=top_degraded,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._events.clear()
        logger.info("degradation_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.degradation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_events": len(self._events),
            "max_degradation_minutes": self._max_degradation_minutes,
            "type_distribution": type_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_degradations": len({r.degradation_id for r in self._records}),
        }
