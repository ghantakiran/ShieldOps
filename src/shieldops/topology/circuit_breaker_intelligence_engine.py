"""Circuit Breaker Intelligence Engine.

Analyze trip frequency, detect flapping breakers,
and recommend threshold tuning."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    DISABLED = "disabled"


class TripCause(StrEnum):
    TIMEOUT = "timeout"
    ERROR_RATE = "error_rate"
    OVERLOAD = "overload"
    MANUAL = "manual"


class FlappingStatus(StrEnum):
    STABLE = "stable"
    OCCASIONAL = "occasional"
    FREQUENT = "frequent"
    CRITICAL = "critical"


# --- Models ---


class CircuitBreakerRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    breaker_name: str = ""
    breaker_state: BreakerState = BreakerState.CLOSED
    trip_cause: TripCause = TripCause.TIMEOUT
    flapping_status: FlappingStatus = FlappingStatus.STABLE
    trip_count: int = 0
    error_threshold: float = 50.0
    current_error_rate: float = 0.0
    created_at: float = Field(default_factory=time.time)


class CircuitBreakerAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    breaker_name: str = ""
    is_flapping: bool = False
    trip_frequency: float = 0.0
    state_changes: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CircuitBreakerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_trip_count: float = 0.0
    by_breaker_state: dict[str, int] = Field(default_factory=dict)
    by_trip_cause: dict[str, int] = Field(default_factory=dict)
    by_flapping_status: dict[str, int] = Field(default_factory=dict)
    flapping_breakers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CircuitBreakerIntelligenceEngine:
    """Analyze trip frequency, detect flapping breakers,
    and recommend threshold tuning."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CircuitBreakerRecord] = []
        self._analyses: dict[str, CircuitBreakerAnalysis] = {}
        logger.info(
            "circuit_breaker_intelligence.init",
            max_records=max_records,
        )

    def record_item(
        self,
        service: str = "",
        breaker_name: str = "",
        breaker_state: BreakerState = (BreakerState.CLOSED),
        trip_cause: TripCause = TripCause.TIMEOUT,
        flapping_status: FlappingStatus = (FlappingStatus.STABLE),
        trip_count: int = 0,
        error_threshold: float = 50.0,
        current_error_rate: float = 0.0,
    ) -> CircuitBreakerRecord:
        record = CircuitBreakerRecord(
            service=service,
            breaker_name=breaker_name,
            breaker_state=breaker_state,
            trip_cause=trip_cause,
            flapping_status=flapping_status,
            trip_count=trip_count,
            error_threshold=error_threshold,
            current_error_rate=current_error_rate,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "circuit_breaker.record_added",
            record_id=record.id,
            service=service,
        )
        return record

    def process(self, key: str) -> CircuitBreakerAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        changes = sum(1 for r in self._records if r.breaker_name == rec.breaker_name)
        is_flap = rec.flapping_status in (
            FlappingStatus.FREQUENT,
            FlappingStatus.CRITICAL,
        )
        analysis = CircuitBreakerAnalysis(
            service=rec.service,
            breaker_name=rec.breaker_name,
            is_flapping=is_flap,
            trip_frequency=round(rec.trip_count / max(changes, 1), 2),
            state_changes=changes,
            description=(f"Breaker {rec.breaker_name} trips {rec.trip_count}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CircuitBreakerReport:
        by_bs: dict[str, int] = {}
        by_tc: dict[str, int] = {}
        by_fs: dict[str, int] = {}
        trips: list[int] = []
        for r in self._records:
            k = r.breaker_state.value
            by_bs[k] = by_bs.get(k, 0) + 1
            k2 = r.trip_cause.value
            by_tc[k2] = by_tc.get(k2, 0) + 1
            k3 = r.flapping_status.value
            by_fs[k3] = by_fs.get(k3, 0) + 1
            trips.append(r.trip_count)
        avg = round(sum(trips) / len(trips), 2) if trips else 0.0
        flapping = list(
            {
                r.breaker_name
                for r in self._records
                if r.flapping_status
                in (
                    FlappingStatus.FREQUENT,
                    FlappingStatus.CRITICAL,
                )
            }
        )[:10]
        recs: list[str] = []
        if flapping:
            recs.append(f"{len(flapping)} flapping breakers")
        if not recs:
            recs.append("All breakers stable")
        return CircuitBreakerReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_trip_count=avg,
            by_breaker_state=by_bs,
            by_trip_cause=by_tc,
            by_flapping_status=by_fs,
            flapping_breakers=flapping,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.breaker_state.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "breaker_state_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("circuit_breaker_intelligence.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def analyze_trip_frequency(
        self,
    ) -> list[dict[str, Any]]:
        """Analyze trip frequency per breaker."""
        breaker_trips: dict[str, list[int]] = {}
        breaker_svc: dict[str, str] = {}
        for r in self._records:
            breaker_trips.setdefault(r.breaker_name, []).append(r.trip_count)
            breaker_svc[r.breaker_name] = r.service
        results: list[dict[str, Any]] = []
        for name, trips in breaker_trips.items():
            total = sum(trips)
            avg = round(total / len(trips), 2)
            results.append(
                {
                    "breaker_name": name,
                    "service": breaker_svc[name],
                    "total_trips": total,
                    "avg_trips": avg,
                    "sample_count": len(trips),
                }
            )
        results.sort(
            key=lambda x: x["total_trips"],
            reverse=True,
        )
        return results

    def detect_flapping_breakers(
        self,
    ) -> list[dict[str, Any]]:
        """Detect breakers that are flapping."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.flapping_status
                in (
                    FlappingStatus.FREQUENT,
                    FlappingStatus.CRITICAL,
                )
                and r.breaker_name not in seen
            ):
                seen.add(r.breaker_name)
                results.append(
                    {
                        "breaker_name": (r.breaker_name),
                        "service": r.service,
                        "flapping_status": (r.flapping_status.value),
                        "trip_count": r.trip_count,
                    }
                )
        results.sort(
            key=lambda x: x["trip_count"],
            reverse=True,
        )
        return results

    def recommend_threshold_tuning(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend threshold adjustments."""
        breaker_data: dict[str, list[float]] = {}
        breaker_thresh: dict[str, float] = {}
        for r in self._records:
            breaker_data.setdefault(r.breaker_name, []).append(r.current_error_rate)
            breaker_thresh[r.breaker_name] = r.error_threshold
        results: list[dict[str, Any]] = []
        for name, rates in breaker_data.items():
            avg_rate = round(sum(rates) / len(rates), 2)
            thresh = breaker_thresh[name]
            gap = round(thresh - avg_rate, 2)
            rec = "Maintain threshold"
            if gap < 5.0:
                rec = "Increase threshold"
            elif gap > 30.0:
                rec = "Decrease threshold"
            results.append(
                {
                    "breaker_name": name,
                    "current_threshold": thresh,
                    "avg_error_rate": avg_rate,
                    "gap": gap,
                    "recommendation": rec,
                }
            )
        results.sort(key=lambda x: x["gap"])
        return results
