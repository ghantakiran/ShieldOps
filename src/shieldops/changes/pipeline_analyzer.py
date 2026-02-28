"""Deployment Pipeline Analyzer — track and analyze CI/CD pipeline performance."""

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
    BUILD = "build"
    TEST = "test"
    SECURITY_SCAN = "security_scan"
    STAGING = "staging"
    PRODUCTION = "production"


class BottleneckType(StrEnum):
    QUEUE_WAIT = "queue_wait"
    SLOW_STEP = "slow_step"
    FLAKY_TEST = "flaky_test"
    RESOURCE_CONTENTION = "resource_contention"
    APPROVAL_DELAY = "approval_delay"


class PipelineHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    SLOW = "slow"
    BROKEN = "broken"
    UNKNOWN = "unknown"


# --- Models ---


class PipelineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_name: str = ""
    stage: PipelineStage = PipelineStage.BUILD
    bottleneck: BottleneckType = BottleneckType.QUEUE_WAIT
    health: PipelineHealth = PipelineHealth.HEALTHY
    duration_minutes: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class StageMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    stage: PipelineStage = PipelineStage.BUILD
    bottleneck: BottleneckType = BottleneckType.QUEUE_WAIT
    avg_duration_minutes: float = 0.0
    failure_rate_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class PipelineAnalyzerReport(BaseModel):
    total_pipelines: int = 0
    total_metrics: int = 0
    healthy_rate_pct: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    bottleneck_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentPipelineAnalyzer:
    """Track and analyze CI/CD pipeline performance."""

    def __init__(
        self,
        max_records: int = 200000,
        max_duration_minutes: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._max_duration_minutes = max_duration_minutes
        self._records: list[PipelineRecord] = []
        self._metrics: list[StageMetric] = []
        logger.info(
            "pipeline_analyzer.initialized",
            max_records=max_records,
            max_duration_minutes=max_duration_minutes,
        )

    # -- record / get / list ---------------------------------------------

    def record_pipeline(
        self,
        pipeline_name: str,
        stage: PipelineStage = PipelineStage.BUILD,
        bottleneck: BottleneckType = BottleneckType.QUEUE_WAIT,
        health: PipelineHealth = PipelineHealth.HEALTHY,
        duration_minutes: float = 0.0,
        details: str = "",
    ) -> PipelineRecord:
        record = PipelineRecord(
            pipeline_name=pipeline_name,
            stage=stage,
            bottleneck=bottleneck,
            health=health,
            duration_minutes=duration_minutes,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "pipeline_analyzer.pipeline_recorded",
            record_id=record.id,
            pipeline_name=pipeline_name,
            stage=stage.value,
            health=health.value,
        )
        return record

    def get_pipeline(self, record_id: str) -> PipelineRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_pipelines(
        self,
        pipeline_name: str | None = None,
        stage: PipelineStage | None = None,
        limit: int = 50,
    ) -> list[PipelineRecord]:
        results = list(self._records)
        if pipeline_name is not None:
            results = [r for r in results if r.pipeline_name == pipeline_name]
        if stage is not None:
            results = [r for r in results if r.stage == stage]
        return results[-limit:]

    def add_stage_metric(
        self,
        metric_name: str,
        stage: PipelineStage = PipelineStage.BUILD,
        bottleneck: BottleneckType = BottleneckType.QUEUE_WAIT,
        avg_duration_minutes: float = 0.0,
        failure_rate_pct: float = 0.0,
    ) -> StageMetric:
        metric = StageMetric(
            metric_name=metric_name,
            stage=stage,
            bottleneck=bottleneck,
            avg_duration_minutes=avg_duration_minutes,
            failure_rate_pct=failure_rate_pct,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "pipeline_analyzer.metric_added",
            metric_name=metric_name,
            stage=stage.value,
            bottleneck=bottleneck.value,
        )
        return metric

    # -- domain operations -----------------------------------------------

    def analyze_pipeline_health(self, pipeline_name: str) -> dict[str, Any]:
        """Analyze health for a specific pipeline."""
        records = [r for r in self._records if r.pipeline_name == pipeline_name]
        if not records:
            return {"pipeline_name": pipeline_name, "status": "no_data"}
        avg_duration = round(sum(r.duration_minutes for r in records) / len(records), 2)
        return {
            "pipeline_name": pipeline_name,
            "avg_duration": avg_duration,
            "record_count": len(records),
            "meets_threshold": avg_duration <= self._max_duration_minutes,
        }

    def identify_bottlenecks(self) -> list[dict[str, Any]]:
        """Find pipelines with >1 SLOW_STEP or FLAKY_TEST bottleneck."""
        bottleneck_counts: dict[str, int] = {}
        for r in self._records:
            if r.bottleneck in (BottleneckType.SLOW_STEP, BottleneckType.FLAKY_TEST):
                bottleneck_counts[r.pipeline_name] = bottleneck_counts.get(r.pipeline_name, 0) + 1
        results: list[dict[str, Any]] = []
        for pipe, count in bottleneck_counts.items():
            if count > 1:
                results.append(
                    {
                        "pipeline_name": pipe,
                        "bottleneck_count": count,
                    }
                )
        results.sort(key=lambda x: x["bottleneck_count"], reverse=True)
        return results

    def rank_by_throughput(self) -> list[dict[str, Any]]:
        """Rank pipelines by avg duration_minutes ascending."""
        durations: dict[str, list[float]] = {}
        for r in self._records:
            durations.setdefault(r.pipeline_name, []).append(r.duration_minutes)
        results: list[dict[str, Any]] = []
        for pipe, durs in durations.items():
            avg = round(sum(durs) / len(durs), 2)
            results.append(
                {
                    "pipeline_name": pipe,
                    "avg_duration_minutes": avg,
                }
            )
        results.sort(key=lambda x: x["avg_duration_minutes"])
        return results

    def detect_pipeline_trends(self) -> list[dict[str, Any]]:
        """Detect pipelines with >3 records."""
        counts: dict[str, int] = {}
        for r in self._records:
            counts[r.pipeline_name] = counts.get(r.pipeline_name, 0) + 1
        results: list[dict[str, Any]] = []
        for pipe, count in counts.items():
            if count > 3:
                results.append(
                    {
                        "pipeline_name": pipe,
                        "record_count": count,
                        "trend_detected": True,
                    }
                )
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> PipelineAnalyzerReport:
        by_stage: dict[str, int] = {}
        by_health: dict[str, int] = {}
        for r in self._records:
            by_stage[r.stage.value] = by_stage.get(r.stage.value, 0) + 1
            by_health[r.health.value] = by_health.get(r.health.value, 0) + 1
        healthy_count = sum(1 for r in self._records if r.health == PipelineHealth.HEALTHY)
        healthy_rate = round(healthy_count / len(self._records) * 100, 2) if self._records else 0.0
        bottleneck_count = len(self.identify_bottlenecks())
        recs: list[str] = []
        if self._records and healthy_rate < 80.0:
            recs.append(f"Healthy rate {healthy_rate}% is below 80% threshold")
        if bottleneck_count > 0:
            recs.append(f"{bottleneck_count} pipeline(s) with bottlenecks")
        trends = len(self.detect_pipeline_trends())
        if trends > 0:
            recs.append(f"{trends} pipeline(s) with detected trends")
        if not recs:
            recs.append("Pipeline performance meets targets")
        return PipelineAnalyzerReport(
            total_pipelines=len(self._records),
            total_metrics=len(self._metrics),
            healthy_rate_pct=healthy_rate,
            by_stage=by_stage,
            by_health=by_health,
            bottleneck_count=bottleneck_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("pipeline_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            key = r.stage.value
            stage_dist[key] = stage_dist.get(key, 0) + 1
        return {
            "total_pipelines": len(self._records),
            "total_metrics": len(self._metrics),
            "max_duration_minutes": self._max_duration_minutes,
            "stage_distribution": stage_dist,
            "unique_pipelines": len({r.pipeline_name for r in self._records}),
        }
