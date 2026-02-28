"""Remediation Pipeline Orchestrator — chain remediations into dependency-aware pipelines."""

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
    VALIDATION = "validation"
    PREPARATION = "preparation"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    ROLLBACK = "rollback"


class PipelineStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class StepDependency(StrEnum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    ON_FAILURE = "on_failure"
    OPTIONAL = "optional"


# --- Models ---


class PipelineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_name: str = ""
    pipeline_stage: PipelineStage = PipelineStage.VALIDATION
    pipeline_status: PipelineStatus = PipelineStatus.QUEUED
    step_dependency: StepDependency = StepDependency.SEQUENTIAL
    step_count: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class PipelineStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_name: str = ""
    pipeline_stage: PipelineStage = PipelineStage.EXECUTION
    pipeline_status: PipelineStatus = PipelineStatus.RUNNING
    duration_seconds: float = 0.0
    created_at: float = Field(default_factory=time.time)


class PipelineOrchestratorReport(BaseModel):
    total_pipelines: int = 0
    total_steps: int = 0
    success_rate_pct: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    rollback_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RemediationPipelineOrchestrator:
    """Chain multiple remediations into dependency-aware pipelines."""

    def __init__(
        self,
        max_records: int = 200000,
        max_step_count: int = 50,
    ) -> None:
        self._max_records = max_records
        self._max_step_count = max_step_count
        self._records: list[PipelineRecord] = []
        self._steps: list[PipelineStep] = []
        logger.info(
            "remediation_pipeline.initialized",
            max_records=max_records,
            max_step_count=max_step_count,
        )

    # -- record / get / list ---------------------------------------------

    def record_pipeline(
        self,
        pipeline_name: str,
        pipeline_stage: PipelineStage = PipelineStage.VALIDATION,
        pipeline_status: PipelineStatus = PipelineStatus.QUEUED,
        step_dependency: StepDependency = StepDependency.SEQUENTIAL,
        step_count: int = 0,
        details: str = "",
    ) -> PipelineRecord:
        record = PipelineRecord(
            pipeline_name=pipeline_name,
            pipeline_stage=pipeline_stage,
            pipeline_status=pipeline_status,
            step_dependency=step_dependency,
            step_count=step_count,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "remediation_pipeline.pipeline_recorded",
            record_id=record.id,
            pipeline_name=pipeline_name,
            pipeline_stage=pipeline_stage.value,
            pipeline_status=pipeline_status.value,
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
        pipeline_status: PipelineStatus | None = None,
        limit: int = 50,
    ) -> list[PipelineRecord]:
        results = list(self._records)
        if pipeline_name is not None:
            results = [r for r in results if r.pipeline_name == pipeline_name]
        if pipeline_status is not None:
            results = [r for r in results if r.pipeline_status == pipeline_status]
        return results[-limit:]

    def add_step(
        self,
        step_name: str,
        pipeline_stage: PipelineStage = PipelineStage.EXECUTION,
        pipeline_status: PipelineStatus = PipelineStatus.RUNNING,
        duration_seconds: float = 0.0,
    ) -> PipelineStep:
        step = PipelineStep(
            step_name=step_name,
            pipeline_stage=pipeline_stage,
            pipeline_status=pipeline_status,
            duration_seconds=duration_seconds,
        )
        self._steps.append(step)
        if len(self._steps) > self._max_records:
            self._steps = self._steps[-self._max_records :]
        logger.info(
            "remediation_pipeline.step_added",
            step_name=step_name,
            pipeline_stage=pipeline_stage.value,
            pipeline_status=pipeline_status.value,
        )
        return step

    # -- domain operations -----------------------------------------------

    def analyze_pipeline_efficiency(self, pipeline_name: str) -> dict[str, Any]:
        """Analyze efficiency for a specific pipeline."""
        records = [r for r in self._records if r.pipeline_name == pipeline_name]
        if not records:
            return {"pipeline_name": pipeline_name, "status": "no_data"}
        successes = sum(1 for r in records if r.pipeline_status == PipelineStatus.SUCCEEDED)
        success_rate = round(successes / len(records) * 100, 2)
        avg_steps = round(sum(r.step_count for r in records) / len(records), 2)
        return {
            "pipeline_name": pipeline_name,
            "total_pipelines": len(records),
            "success_count": successes,
            "success_rate_pct": success_rate,
            "avg_step_count": avg_steps,
            "meets_threshold": avg_steps <= self._max_step_count,
        }

    def identify_failed_pipelines(self) -> list[dict[str, Any]]:
        """Find pipelines with repeated failures."""
        failure_counts: dict[str, int] = {}
        for r in self._records:
            if r.pipeline_status in (
                PipelineStatus.FAILED,
                PipelineStatus.ROLLED_BACK,
            ):
                failure_counts[r.pipeline_name] = failure_counts.get(r.pipeline_name, 0) + 1
        results: list[dict[str, Any]] = []
        for pipeline, count in failure_counts.items():
            if count > 1:
                results.append(
                    {
                        "pipeline_name": pipeline,
                        "failure_count": count,
                    }
                )
        results.sort(key=lambda x: x["failure_count"], reverse=True)
        return results

    def rank_by_completion_rate(self) -> list[dict[str, Any]]:
        """Rank pipelines by success/completion rate descending."""
        totals: dict[str, list[bool]] = {}
        for r in self._records:
            totals.setdefault(r.pipeline_name, []).append(
                r.pipeline_status == PipelineStatus.SUCCEEDED
            )
        results: list[dict[str, Any]] = []
        for pipeline, outcomes in totals.items():
            rate = round(sum(outcomes) / len(outcomes) * 100, 2)
            results.append(
                {
                    "pipeline_name": pipeline,
                    "completion_rate_pct": rate,
                }
            )
        results.sort(key=lambda x: x["completion_rate_pct"], reverse=True)
        return results

    def detect_pipeline_bottlenecks(self) -> list[dict[str, Any]]:
        """Detect pipelines with >3 non-succeeded executions."""
        svc_non_success: dict[str, int] = {}
        for r in self._records:
            if r.pipeline_status != PipelineStatus.SUCCEEDED:
                svc_non_success[r.pipeline_name] = svc_non_success.get(r.pipeline_name, 0) + 1
        results: list[dict[str, Any]] = []
        for pipeline, count in svc_non_success.items():
            if count > 3:
                results.append(
                    {
                        "pipeline_name": pipeline,
                        "non_success_count": count,
                        "bottleneck_detected": True,
                    }
                )
        results.sort(key=lambda x: x["non_success_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> PipelineOrchestratorReport:
        by_stage: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_stage[r.pipeline_stage.value] = by_stage.get(r.pipeline_stage.value, 0) + 1
            by_status[r.pipeline_status.value] = by_status.get(r.pipeline_status.value, 0) + 1
        success_count = sum(
            1 for r in self._records if r.pipeline_status == PipelineStatus.SUCCEEDED
        )
        success_rate = round(success_count / len(self._records) * 100, 2) if self._records else 0.0
        rollback_count = sum(
            1 for r in self._records if r.pipeline_status == PipelineStatus.ROLLED_BACK
        )
        recs: list[str] = []
        if success_rate < 80.0:
            recs.append(f"Success rate {success_rate}% is below 80.0% threshold")
        failed_pipelines = sum(1 for d in self.identify_failed_pipelines())
        if failed_pipelines > 0:
            recs.append(f"{failed_pipelines} pipeline(s) with repeated failures")
        bottlenecks = len(self.detect_pipeline_bottlenecks())
        if bottlenecks > 0:
            recs.append(f"{bottlenecks} pipeline(s) detected as bottlenecks")
        if not recs:
            recs.append("Pipeline orchestration effectiveness meets targets")
        return PipelineOrchestratorReport(
            total_pipelines=len(self._records),
            total_steps=len(self._steps),
            success_rate_pct=success_rate,
            by_stage=by_stage,
            by_status=by_status,
            rollback_count=rollback_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._steps.clear()
        logger.info("remediation_pipeline.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            key = r.pipeline_stage.value
            stage_dist[key] = stage_dist.get(key, 0) + 1
        return {
            "total_pipelines": len(self._records),
            "total_steps": len(self._steps),
            "max_step_count": self._max_step_count,
            "stage_distribution": stage_dist,
            "unique_pipelines": len({r.pipeline_name for r in self._records}),
        }
