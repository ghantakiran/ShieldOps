"""Provisioning Pipeline Optimizer
compute pipeline efficiency, detect bottlenecks,
rank stages by optimization potential."""

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
    PLAN = "plan"
    VALIDATE = "validate"
    APPLY = "apply"
    VERIFY = "verify"


class StageStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SLOW = "slow"
    SKIPPED = "skipped"


class OptimizationType(StrEnum):
    PARALLELIZATION = "parallelization"
    CACHING = "caching"
    BATCHING = "batching"
    ELIMINATION = "elimination"


# --- Models ---


class PipelineOptimizationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str = ""
    stage_name: str = ""
    pipeline_stage: PipelineStage = PipelineStage.PLAN
    stage_status: StageStatus = StageStatus.PASSED
    optimization_type: OptimizationType = OptimizationType.CACHING
    duration_seconds: float = 0.0
    efficiency_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PipelineOptimizationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str = ""
    total_duration: float = 0.0
    efficiency_score: float = 0.0
    bottleneck_stage: str = ""
    has_failures: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PipelineOptimizationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_efficiency: float = 0.0
    by_pipeline_stage: dict[str, int] = Field(default_factory=dict)
    by_stage_status: dict[str, int] = Field(default_factory=dict)
    by_optimization_type: dict[str, int] = Field(default_factory=dict)
    slow_pipelines: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ProvisioningPipelineOptimizer:
    """Compute pipeline efficiency, detect
    bottlenecks, rank stages by optimization."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[PipelineOptimizationRecord] = []
        self._analyses: dict[str, PipelineOptimizationAnalysis] = {}
        logger.info(
            "provisioning_pipeline_optimizer.init",
            max_records=max_records,
        )

    def record_item(
        self,
        pipeline_id: str = "",
        stage_name: str = "",
        pipeline_stage: PipelineStage = (PipelineStage.PLAN),
        stage_status: StageStatus = StageStatus.PASSED,
        optimization_type: OptimizationType = (OptimizationType.CACHING),
        duration_seconds: float = 0.0,
        efficiency_score: float = 0.0,
        description: str = "",
    ) -> PipelineOptimizationRecord:
        record = PipelineOptimizationRecord(
            pipeline_id=pipeline_id,
            stage_name=stage_name,
            pipeline_stage=pipeline_stage,
            stage_status=stage_status,
            optimization_type=optimization_type,
            duration_seconds=duration_seconds,
            efficiency_score=efficiency_score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "pipeline_optimization.record_added",
            record_id=record.id,
            pipeline_id=pipeline_id,
        )
        return record

    def process(self, key: str) -> PipelineOptimizationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        stages = [r for r in self._records if r.pipeline_id == rec.pipeline_id]
        total_dur = sum(s.duration_seconds for s in stages)
        has_fail = any(s.stage_status == StageStatus.FAILED for s in stages)
        bottleneck = (
            max(
                stages,
                key=lambda x: x.duration_seconds,
            ).stage_name
            if stages
            else ""
        )
        analysis = PipelineOptimizationAnalysis(
            pipeline_id=rec.pipeline_id,
            total_duration=round(total_dur, 2),
            efficiency_score=round(rec.efficiency_score, 2),
            bottleneck_stage=bottleneck,
            has_failures=has_fail,
            description=(f"Pipeline {rec.pipeline_id} efficiency {rec.efficiency_score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> PipelineOptimizationReport:
        by_ps: dict[str, int] = {}
        by_ss: dict[str, int] = {}
        by_ot: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.pipeline_stage.value
            by_ps[k] = by_ps.get(k, 0) + 1
            k2 = r.stage_status.value
            by_ss[k2] = by_ss.get(k2, 0) + 1
            k3 = r.optimization_type.value
            by_ot[k3] = by_ot.get(k3, 0) + 1
            scores.append(r.efficiency_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        slow = list(
            {
                r.pipeline_id
                for r in self._records
                if r.stage_status in (StageStatus.SLOW, StageStatus.FAILED)
            }
        )[:10]
        recs: list[str] = []
        if slow:
            recs.append(f"{len(slow)} slow pipelines detected")
        if not recs:
            recs.append("All pipelines running efficiently")
        return PipelineOptimizationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_efficiency=avg,
            by_pipeline_stage=by_ps,
            by_stage_status=by_ss,
            by_optimization_type=by_ot,
            slow_pipelines=slow,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ps_dist: dict[str, int] = {}
        for r in self._records:
            k = r.pipeline_stage.value
            ps_dist[k] = ps_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "pipeline_stage_distribution": ps_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("provisioning_pipeline_optimizer.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_pipeline_efficiency(
        self,
    ) -> list[dict[str, Any]]:
        """Compute efficiency per pipeline."""
        pipe_scores: dict[str, list[float]] = {}
        pipe_durations: dict[str, list[float]] = {}
        for r in self._records:
            pipe_scores.setdefault(r.pipeline_id, []).append(r.efficiency_score)
            pipe_durations.setdefault(r.pipeline_id, []).append(r.duration_seconds)
        results: list[dict[str, Any]] = []
        for pid, scores in pipe_scores.items():
            avg_eff = round(sum(scores) / len(scores), 2)
            total_dur = round(sum(pipe_durations[pid]), 2)
            results.append(
                {
                    "pipeline_id": pid,
                    "avg_efficiency": avg_eff,
                    "total_duration": total_dur,
                    "stage_count": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["avg_efficiency"],
            reverse=True,
        )
        return results

    def detect_pipeline_bottlenecks(
        self,
    ) -> list[dict[str, Any]]:
        """Detect bottleneck stages in pipelines."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.stage_status in (
                StageStatus.SLOW,
                StageStatus.FAILED,
            ):
                results.append(
                    {
                        "pipeline_id": (r.pipeline_id),
                        "stage_name": r.stage_name,
                        "status": (r.stage_status.value),
                        "duration": (r.duration_seconds),
                        "stage": (r.pipeline_stage.value),
                    }
                )
        results.sort(
            key=lambda x: x["duration"],
            reverse=True,
        )
        return results

    def rank_stages_by_optimization_potential(
        self,
    ) -> list[dict[str, Any]]:
        """Rank stages by optimization potential."""
        stage_data: dict[str, list[float]] = {}
        for r in self._records:
            stage_data.setdefault(r.stage_name, []).append(r.duration_seconds)
        results: list[dict[str, Any]] = []
        for sname, durations in stage_data.items():
            avg_dur = round(sum(durations) / len(durations), 2)
            potential = round(avg_dur * 0.3, 2)
            results.append(
                {
                    "stage_name": sname,
                    "avg_duration": avg_dur,
                    "optimization_potential": (potential),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["optimization_potential"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
