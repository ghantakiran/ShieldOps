"""Intel Confidence Scorer — score and validate intelligence confidence levels."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IntelSource(StrEnum):
    HUMINT = "humint"
    SIGINT = "sigint"
    OSINT = "osint"
    TECHINT = "techint"
    GEOINT = "geoint"


class ConfidenceGrade(StrEnum):
    VERIFIED = "verified"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    DOUBTFUL = "doubtful"
    IMPROBABLE = "improbable"


class ScoringMethod(StrEnum):
    ANALYTIC = "analytic"
    STATISTICAL = "statistical"
    MACHINE_LEARNING = "machine_learning"
    CONSENSUS = "consensus"
    HEURISTIC = "heuristic"


# --- Models ---


class ConfidenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intel_name: str = ""
    intel_source: IntelSource = IntelSource.OSINT
    confidence_grade: ConfidenceGrade = ConfidenceGrade.POSSIBLE
    scoring_method: ScoringMethod = ScoringMethod.ANALYTIC
    confidence_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ConfidenceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intel_name: str = ""
    intel_source: IntelSource = IntelSource.OSINT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ConfidenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_confidence_score: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IntelConfidenceScorer:
    """Score and validate intelligence confidence levels across sources."""

    def __init__(self, max_records: int = 200000, quality_threshold: float = 50.0) -> None:
        self._max_records = max_records
        self._quality_threshold = quality_threshold
        self._records: list[ConfidenceRecord] = []
        self._analyses: list[ConfidenceAnalysis] = []
        logger.info(
            "intel_confidence_scorer.initialized",
            max_records=max_records,
            quality_threshold=quality_threshold,
        )

    def record_confidence(
        self,
        intel_name: str,
        intel_source: IntelSource = IntelSource.OSINT,
        confidence_grade: ConfidenceGrade = ConfidenceGrade.POSSIBLE,
        scoring_method: ScoringMethod = ScoringMethod.ANALYTIC,
        confidence_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ConfidenceRecord:
        record = ConfidenceRecord(
            intel_name=intel_name,
            intel_source=intel_source,
            confidence_grade=confidence_grade,
            scoring_method=scoring_method,
            confidence_score=confidence_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "intel_confidence_scorer.recorded",
            record_id=record.id,
            intel_name=intel_name,
            intel_source=intel_source.value,
        )
        return record

    def get_record(self, record_id: str) -> ConfidenceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        intel_source: IntelSource | None = None,
        confidence_grade: ConfidenceGrade | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ConfidenceRecord]:
        results = list(self._records)
        if intel_source is not None:
            results = [r for r in results if r.intel_source == intel_source]
        if confidence_grade is not None:
            results = [r for r in results if r.confidence_grade == confidence_grade]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        intel_name: str,
        intel_source: IntelSource = IntelSource.OSINT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ConfidenceAnalysis:
        analysis = ConfidenceAnalysis(
            intel_name=intel_name,
            intel_source=intel_source,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "intel_confidence_scorer.analysis_added",
            intel_name=intel_name,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_source_distribution(self) -> dict[str, Any]:
        source_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.intel_source.value
            source_data.setdefault(key, []).append(r.confidence_score)
        result: dict[str, Any] = {}
        for source, scores in source_data.items():
            result[source] = {
                "count": len(scores),
                "avg_confidence_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.confidence_score < self._quality_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "intel_name": r.intel_name,
                        "intel_source": r.intel_source.value,
                        "confidence_score": r.confidence_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["confidence_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.confidence_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_confidence_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_confidence_score"])
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

    def generate_report(self) -> ConfidenceReport:
        by_source: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._records:
            by_source[r.intel_source.value] = by_source.get(r.intel_source.value, 0) + 1
            by_grade[r.confidence_grade.value] = by_grade.get(r.confidence_grade.value, 0) + 1
            by_method[r.scoring_method.value] = by_method.get(r.scoring_method.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.confidence_score < self._quality_threshold)
        scores = [r.confidence_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["intel_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} intel item(s) below quality threshold ({self._quality_threshold})"
            )
        if self._records and avg_score < self._quality_threshold:
            recs.append(
                f"Avg confidence score {avg_score} below threshold ({self._quality_threshold})"
            )
        if not recs:
            recs.append("Intel confidence scoring is healthy")
        return ConfidenceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_confidence_score=avg_score,
            by_source=by_source,
            by_grade=by_grade,
            by_method=by_method,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("intel_confidence_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        source_dist: dict[str, int] = {}
        for r in self._records:
            key = r.intel_source.value
            source_dist[key] = source_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_threshold": self._quality_threshold,
            "source_distribution": source_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
