"""Cost Forecast Accuracy Tracker — track and improve cost forecast accuracy over time."""

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
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class AccuracyGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNRELIABLE = "unreliable"


class DeviationCause(StrEnum):
    DEMAND_SPIKE = "demand_spike"
    PRICING_CHANGE = "pricing_change"
    RESOURCE_DRIFT = "resource_drift"
    SEASONAL = "seasonal"
    ANOMALY = "anomaly"


# --- Models ---


class ForecastRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    forecast_id: str = ""
    forecast_horizon: ForecastHorizon = ForecastHorizon.MONTHLY
    accuracy_grade: AccuracyGrade = AccuracyGrade.FAIR
    deviation_cause: DeviationCause = DeviationCause.ANOMALY
    accuracy_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ForecastEvaluation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    forecast_id: str = ""
    forecast_horizon: ForecastHorizon = ForecastHorizon.MONTHLY
    eval_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostForecastAccuracyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_evaluations: int = 0
    inaccurate_count: int = 0
    avg_accuracy_pct: float = 0.0
    by_horizon: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    by_cause: dict[str, int] = Field(default_factory=dict)
    top_inaccurate: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostForecastAccuracyTracker:
    """Track and improve cost forecast accuracy over time."""

    def __init__(
        self,
        max_records: int = 200000,
        min_accuracy_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_accuracy_pct = min_accuracy_pct
        self._records: list[ForecastRecord] = []
        self._evaluations: list[ForecastEvaluation] = []
        logger.info(
            "cost_forecast_accuracy.initialized",
            max_records=max_records,
            min_accuracy_pct=min_accuracy_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_forecast(
        self,
        forecast_id: str,
        forecast_horizon: ForecastHorizon = ForecastHorizon.MONTHLY,
        accuracy_grade: AccuracyGrade = AccuracyGrade.FAIR,
        deviation_cause: DeviationCause = DeviationCause.ANOMALY,
        accuracy_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ForecastRecord:
        record = ForecastRecord(
            forecast_id=forecast_id,
            forecast_horizon=forecast_horizon,
            accuracy_grade=accuracy_grade,
            deviation_cause=deviation_cause,
            accuracy_pct=accuracy_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_forecast_accuracy.forecast_recorded",
            record_id=record.id,
            forecast_id=forecast_id,
            forecast_horizon=forecast_horizon.value,
            accuracy_grade=accuracy_grade.value,
        )
        return record

    def get_forecast(self, record_id: str) -> ForecastRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_forecasts(
        self,
        horizon: ForecastHorizon | None = None,
        grade: AccuracyGrade | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ForecastRecord]:
        results = list(self._records)
        if horizon is not None:
            results = [r for r in results if r.forecast_horizon == horizon]
        if grade is not None:
            results = [r for r in results if r.accuracy_grade == grade]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_evaluation(
        self,
        forecast_id: str,
        forecast_horizon: ForecastHorizon = ForecastHorizon.MONTHLY,
        eval_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ForecastEvaluation:
        evaluation = ForecastEvaluation(
            forecast_id=forecast_id,
            forecast_horizon=forecast_horizon,
            eval_score=eval_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._evaluations.append(evaluation)
        if len(self._evaluations) > self._max_records:
            self._evaluations = self._evaluations[-self._max_records :]
        logger.info(
            "cost_forecast_accuracy.evaluation_added",
            forecast_id=forecast_id,
            forecast_horizon=forecast_horizon.value,
            eval_score=eval_score,
        )
        return evaluation

    # -- domain operations --------------------------------------------------

    def analyze_accuracy_distribution(self) -> dict[str, Any]:
        """Group by forecast_horizon; return count and avg accuracy_pct per horizon."""
        horizon_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.forecast_horizon.value
            horizon_data.setdefault(key, []).append(r.accuracy_pct)
        result: dict[str, Any] = {}
        for horizon, pcts in horizon_data.items():
            result[horizon] = {
                "count": len(pcts),
                "avg_accuracy_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_inaccurate_forecasts(self) -> list[dict[str, Any]]:
        """Return records where accuracy_grade is POOR or UNRELIABLE."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.accuracy_grade in (AccuracyGrade.POOR, AccuracyGrade.UNRELIABLE):
                results.append(
                    {
                        "record_id": r.id,
                        "forecast_id": r.forecast_id,
                        "accuracy_grade": r.accuracy_grade.value,
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
        for service, pcts in svc_pcts.items():
            results.append(
                {
                    "service": service,
                    "avg_accuracy_pct": round(sum(pcts) / len(pcts), 2),
                    "forecast_count": len(pcts),
                }
            )
        results.sort(key=lambda x: x["avg_accuracy_pct"])
        return results

    def detect_accuracy_trends(self) -> dict[str, Any]:
        """Split-half comparison on eval_score; delta threshold 5.0."""
        if len(self._evaluations) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [e.eval_score for e in self._evaluations]
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

    def generate_report(self) -> CostForecastAccuracyReport:
        by_horizon: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        by_cause: dict[str, int] = {}
        for r in self._records:
            by_horizon[r.forecast_horizon.value] = by_horizon.get(r.forecast_horizon.value, 0) + 1
            by_grade[r.accuracy_grade.value] = by_grade.get(r.accuracy_grade.value, 0) + 1
            by_cause[r.deviation_cause.value] = by_cause.get(r.deviation_cause.value, 0) + 1
        inaccurate_count = sum(
            1
            for r in self._records
            if r.accuracy_grade in (AccuracyGrade.POOR, AccuracyGrade.UNRELIABLE)
        )
        avg_accuracy = (
            round(sum(r.accuracy_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_accuracy()
        top_inaccurate = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if inaccurate_count > 0:
            recs.append(
                f"{inaccurate_count} inaccurate forecast(s) detected — review forecast models"
            )
        inaccurate_pct = (
            round(inaccurate_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        if inaccurate_pct > (100.0 - self._min_accuracy_pct):
            recs.append(
                f"Inaccurate forecast rate {inaccurate_pct}% exceeds "
                f"threshold ({100.0 - self._min_accuracy_pct}%)"
            )
        if not recs:
            recs.append("Forecast accuracy levels are acceptable")
        return CostForecastAccuracyReport(
            total_records=len(self._records),
            total_evaluations=len(self._evaluations),
            inaccurate_count=inaccurate_count,
            avg_accuracy_pct=avg_accuracy,
            by_horizon=by_horizon,
            by_grade=by_grade,
            by_cause=by_cause,
            top_inaccurate=top_inaccurate,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._evaluations.clear()
        logger.info("cost_forecast_accuracy.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        horizon_dist: dict[str, int] = {}
        for r in self._records:
            key = r.forecast_horizon.value
            horizon_dist[key] = horizon_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_evaluations": len(self._evaluations),
            "min_accuracy_pct": self._min_accuracy_pct,
            "horizon_distribution": horizon_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
