"""Capacity Forecast Validator — validate capacity forecasts against actuals."""

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
    INACCURATE = "inaccurate"


class ForecastBias(StrEnum):
    OVER_ESTIMATE = "over_estimate"
    SLIGHT_OVER = "slight_over"
    BALANCED = "balanced"
    SLIGHT_UNDER = "slight_under"
    UNDER_ESTIMATE = "under_estimate"


class ForecastMethod(StrEnum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    SEASONAL = "seasonal"
    ML_BASED = "ml_based"
    MANUAL = "manual"


# --- Models ---


class ForecastValidationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    forecast_id: str = ""
    forecast_accuracy: ForecastAccuracy = ForecastAccuracy.ACCEPTABLE
    forecast_bias: ForecastBias = ForecastBias.BALANCED
    forecast_method: ForecastMethod = ForecastMethod.LINEAR
    accuracy_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ForecastCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    forecast_id: str = ""
    forecast_accuracy: ForecastAccuracy = ForecastAccuracy.ACCEPTABLE
    check_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CapacityForecastReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_checks: int = 0
    inaccurate_count: int = 0
    avg_accuracy_pct: float = 0.0
    by_accuracy: dict[str, int] = Field(default_factory=dict)
    by_bias: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    top_inaccurate: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityForecastValidator:
    """Validate capacity forecasts against actuals, measure forecast accuracy, detect bias."""

    def __init__(
        self,
        max_records: int = 200000,
        min_accuracy_pct: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._min_accuracy_pct = min_accuracy_pct
        self._records: list[ForecastValidationRecord] = []
        self._checks: list[ForecastCheck] = []
        logger.info(
            "capacity_forecast_validator.initialized",
            max_records=max_records,
            min_accuracy_pct=min_accuracy_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_validation(
        self,
        forecast_id: str,
        forecast_accuracy: ForecastAccuracy = ForecastAccuracy.ACCEPTABLE,
        forecast_bias: ForecastBias = ForecastBias.BALANCED,
        forecast_method: ForecastMethod = ForecastMethod.LINEAR,
        accuracy_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ForecastValidationRecord:
        record = ForecastValidationRecord(
            forecast_id=forecast_id,
            forecast_accuracy=forecast_accuracy,
            forecast_bias=forecast_bias,
            forecast_method=forecast_method,
            accuracy_pct=accuracy_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "capacity_forecast_validator.validation_recorded",
            record_id=record.id,
            forecast_id=forecast_id,
            forecast_accuracy=forecast_accuracy.value,
            forecast_bias=forecast_bias.value,
        )
        return record

    def get_validation(self, record_id: str) -> ForecastValidationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_validations(
        self,
        accuracy: ForecastAccuracy | None = None,
        bias: ForecastBias | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ForecastValidationRecord]:
        results = list(self._records)
        if accuracy is not None:
            results = [r for r in results if r.forecast_accuracy == accuracy]
        if bias is not None:
            results = [r for r in results if r.forecast_bias == bias]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_check(
        self,
        forecast_id: str,
        forecast_accuracy: ForecastAccuracy = ForecastAccuracy.ACCEPTABLE,
        check_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ForecastCheck:
        check = ForecastCheck(
            forecast_id=forecast_id,
            forecast_accuracy=forecast_accuracy,
            check_score=check_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._checks.append(check)
        if len(self._checks) > self._max_records:
            self._checks = self._checks[-self._max_records :]
        logger.info(
            "capacity_forecast_validator.check_added",
            forecast_id=forecast_id,
            forecast_accuracy=forecast_accuracy.value,
            check_score=check_score,
        )
        return check

    # -- domain operations --------------------------------------------------

    def analyze_forecast_distribution(self) -> dict[str, Any]:
        """Group by forecast_accuracy; return count and avg accuracy_pct."""
        acc_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.forecast_accuracy.value
            acc_data.setdefault(key, []).append(r.accuracy_pct)
        result: dict[str, Any] = {}
        for acc, pcts in acc_data.items():
            result[acc] = {
                "count": len(pcts),
                "avg_accuracy_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_inaccurate_forecasts(self) -> list[dict[str, Any]]:
        """Return records where forecast_accuracy is POOR or INACCURATE."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.forecast_accuracy in (ForecastAccuracy.POOR, ForecastAccuracy.INACCURATE):
                results.append(
                    {
                        "record_id": r.id,
                        "forecast_id": r.forecast_id,
                        "forecast_accuracy": r.forecast_accuracy.value,
                        "accuracy_pct": r.accuracy_pct,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_accuracy(self) -> list[dict[str, Any]]:
        """Group by service, avg accuracy_pct, sort ascending (worst first)."""
        svc_pcts: dict[str, list[float]] = {}
        for r in self._records:
            svc_pcts.setdefault(r.service, []).append(r.accuracy_pct)
        results: list[dict[str, Any]] = []
        for svc, pcts in svc_pcts.items():
            results.append(
                {
                    "service": svc,
                    "avg_accuracy_pct": round(sum(pcts) / len(pcts), 2),
                }
            )
        results.sort(key=lambda x: x["avg_accuracy_pct"])
        return results

    def detect_forecast_trends(self) -> dict[str, Any]:
        """Split-half comparison on check_score; delta threshold 5.0."""
        if len(self._checks) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.check_score for c in self._checks]
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

    def generate_report(self) -> CapacityForecastReport:
        by_accuracy: dict[str, int] = {}
        by_bias: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._records:
            by_accuracy[r.forecast_accuracy.value] = (
                by_accuracy.get(r.forecast_accuracy.value, 0) + 1
            )
            by_bias[r.forecast_bias.value] = by_bias.get(r.forecast_bias.value, 0) + 1
            by_method[r.forecast_method.value] = by_method.get(r.forecast_method.value, 0) + 1
        inaccurate_count = sum(
            1
            for r in self._records
            if r.forecast_accuracy in (ForecastAccuracy.POOR, ForecastAccuracy.INACCURATE)
        )
        pcts = [r.accuracy_pct for r in self._records]
        avg_accuracy_pct = round(sum(pcts) / len(pcts), 2) if pcts else 0.0
        inaccurate_list = self.identify_inaccurate_forecasts()
        top_inaccurate = [o["forecast_id"] for o in inaccurate_list[:5]]
        recs: list[str] = []
        if self._records and avg_accuracy_pct < self._min_accuracy_pct:
            recs.append(
                f"Avg accuracy {avg_accuracy_pct}% below threshold ({self._min_accuracy_pct}%)"
            )
        if inaccurate_count > 0:
            recs.append(f"{inaccurate_count} inaccurate forecast(s) — review methodology")
        if not recs:
            recs.append("Capacity forecast accuracy levels are healthy")
        return CapacityForecastReport(
            total_records=len(self._records),
            total_checks=len(self._checks),
            inaccurate_count=inaccurate_count,
            avg_accuracy_pct=avg_accuracy_pct,
            by_accuracy=by_accuracy,
            by_bias=by_bias,
            by_method=by_method,
            top_inaccurate=top_inaccurate,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._checks.clear()
        logger.info("capacity_forecast_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        accuracy_dist: dict[str, int] = {}
        for r in self._records:
            key = r.forecast_accuracy.value
            accuracy_dist[key] = accuracy_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_checks": len(self._checks),
            "min_accuracy_pct": self._min_accuracy_pct,
            "accuracy_distribution": accuracy_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
