"""Cost Trend Forecaster — record, analyse, and forecast service cost trends."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TrendDirection(StrEnum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    VOLATILE = "volatile"
    SEASONAL = "seasonal"


class CostCategory(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    THIRD_PARTY = "third_party"


class ForecastConfidence(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    SPECULATIVE = "speculative"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class CostTrendRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    cost_amount: float = 0.0
    direction: TrendDirection = TrendDirection.STABLE
    category: CostCategory = CostCategory.COMPUTE
    confidence: ForecastConfidence = ForecastConfidence.INSUFFICIENT_DATA
    period: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CostForecast(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    projected_cost: float = 0.0
    confidence: ForecastConfidence = ForecastConfidence.INSUFFICIENT_DATA
    period: str = ""
    growth_rate_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class CostTrendReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_forecasts: int = 0
    avg_cost: float = 0.0
    avg_growth_rate_pct: float = 0.0
    by_direction: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    high_growth_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostTrendForecaster:
    """Record cost observations and forecast spend trajectories per service."""

    def __init__(
        self,
        max_records: int = 200000,
        max_growth_rate_pct: float = 20.0,
    ) -> None:
        self._max_records = max_records
        self._max_growth_rate_pct = max_growth_rate_pct
        self._records: list[CostTrendRecord] = []
        self._forecasts: list[CostForecast] = []
        logger.info(
            "cost_trend.initialized",
            max_records=max_records,
            max_growth_rate_pct=max_growth_rate_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_trend(
        self,
        service: str,
        cost_amount: float = 0.0,
        direction: TrendDirection = TrendDirection.STABLE,
        category: CostCategory = CostCategory.COMPUTE,
        confidence: ForecastConfidence = ForecastConfidence.INSUFFICIENT_DATA,
        period: str = "",
        details: str = "",
    ) -> CostTrendRecord:
        record = CostTrendRecord(
            service=service,
            cost_amount=cost_amount,
            direction=direction,
            category=category,
            confidence=confidence,
            period=period,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_trend.trend_recorded",
            record_id=record.id,
            service=service,
            cost_amount=cost_amount,
            direction=direction.value,
        )
        return record

    def get_trend(self, record_id: str) -> CostTrendRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_trends(
        self,
        direction: TrendDirection | None = None,
        category: CostCategory | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[CostTrendRecord]:
        results = list(self._records)
        if direction is not None:
            results = [r for r in results if r.direction == direction]
        if category is not None:
            results = [r for r in results if r.category == category]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def add_forecast(
        self,
        service: str,
        projected_cost: float = 0.0,
        confidence: ForecastConfidence = ForecastConfidence.INSUFFICIENT_DATA,
        period: str = "",
        growth_rate_pct: float = 0.0,
    ) -> CostForecast:
        forecast = CostForecast(
            service=service,
            projected_cost=projected_cost,
            confidence=confidence,
            period=period,
            growth_rate_pct=growth_rate_pct,
        )
        self._forecasts.append(forecast)
        if len(self._forecasts) > self._max_records:
            self._forecasts = self._forecasts[-self._max_records :]
        logger.info(
            "cost_trend.forecast_added",
            forecast_id=forecast.id,
            service=service,
            projected_cost=projected_cost,
            growth_rate_pct=growth_rate_pct,
        )
        return forecast

    # -- domain operations --------------------------------------------------

    def analyze_cost_by_category(self) -> dict[str, Any]:
        """Group by category; return avg cost_amount and count."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            cat_data.setdefault(r.category.value, []).append(r.cost_amount)
        result: dict[str, Any] = {}
        for cat, costs in cat_data.items():
            result[cat] = {
                "count": len(costs),
                "avg_cost": round(sum(costs) / len(costs), 2),
            }
        return result

    def identify_high_growth_services(self) -> list[dict[str, Any]]:
        """Return services with avg forecast growth_rate_pct > max_growth_rate_pct."""
        svc_data: dict[str, list[float]] = {}
        for f in self._forecasts:
            svc_data.setdefault(f.service, []).append(f.growth_rate_pct)
        results: list[dict[str, Any]] = []
        for svc, rates in svc_data.items():
            avg_rate = sum(rates) / len(rates)
            if avg_rate > self._max_growth_rate_pct:
                results.append(
                    {
                        "service": svc,
                        "avg_growth_rate_pct": round(avg_rate, 2),
                        "forecast_count": len(rates),
                        "threshold_pct": self._max_growth_rate_pct,
                    }
                )
        results.sort(key=lambda x: x["avg_growth_rate_pct"], reverse=True)
        return results

    def rank_by_cost(self) -> list[dict[str, Any]]:
        """Group by service; return avg cost_amount, sorted descending."""
        svc_data: dict[str, list[float]] = {}
        for r in self._records:
            svc_data.setdefault(r.service, []).append(r.cost_amount)
        results: list[dict[str, Any]] = []
        for svc, costs in svc_data.items():
            results.append(
                {
                    "service": svc,
                    "avg_cost": round(sum(costs) / len(costs), 2),
                    "sample_count": len(costs),
                }
            )
        results.sort(key=lambda x: x["avg_cost"], reverse=True)
        return results

    def detect_cost_trends(self) -> dict[str, Any]:
        """Split-half comparison on cost_amount; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        costs = [r.cost_amount for r in self._records]
        mid = len(costs) // 2
        first_half = costs[:mid]
        second_half = costs[mid:]
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

    def generate_report(self) -> CostTrendReport:
        by_direction: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_direction[r.direction.value] = by_direction.get(r.direction.value, 0) + 1
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
        avg_cost = (
            round(
                sum(r.cost_amount for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        avg_growth = (
            round(
                sum(f.growth_rate_pct for f in self._forecasts) / len(self._forecasts),
                2,
            )
            if self._forecasts
            else 0.0
        )
        high_growth = self.identify_high_growth_services()
        high_growth_svcs = [h["service"] for h in high_growth]
        recs: list[str] = []
        if high_growth:
            recs.append(
                f"{len(high_growth)} service(s) exceed growth rate threshold "
                f"({self._max_growth_rate_pct}%)"
            )
        volatile_count = sum(1 for r in self._records if r.direction == TrendDirection.VOLATILE)
        if volatile_count > 0:
            recs.append(
                f"{volatile_count} volatile cost trend(s) detected — investigate spend drivers"
            )
        if not recs:
            recs.append("Cost trends are within expected growth bounds")
        return CostTrendReport(
            total_records=len(self._records),
            total_forecasts=len(self._forecasts),
            avg_cost=avg_cost,
            avg_growth_rate_pct=avg_growth,
            by_direction=by_direction,
            by_category=by_category,
            high_growth_services=high_growth_svcs,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._forecasts.clear()
        logger.info("cost_trend.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        direction_dist: dict[str, int] = {}
        for r in self._records:
            key = r.direction.value
            direction_dist[key] = direction_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_forecasts": len(self._forecasts),
            "max_growth_rate_pct": self._max_growth_rate_pct,
            "direction_distribution": direction_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_categories": len({r.category for r in self._records}),
        }
