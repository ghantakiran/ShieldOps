"""Build Pipeline Analyzer — track CI/CD build duration, success rates, flaky stages."""

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
    CHECKOUT = "checkout"
    BUILD = "build"
    TEST = "test"
    SECURITY_SCAN = "security_scan"
    PUBLISH = "publish"


class BuildOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNSTABLE = "unstable"


class OptimizationTarget(StrEnum):
    PARALLELISM = "parallelism"
    CACHING = "caching"
    RESOURCE_ALLOCATION = "resource_allocation"
    STAGE_ELIMINATION = "stage_elimination"
    DEPENDENCY_REDUCTION = "dependency_reduction"


# --- Models ---


class BuildRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_name: str = ""
    stage: PipelineStage = PipelineStage.BUILD
    outcome: BuildOutcome = BuildOutcome.SUCCESS
    duration_seconds: float = 0.0
    branch: str = ""
    commit_sha: str = ""
    is_flaky: bool = False
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class BuildOptimization(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_name: str = ""
    target: OptimizationTarget = OptimizationTarget.CACHING
    estimated_savings_seconds: float = 0.0
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class BuildPipelineReport(BaseModel):
    total_builds: int = 0
    total_optimizations: int = 0
    avg_duration_seconds: float = 0.0
    success_rate_pct: float = 0.0
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_stage: dict[str, float] = Field(default_factory=dict)
    flaky_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class BuildPipelineAnalyzer:
    """Track CI/CD build duration, success rates, flaky stages."""

    def __init__(
        self,
        max_records: int = 200000,
        min_success_rate_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_success_rate_pct = min_success_rate_pct
        self._records: list[BuildRecord] = []
        self._optimizations: list[BuildOptimization] = []
        logger.info(
            "build_pipeline.initialized",
            max_records=max_records,
            min_success_rate_pct=min_success_rate_pct,
        )

    # -- record / get / list -------------------------------------------------

    def record_build(
        self,
        pipeline_name: str,
        stage: PipelineStage = PipelineStage.BUILD,
        outcome: BuildOutcome = BuildOutcome.SUCCESS,
        duration_seconds: float = 0.0,
        branch: str = "",
        commit_sha: str = "",
        is_flaky: bool = False,
        details: str = "",
    ) -> BuildRecord:
        record = BuildRecord(
            pipeline_name=pipeline_name,
            stage=stage,
            outcome=outcome,
            duration_seconds=duration_seconds,
            branch=branch,
            commit_sha=commit_sha,
            is_flaky=is_flaky,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "build_pipeline.build_recorded",
            record_id=record.id,
            pipeline_name=pipeline_name,
            outcome=outcome.value,
        )
        return record

    def get_build(self, record_id: str) -> BuildRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_builds(
        self,
        pipeline_name: str | None = None,
        outcome: BuildOutcome | None = None,
        limit: int = 50,
    ) -> list[BuildRecord]:
        results = list(self._records)
        if pipeline_name is not None:
            results = [r for r in results if r.pipeline_name == pipeline_name]
        if outcome is not None:
            results = [r for r in results if r.outcome == outcome]
        return results[-limit:]

    def add_optimization(
        self,
        pipeline_name: str,
        target: OptimizationTarget = OptimizationTarget.CACHING,
        estimated_savings_seconds: float = 0.0,
        reason: str = "",
    ) -> BuildOptimization:
        opt = BuildOptimization(
            pipeline_name=pipeline_name,
            target=target,
            estimated_savings_seconds=estimated_savings_seconds,
            reason=reason,
        )
        self._optimizations.append(opt)
        if len(self._optimizations) > self._max_records:
            self._optimizations = self._optimizations[-self._max_records :]
        logger.info(
            "build_pipeline.optimization_added",
            pipeline_name=pipeline_name,
            target=target.value,
        )
        return opt

    # -- domain operations ---------------------------------------------------

    def analyze_pipeline_performance(self, pipeline_name: str) -> dict[str, Any]:
        """Analyze performance for a specific pipeline."""
        records = [r for r in self._records if r.pipeline_name == pipeline_name]
        if not records:
            return {"pipeline_name": pipeline_name, "status": "no_data"}
        total = len(records)
        successes = sum(1 for r in records if r.outcome == BuildOutcome.SUCCESS)
        avg_dur = round(sum(r.duration_seconds for r in records) / total, 2)
        return {
            "pipeline_name": pipeline_name,
            "total_builds": total,
            "success_rate_pct": round(successes / total * 100, 2),
            "avg_duration_seconds": avg_dur,
            "flaky_count": sum(1 for r in records if r.is_flaky),
        }

    def identify_flaky_stages(self) -> list[dict[str, Any]]:
        """Find stages with flaky builds."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.is_flaky:
                results.append(
                    {
                        "pipeline_name": r.pipeline_name,
                        "stage": r.stage.value,
                        "outcome": r.outcome.value,
                        "duration_seconds": r.duration_seconds,
                    }
                )
        results.sort(key=lambda x: x["duration_seconds"], reverse=True)
        return results

    def rank_slowest_pipelines(self) -> list[dict[str, Any]]:
        """Rank pipelines by average duration."""
        durations: dict[str, list[float]] = {}
        for r in self._records:
            durations.setdefault(r.pipeline_name, []).append(r.duration_seconds)
        results: list[dict[str, Any]] = []
        for name, durs in durations.items():
            results.append(
                {
                    "pipeline_name": name,
                    "avg_duration_seconds": round(sum(durs) / len(durs), 2),
                    "build_count": len(durs),
                }
            )
        results.sort(key=lambda x: x["avg_duration_seconds"], reverse=True)
        return results

    def estimate_time_savings(self) -> list[dict[str, Any]]:
        """Estimate time savings from optimizations."""
        results: list[dict[str, Any]] = []
        for opt in self._optimizations:
            results.append(
                {
                    "pipeline_name": opt.pipeline_name,
                    "target": opt.target.value,
                    "estimated_savings_seconds": opt.estimated_savings_seconds,
                    "reason": opt.reason,
                }
            )
        results.sort(key=lambda x: x["estimated_savings_seconds"], reverse=True)
        return results

    # -- report / stats ------------------------------------------------------

    def generate_report(self) -> BuildPipelineReport:
        by_outcome: dict[str, int] = {}
        stage_durs: dict[str, list[float]] = {}
        for r in self._records:
            by_outcome[r.outcome.value] = by_outcome.get(r.outcome.value, 0) + 1
            stage_durs.setdefault(r.stage.value, []).append(r.duration_seconds)
        by_stage: dict[str, float] = {}
        for stage, durs in stage_durs.items():
            by_stage[stage] = round(sum(durs) / len(durs), 2)
        total = len(self._records)
        avg_dur = round(sum(r.duration_seconds for r in self._records) / total, 2) if total else 0.0
        successes = sum(1 for r in self._records if r.outcome == BuildOutcome.SUCCESS)
        success_rate = round(successes / total * 100, 2) if total else 0.0
        flaky_count = sum(1 for r in self._records if r.is_flaky)
        recs: list[str] = []
        if total > 0 and success_rate < self._min_success_rate_pct:
            recs.append(
                f"Success rate {success_rate}% below {self._min_success_rate_pct}% threshold"
            )
        if flaky_count > 0:
            recs.append(f"{flaky_count} flaky build(s) detected")
        if not recs:
            recs.append("Build pipeline performance meets targets")
        return BuildPipelineReport(
            total_builds=total,
            total_optimizations=len(self._optimizations),
            avg_duration_seconds=avg_dur,
            success_rate_pct=success_rate,
            by_outcome=by_outcome,
            by_stage=by_stage,
            flaky_count=flaky_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._optimizations.clear()
        logger.info("build_pipeline.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        outcome_dist: dict[str, int] = {}
        for r in self._records:
            key = r.outcome.value
            outcome_dist[key] = outcome_dist.get(key, 0) + 1
        return {
            "total_builds": len(self._records),
            "total_optimizations": len(self._optimizations),
            "min_success_rate_pct": self._min_success_rate_pct,
            "outcome_distribution": outcome_dist,
            "unique_pipelines": len({r.pipeline_name for r in self._records}),
        }
