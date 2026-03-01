"""Service Health Trend Analyzer — track service health dimensions and trends."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HealthDimension(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    SATURATION = "saturation"


class TrendDirection(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


class HealthGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


# --- Models ---


class HealthTrendRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    health_dimension: HealthDimension = HealthDimension.AVAILABILITY
    trend_direction: TrendDirection = TrendDirection.STABLE
    health_grade: HealthGrade = HealthGrade.GOOD
    health_score: float = 0.0
    service: str = ""
    created_at: float = Field(default_factory=time.time)


class TrendDataPoint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_label: str = ""
    health_dimension: HealthDimension = HealthDimension.AVAILABILITY
    score_threshold: float = 0.0
    avg_health_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ServiceHealthTrendReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_data_points: int = 0
    degrading_services: int = 0
    avg_health_score: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_direction: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    top_items: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceHealthTrendAnalyzer:
    """Track service health dimensions, trends, and grades over time."""

    def __init__(
        self,
        max_records: int = 200000,
        min_health_trend_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_health_trend_score = min_health_trend_score
        self._records: list[HealthTrendRecord] = []
        self._data_points: list[TrendDataPoint] = []
        logger.info(
            "health_trend.initialized",
            max_records=max_records,
            min_health_trend_score=min_health_trend_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_trend(
        self,
        service_id: str,
        health_dimension: HealthDimension = HealthDimension.AVAILABILITY,
        trend_direction: TrendDirection = TrendDirection.STABLE,
        health_grade: HealthGrade = HealthGrade.GOOD,
        health_score: float = 0.0,
        service: str = "",
    ) -> HealthTrendRecord:
        record = HealthTrendRecord(
            service_id=service_id,
            health_dimension=health_dimension,
            trend_direction=trend_direction,
            health_grade=health_grade,
            health_score=health_score,
            service=service,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "health_trend.trend_recorded",
            record_id=record.id,
            service_id=service_id,
            health_dimension=health_dimension.value,
            trend_direction=trend_direction.value,
        )
        return record

    def get_trend(self, record_id: str) -> HealthTrendRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_trends(
        self,
        dimension: HealthDimension | None = None,
        direction: TrendDirection | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[HealthTrendRecord]:
        results = list(self._records)
        if dimension is not None:
            results = [r for r in results if r.health_dimension == dimension]
        if direction is not None:
            results = [r for r in results if r.trend_direction == direction]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def add_data_point(
        self,
        data_label: str,
        health_dimension: HealthDimension = HealthDimension.AVAILABILITY,
        score_threshold: float = 0.0,
        avg_health_score: float = 0.0,
        description: str = "",
    ) -> TrendDataPoint:
        dp = TrendDataPoint(
            data_label=data_label,
            health_dimension=health_dimension,
            score_threshold=score_threshold,
            avg_health_score=avg_health_score,
            description=description,
        )
        self._data_points.append(dp)
        if len(self._data_points) > self._max_records:
            self._data_points = self._data_points[-self._max_records :]
        logger.info(
            "health_trend.data_point_added",
            data_label=data_label,
            health_dimension=health_dimension.value,
            score_threshold=score_threshold,
        )
        return dp

    # -- domain operations --------------------------------------------------

    def analyze_health_trends(self) -> dict[str, Any]:
        """Group by dimension; return count and avg health score per dimension."""
        dimension_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.health_dimension.value
            dimension_data.setdefault(key, []).append(r.health_score)
        result: dict[str, Any] = {}
        for dimension, scores in dimension_data.items():
            result[dimension] = {
                "count": len(scores),
                "avg_health_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_degrading_services(self) -> list[dict[str, Any]]:
        """Return records where grade is POOR or CRITICAL."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.health_grade in (HealthGrade.POOR, HealthGrade.CRITICAL):
                results.append(
                    {
                        "record_id": r.id,
                        "service_id": r.service_id,
                        "health_dimension": r.health_dimension.value,
                        "health_score": r.health_score,
                        "service": r.service,
                    }
                )
        return results

    def rank_by_health_score(self) -> list[dict[str, Any]]:
        """Group by service, avg health score, sort descending."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            service_scores.setdefault(r.service, []).append(r.health_score)
        results: list[dict[str, Any]] = []
        for service, scores in service_scores.items():
            results.append(
                {
                    "service": service,
                    "avg_health_score": round(sum(scores) / len(scores), 2),
                    "count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_health_score"], reverse=True)
        return results

    def detect_trend_anomalies(self) -> dict[str, Any]:
        """Split-half on avg_health_score; delta threshold 5.0."""
        if len(self._data_points) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [dp.avg_health_score for dp in self._data_points]
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

    def generate_report(self) -> ServiceHealthTrendReport:
        by_dimension: dict[str, int] = {}
        by_direction: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        for r in self._records:
            by_dimension[r.health_dimension.value] = (
                by_dimension.get(r.health_dimension.value, 0) + 1
            )
            by_direction[r.trend_direction.value] = by_direction.get(r.trend_direction.value, 0) + 1
            by_grade[r.health_grade.value] = by_grade.get(r.health_grade.value, 0) + 1
        degrading_count = sum(
            1 for r in self._records if r.health_grade in (HealthGrade.POOR, HealthGrade.CRITICAL)
        )
        avg_score = (
            round(sum(r.health_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_health_score()
        top_items = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if avg_score < self._min_health_trend_score:
            recs.append(
                f"Avg health score {avg_score} is below threshold ({self._min_health_trend_score})"
            )
        if degrading_count > 0:
            recs.append(f"{degrading_count} degrading service(s) detected — review health")
        if not recs:
            recs.append("Service health trends are within acceptable limits")
        return ServiceHealthTrendReport(
            total_records=len(self._records),
            total_data_points=len(self._data_points),
            degrading_services=degrading_count,
            avg_health_score=avg_score,
            by_dimension=by_dimension,
            by_direction=by_direction,
            by_grade=by_grade,
            top_items=top_items,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._data_points.clear()
        logger.info("health_trend.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dimension_dist: dict[str, int] = {}
        for r in self._records:
            key = r.health_dimension.value
            dimension_dist[key] = dimension_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_data_points": len(self._data_points),
            "min_health_trend_score": self._min_health_trend_score,
            "dimension_distribution": dimension_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_service_ids": len({r.service_id for r in self._records}),
        }
