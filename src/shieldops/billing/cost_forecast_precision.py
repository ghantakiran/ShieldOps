"""Cost Forecast Precision — measure and improve forecast accuracy and bias."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ForecastAccuracy(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNRELIABLE = "unreliable"


class BiasDirection(StrEnum):
    OVER_FORECAST = "over_forecast"
    UNDER_FORECAST = "under_forecast"
    CALIBRATED = "calibrated"
    VOLATILE = "volatile"
    TRENDING = "trending"


class ForecastPeriod(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"


# --- Models ---


class PrecisionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    forecast_name: str = ""
    forecast_accuracy: ForecastAccuracy = ForecastAccuracy.EXCELLENT
    bias_direction: BiasDirection = BiasDirection.CALIBRATED
    forecast_period: ForecastPeriod = ForecastPeriod.MONTHLY
    precision_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PrecisionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    forecast_name: str = ""
    forecast_accuracy: ForecastAccuracy = ForecastAccuracy.EXCELLENT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostForecastReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_precision_count: int = 0
    avg_precision_score: float = 0.0
    by_accuracy: dict[str, int] = Field(default_factory=dict)
    by_bias: dict[str, int] = Field(default_factory=dict)
    by_period: dict[str, int] = Field(default_factory=dict)
    top_imprecise: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostForecastPrecision:
    """Measure forecast precision, identify low-precision forecasts, detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        precision_accuracy_threshold: float = 85.0,
    ) -> None:
        self._max_records = max_records
        self._precision_accuracy_threshold = precision_accuracy_threshold
        self._records: list[PrecisionRecord] = []
        self._analyses: list[PrecisionAnalysis] = []
        logger.info(
            "cost_forecast_precision.initialized",
            max_records=max_records,
            precision_accuracy_threshold=precision_accuracy_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_precision(
        self,
        forecast_name: str,
        forecast_accuracy: ForecastAccuracy = ForecastAccuracy.EXCELLENT,
        bias_direction: BiasDirection = BiasDirection.CALIBRATED,
        forecast_period: ForecastPeriod = ForecastPeriod.MONTHLY,
        precision_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PrecisionRecord:
        record = PrecisionRecord(
            forecast_name=forecast_name,
            forecast_accuracy=forecast_accuracy,
            bias_direction=bias_direction,
            forecast_period=forecast_period,
            precision_score=precision_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_forecast_precision.precision_recorded",
            record_id=record.id,
            forecast_name=forecast_name,
            forecast_accuracy=forecast_accuracy.value,
            bias_direction=bias_direction.value,
        )
        return record

    def get_precision(self, record_id: str) -> PrecisionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_precisions(
        self,
        forecast_accuracy: ForecastAccuracy | None = None,
        bias_direction: BiasDirection | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PrecisionRecord]:
        results = list(self._records)
        if forecast_accuracy is not None:
            results = [r for r in results if r.forecast_accuracy == forecast_accuracy]
        if bias_direction is not None:
            results = [r for r in results if r.bias_direction == bias_direction]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        forecast_name: str,
        forecast_accuracy: ForecastAccuracy = ForecastAccuracy.EXCELLENT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PrecisionAnalysis:
        analysis = PrecisionAnalysis(
            forecast_name=forecast_name,
            forecast_accuracy=forecast_accuracy,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "cost_forecast_precision.analysis_added",
            forecast_name=forecast_name,
            forecast_accuracy=forecast_accuracy.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_precision_distribution(self) -> dict[str, Any]:
        """Group by forecast_accuracy; return count and avg score."""
        accuracy_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.forecast_accuracy.value
            accuracy_data.setdefault(key, []).append(r.precision_score)
        result: dict[str, Any] = {}
        for accuracy, scores in accuracy_data.items():
            result[accuracy] = {
                "count": len(scores),
                "avg_precision_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_precision_forecasts(self) -> list[dict[str, Any]]:
        """Return forecasts where precision_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.precision_score < self._precision_accuracy_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "forecast_name": r.forecast_name,
                        "forecast_accuracy": r.forecast_accuracy.value,
                        "bias_direction": r.bias_direction.value,
                        "precision_score": r.precision_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["precision_score"], reverse=False)
        return results

    def rank_by_precision(self) -> list[dict[str, Any]]:
        """Group by service, avg precision_score, sort asc (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.precision_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_precision_score": round(sum(scores) / len(scores), 2),
                    "precision_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_precision_score"], reverse=False)
        return results

    def detect_precision_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [a.analysis_score for a in self._analyses]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> CostForecastReport:
        by_accuracy: dict[str, int] = {}
        by_bias: dict[str, int] = {}
        by_period: dict[str, int] = {}
        for r in self._records:
            by_accuracy[r.forecast_accuracy.value] = (
                by_accuracy.get(r.forecast_accuracy.value, 0) + 1
            )
            by_bias[r.bias_direction.value] = by_bias.get(r.bias_direction.value, 0) + 1
            by_period[r.forecast_period.value] = by_period.get(r.forecast_period.value, 0) + 1
        low_precision_count = sum(
            1 for r in self._records if r.precision_score < self._precision_accuracy_threshold
        )
        avg_precision = (
            round(
                sum(r.precision_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        low = self.identify_low_precision_forecasts()
        top_imprecise = [item["forecast_name"] for item in low]
        recs: list[str] = []
        if low:
            recs.append(f"{len(low)} low-precision forecast(s) detected — review forecast models")
        high_p = sum(
            1 for r in self._records if r.precision_score >= self._precision_accuracy_threshold
        )
        if high_p > 0:
            recs.append(
                f"{high_p} forecast(s) above precision threshold"
                f" ({self._precision_accuracy_threshold}%)"
            )
        if not recs:
            recs.append("Cost forecast precision levels are acceptable")
        return CostForecastReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_precision_count=low_precision_count,
            avg_precision_score=avg_precision,
            by_accuracy=by_accuracy,
            by_bias=by_bias,
            by_period=by_period,
            top_imprecise=top_imprecise,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("cost_forecast_precision.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        accuracy_dist: dict[str, int] = {}
        for r in self._records:
            key = r.forecast_accuracy.value
            accuracy_dist[key] = accuracy_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "precision_accuracy_threshold": self._precision_accuracy_threshold,
            "accuracy_distribution": accuracy_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
