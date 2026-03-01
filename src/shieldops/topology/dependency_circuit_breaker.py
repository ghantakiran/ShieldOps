"""Dependency Circuit Breaker Monitor — monitor circuit breaker states and trip frequency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CircuitState(StrEnum):
    CLOSED = "closed"
    HALF_OPEN = "half_open"
    OPEN = "open"
    FORCED_OPEN = "forced_open"
    DISABLED = "disabled"


class TripReason(StrEnum):
    TIMEOUT = "timeout"
    ERROR_RATE = "error_rate"
    LATENCY = "latency"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    MANUAL = "manual"


class RecoveryStrategy(StrEnum):
    AUTOMATIC = "automatic"
    GRADUAL = "gradual"
    MANUAL = "manual"
    FALLBACK = "fallback"
    RETRY = "retry"


# --- Models ---


class CircuitBreakerRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    circuit_id: str = ""
    circuit_state: CircuitState = CircuitState.CLOSED
    trip_reason: TripReason = TripReason.TIMEOUT
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.AUTOMATIC
    trip_count: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CircuitEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    circuit_id: str = ""
    circuit_state: CircuitState = CircuitState.CLOSED
    event_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencyCircuitBreakerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_events: int = 0
    open_circuits: int = 0
    avg_trip_count: float = 0.0
    by_state: dict[str, int] = Field(default_factory=dict)
    by_reason: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    top_tripping: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DependencyCircuitBreakerMonitor:
    """Monitor circuit breaker states and trip frequency."""

    def __init__(
        self,
        max_records: int = 200000,
        max_open_circuit_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_open_circuit_pct = max_open_circuit_pct
        self._records: list[CircuitBreakerRecord] = []
        self._events: list[CircuitEvent] = []
        logger.info(
            "dependency_circuit_breaker.initialized",
            max_records=max_records,
            max_open_circuit_pct=max_open_circuit_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_circuit(
        self,
        circuit_id: str,
        circuit_state: CircuitState = CircuitState.CLOSED,
        trip_reason: TripReason = TripReason.TIMEOUT,
        recovery_strategy: RecoveryStrategy = RecoveryStrategy.AUTOMATIC,
        trip_count: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CircuitBreakerRecord:
        record = CircuitBreakerRecord(
            circuit_id=circuit_id,
            circuit_state=circuit_state,
            trip_reason=trip_reason,
            recovery_strategy=recovery_strategy,
            trip_count=trip_count,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dependency_circuit_breaker.circuit_recorded",
            record_id=record.id,
            circuit_id=circuit_id,
            circuit_state=circuit_state.value,
            trip_reason=trip_reason.value,
        )
        return record

    def get_circuit(self, record_id: str) -> CircuitBreakerRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_circuits(
        self,
        state: CircuitState | None = None,
        reason: TripReason | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CircuitBreakerRecord]:
        results = list(self._records)
        if state is not None:
            results = [r for r in results if r.circuit_state == state]
        if reason is not None:
            results = [r for r in results if r.trip_reason == reason]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_event(
        self,
        circuit_id: str,
        circuit_state: CircuitState = CircuitState.CLOSED,
        event_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CircuitEvent:
        event = CircuitEvent(
            circuit_id=circuit_id,
            circuit_state=circuit_state,
            event_score=event_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._events.append(event)
        if len(self._events) > self._max_records:
            self._events = self._events[-self._max_records :]
        logger.info(
            "dependency_circuit_breaker.event_added",
            circuit_id=circuit_id,
            circuit_state=circuit_state.value,
            event_score=event_score,
        )
        return event

    # -- domain operations --------------------------------------------------

    def analyze_circuit_distribution(self) -> dict[str, Any]:
        """Group by circuit_state; return count and avg trip_count per state."""
        state_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.circuit_state.value
            state_data.setdefault(key, []).append(r.trip_count)
        result: dict[str, Any] = {}
        for state, counts in state_data.items():
            result[state] = {
                "count": len(counts),
                "avg_trip_count": round(sum(counts) / len(counts), 2),
            }
        return result

    def identify_open_circuits(self) -> list[dict[str, Any]]:
        """Return records where circuit_state is OPEN or FORCED_OPEN."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.circuit_state in (CircuitState.OPEN, CircuitState.FORCED_OPEN):
                results.append(
                    {
                        "record_id": r.id,
                        "circuit_id": r.circuit_id,
                        "circuit_state": r.circuit_state.value,
                        "trip_count": r.trip_count,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_trip_count(self) -> list[dict[str, Any]]:
        """Group by service, total trip_count, sort descending."""
        svc_counts: dict[str, list[float]] = {}
        for r in self._records:
            svc_counts.setdefault(r.service, []).append(r.trip_count)
        results: list[dict[str, Any]] = []
        for service, counts in svc_counts.items():
            results.append(
                {
                    "service": service,
                    "total_trip_count": round(sum(counts), 2),
                    "circuit_count": len(counts),
                }
            )
        results.sort(key=lambda x: x["total_trip_count"], reverse=True)
        return results

    def detect_circuit_trends(self) -> dict[str, Any]:
        """Split-half comparison on event_score; delta threshold 5.0."""
        if len(self._events) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [e.event_score for e in self._events]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> DependencyCircuitBreakerReport:
        by_state: dict[str, int] = {}
        by_reason: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        for r in self._records:
            by_state[r.circuit_state.value] = by_state.get(r.circuit_state.value, 0) + 1
            by_reason[r.trip_reason.value] = by_reason.get(r.trip_reason.value, 0) + 1
            by_strategy[r.recovery_strategy.value] = (
                by_strategy.get(r.recovery_strategy.value, 0) + 1
            )
        open_circuits = sum(
            1
            for r in self._records
            if r.circuit_state in (CircuitState.OPEN, CircuitState.FORCED_OPEN)
        )
        avg_trip = (
            round(sum(r.trip_count for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_trip_count()
        top_tripping = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if open_circuits > 0:
            recs.append(f"{open_circuits} open circuit(s) detected — review dependency health")
        open_pct = round(open_circuits / len(self._records) * 100, 2) if self._records else 0.0
        if open_pct > self._max_open_circuit_pct:
            recs.append(
                f"Open circuit rate {open_pct}% exceeds threshold ({self._max_open_circuit_pct}%)"
            )
        if not recs:
            recs.append("Circuit breaker health is acceptable")
        return DependencyCircuitBreakerReport(
            total_records=len(self._records),
            total_events=len(self._events),
            open_circuits=open_circuits,
            avg_trip_count=avg_trip,
            by_state=by_state,
            by_reason=by_reason,
            by_strategy=by_strategy,
            top_tripping=top_tripping,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._events.clear()
        logger.info("dependency_circuit_breaker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        state_dist: dict[str, int] = {}
        for r in self._records:
            key = r.circuit_state.value
            state_dist[key] = state_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_events": len(self._events),
            "max_open_circuit_pct": self._max_open_circuit_pct,
            "state_distribution": state_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
