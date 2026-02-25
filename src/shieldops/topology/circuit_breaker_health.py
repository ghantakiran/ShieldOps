"""Circuit Breaker Health Monitor — monitor circuit breaker states and recovery."""

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
    FORCED_OPEN = "forced_open"
    DISABLED = "disabled"


class TripReason(StrEnum):
    ERROR_RATE = "error_rate"
    TIMEOUT = "timeout"
    LATENCY = "latency"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    MANUAL = "manual"


class RecoverySpeed(StrEnum):
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"
    STALLED = "stalled"
    NOT_RECOVERING = "not_recovering"


# --- Models ---


class BreakerStateRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    state: BreakerState = BreakerState.CLOSED
    trip_reason: TripReason = TripReason.ERROR_RATE
    error_rate_pct: float = 0.0
    recovery_speed: RecoverySpeed = RecoverySpeed.NORMAL
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class BreakerTransition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    from_state: BreakerState = BreakerState.CLOSED
    to_state: BreakerState = BreakerState.OPEN
    trip_reason: TripReason = TripReason.ERROR_RATE
    duration_seconds: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CircuitBreakerReport(BaseModel):
    total_states: int = 0
    total_transitions: int = 0
    avg_error_rate_pct: float = 0.0
    by_state: dict[str, int] = Field(default_factory=dict)
    by_trip_reason: dict[str, int] = Field(default_factory=dict)
    frequently_tripping_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CircuitBreakerHealthMonitor:
    """Monitor circuit breaker states, transitions, and recovery health."""

    def __init__(
        self,
        max_records: int = 200000,
        max_trip_count_24h: int = 10,
    ) -> None:
        self._max_records = max_records
        self._max_trip_count_24h = max_trip_count_24h
        self._records: list[BreakerStateRecord] = []
        self._transitions: list[BreakerTransition] = []
        logger.info(
            "circuit_breaker_health.initialized",
            max_records=max_records,
            max_trip_count_24h=max_trip_count_24h,
        )

    # -- record / get / list ---------------------------------------------

    def record_state(
        self,
        service_name: str,
        state: BreakerState = BreakerState.CLOSED,
        trip_reason: TripReason = TripReason.ERROR_RATE,
        error_rate_pct: float = 0.0,
        recovery_speed: RecoverySpeed = RecoverySpeed.NORMAL,
        details: str = "",
    ) -> BreakerStateRecord:
        record = BreakerStateRecord(
            service_name=service_name,
            state=state,
            trip_reason=trip_reason,
            error_rate_pct=error_rate_pct,
            recovery_speed=recovery_speed,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "circuit_breaker_health.state_recorded",
            record_id=record.id,
            service_name=service_name,
            state=state.value,
        )
        return record

    def get_state(self, record_id: str) -> BreakerStateRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_states(
        self,
        service_name: str | None = None,
        state: BreakerState | None = None,
        limit: int = 50,
    ) -> list[BreakerStateRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if state is not None:
            results = [r for r in results if r.state == state]
        return results[-limit:]

    def record_transition(
        self,
        service_name: str,
        from_state: BreakerState = BreakerState.CLOSED,
        to_state: BreakerState = BreakerState.OPEN,
        trip_reason: TripReason = TripReason.ERROR_RATE,
        duration_seconds: float = 0.0,
        details: str = "",
    ) -> BreakerTransition:
        transition = BreakerTransition(
            service_name=service_name,
            from_state=from_state,
            to_state=to_state,
            trip_reason=trip_reason,
            duration_seconds=duration_seconds,
            details=details,
        )
        self._transitions.append(transition)
        if len(self._transitions) > self._max_records:
            self._transitions = self._transitions[-self._max_records :]
        logger.info(
            "circuit_breaker_health.transition_recorded",
            service_name=service_name,
            from_state=from_state.value,
            to_state=to_state.value,
        )
        return transition

    # -- domain operations -----------------------------------------------

    def analyze_breaker_health(self, service_name: str) -> dict[str, Any]:
        """Analyze circuit breaker health for a given service."""
        states = [r for r in self._records if r.service_name == service_name]
        if not states:
            return {"service_name": service_name, "status": "no_data"}
        state_breakdown: dict[str, int] = {}
        total_error = 0.0
        for s in states:
            key = s.state.value
            state_breakdown[key] = state_breakdown.get(key, 0) + 1
            total_error += s.error_rate_pct
        avg_error = round(total_error / len(states), 2) if states else 0.0
        transitions = [t for t in self._transitions if t.service_name == service_name]
        return {
            "service_name": service_name,
            "total_states": len(states),
            "total_transitions": len(transitions),
            "state_breakdown": state_breakdown,
            "avg_error_rate_pct": avg_error,
        }

    def identify_frequently_tripping(self) -> list[dict[str, Any]]:
        """Find services with transitions > max_trip_count_24h."""
        svc_counts: dict[str, int] = {}
        for t in self._transitions:
            svc_counts[t.service_name] = svc_counts.get(t.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, cnt in svc_counts.items():
            if cnt > self._max_trip_count_24h:
                results.append(
                    {
                        "service_name": svc,
                        "trip_count": cnt,
                        "threshold": self._max_trip_count_24h,
                    }
                )
        results.sort(key=lambda x: x["trip_count"], reverse=True)
        return results

    def detect_slow_recoveries(self) -> list[dict[str, Any]]:
        """Find services with slow, stalled, or not-recovering states."""
        slow_speeds = {RecoverySpeed.SLOW, RecoverySpeed.STALLED, RecoverySpeed.NOT_RECOVERING}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.recovery_speed in slow_speeds:
                results.append(
                    {
                        "id": r.id,
                        "service_name": r.service_name,
                        "state": r.state.value,
                        "recovery_speed": r.recovery_speed.value,
                        "error_rate_pct": r.error_rate_pct,
                    }
                )
        return results

    def rank_by_impact(self) -> list[dict[str, Any]]:
        """Rank services by circuit breaker impact (open/forced-open states + transitions)."""
        svc_open: dict[str, int] = {}
        for r in self._records:
            if r.state in (BreakerState.OPEN, BreakerState.FORCED_OPEN):
                svc_open[r.service_name] = svc_open.get(r.service_name, 0) + 1
        svc_transitions: dict[str, int] = {}
        for t in self._transitions:
            svc_transitions[t.service_name] = svc_transitions.get(t.service_name, 0) + 1
        all_services = set(svc_open.keys()) | set(svc_transitions.keys())
        results: list[dict[str, Any]] = []
        for svc in all_services:
            open_count = svc_open.get(svc, 0)
            trans_count = svc_transitions.get(svc, 0)
            impact_score = open_count * 2 + trans_count
            results.append(
                {
                    "service_name": svc,
                    "open_count": open_count,
                    "transition_count": trans_count,
                    "impact_score": impact_score,
                }
            )
        results.sort(key=lambda x: x["impact_score"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> CircuitBreakerReport:
        by_state: dict[str, int] = {}
        by_trip_reason: dict[str, int] = {}
        total_error = 0.0
        for r in self._records:
            by_state[r.state.value] = by_state.get(r.state.value, 0) + 1
            total_error += r.error_rate_pct
        for t in self._transitions:
            by_trip_reason[t.trip_reason.value] = by_trip_reason.get(t.trip_reason.value, 0) + 1
        avg_error = round(total_error / len(self._records), 2) if self._records else 0.0
        freq_tripping = len(self.identify_frequently_tripping())
        recs: list[str] = []
        if freq_tripping > 0:
            recs.append(f"{freq_tripping} service(s) tripping too frequently")
        slow = len(self.detect_slow_recoveries())
        if slow > 0:
            recs.append(f"{slow} state(s) with slow recovery")
        if not recs:
            recs.append("Circuit breaker health is good")
        return CircuitBreakerReport(
            total_states=len(self._records),
            total_transitions=len(self._transitions),
            avg_error_rate_pct=avg_error,
            by_state=by_state,
            by_trip_reason=by_trip_reason,
            frequently_tripping_count=freq_tripping,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._transitions.clear()
        logger.info("circuit_breaker_health.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        state_dist: dict[str, int] = {}
        for r in self._records:
            key = r.state.value
            state_dist[key] = state_dist.get(key, 0) + 1
        return {
            "total_states": len(self._records),
            "total_transitions": len(self._transitions),
            "max_trip_count_24h": self._max_trip_count_24h,
            "state_distribution": state_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
