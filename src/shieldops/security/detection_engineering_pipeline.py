"""Detection Engineering Pipeline — manage the detection rule development lifecycle."""

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
    IDEATION = "ideation"
    DEVELOPMENT = "development"
    TESTING = "testing"
    REVIEW = "review"
    DEPLOYED = "deployed"


class DetectionLanguage(StrEnum):
    SIGMA = "sigma"
    YARA = "yara"
    KQL = "kql"
    SPL = "spl"
    CUSTOM = "custom"


class PipelineStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    FAILED = "failed"


# --- Models ---


class PipelineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    pipeline_stage: PipelineStage = PipelineStage.IDEATION
    detection_language: DetectionLanguage = DetectionLanguage.SIGMA
    pipeline_status: PipelineStatus = PipelineStatus.ACTIVE
    pipeline_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PipelineAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    pipeline_stage: PipelineStage = PipelineStage.IDEATION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PipelineReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_language: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DetectionEngineeringPipeline:
    """Manage the detection rule development lifecycle from ideation to deployment."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[PipelineRecord] = []
        self._analyses: list[PipelineAnalysis] = []
        logger.info(
            "detection_engineering_pipeline.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_pipeline(
        self,
        rule_name: str,
        pipeline_stage: PipelineStage = PipelineStage.IDEATION,
        detection_language: DetectionLanguage = DetectionLanguage.SIGMA,
        pipeline_status: PipelineStatus = PipelineStatus.ACTIVE,
        pipeline_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PipelineRecord:
        record = PipelineRecord(
            rule_name=rule_name,
            pipeline_stage=pipeline_stage,
            detection_language=detection_language,
            pipeline_status=pipeline_status,
            pipeline_score=pipeline_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "detection_engineering_pipeline.recorded",
            record_id=record.id,
            rule_name=rule_name,
        )
        return record

    def get_pipeline(self, record_id: str) -> PipelineRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_pipelines(
        self,
        pipeline_stage: PipelineStage | None = None,
        detection_language: DetectionLanguage | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PipelineRecord]:
        results = list(self._records)
        if pipeline_stage is not None:
            results = [r for r in results if r.pipeline_stage == pipeline_stage]
        if detection_language is not None:
            results = [r for r in results if r.detection_language == detection_language]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        rule_name: str,
        pipeline_stage: PipelineStage = PipelineStage.IDEATION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PipelineAnalysis:
        analysis = PipelineAnalysis(
            rule_name=rule_name,
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
            "detection_engineering_pipeline.analysis_added",
            rule_name=rule_name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.pipeline_stage.value
            type_data.setdefault(key, []).append(r.pipeline_score)
        result: dict[str, Any] = {}
        for k, scores in type_data.items():
            result[k] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.pipeline_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "rule_name": r.rule_name,
                        "pipeline_stage": r.pipeline_stage.value,
                        "pipeline_score": r.pipeline_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["pipeline_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.pipeline_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> PipelineReport:
        by_stage_d: dict[str, int] = {}
        by_language_d: dict[str, int] = {}
        by_status_d: dict[str, int] = {}
        for r in self._records:
            by_stage_d[r.pipeline_stage.value] = by_stage_d.get(r.pipeline_stage.value, 0) + 1
            lang = r.detection_language.value
            by_language_d[lang] = by_language_d.get(lang, 0) + 1
            by_status_d[r.pipeline_status.value] = by_status_d.get(r.pipeline_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.pipeline_score < self._threshold)
        scores = [r.pipeline_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["rule_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} pipeline(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Detection engineering pipeline is healthy")
        return PipelineReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_stage=by_stage_d,
            by_language=by_language_d,
            by_status=by_status_d,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("detection_engineering_pipeline.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            key = r.pipeline_stage.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "distribution": dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
