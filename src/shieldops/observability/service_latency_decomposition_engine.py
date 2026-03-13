"""Service Latency Decomposition Engine —
decompose end-to-end latency by service,
identify latency hotspots, forecast latency trends."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LatencyComponent(StrEnum):
    PROCESSING = "processing"
    NETWORK = "network"
    QUEUE = "queue"
    SERIALIZATION = "serialization"


class DecompositionMethod(StrEnum):
    WATERFALL = "waterfall"
    CRITICAL_PATH = "critical_path"
    PERCENTILE = "percentile"
    HISTOGRAM = "histogram"


class LatencyTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"


# --- Models ---


class ServiceLatencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    operation_name: str = ""
    latency_component: LatencyComponent = LatencyComponent.PROCESSING
    decomposition_method: DecompositionMethod = DecompositionMethod.WATERFALL
    latency_trend: LatencyTrend = LatencyTrend.STABLE
    total_latency_ms: float = 0.0
    component_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    sample_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ServiceLatencyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    operation_name: str = ""
    dominant_component: LatencyComponent = LatencyComponent.PROCESSING
    contribution_pct: float = 0.0
    is_hotspot: bool = False
    trend: LatencyTrend = LatencyTrend.STABLE
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ServiceLatencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_total_latency_ms: float = 0.0
    by_latency_component: dict[str, int] = Field(default_factory=dict)
    by_decomposition_method: dict[str, int] = Field(default_factory=dict)
    by_latency_trend: dict[str, int] = Field(default_factory=dict)
    hotspot_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceLatencyDecompositionEngine:
    """Decompose end-to-end latency by service,
    identify latency hotspots, forecast latency trends."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ServiceLatencyRecord] = []
        self._analyses: dict[str, ServiceLatencyAnalysis] = {}
        logger.info("service_latency_decomposition_engine.init", max_records=max_records)

    def add_record(
        self,
        service_name: str = "",
        operation_name: str = "",
        latency_component: LatencyComponent = LatencyComponent.PROCESSING,
        decomposition_method: DecompositionMethod = DecompositionMethod.WATERFALL,
        latency_trend: LatencyTrend = LatencyTrend.STABLE,
        total_latency_ms: float = 0.0,
        component_latency_ms: float = 0.0,
        p99_latency_ms: float = 0.0,
        sample_count: int = 0,
        description: str = "",
    ) -> ServiceLatencyRecord:
        record = ServiceLatencyRecord(
            service_name=service_name,
            operation_name=operation_name,
            latency_component=latency_component,
            decomposition_method=decomposition_method,
            latency_trend=latency_trend,
            total_latency_ms=total_latency_ms,
            component_latency_ms=component_latency_ms,
            p99_latency_ms=p99_latency_ms,
            sample_count=sample_count,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "service_latency.record_added",
            record_id=record.id,
            service_name=service_name,
        )
        return record

    def process(self, key: str) -> ServiceLatencyAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        contrib = 0.0
        if rec.total_latency_ms > 0:
            contrib = round((rec.component_latency_ms / rec.total_latency_ms) * 100, 2)
        analysis = ServiceLatencyAnalysis(
            service_name=rec.service_name,
            operation_name=rec.operation_name,
            dominant_component=rec.latency_component,
            contribution_pct=contrib,
            is_hotspot=contrib > 50.0,
            trend=rec.latency_trend,
            description=(f"{rec.service_name} {rec.latency_component.value} {contrib}% of latency"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ServiceLatencyReport:
        by_comp: dict[str, int] = {}
        by_method: dict[str, int] = {}
        by_trend: dict[str, int] = {}
        latencies: list[float] = []
        for r in self._records:
            c = r.latency_component.value
            by_comp[c] = by_comp.get(c, 0) + 1
            m = r.decomposition_method.value
            by_method[m] = by_method.get(m, 0) + 1
            t = r.latency_trend.value
            by_trend[t] = by_trend.get(t, 0) + 1
            latencies.append(r.total_latency_ms)
        avg = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        hotspots = list(
            {r.service_name for r in self._records if r.latency_trend == LatencyTrend.DEGRADING}
        )[:10]
        recs: list[str] = []
        if hotspots:
            recs.append(f"{len(hotspots)} services with degrading latency")
        if not recs:
            recs.append("Latency within expected bounds")
        return ServiceLatencyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_total_latency_ms=avg,
            by_latency_component=by_comp,
            by_decomposition_method=by_method,
            by_latency_trend=by_trend,
            hotspot_services=hotspots,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        comp_dist: dict[str, int] = {}
        for r in self._records:
            k = r.latency_component.value
            comp_dist[k] = comp_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "component_distribution": comp_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("service_latency_decomposition_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def decompose_service_latency(self) -> list[dict[str, Any]]:
        """Decompose latency by service and component."""
        svc_comp: dict[str, dict[str, float]] = {}
        svc_total: dict[str, float] = {}
        for r in self._records:
            svc_comp.setdefault(r.service_name, {})
            comp = r.latency_component.value
            prev = svc_comp[r.service_name].get(comp, 0.0)
            svc_comp[r.service_name][comp] = prev + r.component_latency_ms
            svc_total[r.service_name] = svc_total.get(r.service_name, 0.0) + r.total_latency_ms
        results: list[dict[str, Any]] = []
        for svc, comp_map in svc_comp.items():
            total = svc_total.get(svc, 1.0)
            breakdown = {comp: round(ms / total * 100, 2) for comp, ms in comp_map.items()}
            results.append(
                {
                    "service_name": svc,
                    "total_latency_ms": round(total, 2),
                    "component_breakdown_pct": breakdown,
                }
            )
        results.sort(key=lambda x: x["total_latency_ms"], reverse=True)
        return results

    def identify_latency_hotspots(self) -> list[dict[str, Any]]:
        """Identify services contributing most to end-to-end latency."""
        svc_data: dict[str, list[float]] = {}
        for r in self._records:
            svc_data.setdefault(r.service_name, []).append(r.total_latency_ms)
        results: list[dict[str, Any]] = []
        for svc, lats in svc_data.items():
            avg_lat = sum(lats) / len(lats)
            max_lat = max(lats)
            results.append(
                {
                    "service_name": svc,
                    "avg_latency_ms": round(avg_lat, 2),
                    "max_latency_ms": round(max_lat, 2),
                    "sample_count": len(lats),
                    "is_hotspot": avg_lat > 500.0,
                }
            )
        results.sort(key=lambda x: x["avg_latency_ms"], reverse=True)
        return results

    def forecast_latency_trends(self) -> list[dict[str, Any]]:
        """Forecast latency trends per service based on recorded trends."""
        svc_trends: dict[str, list[str]] = {}
        svc_p99: dict[str, list[float]] = {}
        for r in self._records:
            svc_trends.setdefault(r.service_name, []).append(r.latency_trend.value)
            svc_p99.setdefault(r.service_name, []).append(r.p99_latency_ms)
        results: list[dict[str, Any]] = []
        for svc, trends in svc_trends.items():
            degrading_pct = round(trends.count("degrading") / len(trends) * 100, 2)
            p99_vals = svc_p99.get(svc, [0.0])
            avg_p99 = round(sum(p99_vals) / len(p99_vals), 2)
            results.append(
                {
                    "service_name": svc,
                    "degrading_pct": degrading_pct,
                    "avg_p99_latency_ms": avg_p99,
                    "dominant_trend": max(set(trends), key=trends.count),
                    "forecast_risk": "high" if degrading_pct > 50 else "low",
                }
            )
        results.sort(key=lambda x: x["degrading_pct"], reverse=True)
        return results
