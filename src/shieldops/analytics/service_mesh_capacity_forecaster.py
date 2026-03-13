"""Service Mesh Capacity Forecaster.

Forecast proxy resource needs, model mesh scaling
scenarios, and detect capacity bottlenecks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResourceType(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    CONNECTIONS = "connections"
    BANDWIDTH = "bandwidth"


class ScalingTrigger(StrEnum):
    TRAFFIC_GROWTH = "traffic_growth"
    NEW_SERVICES = "new_services"
    MESH_EXPANSION = "mesh_expansion"
    PERFORMANCE = "performance"


class BottleneckSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class MeshCapacityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    proxy_name: str = ""
    resource_type: ResourceType = ResourceType.CPU
    scaling_trigger: ScalingTrigger = ScalingTrigger.TRAFFIC_GROWTH
    bottleneck_severity: BottleneckSeverity = BottleneckSeverity.LOW
    current_usage: float = 0.0
    capacity_limit: float = 100.0
    utilization_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class MeshCapacityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    proxy_name: str = ""
    is_bottleneck: bool = False
    headroom_pct: float = 0.0
    forecast_days: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MeshCapacityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_utilization: float = 0.0
    by_resource_type: dict[str, int] = Field(default_factory=dict)
    by_scaling_trigger: dict[str, int] = Field(default_factory=dict)
    by_bottleneck_severity: dict[str, int] = Field(default_factory=dict)
    bottleneck_proxies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceMeshCapacityForecaster:
    """Forecast proxy resource needs, model scaling
    scenarios, detect capacity bottlenecks."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[MeshCapacityRecord] = []
        self._analyses: dict[str, MeshCapacityAnalysis] = {}
        logger.info(
            "service_mesh_capacity_forecaster.init",
            max_records=max_records,
        )

    def add_record(
        self,
        service: str = "",
        proxy_name: str = "",
        resource_type: ResourceType = (ResourceType.CPU),
        scaling_trigger: ScalingTrigger = (ScalingTrigger.TRAFFIC_GROWTH),
        bottleneck_severity: BottleneckSeverity = (BottleneckSeverity.LOW),
        current_usage: float = 0.0,
        capacity_limit: float = 100.0,
        utilization_pct: float = 0.0,
    ) -> MeshCapacityRecord:
        record = MeshCapacityRecord(
            service=service,
            proxy_name=proxy_name,
            resource_type=resource_type,
            scaling_trigger=scaling_trigger,
            bottleneck_severity=bottleneck_severity,
            current_usage=current_usage,
            capacity_limit=capacity_limit,
            utilization_pct=utilization_pct,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "mesh_capacity.record_added",
            record_id=record.id,
            service=service,
        )
        return record

    def process(self, key: str) -> MeshCapacityAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_bn = rec.bottleneck_severity in (
            BottleneckSeverity.CRITICAL,
            BottleneckSeverity.HIGH,
        )
        headroom = round(100.0 - rec.utilization_pct, 2)
        forecast = int(headroom / max(5.0, 1.0)) if headroom > 0 else 0
        analysis = MeshCapacityAnalysis(
            service=rec.service,
            proxy_name=rec.proxy_name,
            is_bottleneck=is_bn,
            headroom_pct=headroom,
            forecast_days=forecast,
            description=(f"Proxy {rec.proxy_name} util {rec.utilization_pct}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> MeshCapacityReport:
        by_rt: dict[str, int] = {}
        by_st: dict[str, int] = {}
        by_bs: dict[str, int] = {}
        utils: list[float] = []
        for r in self._records:
            k = r.resource_type.value
            by_rt[k] = by_rt.get(k, 0) + 1
            k2 = r.scaling_trigger.value
            by_st[k2] = by_st.get(k2, 0) + 1
            k3 = r.bottleneck_severity.value
            by_bs[k3] = by_bs.get(k3, 0) + 1
            utils.append(r.utilization_pct)
        avg = round(sum(utils) / len(utils), 2) if utils else 0.0
        bottlenecks = list(
            {
                r.proxy_name
                for r in self._records
                if r.bottleneck_severity
                in (
                    BottleneckSeverity.CRITICAL,
                    BottleneckSeverity.HIGH,
                )
            }
        )[:10]
        recs: list[str] = []
        if bottlenecks:
            recs.append(f"{len(bottlenecks)} proxy bottlenecks")
        if not recs:
            recs.append("Capacity sufficient")
        return MeshCapacityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_utilization=avg,
            by_resource_type=by_rt,
            by_scaling_trigger=by_st,
            by_bottleneck_severity=by_bs,
            bottleneck_proxies=bottlenecks,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.resource_type.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "resource_type_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("service_mesh_capacity_forecaster.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def forecast_proxy_resource_needs(
        self,
    ) -> list[dict[str, Any]]:
        """Forecast resource needs per proxy."""
        proxy_usage: dict[str, list[float]] = {}
        proxy_svc: dict[str, str] = {}
        for r in self._records:
            proxy_usage.setdefault(r.proxy_name, []).append(r.utilization_pct)
            proxy_svc[r.proxy_name] = r.service
        results: list[dict[str, Any]] = []
        for proxy, utils in proxy_usage.items():
            avg = round(sum(utils) / len(utils), 2)
            headroom = round(100.0 - avg, 2)
            results.append(
                {
                    "proxy_name": proxy,
                    "service": proxy_svc[proxy],
                    "avg_utilization": avg,
                    "headroom_pct": headroom,
                    "sample_count": len(utils),
                }
            )
        results.sort(
            key=lambda x: x["avg_utilization"],
            reverse=True,
        )
        return results

    def model_mesh_scaling_scenarios(
        self,
    ) -> list[dict[str, Any]]:
        """Model scaling scenarios by trigger."""
        trigger_data: dict[str, list[float]] = {}
        for r in self._records:
            trigger_data.setdefault(r.scaling_trigger.value, []).append(r.utilization_pct)
        results: list[dict[str, Any]] = []
        for trigger, utils in trigger_data.items():
            avg = round(sum(utils) / len(utils), 2)
            results.append(
                {
                    "trigger": trigger,
                    "avg_utilization": avg,
                    "record_count": len(utils),
                    "scale_factor": round(avg / 50.0, 2),
                }
            )
        results.sort(
            key=lambda x: x["avg_utilization"],
            reverse=True,
        )
        return results

    def detect_capacity_bottlenecks(
        self,
    ) -> list[dict[str, Any]]:
        """Detect capacity bottlenecks."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.bottleneck_severity
                in (
                    BottleneckSeverity.CRITICAL,
                    BottleneckSeverity.HIGH,
                )
                and r.proxy_name not in seen
            ):
                seen.add(r.proxy_name)
                results.append(
                    {
                        "proxy_name": r.proxy_name,
                        "service": r.service,
                        "severity": (r.bottleneck_severity.value),
                        "resource": (r.resource_type.value),
                        "utilization_pct": (r.utilization_pct),
                    }
                )
        results.sort(
            key=lambda x: x["utilization_pct"],
            reverse=True,
        )
        return results
