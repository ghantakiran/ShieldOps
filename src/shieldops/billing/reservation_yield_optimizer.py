"""Reservation Yield Optimizer
analyze reservation coverage, recommend exchanges,
forecast reservation expiry impact."""

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
    RESERVED_INSTANCE = "reserved_instance"
    SAVINGS_PLAN = "savings_plan"
    COMMITTED_USE = "committed_use"
    SPOT = "spot"


class CoverageStatus(StrEnum):
    FULLY_COVERED = "fully_covered"
    PARTIAL = "partial"
    UNCOVERED = "uncovered"
    OVER_COMMITTED = "over_committed"


class YieldLevel(StrEnum):
    OPTIMAL = "optimal"
    GOOD = "good"
    SUBOPTIMAL = "suboptimal"
    WASTEFUL = "wasteful"


# --- Models ---


class ReservationYieldRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reservation_id: str = ""
    reservation_type: ReservationType = ReservationType.RESERVED_INSTANCE
    coverage_status: CoverageStatus = CoverageStatus.PARTIAL
    yield_level: YieldLevel = YieldLevel.GOOD
    monthly_cost: float = 0.0
    utilization_pct: float = 0.0
    expiry_days: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReservationYieldAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reservation_id: str = ""
    reservation_type: ReservationType = ReservationType.RESERVED_INSTANCE
    utilization_pct: float = 0.0
    yield_level: YieldLevel = YieldLevel.GOOD
    waste_amount: float = 0.0
    exchange_recommended: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReservationYieldReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_utilization: float = 0.0
    by_reservation_type: dict[str, int] = Field(default_factory=dict)
    by_coverage_status: dict[str, int] = Field(default_factory=dict)
    by_yield_level: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ReservationYieldOptimizer:
    """Analyze reservation coverage, recommend
    exchanges, forecast expiry impact."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ReservationYieldRecord] = []
        self._analyses: dict[str, ReservationYieldAnalysis] = {}
        logger.info(
            "reservation_yield_optimizer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        reservation_id: str = "",
        reservation_type: ReservationType = (ReservationType.RESERVED_INSTANCE),
        coverage_status: CoverageStatus = (CoverageStatus.PARTIAL),
        yield_level: YieldLevel = YieldLevel.GOOD,
        monthly_cost: float = 0.0,
        utilization_pct: float = 0.0,
        expiry_days: int = 0,
        description: str = "",
    ) -> ReservationYieldRecord:
        record = ReservationYieldRecord(
            reservation_id=reservation_id,
            reservation_type=reservation_type,
            coverage_status=coverage_status,
            yield_level=yield_level,
            monthly_cost=monthly_cost,
            utilization_pct=utilization_pct,
            expiry_days=expiry_days,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "reservation_yield.record_added",
            record_id=record.id,
            reservation_id=reservation_id,
        )
        return record

    def process(self, key: str) -> ReservationYieldAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        waste = round(
            rec.monthly_cost * (1 - rec.utilization_pct / 100),
            2,
        )
        exchange = rec.yield_level in (
            YieldLevel.SUBOPTIMAL,
            YieldLevel.WASTEFUL,
        )
        analysis = ReservationYieldAnalysis(
            reservation_id=rec.reservation_id,
            reservation_type=rec.reservation_type,
            utilization_pct=rec.utilization_pct,
            yield_level=rec.yield_level,
            waste_amount=waste,
            exchange_recommended=exchange,
            description=(f"Reservation {rec.reservation_id} util {rec.utilization_pct}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> ReservationYieldReport:
        by_rt: dict[str, int] = {}
        by_cs: dict[str, int] = {}
        by_yl: dict[str, int] = {}
        utils: list[float] = []
        for r in self._records:
            k = r.reservation_type.value
            by_rt[k] = by_rt.get(k, 0) + 1
            k2 = r.coverage_status.value
            by_cs[k2] = by_cs.get(k2, 0) + 1
            k3 = r.yield_level.value
            by_yl[k3] = by_yl.get(k3, 0) + 1
            utils.append(r.utilization_pct)
        avg = round(sum(utils) / len(utils), 2) if utils else 0.0
        recs: list[str] = []
        wasteful = [r for r in self._records if r.yield_level == YieldLevel.WASTEFUL]
        if wasteful:
            recs.append(f"{len(wasteful)} wasteful reservations need attention")
        if not recs:
            recs.append("Reservation yield within norms")
        return ReservationYieldReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_utilization=avg,
            by_reservation_type=by_rt,
            by_coverage_status=by_cs,
            by_yield_level=by_yl,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        rt_dist: dict[str, int] = {}
        for r in self._records:
            k = r.reservation_type.value
            rt_dist[k] = rt_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "reservation_type_distribution": rt_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("reservation_yield_optimizer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def analyze_reservation_coverage(
        self,
    ) -> list[dict[str, Any]]:
        """Analyze coverage across reservations."""
        cov_map: dict[str, list[float]] = {}
        for r in self._records:
            k = r.coverage_status.value
            cov_map.setdefault(k, []).append(r.utilization_pct)
        results: list[dict[str, Any]] = []
        for status, utils in cov_map.items():
            avg = round(sum(utils) / len(utils), 2)
            results.append(
                {
                    "coverage_status": status,
                    "count": len(utils),
                    "avg_utilization": avg,
                }
            )
        return results

    def recommend_reservation_exchanges(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend exchange for suboptimal."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.yield_level
                in (
                    YieldLevel.SUBOPTIMAL,
                    YieldLevel.WASTEFUL,
                )
                and r.reservation_id not in seen
            ):
                seen.add(r.reservation_id)
                waste = round(
                    r.monthly_cost * (1 - r.utilization_pct / 100),
                    2,
                )
                results.append(
                    {
                        "reservation_id": (r.reservation_id),
                        "type": (r.reservation_type.value),
                        "waste_amount": waste,
                        "utilization": (r.utilization_pct),
                    }
                )
        results.sort(
            key=lambda x: x["waste_amount"],
            reverse=True,
        )
        return results

    def forecast_reservation_expiry_impact(
        self,
    ) -> list[dict[str, Any]]:
        """Forecast impact of expiring reservations."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.expiry_days <= 90:
                results.append(
                    {
                        "reservation_id": (r.reservation_id),
                        "type": (r.reservation_type.value),
                        "expiry_days": r.expiry_days,
                        "monthly_cost": (r.monthly_cost),
                        "impact": round(r.monthly_cost * 0.3, 2),
                    }
                )
        results.sort(key=lambda x: x["expiry_days"])
        return results
