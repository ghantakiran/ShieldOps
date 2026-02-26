"""Error Budget Forecaster — forecast error budget exhaustion and burn rate analysis."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BudgetStatus(StrEnum):
    HEALTHY = "healthy"
    CAUTIOUS = "cautious"
    AT_RISK = "at_risk"
    EXHAUSTING = "exhausting"
    EXHAUSTED = "exhausted"


class BurnRate(StrEnum):
    SLOW = "slow"
    NORMAL = "normal"
    ELEVATED = "elevated"
    FAST = "fast"
    CRITICAL = "critical"


class ForecastHorizon(StrEnum):
    ONE_DAY = "one_day"
    ONE_WEEK = "one_week"
    TWO_WEEKS = "two_weeks"
    ONE_MONTH = "one_month"
    ONE_QUARTER = "one_quarter"


# --- Models ---


class BudgetSnapshot(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slo_name: str = ""
    budget_remaining_pct: float = 100.0
    burn_rate: BurnRate = BurnRate.NORMAL
    status: BudgetStatus = BudgetStatus.HEALTHY
    error_count: int = 0
    total_requests: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class BudgetForecast(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slo_name: str = ""
    horizon: ForecastHorizon = ForecastHorizon.ONE_WEEK
    projected_remaining_pct: float = 0.0
    exhaustion_days: float = 0.0
    confidence_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ErrorBudgetForecastReport(BaseModel):
    total_snapshots: int = 0
    total_forecasts: int = 0
    avg_remaining_pct: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_burn_rate: dict[str, int] = Field(default_factory=dict)
    at_risk_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ErrorBudgetForecaster:
    """Forecast error budget exhaustion and analyze burn rates."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_threshold_pct: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._risk_threshold_pct = risk_threshold_pct
        self._records: list[BudgetSnapshot] = []
        self._forecasts: list[BudgetForecast] = []
        logger.info(
            "error_budget_forecast.initialized",
            max_records=max_records,
            risk_threshold_pct=risk_threshold_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _remaining_to_status(self, remaining: float) -> BudgetStatus:
        if remaining >= 80:
            return BudgetStatus.HEALTHY
        if remaining >= 50:
            return BudgetStatus.CAUTIOUS
        if remaining >= 30:
            return BudgetStatus.AT_RISK
        if remaining > 0:
            return BudgetStatus.EXHAUSTING
        return BudgetStatus.EXHAUSTED

    # -- record / get / list ---------------------------------------------

    def record_snapshot(
        self,
        slo_name: str,
        budget_remaining_pct: float = 100.0,
        burn_rate: BurnRate = BurnRate.NORMAL,
        status: BudgetStatus | None = None,
        error_count: int = 0,
        total_requests: int = 0,
        details: str = "",
    ) -> BudgetSnapshot:
        if status is None:
            status = self._remaining_to_status(budget_remaining_pct)
        record = BudgetSnapshot(
            slo_name=slo_name,
            budget_remaining_pct=budget_remaining_pct,
            burn_rate=burn_rate,
            status=status,
            error_count=error_count,
            total_requests=total_requests,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "error_budget_forecast.snapshot_recorded",
            record_id=record.id,
            slo_name=slo_name,
            status=status.value,
        )
        return record

    def get_snapshot(self, record_id: str) -> BudgetSnapshot | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_snapshots(
        self,
        slo_name: str | None = None,
        status: BudgetStatus | None = None,
        limit: int = 50,
    ) -> list[BudgetSnapshot]:
        results = list(self._records)
        if slo_name is not None:
            results = [r for r in results if r.slo_name == slo_name]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results[-limit:]

    def create_forecast(
        self,
        slo_name: str,
        horizon: ForecastHorizon = ForecastHorizon.ONE_WEEK,
        projected_remaining_pct: float = 0.0,
        exhaustion_days: float = 0.0,
        confidence_pct: float = 0.0,
    ) -> BudgetForecast:
        forecast = BudgetForecast(
            slo_name=slo_name,
            horizon=horizon,
            projected_remaining_pct=projected_remaining_pct,
            exhaustion_days=exhaustion_days,
            confidence_pct=confidence_pct,
        )
        self._forecasts.append(forecast)
        if len(self._forecasts) > self._max_records:
            self._forecasts = self._forecasts[-self._max_records :]
        logger.info(
            "error_budget_forecast.forecast_created",
            slo_name=slo_name,
            horizon=horizon.value,
        )
        return forecast

    # -- domain operations -----------------------------------------------

    def analyze_budget_health(self, slo_name: str) -> dict[str, Any]:
        """Analyze budget health for a specific SLO."""
        records = [r for r in self._records if r.slo_name == slo_name]
        if not records:
            return {"slo_name": slo_name, "status": "no_data"}
        latest = records[-1]
        return {
            "slo_name": slo_name,
            "budget_remaining_pct": latest.budget_remaining_pct,
            "burn_rate": latest.burn_rate.value,
            "status": latest.status.value,
            "error_count": latest.error_count,
        }

    def identify_at_risk_budgets(self) -> list[dict[str, Any]]:
        """Find budgets at risk of exhaustion."""
        at_risk = {
            BudgetStatus.AT_RISK,
            BudgetStatus.EXHAUSTING,
            BudgetStatus.EXHAUSTED,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.status in at_risk:
                results.append(
                    {
                        "slo_name": r.slo_name,
                        "budget_remaining_pct": r.budget_remaining_pct,
                        "status": r.status.value,
                        "burn_rate": r.burn_rate.value,
                    }
                )
        results.sort(key=lambda x: x["budget_remaining_pct"])
        return results

    def rank_by_burn_rate(self) -> list[dict[str, Any]]:
        """Rank SLOs by burn rate severity."""
        rate_order = {
            BurnRate.CRITICAL: 5,
            BurnRate.FAST: 4,
            BurnRate.ELEVATED: 3,
            BurnRate.NORMAL: 2,
            BurnRate.SLOW: 1,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "slo_name": r.slo_name,
                    "burn_rate": r.burn_rate.value,
                    "rate_score": rate_order.get(r.burn_rate, 0),
                    "budget_remaining_pct": r.budget_remaining_pct,
                }
            )
        results.sort(key=lambda x: x["rate_score"], reverse=True)
        return results

    def project_exhaustion_timeline(self) -> list[dict[str, Any]]:
        """Project when budgets will exhaust."""
        results: list[dict[str, Any]] = []
        for f in self._forecasts:
            results.append(
                {
                    "slo_name": f.slo_name,
                    "horizon": f.horizon.value,
                    "projected_remaining_pct": f.projected_remaining_pct,
                    "exhaustion_days": f.exhaustion_days,
                    "confidence_pct": f.confidence_pct,
                }
            )
        results.sort(key=lambda x: x["exhaustion_days"])
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ErrorBudgetForecastReport:
        by_status: dict[str, int] = {}
        by_burn: dict[str, int] = {}
        for r in self._records:
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
            by_burn[r.burn_rate.value] = by_burn.get(r.burn_rate.value, 0) + 1
        avg_remaining = (
            round(
                sum(r.budget_remaining_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        at_risk = {
            BudgetStatus.AT_RISK,
            BudgetStatus.EXHAUSTING,
            BudgetStatus.EXHAUSTED,
        }
        at_risk_count = sum(1 for r in self._records if r.status in at_risk)
        recs: list[str] = []
        if at_risk_count > 0:
            recs.append(f"{at_risk_count} SLO(s) at risk of budget exhaustion")
        critical_burn = sum(1 for r in self._records if r.burn_rate == BurnRate.CRITICAL)
        if critical_burn > 0:
            recs.append(f"{critical_burn} SLO(s) with critical burn rate")
        if not recs:
            recs.append("Error budgets within healthy limits")
        return ErrorBudgetForecastReport(
            total_snapshots=len(self._records),
            total_forecasts=len(self._forecasts),
            avg_remaining_pct=avg_remaining,
            by_status=by_status,
            by_burn_rate=by_burn,
            at_risk_count=at_risk_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._forecasts.clear()
        logger.info("error_budget_forecast.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_snapshots": len(self._records),
            "total_forecasts": len(self._forecasts),
            "risk_threshold_pct": self._risk_threshold_pct,
            "status_distribution": status_dist,
            "unique_slos": len({r.slo_name for r in self._records}),
        }
