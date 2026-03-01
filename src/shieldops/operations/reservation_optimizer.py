"""Reservation Optimizer — optimize infrastructure reservation utilization."""

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
    COMPUTE = "compute"
    STORAGE = "storage"
    DATABASE = "database"
    NETWORK = "network"
    SPECIALIZED = "specialized"


class UtilizationLevel(StrEnum):
    OPTIMAL = "optimal"
    ADEQUATE = "adequate"
    UNDERUTILIZED = "underutilized"
    WASTEFUL = "wasteful"
    UNUSED = "unused"


class ReservationAction(StrEnum):
    KEEP = "keep"
    MODIFY = "modify"
    EXCHANGE = "exchange"
    SELL = "sell"
    TERMINATE = "terminate"


# --- Models ---


class ReservationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reservation_id: str = ""
    reservation_type: ReservationType = ReservationType.COMPUTE
    utilization_level: UtilizationLevel = UtilizationLevel.OPTIMAL
    reservation_action: ReservationAction = ReservationAction.KEEP
    utilization_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class UtilizationMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reservation_id: str = ""
    reservation_type: ReservationType = ReservationType.COMPUTE
    metric_value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReservationOptimizerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    underutilized_count: int = 0
    avg_utilization_pct: float = 0.0
    by_reservation_type: dict[str, int] = Field(default_factory=dict)
    by_utilization: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    top_underutilized: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ReservationOptimizer:
    """Optimize infrastructure reservation utilization, detect underused reservations."""

    def __init__(
        self,
        max_records: int = 200000,
        min_utilization_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_utilization_pct = min_utilization_pct
        self._records: list[ReservationRecord] = []
        self._metrics: list[UtilizationMetric] = []
        logger.info(
            "reservation_optimizer.initialized",
            max_records=max_records,
            min_utilization_pct=min_utilization_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_reservation(
        self,
        reservation_id: str,
        reservation_type: ReservationType = ReservationType.COMPUTE,
        utilization_level: UtilizationLevel = UtilizationLevel.OPTIMAL,
        reservation_action: ReservationAction = ReservationAction.KEEP,
        utilization_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ReservationRecord:
        record = ReservationRecord(
            reservation_id=reservation_id,
            reservation_type=reservation_type,
            utilization_level=utilization_level,
            reservation_action=reservation_action,
            utilization_pct=utilization_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "reservation_optimizer.reservation_recorded",
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
        reservation_type: ReservationType | None = None,
        utilization: UtilizationLevel | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ReservationRecord]:
        results = list(self._records)
        if reservation_type is not None:
            results = [r for r in results if r.reservation_type == reservation_type]
        if utilization is not None:
            results = [r for r in results if r.utilization_level == utilization]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        reservation_id: str,
        reservation_type: ReservationType = ReservationType.COMPUTE,
        metric_value: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> UtilizationMetric:
        metric = UtilizationMetric(
            reservation_id=reservation_id,
            reservation_type=reservation_type,
            metric_value=metric_value,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "reservation_optimizer.metric_added",
            reservation_id=reservation_id,
            reservation_type=reservation_type.value,
            metric_value=metric_value,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_utilization(self) -> dict[str, Any]:
        """Group by reservation type; return count and avg utilization pct per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.reservation_type.value
            type_data.setdefault(key, []).append(r.utilization_pct)
        result: dict[str, Any] = {}
        for rtype, pcts in type_data.items():
            result[rtype] = {
                "count": len(pcts),
                "avg_utilization_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_underutilized_reservations(self) -> list[dict[str, Any]]:
        """Return records where utilization_level is WASTEFUL or UNUSED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.utilization_level in (
                UtilizationLevel.WASTEFUL,
                UtilizationLevel.UNUSED,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "reservation_id": r.reservation_id,
                        "reservation_type": r.reservation_type.value,
                        "utilization_level": r.utilization_level.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_utilization(self) -> list[dict[str, Any]]:
        """Group by service, total records, sort descending by avg utilization pct."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.utilization_pct)
        results: list[dict[str, Any]] = []
        for service, pcts in service_data.items():
            results.append(
                {
                    "service": service,
                    "record_count": len(pcts),
                    "avg_utilization_pct": round(sum(pcts) / len(pcts), 2),
                }
            )
        results.sort(key=lambda x: x["avg_utilization_pct"], reverse=True)
        return results

    def detect_utilization_trends(self) -> dict[str, Any]:
        """Split-half on metric_value; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [m.metric_value for m in self._metrics]
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

    def generate_report(self) -> ReservationOptimizerReport:
        by_reservation_type: dict[str, int] = {}
        by_utilization: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_reservation_type[r.reservation_type.value] = (
                by_reservation_type.get(r.reservation_type.value, 0) + 1
            )
            by_utilization[r.utilization_level.value] = (
                by_utilization.get(r.utilization_level.value, 0) + 1
            )
            by_action[r.reservation_action.value] = by_action.get(r.reservation_action.value, 0) + 1
        underutilized_count = sum(
            1
            for r in self._records
            if r.utilization_level in (UtilizationLevel.WASTEFUL, UtilizationLevel.UNUSED)
        )
        pcts = [r.utilization_pct for r in self._records]
        avg_pct = round(sum(pcts) / len(pcts), 2) if pcts else 0.0
        rankings = self.rank_by_utilization()
        top_underutilized = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        underutilized_rate = (
            round(underutilized_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        if avg_pct < self._min_utilization_pct and self._records:
            recs.append(
                f"Average utilization {avg_pct}% below threshold ({self._min_utilization_pct}%)"
            )
        if underutilized_count > 0:
            recs.append(
                f"{underutilized_count} underutilized reservation(s) detected — review sizing"
            )
        if underutilized_rate > 20.0:
            recs.append(f"Underutilized rate {underutilized_rate}% — consider right-sizing")
        if not recs:
            recs.append("Reservation utilization is within acceptable limits")
        return ReservationOptimizerReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            underutilized_count=underutilized_count,
            avg_utilization_pct=avg_pct,
            by_reservation_type=by_reservation_type,
            by_utilization=by_utilization,
            by_action=by_action,
            top_underutilized=top_underutilized,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("reservation_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.reservation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_utilization_pct": self._min_utilization_pct,
            "reservation_type_distribution": type_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_reservations": len({r.reservation_id for r in self._records}),
        }
