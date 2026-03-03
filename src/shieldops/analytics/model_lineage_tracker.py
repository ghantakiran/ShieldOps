"""Model Lineage Tracker — track ML model lineage and artifact provenance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LineageStage(StrEnum):
    DATA_COLLECTION = "data_collection"
    PREPROCESSING = "preprocessing"
    TRAINING = "training"
    VALIDATION = "validation"
    DEPLOYMENT = "deployment"


class ArtifactType(StrEnum):
    DATASET = "dataset"
    FEATURE_STORE = "feature_store"
    MODEL_WEIGHTS = "model_weights"
    CHECKPOINT = "checkpoint"
    CONFIG = "config"


class LineageStatus(StrEnum):
    TRACKED = "tracked"
    MISSING = "missing"
    CORRUPTED = "corrupted"
    ARCHIVED = "archived"
    UNKNOWN = "unknown"


# --- Models ---


class LineageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    lineage_stage: LineageStage = LineageStage.DATA_COLLECTION
    artifact_type: ArtifactType = ArtifactType.DATASET
    lineage_status: LineageStatus = LineageStatus.UNKNOWN
    lineage_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class LineageAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    lineage_stage: LineageStage = LineageStage.DATA_COLLECTION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LineageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_lineage_score: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_artifact: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ModelLineageTracker:
    """Track ML model lineage and artifact provenance."""

    def __init__(
        self,
        max_records: int = 200000,
        lineage_gap_threshold: float = 0.6,
    ) -> None:
        self._max_records = max_records
        self._lineage_gap_threshold = lineage_gap_threshold
        self._records: list[LineageRecord] = []
        self._analyses: list[LineageAnalysis] = []
        logger.info(
            "model_lineage_tracker.initialized",
            max_records=max_records,
            lineage_gap_threshold=lineage_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_lineage(
        self,
        model_id: str,
        lineage_stage: LineageStage = LineageStage.DATA_COLLECTION,
        artifact_type: ArtifactType = ArtifactType.DATASET,
        lineage_status: LineageStatus = LineageStatus.UNKNOWN,
        lineage_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> LineageRecord:
        record = LineageRecord(
            model_id=model_id,
            lineage_stage=lineage_stage,
            artifact_type=artifact_type,
            lineage_status=lineage_status,
            lineage_score=lineage_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "model_lineage_tracker.lineage_recorded",
            record_id=record.id,
            model_id=model_id,
            lineage_stage=lineage_stage.value,
        )
        return record

    def get_lineage(self, record_id: str) -> LineageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_lineages(
        self,
        lineage_stage: LineageStage | None = None,
        lineage_status: LineageStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[LineageRecord]:
        results = list(self._records)
        if lineage_stage is not None:
            results = [r for r in results if r.lineage_stage == lineage_stage]
        if lineage_status is not None:
            results = [r for r in results if r.lineage_status == lineage_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        model_id: str,
        lineage_stage: LineageStage = LineageStage.DATA_COLLECTION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> LineageAnalysis:
        analysis = LineageAnalysis(
            model_id=model_id,
            lineage_stage=lineage_stage,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "model_lineage_tracker.analysis_added",
            model_id=model_id,
            lineage_stage=lineage_stage.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by lineage_stage; return count and avg lineage_score."""
        stage_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.lineage_stage.value
            stage_data.setdefault(key, []).append(r.lineage_score)
        result: dict[str, Any] = {}
        for stage, scores in stage_data.items():
            result[stage] = {
                "count": len(scores),
                "avg_lineage_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_severe_drifts(self) -> list[dict[str, Any]]:
        """Return records where lineage_score < lineage_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.lineage_score < self._lineage_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "model_id": r.model_id,
                        "lineage_stage": r.lineage_stage.value,
                        "lineage_score": r.lineage_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["lineage_score"])

    def rank_by_severity(self) -> list[dict[str, Any]]:
        """Group by model_id, avg lineage_score, sort ascending (lowest first)."""
        model_scores: dict[str, list[float]] = {}
        for r in self._records:
            model_scores.setdefault(r.model_id, []).append(r.lineage_score)
        results: list[dict[str, Any]] = []
        for model_id, scores in model_scores.items():
            results.append(
                {
                    "model_id": model_id,
                    "avg_lineage_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_lineage_score"])
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

    def generate_report(self) -> LineageReport:
        by_stage: dict[str, int] = {}
        by_artifact: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_stage[r.lineage_stage.value] = by_stage.get(r.lineage_stage.value, 0) + 1
            by_artifact[r.artifact_type.value] = by_artifact.get(r.artifact_type.value, 0) + 1
            by_status[r.lineage_status.value] = by_status.get(r.lineage_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.lineage_score < self._lineage_gap_threshold)
        scores = [r.lineage_score for r in self._records]
        avg_lineage_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_severe_drifts()
        top_gaps = [o["model_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} model(s) below lineage threshold ({self._lineage_gap_threshold})"
            )
        if self._records and avg_lineage_score < self._lineage_gap_threshold:
            recs.append(
                f"Avg lineage score {avg_lineage_score} below threshold "
                f"({self._lineage_gap_threshold})"
            )
        if not recs:
            recs.append("Model lineage tracking is complete")
        return LineageReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_lineage_score=avg_lineage_score,
            by_stage=by_stage,
            by_artifact=by_artifact,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("model_lineage_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            key = r.lineage_stage.value
            stage_dist[key] = stage_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "lineage_gap_threshold": self._lineage_gap_threshold,
            "stage_distribution": stage_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_models": len({r.model_id for r in self._records}),
        }
