"""SLO Error Budget Forecaster — forecast error budget depletion and predict exhaustion dates."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BudgetForecast(StrEnum):
    SAFE = "safe"
    CAUTION = "caution"
    WARNING = "warning"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"


class DepletionRate(StrEnum):
    ACCELERATING = "accelerating"
    STEADY = "steady"
    DECELERATING = "decelerating"
    RECOVERING = "recovering"
    STABLE = "stable"


class ForecastHorizon(StrEnum):
    ONE_DAY = "one_day"
    ONE_WEEK = "one_week"
    ONE_MONTH = "one_month"
    ONE_QUARTER = "one_quarter"
    ONE_YEAR = "one_year"


# --- Models ---


class ForecastRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    forecast_id: str = ""
    budget_forecast: BudgetForecast = BudgetForecast.SAFE
    depletion_rate: DepletionRate = DepletionRate.STABLE
    forecast_horizon: ForecastHorizon = ForecastHorizon.ONE_MONTH
    remaining_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ForecastMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    forecast_id: str = ""
    budget_forecast: BudgetForecast = BudgetForecast.SAFE
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SLOErrorBudgetForecastReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    critical_forecasts: int = 0
    avg_remaining_pct: float = 0.0
    by_forecast: dict[str, int] = Field(default_factory=dict)
    by_rate: dict[str, int] = Field(default_factory=dict)
    by_horizon: dict[str, int] = Field(default_factory=dict)
    top_depleting: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLOErrorBudgetForecaster:
    """Forecast error budget depletion, predict exhaustion dates, recommend throttling."""

    def __init__(
        self,
        max_records: int = 200000,
        min_remaining_pct: float = 20.0,
    ) -> None:
        self._max_records = max_records
        self._min_remaining_pct = min_remaining_pct
        self._records: list[ForecastRecord] = []
        self._metrics: list[ForecastMetric] = []
        logger.info(
            "slo_error_budget_forecaster.initialized",
            max_records=max_records,
            min_remaining_pct=min_remaining_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_forecast(
        self,
        forecast_id: str,
        budget_forecast: BudgetForecast = BudgetForecast.SAFE,
        depletion_rate: DepletionRate = DepletionRate.STABLE,
        forecast_horizon: ForecastHorizon = ForecastHorizon.ONE_MONTH,
        remaining_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ForecastRecord:
        record = ForecastRecord(
            forecast_id=forecast_id,
            budget_forecast=budget_forecast,
            depletion_rate=depletion_rate,
            forecast_horizon=forecast_horizon,
            remaining_pct=remaining_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "slo_error_budget_forecaster.forecast_recorded",
            record_id=record.id,
            forecast_id=forecast_id,
            budget_forecast=budget_forecast.value,
            depletion_rate=depletion_rate.value,
        )
        return record

    def get_forecast(self, record_id: str) -> ForecastRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_forecasts(
        self,
        budget_forecast: BudgetForecast | None = None,
        depletion_rate: DepletionRate | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ForecastRecord]:
        results = list(self._records)
        if budget_forecast is not None:
            results = [r for r in results if r.budget_forecast == budget_forecast]
        if depletion_rate is not None:
            results = [r for r in results if r.depletion_rate == depletion_rate]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        forecast_id: str,
        budget_forecast: BudgetForecast = BudgetForecast.SAFE,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ForecastMetric:
        metric = ForecastMetric(
            forecast_id=forecast_id,
            budget_forecast=budget_forecast,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "slo_error_budget_forecaster.metric_added",
            forecast_id=forecast_id,
            budget_forecast=budget_forecast.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_forecast_distribution(self) -> dict[str, Any]:
        """Group by budget_forecast; return count and avg remaining_pct per forecast."""
        forecast_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.budget_forecast.value
            forecast_data.setdefault(key, []).append(r.remaining_pct)
        result: dict[str, Any] = {}
        for forecast, scores in forecast_data.items():
            result[forecast] = {
                "count": len(scores),
                "avg_remaining_pct": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_critical_forecasts(self) -> list[dict[str, Any]]:
        """Return forecasts where budget_forecast is CRITICAL or EXHAUSTED."""
        critical_forecasts = {
            BudgetForecast.CRITICAL,
            BudgetForecast.EXHAUSTED,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.budget_forecast in critical_forecasts:
                results.append(
                    {
                        "record_id": r.id,
                        "forecast_id": r.forecast_id,
                        "budget_forecast": r.budget_forecast.value,
                        "depletion_rate": r.depletion_rate.value,
                        "remaining_pct": r.remaining_pct,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["remaining_pct"], reverse=False)
        return results

    def rank_by_remaining(self) -> list[dict[str, Any]]:
        """Group by service, avg remaining_pct, sort asc (worst first)."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            service_scores.setdefault(r.service, []).append(r.remaining_pct)
        results: list[dict[str, Any]] = []
        for service, scores in service_scores.items():
            results.append(
                {
                    "service": service,
                    "avg_remaining_pct": round(sum(scores) / len(scores), 2),
                    "forecast_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_remaining_pct"], reverse=False)
        return results

    def detect_forecast_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [m.metric_score for m in self._metrics]
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

    def generate_report(self) -> SLOErrorBudgetForecastReport:
        by_forecast: dict[str, int] = {}
        by_rate: dict[str, int] = {}
        by_horizon: dict[str, int] = {}
        for r in self._records:
            by_forecast[r.budget_forecast.value] = by_forecast.get(r.budget_forecast.value, 0) + 1
            by_rate[r.depletion_rate.value] = by_rate.get(r.depletion_rate.value, 0) + 1
            by_horizon[r.forecast_horizon.value] = by_horizon.get(r.forecast_horizon.value, 0) + 1
        critical_forecasts = sum(
            1
            for r in self._records
            if r.budget_forecast in {BudgetForecast.CRITICAL, BudgetForecast.EXHAUSTED}
        )
        avg_remaining_pct = (
            round(
                sum(r.remaining_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        critical = self.identify_critical_forecasts()
        top_depleting = [c["forecast_id"] for c in critical]
        recs: list[str] = []
        if critical:
            recs.append(
                f"{len(critical)} critical forecast(s) detected — review error budget allocation"
            )
        low_rem = sum(1 for r in self._records if r.remaining_pct < self._min_remaining_pct)
        if low_rem > 0:
            recs.append(
                f"{low_rem} forecast(s) below remaining threshold ({self._min_remaining_pct}%)"
            )
        if not recs:
            recs.append("Error budget forecast levels are acceptable")
        return SLOErrorBudgetForecastReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            critical_forecasts=critical_forecasts,
            avg_remaining_pct=avg_remaining_pct,
            by_forecast=by_forecast,
            by_rate=by_rate,
            by_horizon=by_horizon,
            top_depleting=top_depleting,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("slo_error_budget_forecaster.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        forecast_dist: dict[str, int] = {}
        for r in self._records:
            key = r.budget_forecast.value
            forecast_dist[key] = forecast_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_remaining_pct": self._min_remaining_pct,
            "forecast_distribution": forecast_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_forecasts": len({r.forecast_id for r in self._records}),
        }
