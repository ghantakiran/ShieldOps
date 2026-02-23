"""Cost Forecast Engine — forecasts future cloud costs from historical trends."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ForecastMethod(StrEnum):
    LINEAR = "linear"
    MOVING_AVERAGE = "moving_average"
    EXPONENTIAL = "exponential"


class ForecastConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class CostDataPoint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    amount: float
    currency: str = "USD"
    period: str = ""
    recorded_at: float = Field(default_factory=time.time)


class CostForecast(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    method: ForecastMethod
    predicted_amount: float = 0.0
    confidence: ForecastConfidence = ForecastConfidence.MEDIUM
    period: str = ""
    lower_bound: float = 0.0
    upper_bound: float = 0.0
    data_points_used: int = 0
    generated_at: float = Field(default_factory=time.time)


class BudgetAlert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    budget_limit: float
    forecasted_amount: float
    overage_pct: float = 0.0
    message: str = ""
    triggered_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostForecastEngine:
    """Forecasts future cloud costs based on historical trends."""

    def __init__(
        self,
        max_datapoints: int = 500000,
        max_forecasts: int = 10000,
        budget_alert_threshold: float = 0.9,
    ) -> None:
        self._max_datapoints = max_datapoints
        self._max_forecasts = max_forecasts
        self._budget_alert_threshold = budget_alert_threshold
        self._datapoints: list[CostDataPoint] = []
        self._forecasts: dict[str, CostForecast] = {}
        self._budgets: dict[str, float] = {}
        self._alerts: list[BudgetAlert] = []
        logger.info(
            "cost_forecast_engine.initialized",
            max_datapoints=max_datapoints,
            max_forecasts=max_forecasts,
            budget_alert_threshold=budget_alert_threshold,
        )

    def record_cost(
        self,
        service: str,
        amount: float,
        period: str = "",
        currency: str = "USD",
    ) -> CostDataPoint:
        """Record a historical cost data point."""
        dp = CostDataPoint(
            service=service,
            amount=amount,
            period=period,
            currency=currency,
        )
        self._datapoints.append(dp)
        if len(self._datapoints) > self._max_datapoints:
            self._datapoints = self._datapoints[-self._max_datapoints :]
        logger.info(
            "cost_forecast_engine.cost_recorded",
            dp_id=dp.id,
            service=service,
            amount=amount,
        )
        return dp

    def _get_service_amounts(self, service: str) -> list[float]:
        """Return ordered amounts for a service."""
        return [dp.amount for dp in self._datapoints if dp.service == service]

    def _determine_confidence(self, count: int) -> ForecastConfidence:
        """Determine forecast confidence from data point count."""
        if count >= 10:
            return ForecastConfidence.HIGH
        if count >= 5:
            return ForecastConfidence.MEDIUM
        return ForecastConfidence.LOW

    def _forecast_linear(
        self,
        amounts: list[float],
        periods_ahead: int,
    ) -> float:
        """Simple linear extrapolation via slope of first/last."""
        if len(amounts) < 2:
            return amounts[-1] if amounts else 0.0
        n = len(amounts)
        # Least-effort linear: slope from endpoints
        slope = (amounts[-1] - amounts[0]) / (n - 1)
        return amounts[-1] + slope * periods_ahead

    def _forecast_moving_average(self, amounts: list[float]) -> float:
        """Average of last 5 data points."""
        window = amounts[-5:]
        return sum(window) / len(window) if window else 0.0

    def _forecast_exponential(self, amounts: list[float]) -> float:
        """Exponential moving average with alpha=0.3."""
        alpha = 0.3
        ema = amounts[0]
        for val in amounts[1:]:
            ema = alpha * val + (1 - alpha) * ema
        return ema

    def forecast(
        self,
        service: str,
        method: str = "linear",
        periods_ahead: int = 1,
    ) -> CostForecast:
        """Generate a cost forecast for a service."""
        amounts = self._get_service_amounts(service)
        fm = ForecastMethod(method)

        if not amounts:
            predicted = 0.0
        elif fm == ForecastMethod.LINEAR:
            predicted = self._forecast_linear(amounts, periods_ahead)
        elif fm == ForecastMethod.MOVING_AVERAGE:
            predicted = self._forecast_moving_average(amounts)
        else:
            predicted = self._forecast_exponential(amounts)

        predicted = max(predicted, 0.0)
        confidence = self._determine_confidence(len(amounts))
        lower_bound = round(predicted * 0.85, 2)
        upper_bound = round(predicted * 1.15, 2)

        fc = CostForecast(
            service=service,
            method=fm,
            predicted_amount=round(predicted, 2),
            confidence=confidence,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            data_points_used=len(amounts),
        )
        self._forecasts[fc.id] = fc
        if len(self._forecasts) > self._max_forecasts:
            oldest = next(iter(self._forecasts))
            del self._forecasts[oldest]
        logger.info(
            "cost_forecast_engine.forecast_generated",
            forecast_id=fc.id,
            service=service,
            method=method,
            predicted_amount=fc.predicted_amount,
        )
        return fc

    def set_budget(self, service: str, limit: float) -> None:
        """Set a budget limit for a service."""
        self._budgets[service] = limit
        logger.info(
            "cost_forecast_engine.budget_set",
            service=service,
            limit=limit,
        )

    def check_budgets(self) -> list[BudgetAlert]:
        """Check all budgeted services and create alerts if needed."""
        alerts: list[BudgetAlert] = []
        for service, limit in self._budgets.items():
            fc = self.forecast(service)
            if fc.predicted_amount <= 0.0:
                continue
            ratio = fc.predicted_amount / limit
            if ratio >= self._budget_alert_threshold:
                overage_pct = round((ratio - 1.0) * 100, 2)
                alert = BudgetAlert(
                    service=service,
                    budget_limit=limit,
                    forecasted_amount=fc.predicted_amount,
                    overage_pct=max(overage_pct, 0.0),
                    message=(
                        f"Service '{service}' forecasted at "
                        f"${fc.predicted_amount:.2f} vs budget "
                        f"${limit:.2f} ({ratio:.0%} of budget)"
                    ),
                )
                alerts.append(alert)
                self._alerts.append(alert)
                logger.warning(
                    "cost_forecast_engine.budget_alert",
                    service=service,
                    forecasted=fc.predicted_amount,
                    limit=limit,
                )
        return alerts

    def get_forecast(self, forecast_id: str) -> CostForecast | None:
        """Retrieve a forecast by ID."""
        return self._forecasts.get(forecast_id)

    def list_forecasts(
        self,
        service: str | None = None,
        limit: int = 50,
    ) -> list[CostForecast]:
        """List stored forecasts with optional service filter."""
        results = list(self._forecasts.values())
        if service is not None:
            results = [f for f in results if f.service == service]
        return results[-limit:]

    def get_cost_history(
        self,
        service: str,
        limit: int = 100,
    ) -> list[CostDataPoint]:
        """Return historical cost data points for a service."""
        points = [dp for dp in self._datapoints if dp.service == service]
        return points[-limit:]

    def get_alerts(
        self,
        service: str | None = None,
    ) -> list[BudgetAlert]:
        """Return budget alerts, optionally filtered by service."""
        results = list(self._alerts)
        if service is not None:
            results = [a for a in results if a.service == service]
        return results

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        services: set[str] = set()
        total_cost = 0.0
        for dp in self._datapoints:
            services.add(dp.service)
            total_cost += dp.amount
        return {
            "total_datapoints": len(self._datapoints),
            "total_forecasts": len(self._forecasts),
            "total_alerts": len(self._alerts),
            "total_budgets": len(self._budgets),
            "services_tracked": len(services),
            "total_recorded_cost": round(total_cost, 2),
        }
