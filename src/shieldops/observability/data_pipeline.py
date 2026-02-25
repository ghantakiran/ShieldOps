"""Data Pipeline Reliability Monitor — track data pipeline health and freshness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PipelineType(StrEnum):
    BATCH = "batch"
    STREAMING = "streaming"
    MICRO_BATCH = "micro_batch"
    CDC = "cdc"
    ETL = "etl"


class PipelineHealth(StrEnum):
    HEALTHY = "healthy"
    DELAYED = "delayed"
    FAILING = "failing"
    STALE = "stale"
    UNKNOWN = "unknown"


class DataQualityIssue(StrEnum):
    SCHEMA_DRIFT = "schema_drift"
    MISSING_DATA = "missing_data"
    DUPLICATE_RECORDS = "duplicate_records"
    TYPE_MISMATCH = "type_mismatch"
    FRESHNESS_VIOLATION = "freshness_violation"


# --- Models ---


class PipelineRunRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_name: str = ""
    pipeline_type: PipelineType = PipelineType.BATCH
    health: PipelineHealth = PipelineHealth.HEALTHY
    records_processed: int = 0
    duration_seconds: float = 0.0
    freshness_seconds: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class DataQualityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_name: str = ""
    issue_type: DataQualityIssue = DataQualityIssue.SCHEMA_DRIFT
    affected_records: int = 0
    severity: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class DataPipelineReport(BaseModel):
    total_runs: int = 0
    total_quality_issues: int = 0
    avg_duration_seconds: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    stale_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataPipelineReliabilityMonitor:
    """Track data pipeline health, freshness, and quality issues."""

    def __init__(
        self,
        max_records: int = 200000,
        freshness_threshold_seconds: float = 3600.0,
    ) -> None:
        self._max_records = max_records
        self._freshness_threshold_seconds = freshness_threshold_seconds
        self._records: list[PipelineRunRecord] = []
        self._quality_issues: list[DataQualityRecord] = []
        logger.info(
            "data_pipeline.initialized",
            max_records=max_records,
            freshness_threshold_seconds=freshness_threshold_seconds,
        )

    # -- record / get / list ---------------------------------------------

    def record_run(
        self,
        pipeline_name: str,
        pipeline_type: PipelineType = PipelineType.BATCH,
        health: PipelineHealth = PipelineHealth.HEALTHY,
        records_processed: int = 0,
        duration_seconds: float = 0.0,
        freshness_seconds: float = 0.0,
        details: str = "",
    ) -> PipelineRunRecord:
        record = PipelineRunRecord(
            pipeline_name=pipeline_name,
            pipeline_type=pipeline_type,
            health=health,
            records_processed=records_processed,
            duration_seconds=duration_seconds,
            freshness_seconds=freshness_seconds,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "data_pipeline.run_recorded",
            record_id=record.id,
            pipeline_name=pipeline_name,
            health=health.value,
        )
        return record

    def get_run(self, record_id: str) -> PipelineRunRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_runs(
        self,
        pipeline_name: str | None = None,
        health: PipelineHealth | None = None,
        limit: int = 50,
    ) -> list[PipelineRunRecord]:
        results = list(self._records)
        if pipeline_name is not None:
            results = [r for r in results if r.pipeline_name == pipeline_name]
        if health is not None:
            results = [r for r in results if r.health == health]
        return results[-limit:]

    def record_quality_issue(
        self,
        pipeline_name: str,
        issue_type: DataQualityIssue = DataQualityIssue.SCHEMA_DRIFT,
        affected_records: int = 0,
        severity: float = 0.0,
        details: str = "",
    ) -> DataQualityRecord:
        issue = DataQualityRecord(
            pipeline_name=pipeline_name,
            issue_type=issue_type,
            affected_records=affected_records,
            severity=severity,
            details=details,
        )
        self._quality_issues.append(issue)
        if len(self._quality_issues) > self._max_records:
            self._quality_issues = self._quality_issues[-self._max_records :]
        logger.info(
            "data_pipeline.quality_issue_recorded",
            pipeline_name=pipeline_name,
            issue_type=issue_type.value,
            affected_records=affected_records,
        )
        return issue

    # -- domain operations -----------------------------------------------

    def analyze_pipeline_health(self, pipeline_name: str) -> dict[str, Any]:
        """Analyze health of a specific pipeline."""
        runs = [r for r in self._records if r.pipeline_name == pipeline_name]
        if not runs:
            return {"pipeline_name": pipeline_name, "status": "no_data"}
        health_breakdown: dict[str, int] = {}
        total_duration = 0.0
        for r in runs:
            key = r.health.value
            health_breakdown[key] = health_breakdown.get(key, 0) + 1
            total_duration += r.duration_seconds
        avg_duration = round(total_duration / len(runs), 2) if runs else 0.0
        quality = [q for q in self._quality_issues if q.pipeline_name == pipeline_name]
        return {
            "pipeline_name": pipeline_name,
            "total_runs": len(runs),
            "total_quality_issues": len(quality),
            "health_breakdown": health_breakdown,
            "avg_duration_seconds": avg_duration,
        }

    def identify_stale_pipelines(self) -> list[dict[str, Any]]:
        """Find pipelines with freshness exceeding threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.freshness_seconds > self._freshness_threshold_seconds:
                results.append(
                    {
                        "id": r.id,
                        "pipeline_name": r.pipeline_name,
                        "pipeline_type": r.pipeline_type.value,
                        "freshness_seconds": r.freshness_seconds,
                        "threshold": self._freshness_threshold_seconds,
                    }
                )
        results.sort(key=lambda x: x["freshness_seconds"], reverse=True)
        return results

    def rank_by_error_rate(self) -> list[dict[str, Any]]:
        """Rank pipelines by failure rate."""
        pipeline_total: dict[str, int] = {}
        pipeline_failing: dict[str, int] = {}
        for r in self._records:
            pipeline_total[r.pipeline_name] = pipeline_total.get(r.pipeline_name, 0) + 1
            if r.health in (PipelineHealth.FAILING, PipelineHealth.STALE):
                pipeline_failing[r.pipeline_name] = pipeline_failing.get(r.pipeline_name, 0) + 1
        results: list[dict[str, Any]] = []
        for name, total in pipeline_total.items():
            failing = pipeline_failing.get(name, 0)
            error_rate = round((failing / total) * 100, 2) if total > 0 else 0.0
            results.append(
                {
                    "pipeline_name": name,
                    "total_runs": total,
                    "failing_runs": failing,
                    "error_rate_pct": error_rate,
                }
            )
        results.sort(key=lambda x: x["error_rate_pct"], reverse=True)
        return results

    def detect_schema_drifts(self) -> list[dict[str, Any]]:
        """Find quality issues of type SCHEMA_DRIFT."""
        results: list[dict[str, Any]] = []
        for q in self._quality_issues:
            if q.issue_type == DataQualityIssue.SCHEMA_DRIFT:
                results.append(
                    {
                        "id": q.id,
                        "pipeline_name": q.pipeline_name,
                        "affected_records": q.affected_records,
                        "severity": q.severity,
                        "details": q.details,
                    }
                )
        results.sort(key=lambda x: x["severity"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> DataPipelineReport:
        by_type: dict[str, int] = {}
        by_health: dict[str, int] = {}
        total_duration = 0.0
        for r in self._records:
            by_type[r.pipeline_type.value] = by_type.get(r.pipeline_type.value, 0) + 1
            by_health[r.health.value] = by_health.get(r.health.value, 0) + 1
            total_duration += r.duration_seconds
        avg_duration = round(total_duration / len(self._records), 2) if self._records else 0.0
        stale = len(self.identify_stale_pipelines())
        recs: list[str] = []
        if stale > 0:
            recs.append(f"{stale} pipeline(s) are stale")
        drifts = len(self.detect_schema_drifts())
        if drifts > 0:
            recs.append(f"{drifts} schema drift(s) detected")
        if not recs:
            recs.append("Data pipeline health is good")
        return DataPipelineReport(
            total_runs=len(self._records),
            total_quality_issues=len(self._quality_issues),
            avg_duration_seconds=avg_duration,
            by_type=by_type,
            by_health=by_health,
            stale_count=stale,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._quality_issues.clear()
        logger.info("data_pipeline.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.pipeline_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_runs": len(self._records),
            "total_quality_issues": len(self._quality_issues),
            "freshness_threshold_seconds": self._freshness_threshold_seconds,
            "type_distribution": type_dist,
            "unique_pipelines": len({r.pipeline_name for r in self._records}),
        }
