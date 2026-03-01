"""Cost Forecast Validator — validate forecasts, accuracy, and error tracking."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ForecastPeriod(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class ForecastAccuracy(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNRELIABLE = "unreliable"


class CostDomain(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    PLATFORM = "platform"


# --- Models ---


class ForecastRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    forecast_period: ForecastPeriod = ForecastPeriod.MONTHLY
    forecast_accuracy: ForecastAccuracy = ForecastAccuracy.FAIR
    cost_domain: CostDomain = CostDomain.COMPUTE
    forecasted_amount: float = 0.0
    actual_amount: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ForecastRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_pattern: str = ""
    forecast_period: ForecastPeriod = ForecastPeriod.MONTHLY
    cost_domain: CostDomain = CostDomain.COMPUTE
    max_deviation_pct: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ForecastValidationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    accurate_forecasts: int = 0
    avg_error_pct: float = 0.0
    by_period: dict[str, int] = Field(default_factory=dict)
    by_accuracy: dict[str, int] = Field(default_factory=dict)
    by_domain: dict[str, int] = Field(default_factory=dict)
    inaccurate_forecasts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostForecastValidator:
    """Validate cost forecasts, identify inaccuracies, track error trends."""

    def __init__(
        self,
        max_records: int = 200000,
        max_forecast_error_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_forecast_error_pct = max_forecast_error_pct
        self._records: list[ForecastRecord] = []
        self._rules: list[ForecastRule] = []
        logger.info(
            "forecast_validator.initialized",
            max_records=max_records,
            max_forecast_error_pct=max_forecast_error_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_forecast(
        self,
        service_name: str,
        forecast_period: ForecastPeriod = ForecastPeriod.MONTHLY,
        forecast_accuracy: ForecastAccuracy = ForecastAccuracy.FAIR,
        cost_domain: CostDomain = CostDomain.COMPUTE,
        forecasted_amount: float = 0.0,
        actual_amount: float = 0.0,
        team: str = "",
    ) -> ForecastRecord:
        record = ForecastRecord(
            service_name=service_name,
            forecast_period=forecast_period,
            forecast_accuracy=forecast_accuracy,
            cost_domain=cost_domain,
            forecasted_amount=forecasted_amount,
            actual_amount=actual_amount,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "forecast_validator.forecast_recorded",
            record_id=record.id,
            service_name=service_name,
            forecast_period=forecast_period.value,
            forecast_accuracy=forecast_accuracy.value,
        )
        return record

    def get_forecast(self, record_id: str) -> ForecastRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_forecasts(
        self,
        period: ForecastPeriod | None = None,
        accuracy: ForecastAccuracy | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ForecastRecord]:
        results = list(self._records)
        if period is not None:
            results = [r for r in results if r.forecast_period == period]
        if accuracy is not None:
            results = [r for r in results if r.forecast_accuracy == accuracy]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_rule(
        self,
        service_pattern: str,
        forecast_period: ForecastPeriod = ForecastPeriod.MONTHLY,
        cost_domain: CostDomain = CostDomain.COMPUTE,
        max_deviation_pct: float = 0.0,
        description: str = "",
    ) -> ForecastRule:
        rule = ForecastRule(
            service_pattern=service_pattern,
            forecast_period=forecast_period,
            cost_domain=cost_domain,
            max_deviation_pct=max_deviation_pct,
            description=description,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "forecast_validator.rule_added",
            service_pattern=service_pattern,
            forecast_period=forecast_period.value,
            max_deviation_pct=max_deviation_pct,
        )
        return rule

    # -- domain operations --------------------------------------------------

    def analyze_forecast_accuracy(self) -> dict[str, Any]:
        """Group by period; return count and avg error pct per period."""
        period_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.forecast_period.value
            if r.actual_amount > 0:
                error_pct = abs(r.forecasted_amount - r.actual_amount) / r.actual_amount * 100
            else:
                error_pct = 0.0
            period_data.setdefault(key, []).append(error_pct)
        result: dict[str, Any] = {}
        for period, errors in period_data.items():
            result[period] = {
                "count": len(errors),
                "avg_error_pct": round(sum(errors) / len(errors), 2),
            }
        return result

    def identify_inaccurate_forecasts(self) -> list[dict[str, Any]]:
        """Return records where accuracy is POOR or UNRELIABLE."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.forecast_accuracy in (ForecastAccuracy.POOR, ForecastAccuracy.UNRELIABLE):
                results.append(
                    {
                        "record_id": r.id,
                        "service_name": r.service_name,
                        "forecast_period": r.forecast_period.value,
                        "forecasted_amount": r.forecasted_amount,
                        "actual_amount": r.actual_amount,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_error(self) -> list[dict[str, Any]]:
        """Group by team, avg error pct, sort descending."""
        team_errors: dict[str, list[float]] = {}
        for r in self._records:
            if r.actual_amount > 0:
                error_pct = abs(r.forecasted_amount - r.actual_amount) / r.actual_amount * 100
            else:
                error_pct = 0.0
            team_errors.setdefault(r.team, []).append(error_pct)
        results: list[dict[str, Any]] = []
        for team, errors in team_errors.items():
            results.append(
                {
                    "team": team,
                    "avg_error_pct": round(sum(errors) / len(errors), 2),
                    "count": len(errors),
                }
            )
        results.sort(key=lambda x: x["avg_error_pct"], reverse=True)
        return results

    def detect_forecast_trends(self) -> dict[str, Any]:
        """Split-half on max_deviation_pct; delta threshold 5.0."""
        if len(self._rules) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        devs = [ru.max_deviation_pct for ru in self._rules]
        mid = len(devs) // 2
        first_half = devs[:mid]
        second_half = devs[mid:]
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

    def generate_report(self) -> ForecastValidationReport:
        by_period: dict[str, int] = {}
        by_accuracy: dict[str, int] = {}
        by_domain: dict[str, int] = {}
        for r in self._records:
            by_period[r.forecast_period.value] = by_period.get(r.forecast_period.value, 0) + 1
            by_accuracy[r.forecast_accuracy.value] = (
                by_accuracy.get(r.forecast_accuracy.value, 0) + 1
            )
            by_domain[r.cost_domain.value] = by_domain.get(r.cost_domain.value, 0) + 1
        accurate_count = sum(
            1
            for r in self._records
            if r.forecast_accuracy in (ForecastAccuracy.EXCELLENT, ForecastAccuracy.GOOD)
        )
        total_error = 0.0
        for r in self._records:
            if r.actual_amount > 0:
                total_error += abs(r.forecasted_amount - r.actual_amount) / r.actual_amount * 100
        avg_error = round(total_error / len(self._records), 2) if self._records else 0.0
        inaccurate_items = self.identify_inaccurate_forecasts()
        inaccurate_forecasts = [item["service_name"] for item in inaccurate_items[:5]]
        recs: list[str] = []
        if avg_error > self._max_forecast_error_pct:
            recs.append(
                f"Avg forecast error {avg_error}% exceeds "
                f"threshold ({self._max_forecast_error_pct}%)"
            )
        if len(inaccurate_items) > 0:
            recs.append(f"{len(inaccurate_items)} inaccurate forecast(s) detected — review models")
        if not recs:
            recs.append("Forecast accuracy is within acceptable limits")
        return ForecastValidationReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            accurate_forecasts=accurate_count,
            avg_error_pct=avg_error,
            by_period=by_period,
            by_accuracy=by_accuracy,
            by_domain=by_domain,
            inaccurate_forecasts=inaccurate_forecasts,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("forecast_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        period_dist: dict[str, int] = {}
        for r in self._records:
            key = r.forecast_period.value
            period_dist[key] = period_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "max_forecast_error_pct": self._max_forecast_error_pct,
            "period_distribution": period_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service_name for r in self._records}),
        }
