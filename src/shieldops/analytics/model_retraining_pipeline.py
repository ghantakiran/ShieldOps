"""Model Retraining Pipeline — manage and monitor ML model retraining pipelines."""

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
    DATA_PREP = "data_prep"
    FEATURE_ENG = "feature_eng"
    TRAINING = "training"
    EVALUATION = "evaluation"
    DEPLOYMENT = "deployment"


class TriggerType(StrEnum):
    SCHEDULED = "scheduled"
    DRIFT_DETECTED = "drift_detected"
    PERFORMANCE_DROP = "performance_drop"
    MANUAL = "manual"
    CONTINUOUS = "continuous"


class PipelineStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    QUEUED = "queued"
    CANCELLED = "cancelled"


# --- Models ---


class RetrainingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    pipeline_stage: PipelineStage = PipelineStage.DATA_PREP
    trigger_type: TriggerType = TriggerType.SCHEDULED
    pipeline_status: PipelineStatus = PipelineStatus.QUEUED
    success_rate: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RetrainingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    pipeline_stage: PipelineStage = PipelineStage.DATA_PREP
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RetrainingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    failed_count: int = 0
    avg_success_rate: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_trigger: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_failing: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ModelRetrainingPipeline:
    """Manage and monitor ML model retraining pipelines."""

    def __init__(
        self,
        max_records: int = 200000,
        success_rate_threshold: float = 0.8,
    ) -> None:
        self._max_records = max_records
        self._success_rate_threshold = success_rate_threshold
        self._records: list[RetrainingRecord] = []
        self._analyses: list[RetrainingAnalysis] = []
        logger.info(
            "model_retraining_pipeline.initialized",
            max_records=max_records,
            success_rate_threshold=success_rate_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_pipeline(
        self,
        model_id: str,
        pipeline_stage: PipelineStage = PipelineStage.DATA_PREP,
        trigger_type: TriggerType = TriggerType.SCHEDULED,
        pipeline_status: PipelineStatus = PipelineStatus.QUEUED,
        success_rate: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RetrainingRecord:
        record = RetrainingRecord(
            model_id=model_id,
            pipeline_stage=pipeline_stage,
            trigger_type=trigger_type,
            pipeline_status=pipeline_status,
            success_rate=success_rate,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "model_retraining_pipeline.pipeline_recorded",
            record_id=record.id,
            model_id=model_id,
            pipeline_stage=pipeline_stage.value,
        )
        return record

    def get_pipeline(self, record_id: str) -> RetrainingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_pipelines(
        self,
        pipeline_stage: PipelineStage | None = None,
        pipeline_status: PipelineStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RetrainingRecord]:
        results = list(self._records)
        if pipeline_stage is not None:
            results = [r for r in results if r.pipeline_stage == pipeline_stage]
        if pipeline_status is not None:
            results = [r for r in results if r.pipeline_status == pipeline_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        model_id: str,
        pipeline_stage: PipelineStage = PipelineStage.DATA_PREP,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RetrainingAnalysis:
        analysis = RetrainingAnalysis(
            model_id=model_id,
            pipeline_stage=pipeline_stage,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "model_retraining_pipeline.analysis_added",
            model_id=model_id,
            pipeline_stage=pipeline_stage.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by pipeline_stage; return count and avg success_rate."""
        stage_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.pipeline_stage.value
            stage_data.setdefault(key, []).append(r.success_rate)
        result: dict[str, Any] = {}
        for stage, rates in stage_data.items():
            result[stage] = {
                "count": len(rates),
                "avg_success_rate": round(sum(rates) / len(rates), 2),
            }
        return result

    def identify_severe_drifts(self) -> list[dict[str, Any]]:
        """Return records where success_rate < success_rate_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.success_rate < self._success_rate_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "model_id": r.model_id,
                        "pipeline_stage": r.pipeline_stage.value,
                        "success_rate": r.success_rate,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["success_rate"])

    def rank_by_severity(self) -> list[dict[str, Any]]:
        """Group by model_id, avg success_rate, sort ascending (lowest first)."""
        model_rates: dict[str, list[float]] = {}
        for r in self._records:
            model_rates.setdefault(r.model_id, []).append(r.success_rate)
        results: list[dict[str, Any]] = []
        for model_id, rates in model_rates.items():
            results.append(
                {
                    "model_id": model_id,
                    "avg_success_rate": round(sum(rates) / len(rates), 2),
                }
            )
        results.sort(key=lambda x: x["avg_success_rate"])
        return results

    def detect_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> RetrainingReport:
        by_stage: dict[str, int] = {}
        by_trigger: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_stage[r.pipeline_stage.value] = by_stage.get(r.pipeline_stage.value, 0) + 1
            by_trigger[r.trigger_type.value] = by_trigger.get(r.trigger_type.value, 0) + 1
            by_status[r.pipeline_status.value] = by_status.get(r.pipeline_status.value, 0) + 1
        failed_count = sum(
            1 for r in self._records if r.success_rate < self._success_rate_threshold
        )
        rates = [r.success_rate for r in self._records]
        avg_success_rate = round(sum(rates) / len(rates), 2) if rates else 0.0
        failure_list = self.identify_severe_drifts()
        top_failing = [o["model_id"] for o in failure_list[:5]]
        recs: list[str] = []
        if self._records and failed_count > 0:
            recs.append(
                f"{failed_count} pipeline(s) below success threshold "
                f"({self._success_rate_threshold})"
            )
        if self._records and avg_success_rate < self._success_rate_threshold:
            recs.append(
                f"Avg success rate {avg_success_rate} below threshold "
                f"({self._success_rate_threshold})"
            )
        if not recs:
            recs.append("Retraining pipeline health is within acceptable bounds")
        return RetrainingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            failed_count=failed_count,
            avg_success_rate=avg_success_rate,
            by_stage=by_stage,
            by_trigger=by_trigger,
            by_status=by_status,
            top_failing=top_failing,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("model_retraining_pipeline.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            key = r.pipeline_stage.value
            stage_dist[key] = stage_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "success_rate_threshold": self._success_rate_threshold,
            "stage_distribution": stage_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_models": len({r.model_id for r in self._records}),
        }
