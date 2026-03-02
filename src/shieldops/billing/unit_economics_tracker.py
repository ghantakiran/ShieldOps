"""Unit Economics Tracker — track cost-per-unit metrics across services."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class UnitMetric(StrEnum):
    COST_PER_REQUEST = "cost_per_request"
    COST_PER_USER = "cost_per_user"
    COST_PER_TRANSACTION = "cost_per_transaction"
    COST_PER_GB = "cost_per_gb"
    COST_PER_CPU_HOUR = "cost_per_cpu_hour"


class Granularity(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class TrendDirection(StrEnum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


# --- Models ---


class UnitEconomicsRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    unit_metric: UnitMetric = UnitMetric.COST_PER_REQUEST
    granularity: Granularity = Granularity.DAILY
    trend_direction: TrendDirection = TrendDirection.UNKNOWN
    unit_cost: float = 0.0
    unit_volume: float = 0.0
    total_cost: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EconomicsAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    unit_metric: UnitMetric = UnitMetric.COST_PER_REQUEST
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class UnitEconomicsReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    degrading_count: int = 0
    avg_unit_cost: float = 0.0
    by_unit_metric: dict[str, int] = Field(default_factory=dict)
    by_granularity: dict[str, int] = Field(default_factory=dict)
    by_trend_direction: dict[str, int] = Field(default_factory=dict)
    top_expensive: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class UnitEconomicsTracker:
    """Track cost-per-unit metrics and trends across services."""

    def __init__(
        self,
        max_records: int = 200000,
        cost_increase_threshold: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._cost_increase_threshold = cost_increase_threshold
        self._records: list[UnitEconomicsRecord] = []
        self._analyses: list[EconomicsAnalysis] = []
        logger.info(
            "unit_economics_tracker.initialized",
            max_records=max_records,
            cost_increase_threshold=cost_increase_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_unit_economics(
        self,
        unit_metric: UnitMetric = UnitMetric.COST_PER_REQUEST,
        granularity: Granularity = Granularity.DAILY,
        trend_direction: TrendDirection = TrendDirection.UNKNOWN,
        unit_cost: float = 0.0,
        unit_volume: float = 0.0,
        total_cost: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> UnitEconomicsRecord:
        record = UnitEconomicsRecord(
            unit_metric=unit_metric,
            granularity=granularity,
            trend_direction=trend_direction,
            unit_cost=unit_cost,
            unit_volume=unit_volume,
            total_cost=total_cost,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "unit_economics_tracker.economics_recorded",
            record_id=record.id,
            unit_metric=unit_metric.value,
            unit_cost=unit_cost,
        )
        return record

    def get_unit_economics(self, record_id: str) -> UnitEconomicsRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_unit_economics(
        self,
        unit_metric: UnitMetric | None = None,
        granularity: Granularity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[UnitEconomicsRecord]:
        results = list(self._records)
        if unit_metric is not None:
            results = [r for r in results if r.unit_metric == unit_metric]
        if granularity is not None:
            results = [r for r in results if r.granularity == granularity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        unit_metric: UnitMetric = UnitMetric.COST_PER_REQUEST,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> EconomicsAnalysis:
        analysis = EconomicsAnalysis(
            unit_metric=unit_metric,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "unit_economics_tracker.analysis_added",
            unit_metric=unit_metric.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_metric_distribution(self) -> dict[str, Any]:
        """Group by unit_metric; return count and avg unit_cost."""
        metric_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.unit_metric.value
            metric_data.setdefault(key, []).append(r.unit_cost)
        result: dict[str, Any] = {}
        for metric, costs in metric_data.items():
            result[metric] = {
                "count": len(costs),
                "avg_unit_cost": round(sum(costs) / len(costs), 4),
            }
        return result

    def identify_increasing_costs(self) -> list[dict[str, Any]]:
        """Return records where trend_direction is INCREASING."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.trend_direction == TrendDirection.INCREASING:
                results.append(
                    {
                        "record_id": r.id,
                        "unit_metric": r.unit_metric.value,
                        "unit_cost": r.unit_cost,
                        "total_cost": r.total_cost,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["unit_cost"], reverse=True)

    def rank_by_unit_cost(self) -> list[dict[str, Any]]:
        """Group by service, avg unit_cost, sort descending."""
        svc_costs: dict[str, list[float]] = {}
        for r in self._records:
            svc_costs.setdefault(r.service, []).append(r.unit_cost)
        results: list[dict[str, Any]] = [
            {
                "service": svc,
                "avg_unit_cost": round(sum(costs) / len(costs), 4),
            }
            for svc, costs in svc_costs.items()
        ]
        results.sort(key=lambda x: x["avg_unit_cost"], reverse=True)
        return results

    def detect_cost_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> UnitEconomicsReport:
        by_metric: dict[str, int] = {}
        by_granularity: dict[str, int] = {}
        by_trend: dict[str, int] = {}
        for r in self._records:
            by_metric[r.unit_metric.value] = by_metric.get(r.unit_metric.value, 0) + 1
            by_granularity[r.granularity.value] = by_granularity.get(r.granularity.value, 0) + 1
            by_trend[r.trend_direction.value] = by_trend.get(r.trend_direction.value, 0) + 1
        degrading_count = sum(
            1 for r in self._records if r.trend_direction == TrendDirection.INCREASING
        )
        costs = [r.unit_cost for r in self._records]
        avg_unit_cost = round(sum(costs) / len(costs), 4) if costs else 0.0
        expensive = self.identify_increasing_costs()
        top_expensive = [o["record_id"] for o in expensive[:5]]
        recs: list[str] = []
        if degrading_count > 0:
            recs.append(f"{degrading_count} service(s) with increasing unit costs")
        if avg_unit_cost > self._cost_increase_threshold:
            recs.append(
                f"Avg unit cost {avg_unit_cost} exceeds threshold ({self._cost_increase_threshold})"
            )
        if not recs:
            recs.append("Unit economics are healthy")
        return UnitEconomicsReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            degrading_count=degrading_count,
            avg_unit_cost=avg_unit_cost,
            by_unit_metric=by_metric,
            by_granularity=by_granularity,
            by_trend_direction=by_trend,
            top_expensive=top_expensive,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("unit_economics_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        metric_dist: dict[str, int] = {}
        for r in self._records:
            key = r.unit_metric.value
            metric_dist[key] = metric_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "cost_increase_threshold": self._cost_increase_threshold,
            "unit_metric_distribution": metric_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
