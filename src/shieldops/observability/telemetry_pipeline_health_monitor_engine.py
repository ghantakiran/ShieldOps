"""Telemetry Pipeline Health Monitor Engine —
monitor telemetry pipeline health,
detect pipeline bottlenecks, forecast pipeline capacity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PipelineStage(StrEnum):
    COLLECTION = "collection"
    PROCESSING = "processing"
    EXPORT = "export"
    STORAGE = "storage"


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class IssueType(StrEnum):
    DATA_LOSS = "data_loss"
    LATENCY = "latency"
    BACKPRESSURE = "backpressure"
    CONFIGURATION = "configuration"


# --- Models ---


class TelemetryPipelineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str = ""
    stage_name: str = ""
    pipeline_stage: PipelineStage = PipelineStage.COLLECTION
    health_status: HealthStatus = HealthStatus.HEALTHY
    issue_type: IssueType = IssueType.LATENCY
    throughput_eps: float = 0.0
    drop_rate: float = 0.0
    latency_ms: float = 0.0
    queue_depth: int = 0
    capacity_pct: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TelemetryPipelineAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str = ""
    stage_name: str = ""
    pipeline_stage: PipelineStage = PipelineStage.COLLECTION
    health_score: float = 0.0
    is_bottleneck: bool = False
    health_status: HealthStatus = HealthStatus.HEALTHY
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TelemetryPipelineReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_throughput_eps: float = 0.0
    by_pipeline_stage: dict[str, int] = Field(default_factory=dict)
    by_health_status: dict[str, int] = Field(default_factory=dict)
    by_issue_type: dict[str, int] = Field(default_factory=dict)
    bottleneck_stages: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TelemetryPipelineHealthMonitorEngine:
    """Monitor telemetry pipeline health,
    detect pipeline bottlenecks, forecast pipeline capacity."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TelemetryPipelineRecord] = []
        self._analyses: dict[str, TelemetryPipelineAnalysis] = {}
        logger.info("telemetry_pipeline_health_monitor_engine.init", max_records=max_records)

    def add_record(
        self,
        pipeline_id: str = "",
        stage_name: str = "",
        pipeline_stage: PipelineStage = PipelineStage.COLLECTION,
        health_status: HealthStatus = HealthStatus.HEALTHY,
        issue_type: IssueType = IssueType.LATENCY,
        throughput_eps: float = 0.0,
        drop_rate: float = 0.0,
        latency_ms: float = 0.0,
        queue_depth: int = 0,
        capacity_pct: float = 0.0,
        description: str = "",
    ) -> TelemetryPipelineRecord:
        record = TelemetryPipelineRecord(
            pipeline_id=pipeline_id,
            stage_name=stage_name,
            pipeline_stage=pipeline_stage,
            health_status=health_status,
            issue_type=issue_type,
            throughput_eps=throughput_eps,
            drop_rate=drop_rate,
            latency_ms=latency_ms,
            queue_depth=queue_depth,
            capacity_pct=capacity_pct,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "telemetry_pipeline.record_added",
            record_id=record.id,
            pipeline_id=pipeline_id,
        )
        return record

    def process(self, key: str) -> TelemetryPipelineAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        health_weights = {"healthy": 100, "degraded": 60, "unhealthy": 20, "unknown": 50}
        base = health_weights.get(rec.health_status.value, 50)
        health_score = max(0.0, round(base - rec.drop_rate * 100 - rec.capacity_pct * 0.2, 2))
        is_bottleneck = rec.capacity_pct > 85.0 or rec.drop_rate > 0.05
        analysis = TelemetryPipelineAnalysis(
            pipeline_id=rec.pipeline_id,
            stage_name=rec.stage_name,
            pipeline_stage=rec.pipeline_stage,
            health_score=health_score,
            is_bottleneck=is_bottleneck,
            health_status=rec.health_status,
            description=(
                f"Pipeline {rec.pipeline_id} stage {rec.pipeline_stage.value} health={health_score}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TelemetryPipelineReport:
        by_stage: dict[str, int] = {}
        by_health: dict[str, int] = {}
        by_issue: dict[str, int] = {}
        throughputs: list[float] = []
        for r in self._records:
            s = r.pipeline_stage.value
            by_stage[s] = by_stage.get(s, 0) + 1
            h = r.health_status.value
            by_health[h] = by_health.get(h, 0) + 1
            i = r.issue_type.value
            by_issue[i] = by_issue.get(i, 0) + 1
            throughputs.append(r.throughput_eps)
        avg = round(sum(throughputs) / len(throughputs), 2) if throughputs else 0.0
        bottlenecks = list(
            {
                r.stage_name
                for r in self._records
                if r.health_status in (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED)
                or r.capacity_pct > 85.0
            }
        )[:10]
        recs: list[str] = []
        if bottlenecks:
            recs.append(f"{len(bottlenecks)} pipeline stages with health issues")
        if not recs:
            recs.append("All telemetry pipeline stages healthy")
        return TelemetryPipelineReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_throughput_eps=avg,
            by_pipeline_stage=by_stage,
            by_health_status=by_health,
            by_issue_type=by_issue,
            bottleneck_stages=bottlenecks,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            k = r.pipeline_stage.value
            stage_dist[k] = stage_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "stage_distribution": stage_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("telemetry_pipeline_health_monitor_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def evaluate_pipeline_health(self) -> list[dict[str, Any]]:
        """Evaluate pipeline health per stage."""
        stage_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            sv = r.pipeline_stage.value
            if sv not in stage_data:
                stage_data[sv] = {
                    "count": 0,
                    "total_throughput": 0.0,
                    "total_drop": 0.0,
                    "total_cap": 0.0,
                    "unhealthy": 0,
                }
            stage_data[sv]["count"] += 1
            stage_data[sv]["total_throughput"] += r.throughput_eps
            stage_data[sv]["total_drop"] += r.drop_rate
            stage_data[sv]["total_cap"] += r.capacity_pct
            if r.health_status in (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED):
                stage_data[sv]["unhealthy"] += 1
        results: list[dict[str, Any]] = []
        for sv, data in stage_data.items():
            cnt = data["count"]
            results.append(
                {
                    "pipeline_stage": sv,
                    "record_count": cnt,
                    "avg_throughput_eps": round(data["total_throughput"] / cnt, 2),
                    "avg_drop_rate": round(data["total_drop"] / cnt, 4),
                    "avg_capacity_pct": round(data["total_cap"] / cnt, 2),
                    "unhealthy_pct": round(data["unhealthy"] / cnt * 100, 2),
                }
            )
        results.sort(key=lambda x: x["unhealthy_pct"], reverse=True)
        return results

    def detect_pipeline_bottlenecks(self) -> list[dict[str, Any]]:
        """Detect pipeline stages acting as throughput bottlenecks."""
        stage_cap: dict[str, list[float]] = {}
        stage_drop: dict[str, list[float]] = {}
        for r in self._records:
            sv = r.stage_name
            stage_cap.setdefault(sv, []).append(r.capacity_pct)
            stage_drop.setdefault(sv, []).append(r.drop_rate)
        results: list[dict[str, Any]] = []
        for sv, caps in stage_cap.items():
            drops = stage_drop.get(sv, [0.0])
            avg_cap = sum(caps) / len(caps)
            avg_drop = sum(drops) / len(drops)
            results.append(
                {
                    "stage_name": sv,
                    "avg_capacity_pct": round(avg_cap, 2),
                    "avg_drop_rate": round(avg_drop, 4),
                    "sample_count": len(caps),
                    "is_bottleneck": avg_cap > 85.0 or avg_drop > 0.05,
                }
            )
        results.sort(key=lambda x: x["avg_capacity_pct"], reverse=True)
        return results

    def forecast_pipeline_capacity(self) -> list[dict[str, Any]]:
        """Forecast capacity usage trends per pipeline stage."""
        stage_series: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            stage_series.setdefault(r.pipeline_stage.value, []).append(
                {
                    "capacity_pct": r.capacity_pct,
                    "throughput_eps": r.throughput_eps,
                    "created_at": r.created_at,
                }
            )
        results: list[dict[str, Any]] = []
        for sv, items in stage_series.items():
            sorted_items = sorted(items, key=lambda x: x["created_at"])
            avg_cap = sum(i["capacity_pct"] for i in sorted_items) / len(sorted_items)
            if len(sorted_items) >= 2:
                first_cap = sorted_items[0]["capacity_pct"]
                last_cap = sorted_items[-1]["capacity_pct"]
                trend = "increasing" if last_cap > first_cap else "decreasing"
                growth_rate = round((last_cap - first_cap) / len(sorted_items), 2)
            else:
                trend = "stable"
                growth_rate = 0.0
            forecast_cap = min(100.0, round(avg_cap + growth_rate * 10, 2))
            results.append(
                {
                    "pipeline_stage": sv,
                    "avg_capacity_pct": round(avg_cap, 2),
                    "capacity_trend": trend,
                    "growth_rate_per_sample": growth_rate,
                    "forecast_10_samples": forecast_cap,
                    "capacity_risk": "high" if forecast_cap > 90.0 else "low",
                }
            )
        results.sort(key=lambda x: x["forecast_10_samples"], reverse=True)
        return results
