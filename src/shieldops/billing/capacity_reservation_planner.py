"""Capacity Reservation Planner — plan and optimize capacity reservations for cost efficiency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReservationType(StrEnum):
    ON_DEMAND = "on_demand"
    RESERVED = "reserved"
    SPOT = "spot"
    SAVINGS_PLAN = "savings_plan"
    COMMITTED = "committed"


class UtilizationLevel(StrEnum):
    OVER_PROVISIONED = "over_provisioned"
    OPTIMAL = "optimal"
    UNDER_UTILIZED = "under_utilized"
    IDLE = "idle"
    UNKNOWN = "unknown"


class ReservationTerm(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    THREE_YEAR = "three_year"
    CUSTOM = "custom"


# --- Models ---


class ReservationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reservation_id: str = ""
    reservation_type: ReservationType = ReservationType.ON_DEMAND
    utilization_level: UtilizationLevel = UtilizationLevel.UNKNOWN
    reservation_term: ReservationTerm = ReservationTerm.ANNUAL
    utilization_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ReservationPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reservation_id: str = ""
    reservation_type: ReservationType = ReservationType.ON_DEMAND
    plan_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CapacityReservationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_plans: int = 0
    under_utilized_count: int = 0
    avg_utilization_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_term: dict[str, int] = Field(default_factory=dict)
    top_under_utilized: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityReservationPlanner:
    """Plan and optimize capacity reservations for cost efficiency."""

    def __init__(
        self,
        max_records: int = 200000,
        min_utilization_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_utilization_pct = min_utilization_pct
        self._records: list[ReservationRecord] = []
        self._plans: list[ReservationPlan] = []
        logger.info(
            "capacity_reservation.initialized",
            max_records=max_records,
            min_utilization_pct=min_utilization_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_reservation(
        self,
        reservation_id: str,
        reservation_type: ReservationType = ReservationType.ON_DEMAND,
        utilization_level: UtilizationLevel = UtilizationLevel.UNKNOWN,
        reservation_term: ReservationTerm = ReservationTerm.ANNUAL,
        utilization_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ReservationRecord:
        record = ReservationRecord(
            reservation_id=reservation_id,
            reservation_type=reservation_type,
            utilization_level=utilization_level,
            reservation_term=reservation_term,
            utilization_pct=utilization_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "capacity_reservation.reservation_recorded",
            record_id=record.id,
            reservation_id=reservation_id,
            reservation_type=reservation_type.value,
            utilization_level=utilization_level.value,
        )
        return record

    def get_reservation(self, record_id: str) -> ReservationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_reservations(
        self,
        res_type: ReservationType | None = None,
        level: UtilizationLevel | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ReservationRecord]:
        results = list(self._records)
        if res_type is not None:
            results = [r for r in results if r.reservation_type == res_type]
        if level is not None:
            results = [r for r in results if r.utilization_level == level]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_plan(
        self,
        reservation_id: str,
        reservation_type: ReservationType = ReservationType.ON_DEMAND,
        plan_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ReservationPlan:
        plan = ReservationPlan(
            reservation_id=reservation_id,
            reservation_type=reservation_type,
            plan_score=plan_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._plans.append(plan)
        if len(self._plans) > self._max_records:
            self._plans = self._plans[-self._max_records :]
        logger.info(
            "capacity_reservation.plan_added",
            reservation_id=reservation_id,
            reservation_type=reservation_type.value,
            plan_score=plan_score,
        )
        return plan

    # -- domain operations --------------------------------------------------

    def analyze_reservation_distribution(self) -> dict[str, Any]:
        """Group by reservation_type; return count and avg utilization_pct."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.reservation_type.value
            type_data.setdefault(key, []).append(r.utilization_pct)
        result: dict[str, Any] = {}
        for rtype, scores in type_data.items():
            result[rtype] = {
                "count": len(scores),
                "avg_utilization_pct": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_under_utilized_reservations(self) -> list[dict[str, Any]]:
        """Return records where utilization_level is UNDER_UTILIZED or IDLE."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.utilization_level in (UtilizationLevel.UNDER_UTILIZED, UtilizationLevel.IDLE):
                results.append(
                    {
                        "record_id": r.id,
                        "reservation_id": r.reservation_id,
                        "reservation_type": r.reservation_type.value,
                        "utilization_pct": r.utilization_pct,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_utilization(self) -> list[dict[str, Any]]:
        """Group by service, avg utilization_pct, sort ascending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.utilization_pct)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_utilization_pct": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_utilization_pct"])
        return results

    def detect_reservation_trends(self) -> dict[str, Any]:
        """Split-half comparison on plan_score; delta threshold 5.0."""
        if len(self._plans) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [p.plan_score for p in self._plans]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "growing"
        else:
            trend = "shrinking"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> CapacityReservationReport:
        by_type: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_term: dict[str, int] = {}
        for r in self._records:
            by_type[r.reservation_type.value] = by_type.get(r.reservation_type.value, 0) + 1
            by_level[r.utilization_level.value] = by_level.get(r.utilization_level.value, 0) + 1
            by_term[r.reservation_term.value] = by_term.get(r.reservation_term.value, 0) + 1
        under_utilized_count = sum(
            1
            for r in self._records
            if r.utilization_level in (UtilizationLevel.UNDER_UTILIZED, UtilizationLevel.IDLE)
        )
        scores = [r.utilization_pct for r in self._records]
        avg_utilization_pct = round(sum(scores) / len(scores), 2) if scores else 0.0
        under_list = self.identify_under_utilized_reservations()
        top_under_utilized = [o["reservation_id"] for o in under_list[:5]]
        recs: list[str] = []
        if self._records and avg_utilization_pct < self._min_utilization_pct:
            recs.append(
                f"Avg utilization {avg_utilization_pct}% below threshold "
                f"({self._min_utilization_pct}%)"
            )
        if under_utilized_count > 0:
            recs.append(f"{under_utilized_count} under-utilized reservation(s) — review or release")
        if not recs:
            recs.append("Capacity reservation utilization is acceptable")
        return CapacityReservationReport(
            total_records=len(self._records),
            total_plans=len(self._plans),
            under_utilized_count=under_utilized_count,
            avg_utilization_pct=avg_utilization_pct,
            by_type=by_type,
            by_level=by_level,
            by_term=by_term,
            top_under_utilized=top_under_utilized,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._plans.clear()
        logger.info("capacity_reservation.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.reservation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_plans": len(self._plans),
            "min_utilization_pct": self._min_utilization_pct,
            "reservation_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
