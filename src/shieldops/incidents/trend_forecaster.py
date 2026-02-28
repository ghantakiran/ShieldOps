"""Incident Trend Forecaster — forecast incident trends and detect anomalies."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TrendDirection(StrEnum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


class ForecastConfidence(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    SPECULATIVE = "speculative"
    NO_DATA = "no_data"


class IncidentCategory(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    SECURITY = "security"
    NETWORK = "network"
    DATABASE = "database"


# --- Models ---


class TrendRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    category: IncidentCategory = IncidentCategory.INFRASTRUCTURE
    direction: TrendDirection = TrendDirection.STABLE
    confidence: ForecastConfidence = ForecastConfidence.MODERATE
    incident_count: int = 0
    growth_rate_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ForecastDataPoint(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    category: IncidentCategory = IncidentCategory.INFRASTRUCTURE
    period_label: str = ""
    incident_count: int = 0
    forecast_count: int = 0
    notes: str = ""
    created_at: float = Field(default_factory=time.time)


class TrendForecasterReport(BaseModel):
    total_trends: int = 0
    total_data_points: int = 0
    avg_growth_rate_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_direction: dict[str, int] = Field(default_factory=dict)
    rising_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentTrendForecaster:
    """Forecast incident trends and detect anomalies by category."""

    def __init__(
        self,
        max_records: int = 200000,
        max_growth_rate_pct: float = 20.0,
    ) -> None:
        self._max_records = max_records
        self._max_growth_rate_pct = max_growth_rate_pct
        self._records: list[TrendRecord] = []
        self._data_points: list[ForecastDataPoint] = []
        logger.info(
            "trend_forecaster.initialized",
            max_records=max_records,
            max_growth_rate_pct=max_growth_rate_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_trend(
        self,
        category: IncidentCategory = IncidentCategory.INFRASTRUCTURE,
        direction: TrendDirection = TrendDirection.STABLE,
        confidence: ForecastConfidence = ForecastConfidence.MODERATE,
        incident_count: int = 0,
        growth_rate_pct: float = 0.0,
        details: str = "",
    ) -> TrendRecord:
        record = TrendRecord(
            category=category,
            direction=direction,
            confidence=confidence,
            incident_count=incident_count,
            growth_rate_pct=growth_rate_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "trend_forecaster.trend_recorded",
            record_id=record.id,
            category=category.value,
            direction=direction.value,
        )
        return record

    def get_trend(self, record_id: str) -> TrendRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_trends(
        self,
        category: IncidentCategory | None = None,
        direction: TrendDirection | None = None,
        limit: int = 50,
    ) -> list[TrendRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.category == category]
        if direction is not None:
            results = [r for r in results if r.direction == direction]
        return results[-limit:]

    def add_data_point(
        self,
        category: IncidentCategory = IncidentCategory.INFRASTRUCTURE,
        period_label: str = "",
        incident_count: int = 0,
        forecast_count: int = 0,
        notes: str = "",
    ) -> ForecastDataPoint:
        point = ForecastDataPoint(
            category=category,
            period_label=period_label,
            incident_count=incident_count,
            forecast_count=forecast_count,
            notes=notes,
        )
        self._data_points.append(point)
        if len(self._data_points) > self._max_records:
            self._data_points = self._data_points[-self._max_records :]
        logger.info(
            "trend_forecaster.data_point_added",
            category=category.value,
            period_label=period_label,
        )
        return point

    # -- domain operations -----------------------------------------------

    def analyze_trend_by_category(self, category: IncidentCategory) -> dict[str, Any]:
        """Analyze trend data for a specific incident category."""
        records = [r for r in self._records if r.category == category]
        if not records:
            return {"category": category.value, "status": "no_data"}
        avg_growth = round(sum(r.growth_rate_pct for r in records) / len(records), 2)
        rising = sum(1 for r in records if r.direction == TrendDirection.INCREASING)
        return {
            "category": category.value,
            "total": len(records),
            "avg_growth_rate_pct": avg_growth,
            "rising_count": rising,
            "within_limits": avg_growth <= self._max_growth_rate_pct,
        }

    def identify_rising_trends(self) -> list[dict[str, Any]]:
        """Find categories with increasing trend direction."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.direction == TrendDirection.INCREASING:
                results.append(
                    {
                        "category": r.category.value,
                        "growth_rate_pct": r.growth_rate_pct,
                        "incident_count": r.incident_count,
                        "confidence": r.confidence.value,
                    }
                )
        results.sort(key=lambda x: x["growth_rate_pct"], reverse=True)
        return results

    def rank_by_growth_rate(self) -> list[dict[str, Any]]:
        """Rank trend records by growth rate descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "category": r.category.value,
                    "growth_rate_pct": r.growth_rate_pct,
                    "direction": r.direction.value,
                    "confidence": r.confidence.value,
                }
            )
        results.sort(key=lambda x: x["growth_rate_pct"], reverse=True)
        return results

    def detect_trend_anomalies(self) -> list[dict[str, Any]]:
        """Detect anomalous trends per category using sufficient historical data."""
        cat_records: dict[str, list[TrendRecord]] = {}
        for r in self._records:
            cat_records.setdefault(r.category.value, []).append(r)
        results: list[dict[str, Any]] = []
        for cat, recs in cat_records.items():
            if len(recs) > 3:
                rates = [r.growth_rate_pct for r in recs]
                anomaly = "spike" if rates[-1] > rates[0] else "drop"
                results.append(
                    {
                        "category": cat,
                        "record_count": len(recs),
                        "anomaly_type": anomaly,
                    }
                )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> TrendForecasterReport:
        by_category: dict[str, int] = {}
        by_direction: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_direction[r.direction.value] = by_direction.get(r.direction.value, 0) + 1
        avg_growth = (
            round(sum(r.growth_rate_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rising_count = sum(1 for r in self._records if r.direction == TrendDirection.INCREASING)
        recs: list[str] = []
        if avg_growth > self._max_growth_rate_pct:
            recs.append(
                f"Average growth rate {avg_growth}% exceeds threshold of"
                f" {self._max_growth_rate_pct}%"
            )
        if rising_count > 0:
            recs.append(f"{rising_count} rising trend(s) detected")
        if not recs:
            recs.append("Incident trends within acceptable growth limits")
        return TrendForecasterReport(
            total_trends=len(self._records),
            total_data_points=len(self._data_points),
            avg_growth_rate_pct=avg_growth,
            by_category=by_category,
            by_direction=by_direction,
            rising_count=rising_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._data_points.clear()
        logger.info("trend_forecaster.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_trends": len(self._records),
            "total_data_points": len(self._data_points),
            "max_growth_rate_pct": self._max_growth_rate_pct,
            "category_distribution": cat_dist,
            "unique_categories": len({r.category.value for r in self._records}),
        }
