"""Telemetry Pipeline Orchestrator — orchestrate telemetry collection, processing, routing."""

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
    ROUTING = "routing"
    STORAGE = "storage"
    EXPORT = "export"


class PipelineHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class BackpressureLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# --- Models ---


class PipelineConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    stage: PipelineStage = PipelineStage.COLLECTION
    health: PipelineHealth = PipelineHealth.UNKNOWN
    throughput_eps: float = 0.0
    max_throughput_eps: float = 10000.0
    drop_rate_pct: float = 0.0
    enabled: bool = True
    created_at: float = Field(default_factory=time.time)


class BackpressureEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_name: str = ""
    level: BackpressureLevel = BackpressureLevel.NONE
    queue_depth: int = 0
    max_queue: int = 10000
    created_at: float = Field(default_factory=time.time)


class PipelineReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_pipelines: int = 0
    healthy_count: int = 0
    total_throughput_eps: float = 0.0
    avg_drop_rate: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    backpressure_events: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TelemetryPipelineOrchestrator:
    """Orchestrate telemetry collection, processing, and routing."""

    def __init__(self, max_pipelines: int = 5000) -> None:
        self._max_pipelines = max_pipelines
        self._pipelines: list[PipelineConfig] = []
        self._backpressure: list[BackpressureEvent] = []
        logger.info(
            "telemetry_pipeline_orchestrator.initialized",
            max_pipelines=max_pipelines,
        )

    def configure_pipeline(
        self,
        name: str,
        stage: PipelineStage = PipelineStage.COLLECTION,
        max_throughput_eps: float = 10000.0,
    ) -> PipelineConfig:
        """Configure a telemetry pipeline."""
        config = PipelineConfig(
            name=name,
            stage=stage,
            max_throughput_eps=max_throughput_eps,
            health=PipelineHealth.HEALTHY,
        )
        self._pipelines.append(config)
        if len(self._pipelines) > self._max_pipelines:
            self._pipelines = self._pipelines[-self._max_pipelines :]
        logger.info(
            "telemetry_pipeline_orchestrator.configured",
            name=name,
            stage=stage.value,
        )
        return config

    def validate_pipeline(self, name: str) -> dict[str, Any]:
        """Validate a pipeline configuration."""
        pipes = [p for p in self._pipelines if p.name == name]
        if not pipes:
            return {"name": name, "valid": False, "errors": ["pipeline not found"]}
        pipe = pipes[-1]
        errors: list[str] = []
        if pipe.max_throughput_eps <= 0:
            errors.append("max_throughput must be positive")
        if pipe.drop_rate_pct > 10:
            errors.append(f"drop rate {pipe.drop_rate_pct}% exceeds 10% threshold")
        return {
            "name": name,
            "valid": len(errors) == 0,
            "errors": errors,
            "stage": pipe.stage.value,
            "health": pipe.health.value,
        }

    def update_throughput(
        self,
        name: str,
        throughput_eps: float,
        drop_rate_pct: float = 0.0,
    ) -> dict[str, Any]:
        """Update pipeline throughput metrics."""
        pipes = [p for p in self._pipelines if p.name == name]
        if not pipes:
            return {"name": name, "status": "not_found"}
        pipe = pipes[-1]
        pipe.throughput_eps = throughput_eps
        pipe.drop_rate_pct = drop_rate_pct
        utilization = throughput_eps / pipe.max_throughput_eps if pipe.max_throughput_eps else 0
        if utilization > 0.9 or drop_rate_pct > 5:
            pipe.health = PipelineHealth.CRITICAL
        elif utilization > 0.7 or drop_rate_pct > 2:
            pipe.health = PipelineHealth.DEGRADED
        else:
            pipe.health = PipelineHealth.HEALTHY
        return {
            "name": name,
            "throughput_eps": throughput_eps,
            "utilization_pct": round(utilization * 100, 1),
            "health": pipe.health.value,
        }

    def optimize_throughput(self) -> list[dict[str, Any]]:
        """Suggest throughput optimizations."""
        suggestions: list[dict[str, Any]] = []
        for p in self._pipelines:
            if not p.enabled:
                continue
            util = p.throughput_eps / p.max_throughput_eps if p.max_throughput_eps else 0
            if util > 0.8:
                suggestions.append(
                    {
                        "pipeline": p.name,
                        "type": "scale_up",
                        "message": f"Utilization at {round(util * 100, 1)}% — scale up",
                        "current_throughput": p.throughput_eps,
                    }
                )
            elif util < 0.2 and p.throughput_eps > 0:
                suggestions.append(
                    {
                        "pipeline": p.name,
                        "type": "scale_down",
                        "message": f"Utilization at {round(util * 100, 1)}% — scale down",
                        "current_throughput": p.throughput_eps,
                    }
                )
        if not suggestions:
            suggestions.append(
                {
                    "pipeline": "all",
                    "type": "none",
                    "message": "All pipelines optimally utilized",
                }
            )
        return suggestions

    def monitor_backpressure(
        self,
        name: str,
        queue_depth: int,
        max_queue: int = 10000,
    ) -> BackpressureEvent:
        """Monitor backpressure for a pipeline."""
        ratio = queue_depth / max_queue if max_queue else 0
        if ratio > 0.9:
            level = BackpressureLevel.CRITICAL
        elif ratio > 0.7:
            level = BackpressureLevel.HIGH
        elif ratio > 0.4:
            level = BackpressureLevel.MEDIUM
        elif ratio > 0.1:
            level = BackpressureLevel.LOW
        else:
            level = BackpressureLevel.NONE
        event = BackpressureEvent(
            pipeline_name=name,
            level=level,
            queue_depth=queue_depth,
            max_queue=max_queue,
        )
        self._backpressure.append(event)
        if level in (BackpressureLevel.HIGH, BackpressureLevel.CRITICAL):
            logger.warning(
                "telemetry_pipeline_orchestrator.backpressure",
                pipeline=name,
                level=level.value,
                queue_depth=queue_depth,
            )
        return event

    def get_pipeline_health(self) -> dict[str, Any]:
        """Get overall pipeline health."""
        if not self._pipelines:
            return {"overall": "unknown", "pipelines": []}
        health_map: list[dict[str, Any]] = []
        for p in self._pipelines:
            health_map.append(
                {
                    "name": p.name,
                    "stage": p.stage.value,
                    "health": p.health.value,
                    "throughput_eps": p.throughput_eps,
                    "drop_rate_pct": p.drop_rate_pct,
                }
            )
        critical = sum(1 for p in self._pipelines if p.health == PipelineHealth.CRITICAL)
        degraded = sum(1 for p in self._pipelines if p.health == PipelineHealth.DEGRADED)
        if critical > 0:
            overall = "critical"
        elif degraded > 0:
            overall = "degraded"
        else:
            overall = "healthy"
        return {"overall": overall, "pipelines": health_map}

    def generate_report(self) -> PipelineReport:
        """Generate pipeline orchestration report."""
        by_stage: dict[str, int] = {}
        by_health: dict[str, int] = {}
        for p in self._pipelines:
            by_stage[p.stage.value] = by_stage.get(p.stage.value, 0) + 1
            by_health[p.health.value] = by_health.get(p.health.value, 0) + 1
        healthy = sum(1 for p in self._pipelines if p.health == PipelineHealth.HEALTHY)
        total_tp = sum(p.throughput_eps for p in self._pipelines)
        drops = [p.drop_rate_pct for p in self._pipelines]
        avg_drop = round(sum(drops) / len(drops), 2) if drops else 0.0
        recs: list[str] = []
        critical = sum(1 for p in self._pipelines if p.health == PipelineHealth.CRITICAL)
        if critical > 0:
            recs.append(f"{critical} pipeline(s) in critical state")
        bp_critical = sum(1 for b in self._backpressure if b.level == BackpressureLevel.CRITICAL)
        if bp_critical > 0:
            recs.append(f"{bp_critical} critical backpressure event(s)")
        if not recs:
            recs.append("All pipelines healthy")
        return PipelineReport(
            total_pipelines=len(self._pipelines),
            healthy_count=healthy,
            total_throughput_eps=round(total_tp, 2),
            avg_drop_rate=avg_drop,
            by_stage=by_stage,
            by_health=by_health,
            backpressure_events=len(self._backpressure),
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all pipelines and backpressure events."""
        self._pipelines.clear()
        self._backpressure.clear()
        logger.info("telemetry_pipeline_orchestrator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        """Return engine statistics."""
        return {
            "total_pipelines": len(self._pipelines),
            "total_backpressure_events": len(self._backpressure),
            "enabled_pipelines": sum(1 for p in self._pipelines if p.enabled),
        }
