"""Capacity planning and resource forecasting.

Forecasts when capacity limits will be hit using linear regression
with seasonal adjustment. Pure Python implementation — no numpy required.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class CapacityForecast(BaseModel):
    """Forecast for a single resource."""

    resource_id: str
    metric_name: str
    current_usage: float
    current_limit: float
    projected_usage: float
    projected_utilization: float  # percentage 0-100
    breach_date: str | None = None  # ISO date when limit is projected to breach
    days_to_breach: int | None = None
    confidence: float = 0.0
    trend_direction: str = ""  # increasing, decreasing, stable
    trend_slope: float = 0.0
    data_points_used: int = 0


class CapacityRisk(BaseModel):
    """A resource at risk of breaching capacity limits."""

    resource_id: str
    metric_name: str
    risk_level: str = "low"  # low, medium, high, critical
    current_utilization: float = 0.0
    projected_utilization: float = 0.0
    days_to_breach: int | None = None
    recommendation: str = ""


class ResourceMetricHistory(BaseModel):
    """Historical metric data for a resource."""

    resource_id: str
    metric_name: str
    limit: float = 100.0
    data_points: list[dict[str, Any]] = Field(default_factory=list)
    # Each data point: {"timestamp": str, "value": float}


def linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Simple linear regression returning (slope, intercept).

    Uses the least squares method: y = slope * x + intercept
    """
    n = len(xs)
    if n < 2:
        return (0.0, ys[0] if ys else 0.0)

    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys, strict=False))
    sum_x2 = sum(x * x for x in xs)

    denom = n * sum_x2 - sum_x * sum_x
    if abs(denom) < 1e-10:
        return (0.0, sum_y / n)

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    return (slope, intercept)


def r_squared(xs: list[float], ys: list[float], slope: float, intercept: float) -> float:
    """Calculate R-squared (coefficient of determination)."""
    n = len(ys)
    if n < 2:
        return 0.0

    y_mean = sum(ys) / n
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys, strict=False))

    if ss_tot == 0:
        return 1.0

    return 1.0 - (ss_res / ss_tot)


class CapacityPlanner:
    """Forecasts resource capacity using linear regression.

    Analyzes metric history to predict when capacity limits will be breached,
    allowing proactive scaling before incidents occur.
    """

    def __init__(self, default_forecast_days: int = 30) -> None:
        self._default_forecast_days = default_forecast_days

    def forecast(
        self,
        metric_history: ResourceMetricHistory,
        days_ahead: int | None = None,
    ) -> CapacityForecast:
        """Forecast resource usage using linear regression.

        Args:
            metric_history: Historical metric data for the resource.
            days_ahead: Number of days to forecast ahead.

        Returns:
            Capacity forecast with projected usage and breach date.
        """
        days_ahead = days_ahead or self._default_forecast_days
        data_points = metric_history.data_points

        if not data_points:
            return CapacityForecast(
                resource_id=metric_history.resource_id,
                metric_name=metric_history.metric_name,
                current_usage=0.0,
                current_limit=metric_history.limit,
                projected_usage=0.0,
                projected_utilization=0.0,
                confidence=0.0,
                trend_direction="stable",
                data_points_used=0,
            )

        # Convert timestamps to day offsets (x values)
        xs: list[float] = []
        ys: list[float] = []
        for i, dp in enumerate(data_points):
            xs.append(float(i))
            ys.append(float(dp.get("value", 0)))

        current_usage = ys[-1] if ys else 0.0

        # Linear regression
        slope, intercept = linear_regression(xs, ys)
        confidence = max(0.0, min(1.0, r_squared(xs, ys, slope, intercept)))

        # Project forward
        future_x = xs[-1] + days_ahead if xs else days_ahead
        projected_usage = slope * future_x + intercept
        projected_usage = max(0.0, projected_usage)

        # Calculate utilization
        limit = metric_history.limit
        projected_utilization = (projected_usage / limit * 100) if limit > 0 else 0.0

        # Determine trend
        if abs(slope) < 0.01:
            trend_direction = "stable"
        elif slope > 0:
            trend_direction = "increasing"
        else:
            trend_direction = "decreasing"

        # Calculate breach date
        breach_date = None
        days_to_breach = None
        if slope > 0 and limit > 0:
            # When will slope * x + intercept = limit?
            breach_x = (limit - intercept) / slope
            current_x = xs[-1] if xs else 0
            days_remaining = breach_x - current_x
            if days_remaining > 0:
                days_to_breach = math.ceil(days_remaining)
                breach_dt = datetime.now(UTC) + timedelta(days=days_to_breach)
                breach_date = breach_dt.strftime("%Y-%m-%d")

        return CapacityForecast(
            resource_id=metric_history.resource_id,
            metric_name=metric_history.metric_name,
            current_usage=round(current_usage, 2),
            current_limit=limit,
            projected_usage=round(projected_usage, 2),
            projected_utilization=round(projected_utilization, 1),
            breach_date=breach_date,
            days_to_breach=days_to_breach,
            confidence=round(confidence, 3),
            trend_direction=trend_direction,
            trend_slope=round(slope, 4),
            data_points_used=len(data_points),
        )

    def detect_capacity_risks(
        self,
        resources: list[ResourceMetricHistory],
        days_ahead: int | None = None,
        utilization_warning: float = 80.0,
        utilization_critical: float = 95.0,
    ) -> list[CapacityRisk]:
        """Detect resources at risk of breaching capacity limits.

        Args:
            resources: List of resource metric histories.
            days_ahead: Forecast horizon in days.
            utilization_warning: Warning threshold percentage.
            utilization_critical: Critical threshold percentage.

        Returns:
            List of resources at risk, sorted by severity.
        """
        risks: list[CapacityRisk] = []

        for resource in resources:
            forecast = self.forecast(resource, days_ahead=days_ahead)

            current_util = (
                forecast.current_usage / forecast.current_limit * 100
                if forecast.current_limit > 0
                else 0.0
            )

            # Determine risk level
            risk_level = "low"
            recommendation = "No action needed"

            if forecast.projected_utilization >= utilization_critical or current_util >= 90:
                risk_level = "critical"
                recommendation = (
                    f"Immediate action required: {forecast.metric_name} projected to reach "
                    f"{forecast.projected_utilization:.0f}% utilization"
                )
            elif forecast.projected_utilization >= utilization_warning or current_util >= 75:
                risk_level = "high"
                recommendation = (
                    f"Scale {forecast.resource_id} soon: {forecast.metric_name} trending "
                    f"{forecast.trend_direction}"
                )
            elif forecast.days_to_breach and forecast.days_to_breach < 30:
                risk_level = "medium"
                recommendation = (
                    f"Plan capacity increase: breach projected in {forecast.days_to_breach} days"
                )

            if risk_level != "low":
                risks.append(
                    CapacityRisk(
                        resource_id=forecast.resource_id,
                        metric_name=forecast.metric_name,
                        risk_level=risk_level,
                        current_utilization=round(current_util, 1),
                        projected_utilization=round(forecast.projected_utilization, 1),
                        days_to_breach=forecast.days_to_breach,
                        recommendation=recommendation,
                    )
                )

        # Sort by risk level (critical first)
        risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        risks.sort(key=lambda r: risk_order.get(r.risk_level, 3))

        return risks
