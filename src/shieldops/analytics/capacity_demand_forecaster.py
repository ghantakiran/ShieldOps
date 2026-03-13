"""Capacity Demand Forecaster
compute demand forecasts, detect capacity exhaustion risk,
rank resources by scaling urgency."""

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
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"
    SEASONAL = "seasonal"


class ResourceType(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"


class DemandTrend(StrEnum):
    GROWING = "growing"
    STABLE = "stable"
    DECLINING = "declining"
    VOLATILE = "volatile"


# --- Models ---


class CapacityDemandRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    forecast_horizon: ForecastHorizon = ForecastHorizon.SHORT_TERM
    resource_type: ResourceType = ResourceType.CPU
    demand_trend: DemandTrend = DemandTrend.STABLE
    current_usage: float = 0.0
    capacity_limit: float = 100.0
    forecast_value: float = 0.0
    region: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CapacityDemandAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    forecasted_demand: float = 0.0
    exhaustion_risk: bool = False
    utilization_pct: float = 0.0
    data_points: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CapacityDemandReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_utilization: float = 0.0
    by_horizon: dict[str, int] = Field(default_factory=dict)
    by_resource_type: dict[str, int] = Field(default_factory=dict)
    by_demand_trend: dict[str, int] = Field(default_factory=dict)
    at_risk_resources: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityDemandForecaster:
    """Compute demand forecasts, detect capacity exhaustion
    risk, rank resources by scaling urgency."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CapacityDemandRecord] = []
        self._analyses: dict[str, CapacityDemandAnalysis] = {}
        logger.info(
            "capacity_demand_forecaster.init",
            max_records=max_records,
        )

    def add_record(
        self,
        resource_id: str = "",
        forecast_horizon: ForecastHorizon = ForecastHorizon.SHORT_TERM,
        resource_type: ResourceType = ResourceType.CPU,
        demand_trend: DemandTrend = DemandTrend.STABLE,
        current_usage: float = 0.0,
        capacity_limit: float = 100.0,
        forecast_value: float = 0.0,
        region: str = "",
        description: str = "",
    ) -> CapacityDemandRecord:
        record = CapacityDemandRecord(
            resource_id=resource_id,
            forecast_horizon=forecast_horizon,
            resource_type=resource_type,
            demand_trend=demand_trend,
            current_usage=current_usage,
            capacity_limit=capacity_limit,
            forecast_value=forecast_value,
            region=region,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "capacity_demand_forecaster.record_added",
            record_id=record.id,
            resource_id=resource_id,
        )
        return record

    def process(self, key: str) -> CapacityDemandAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        points = sum(1 for r in self._records if r.resource_id == rec.resource_id)
        util = round(rec.current_usage / rec.capacity_limit * 100, 2) if rec.capacity_limit else 0.0
        exhaustion = rec.forecast_value >= rec.capacity_limit * 0.9
        analysis = CapacityDemandAnalysis(
            resource_id=rec.resource_id,
            forecasted_demand=round(rec.forecast_value, 2),
            exhaustion_risk=exhaustion,
            utilization_pct=util,
            data_points=points,
            description=f"Resource {rec.resource_id} usage {rec.current_usage}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CapacityDemandReport:
        by_h: dict[str, int] = {}
        by_rt: dict[str, int] = {}
        by_dt: dict[str, int] = {}
        utils: list[float] = []
        for r in self._records:
            k = r.forecast_horizon.value
            by_h[k] = by_h.get(k, 0) + 1
            k2 = r.resource_type.value
            by_rt[k2] = by_rt.get(k2, 0) + 1
            k3 = r.demand_trend.value
            by_dt[k3] = by_dt.get(k3, 0) + 1
            if r.capacity_limit:
                utils.append(r.current_usage / r.capacity_limit * 100)
        avg = round(sum(utils) / len(utils), 2) if utils else 0.0
        at_risk = list(
            {r.resource_id for r in self._records if r.forecast_value >= r.capacity_limit * 0.9}
        )[:10]
        recs: list[str] = []
        if at_risk:
            recs.append(f"{len(at_risk)} resources at capacity exhaustion risk")
        if not recs:
            recs.append("No capacity exhaustion risks detected")
        return CapacityDemandReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_utilization=avg,
            by_horizon=by_h,
            by_resource_type=by_rt,
            by_demand_trend=by_dt,
            at_risk_resources=at_risk,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        rt_dist: dict[str, int] = {}
        for r in self._records:
            k = r.resource_type.value
            rt_dist[k] = rt_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "resource_type_distribution": rt_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("capacity_demand_forecaster.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_demand_forecast(
        self,
    ) -> list[dict[str, Any]]:
        """Aggregate demand forecast per resource."""
        res_data: dict[str, list[float]] = {}
        res_types: dict[str, str] = {}
        for r in self._records:
            res_data.setdefault(r.resource_id, []).append(r.forecast_value)
            res_types[r.resource_id] = r.resource_type.value
        results: list[dict[str, Any]] = []
        for rid, forecasts in res_data.items():
            avg = round(sum(forecasts) / len(forecasts), 2)
            results.append(
                {
                    "resource_id": rid,
                    "resource_type": res_types[rid],
                    "avg_forecast": avg,
                    "data_points": len(forecasts),
                }
            )
        results.sort(key=lambda x: x["avg_forecast"], reverse=True)
        return results

    def detect_capacity_exhaustion_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Detect resources approaching capacity limits."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.forecast_value >= r.capacity_limit * 0.9 and r.resource_id not in seen:
                seen.add(r.resource_id)
                results.append(
                    {
                        "resource_id": r.resource_id,
                        "resource_type": r.resource_type.value,
                        "forecast_value": r.forecast_value,
                        "capacity_limit": r.capacity_limit,
                        "utilization_pct": round(r.forecast_value / r.capacity_limit * 100, 2)
                        if r.capacity_limit
                        else 0.0,
                    }
                )
        results.sort(key=lambda x: x["utilization_pct"], reverse=True)
        return results

    def rank_resources_by_scaling_urgency(
        self,
    ) -> list[dict[str, Any]]:
        """Rank all resources by scaling urgency."""
        res_data: dict[str, float] = {}
        res_types: dict[str, str] = {}
        res_limits: dict[str, float] = {}
        for r in self._records:
            if r.resource_id not in res_data or r.forecast_value > res_data[r.resource_id]:
                res_data[r.resource_id] = r.forecast_value
            res_types[r.resource_id] = r.resource_type.value
            res_limits[r.resource_id] = r.capacity_limit
        results: list[dict[str, Any]] = []
        for rid, fv in res_data.items():
            util = round(fv / res_limits[rid] * 100, 2) if res_limits[rid] else 0.0
            results.append(
                {
                    "resource_id": rid,
                    "resource_type": res_types[rid],
                    "utilization_pct": util,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["utilization_pct"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
