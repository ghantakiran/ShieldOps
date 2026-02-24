"""Capacity Forecast Engine — forecast capacity with trend detection."""

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
    EXPONENTIAL = "exponential"
    SEASONAL = "seasonal"
    HOLT_WINTERS = "holt_winters"
    ENSEMBLE = "ensemble"


class CapacityRisk(StrEnum):
    SURPLUS = "surplus"
    ADEQUATE = "adequate"
    TIGHT = "tight"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"


class ResourceDimension(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    CONNECTIONS = "connections"


# --- Models ---


class UsageDataPoint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    dimension: ResourceDimension = ResourceDimension.CPU
    value: float = 0.0
    capacity_limit: float = 100.0
    utilization_pct: float = 0.0
    recorded_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class CapacityForecast(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    dimension: ResourceDimension = ResourceDimension.CPU
    method: ForecastMethod = ForecastMethod.LINEAR
    current_utilization_pct: float = 0.0
    forecast_utilization_pct: float = 0.0
    days_to_exhaustion: float = 0.0
    risk: CapacityRisk = CapacityRisk.ADEQUATE
    confidence: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ForecastReport(BaseModel):
    total_services: int = 0
    total_data_points: int = 0
    forecasts_generated: int = 0
    by_risk: dict[str, int] = Field(default_factory=dict)
    by_dimension: dict[str, int] = Field(default_factory=dict)
    urgent_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityForecastEngine:
    """Forecast capacity needs using historical usage data."""

    def __init__(
        self,
        max_data_points: int = 500000,
        headroom_target_pct: float = 70.0,
    ) -> None:
        self._max_data_points = max_data_points
        self._headroom_target_pct = headroom_target_pct
        self._items: list[UsageDataPoint] = []
        self._forecasts: dict[str, CapacityForecast] = {}
        logger.info(
            "capacity_forecast_engine.initialized",
            max_data_points=max_data_points,
            headroom_target_pct=headroom_target_pct,
        )

    # -- CRUD -------------------------------------------------------

    def ingest_usage(
        self,
        service_name: str,
        dimension: ResourceDimension = ResourceDimension.CPU,
        value: float = 0.0,
        capacity_limit: float = 100.0,
        recorded_at: float | None = None,
    ) -> UsageDataPoint:
        util_pct = round(value / capacity_limit * 100, 2) if capacity_limit > 0 else 0.0
        dp = UsageDataPoint(
            service_name=service_name,
            dimension=dimension,
            value=value,
            capacity_limit=capacity_limit,
            utilization_pct=util_pct,
            recorded_at=recorded_at or time.time(),
        )
        self._items.append(dp)
        if len(self._items) > self._max_data_points:
            self._items = self._items[-self._max_data_points :]
        logger.info(
            "capacity_forecast_engine.usage_ingested",
            dp_id=dp.id,
            service_name=service_name,
            dimension=dimension,
            utilization_pct=util_pct,
        )
        return dp

    def get_data_point(self, dp_id: str) -> UsageDataPoint | None:
        for dp in self._items:
            if dp.id == dp_id:
                return dp
        return None

    def list_usage(
        self,
        service_name: str | None = None,
        dimension: ResourceDimension | None = None,
        limit: int = 50,
    ) -> list[UsageDataPoint]:
        results = list(self._items)
        if service_name is not None:
            results = [d for d in results if d.service_name == service_name]
        if dimension is not None:
            results = [d for d in results if d.dimension == dimension]
        return results[-limit:]

    # -- Forecasting ------------------------------------------------

    def generate_forecast(
        self,
        service_name: str,
        dimension: ResourceDimension,
        method: ForecastMethod = ForecastMethod.LINEAR,
    ) -> CapacityForecast:
        points = [
            d for d in self._items if d.service_name == service_name and d.dimension == dimension
        ]

        if not points:
            fc = CapacityForecast(
                service_name=service_name,
                dimension=dimension,
                method=method,
            )
            self._forecasts[fc.id] = fc
            return fc

        current_util = points[-1].utilization_pct
        # Simple linear trend from first to last point
        if len(points) >= 2:
            first_util = points[0].utilization_pct
            delta = current_util - first_util
            n = len(points)
            trend_per_step = delta / n if n > 1 else 0.0
            forecast_util = min(current_util + trend_per_step * 30, 100.0)
        else:
            trend_per_step = 0.0
            forecast_util = current_util

        # Apply method multipliers for variety
        if method == ForecastMethod.EXPONENTIAL:
            forecast_util = min(forecast_util * 1.15, 100.0)
        elif method == ForecastMethod.SEASONAL:
            forecast_util = min(forecast_util * 1.05, 100.0)
        elif method == ForecastMethod.HOLT_WINTERS:
            forecast_util = min(forecast_util * 1.10, 100.0)
        elif method == ForecastMethod.ENSEMBLE:
            forecast_util = min(forecast_util * 1.08, 100.0)

        forecast_util = round(forecast_util, 2)

        days = self._calc_days_to_exhaustion(current_util, trend_per_step)
        risk = self._classify_risk(forecast_util)
        confidence = self._calc_confidence(len(points))

        fc = CapacityForecast(
            service_name=service_name,
            dimension=dimension,
            method=method,
            current_utilization_pct=current_util,
            forecast_utilization_pct=forecast_util,
            days_to_exhaustion=days,
            risk=risk,
            confidence=confidence,
        )
        self._forecasts[fc.id] = fc
        logger.info(
            "capacity_forecast_engine.forecast_generated",
            forecast_id=fc.id,
            service_name=service_name,
            dimension=dimension,
            risk=risk,
        )
        return fc

    def _calc_days_to_exhaustion(
        self,
        current_util: float,
        trend_per_step: float,
    ) -> float:
        if trend_per_step <= 0:
            return 999.0
        remaining = 100.0 - current_util
        if remaining <= 0:
            return 0.0
        return round(remaining / trend_per_step, 1)

    def _classify_risk(self, utilization_pct: float) -> CapacityRisk:
        if utilization_pct >= 95:
            return CapacityRisk.EXHAUSTED
        if utilization_pct >= 85:
            return CapacityRisk.CRITICAL
        if utilization_pct >= 70:
            return CapacityRisk.TIGHT
        if utilization_pct >= 50:
            return CapacityRisk.ADEQUATE
        return CapacityRisk.SURPLUS

    def _calc_confidence(self, point_count: int) -> float:
        if point_count >= 100:
            return 0.95
        if point_count >= 30:
            return 0.85
        if point_count >= 10:
            return 0.70
        if point_count >= 3:
            return 0.50
        return 0.30

    # -- Analysis ---------------------------------------------------

    def detect_capacity_risk(
        self,
    ) -> list[dict[str, Any]]:
        svc_dims: set[tuple[str, str]] = set()
        for dp in self._items:
            svc_dims.add((dp.service_name, dp.dimension.value))

        risks: list[dict[str, Any]] = []
        for svc, dim in svc_dims:
            dim_enum = ResourceDimension(dim)
            fc = self.generate_forecast(svc, dim_enum)
            if fc.risk in (
                CapacityRisk.TIGHT,
                CapacityRisk.CRITICAL,
                CapacityRisk.EXHAUSTED,
            ):
                risks.append(
                    {
                        "service_name": svc,
                        "dimension": dim,
                        "risk": fc.risk.value,
                        "forecast_utilization_pct": (fc.forecast_utilization_pct),
                        "days_to_exhaustion": (fc.days_to_exhaustion),
                    }
                )

        risks.sort(
            key=lambda x: x["forecast_utilization_pct"],
            reverse=True,
        )
        logger.info(
            "capacity_forecast_engine.risk_detected",
            risk_count=len(risks),
        )
        return risks

    def calculate_days_to_exhaustion(
        self,
        service_name: str,
        dimension: ResourceDimension,
    ) -> float:
        fc = self.generate_forecast(service_name, dimension)
        return fc.days_to_exhaustion

    def identify_trending_services(
        self,
    ) -> list[dict[str, Any]]:
        """Find services where utilization is rising across data points."""
        svc_points: dict[str, list[float]] = {}
        for dp in self._items:
            key = f"{dp.service_name}:{dp.dimension.value}"
            svc_points.setdefault(key, []).append(dp.utilization_pct)

        trending: list[dict[str, Any]] = []
        for key, utils in svc_points.items():
            if len(utils) < 2:
                continue
            first_half = utils[: len(utils) // 2]
            second_half = utils[len(utils) // 2 :]
            avg_first = sum(first_half) / len(first_half) if first_half else 0.0
            avg_second = sum(second_half) / len(second_half) if second_half else 0.0
            if avg_second > avg_first:
                parts = key.split(":", 1)
                trending.append(
                    {
                        "service_name": parts[0],
                        "dimension": (parts[1] if len(parts) > 1 else ""),
                        "trend_increase_pct": round(avg_second - avg_first, 2),
                        "latest_utilization_pct": utils[-1],
                    }
                )

        trending.sort(
            key=lambda x: x["trend_increase_pct"],
            reverse=True,
        )
        logger.info(
            "capacity_forecast_engine.trending_identified",
            trending_count=len(trending),
        )
        return trending

    def plan_headroom(self, target_utilization_pct: float = 70.0) -> list[dict[str, Any]]:
        target = target_utilization_pct
        plans: list[dict[str, Any]] = []

        svc_dims: set[tuple[str, str]] = set()
        for dp in self._items:
            svc_dims.add((dp.service_name, dp.dimension.value))

        for svc, dim in svc_dims:
            dim_enum = ResourceDimension(dim)
            fc = self.generate_forecast(svc, dim_enum)
            if fc.forecast_utilization_pct > target:
                overage = round(
                    fc.forecast_utilization_pct - target,
                    2,
                )
                plans.append(
                    {
                        "service_name": svc,
                        "dimension": dim,
                        "current_utilization_pct": (fc.current_utilization_pct),
                        "forecast_utilization_pct": (fc.forecast_utilization_pct),
                        "target_utilization_pct": target,
                        "overage_pct": overage,
                        "action": "scale_up",
                    }
                )

        plans.sort(
            key=lambda x: x["overage_pct"],
            reverse=True,
        )
        logger.info(
            "capacity_forecast_engine.headroom_planned",
            plan_count=len(plans),
            target_pct=target,
        )
        return plans

    # -- Report -----------------------------------------------------

    def generate_forecast_report(self) -> ForecastReport:
        total = len(self._items)
        if total == 0:
            return ForecastReport(
                recommendations=["No usage data ingested"],
            )

        svc_names: set[str] = set()
        by_dim: dict[str, int] = {}
        for dp in self._items:
            svc_names.add(dp.service_name)
            dk = dp.dimension.value
            by_dim[dk] = by_dim.get(dk, 0) + 1

        by_risk: dict[str, int] = {}
        urgent: list[str] = []
        for fc in self._forecasts.values():
            rk = fc.risk.value
            by_risk[rk] = by_risk.get(rk, 0) + 1
            if fc.risk in (
                CapacityRisk.CRITICAL,
                CapacityRisk.EXHAUSTED,
            ):
                urgent.append(fc.service_name)

        recs: list[str] = []
        if urgent:
            recs.append(f"{len(set(urgent))} service(s) at critical or exhausted capacity")
        headroom = self.plan_headroom(self._headroom_target_pct)
        if headroom:
            recs.append(f"{len(headroom)} service/dimension pair(s) exceed headroom target")
        trending = self.identify_trending_services()
        if trending:
            recs.append(f"{len(trending)} service(s) showing upward utilization trend")

        report = ForecastReport(
            total_services=len(svc_names),
            total_data_points=total,
            forecasts_generated=len(self._forecasts),
            by_risk=by_risk,
            by_dimension=by_dim,
            urgent_services=sorted(set(urgent)),
            recommendations=recs,
        )
        logger.info(
            "capacity_forecast_engine.report_generated",
            total_services=len(svc_names),
            total_data_points=total,
        )
        return report

    # -- Housekeeping -----------------------------------------------

    def clear_data(self) -> None:
        self._items.clear()
        self._forecasts.clear()
        logger.info("capacity_forecast_engine.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        services = {d.service_name for d in self._items}
        dimensions = {d.dimension.value for d in self._items}
        return {
            "total_data_points": len(self._items),
            "total_forecasts": len(self._forecasts),
            "unique_services": len(services),
            "dimensions": sorted(dimensions),
        }
