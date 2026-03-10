"""Operational Forecasting Engine

Time-series forecasting for operational metrics with
multi-horizon predictions and accuracy tracking.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ForecastHorizon(StrEnum):
    ONE_HOUR = "one_hour"
    SIX_HOURS = "six_hours"
    ONE_DAY = "one_day"
    SEVEN_DAYS = "seven_days"
    THIRTY_DAYS = "thirty_days"


class ForecastMethod(StrEnum):
    ARIMA = "arima"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    PROPHET = "prophet"
    LINEAR = "linear"
    ENSEMBLE = "ensemble"


class ForecastAccuracy(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class ForecastRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    service: str = ""
    horizon: ForecastHorizon = ForecastHorizon.ONE_DAY
    method: ForecastMethod = ForecastMethod.LINEAR
    predicted_value: float = 0.0
    actual_value: float = 0.0
    confidence_interval_pct: float = 0.0
    accuracy_score: float = 0.0
    breach_predicted: bool = False
    created_at: float = Field(default_factory=time.time)


class ForecastAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ForecastReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_accuracy: float = 0.0
    breach_prediction_rate: float = 0.0
    by_horizon: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    by_accuracy_band: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class OperationalForecastingEngine:
    """Operational Forecasting Engine

    Time-series forecasting for operational metrics
    with multi-horizon predictions and accuracy tracking.
    """

    def __init__(
        self,
        max_records: int = 200000,
        accuracy_threshold: float = 0.8,
    ) -> None:
        self._max_records = max_records
        self._accuracy_threshold = accuracy_threshold
        self._records: list[ForecastRecord] = []
        self._analyses: list[ForecastAnalysis] = []
        logger.info(
            "operational_forecasting_engine.initialized",
            max_records=max_records,
            accuracy_threshold=accuracy_threshold,
        )

    def add_record(
        self,
        metric_name: str,
        service: str,
        horizon: ForecastHorizon = (ForecastHorizon.ONE_DAY),
        method: ForecastMethod = ForecastMethod.LINEAR,
        predicted_value: float = 0.0,
        actual_value: float = 0.0,
        confidence_interval_pct: float = 0.0,
        accuracy_score: float = 0.0,
        breach_predicted: bool = False,
    ) -> ForecastRecord:
        record = ForecastRecord(
            metric_name=metric_name,
            service=service,
            horizon=horizon,
            method=method,
            predicted_value=predicted_value,
            actual_value=actual_value,
            confidence_interval_pct=(confidence_interval_pct),
            accuracy_score=accuracy_score,
            breach_predicted=breach_predicted,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "operational_forecasting_engine.record_added",
            record_id=record.id,
            metric_name=metric_name,
            service=service,
        )
        return record

    def generate_forecast(self, metric_name: str, service: str = "") -> dict[str, Any]:
        matching = [r for r in self._records if r.metric_name == metric_name]
        if service:
            matching = [r for r in matching if r.service == service]
        if not matching:
            return {
                "metric_name": metric_name,
                "status": "no_data",
            }
        latest = sorted(
            matching,
            key=lambda r: r.created_at,
            reverse=True,
        )[:10]
        avg_predicted = round(
            sum(r.predicted_value for r in latest) / len(latest),
            4,
        )
        return {
            "metric_name": metric_name,
            "service": service or "all",
            "avg_predicted": avg_predicted,
            "sample_count": len(latest),
            "latest_method": latest[0].method.value,
        }

    def evaluate_accuracy(self, method: ForecastMethod | None = None) -> dict[str, Any]:
        matching = [r for r in self._records if r.actual_value > 0]
        if method is not None:
            matching = [r for r in matching if r.method == method]
        if not matching:
            return {
                "method": (method.value if method else "all"),
                "status": "no_data",
            }
        scores = [r.accuracy_score for r in matching]
        avg = round(sum(scores) / len(scores), 4)
        band = (
            "excellent"
            if avg >= 0.9
            else "good"
            if avg >= 0.8
            else "fair"
            if avg >= 0.6
            else "poor"
        )
        return {
            "method": (method.value if method else "all"),
            "avg_accuracy": avg,
            "band": band,
            "sample_count": len(matching),
        }

    def detect_threshold_breach(self, metric_name: str, threshold: float) -> list[dict[str, Any]]:
        matching = [
            r
            for r in self._records
            if r.metric_name == metric_name and r.predicted_value > threshold
        ]
        return [
            {
                "record_id": r.id,
                "predicted": r.predicted_value,
                "threshold": threshold,
                "service": r.service,
                "horizon": r.horizon.value,
            }
            for r in matching
        ]

    def process(self, metric_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.metric_name == metric_name]
        if not matching:
            return {
                "metric_name": metric_name,
                "status": "no_data",
            }
        scores = [r.accuracy_score for r in matching if r.accuracy_score > 0]
        avg_acc = round(sum(scores) / len(scores), 4) if scores else 0.0
        breaches = sum(1 for r in matching if r.breach_predicted)
        return {
            "metric_name": metric_name,
            "record_count": len(matching),
            "avg_accuracy": avg_acc,
            "breach_predictions": breaches,
        }

    def generate_report(self) -> ForecastReport:
        by_horizon: dict[str, int] = {}
        by_method: dict[str, int] = {}
        by_band: dict[str, int] = {}
        for r in self._records:
            hv = r.horizon.value
            by_horizon[hv] = by_horizon.get(hv, 0) + 1
            mv = r.method.value
            by_method[mv] = by_method.get(mv, 0) + 1
            band = (
                "excellent"
                if r.accuracy_score >= 0.9
                else "good"
                if r.accuracy_score >= 0.8
                else "fair"
                if r.accuracy_score >= 0.6
                else "poor"
            )
            by_band[band] = by_band.get(band, 0) + 1
        scores = [r.accuracy_score for r in self._records if r.accuracy_score > 0]
        avg_acc = round(sum(scores) / len(scores), 4) if scores else 0.0
        total = len(self._records)
        breaches = sum(1 for r in self._records if r.breach_predicted)
        breach_rate = round(breaches / total, 4) if total else 0.0
        recs: list[str] = []
        poor = by_band.get("poor", 0)
        if total > 0 and poor / total > 0.3:
            recs.append("Over 30% forecasts are poor — retrain models")
        if avg_acc < self._accuracy_threshold:
            recs.append(f"Avg accuracy {avg_acc:.0%} — consider ensemble methods")
        if not recs:
            recs.append("Forecast accuracy is nominal")
        return ForecastReport(
            total_records=total,
            total_analyses=len(self._analyses),
            avg_accuracy=avg_acc,
            breach_prediction_rate=breach_rate,
            by_horizon=by_horizon,
            by_method=by_method,
            by_accuracy_band=by_band,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        method_dist: dict[str, int] = {}
        for r in self._records:
            k = r.method.value
            method_dist[k] = method_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "accuracy_threshold": (self._accuracy_threshold),
            "method_distribution": method_dist,
            "unique_metrics": len({r.metric_name for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("operational_forecasting_engine.cleared")
        return {"status": "cleared"}
