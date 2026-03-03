"""Detection Gap Prioritizer — prioritize detection gaps by likelihood, impact, and."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GapCategory(StrEnum):
    TECHNIQUE_COVERAGE = "technique_coverage"
    DATA_SOURCE = "data_source"
    PLATFORM = "platform"
    ENVIRONMENT = "environment"
    THREAT_ACTOR = "threat_actor"


class PrioritizationFactor(StrEnum):
    LIKELIHOOD = "likelihood"
    IMPACT = "impact"
    EXPLOITABILITY = "exploitability"
    ASSET_VALUE = "asset_value"
    THREAT_INTEL = "threat_intel"


class GapSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ACCEPTABLE = "acceptable"


# --- Models ---


class DetectionGapRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_id: str = ""
    gap_category: GapCategory = GapCategory.TECHNIQUE_COVERAGE
    prioritization_factor: PrioritizationFactor = PrioritizationFactor.LIKELIHOOD
    gap_severity: GapSeverity = GapSeverity.MEDIUM
    gap_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DetectionGapAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_id: str = ""
    gap_category: GapCategory = GapCategory.TECHNIQUE_COVERAGE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DetectionGapReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_gap_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_factor: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DetectionGapPrioritizer:
    """Prioritize detection gaps by likelihood, impact, and exploitability."""

    def __init__(
        self,
        max_records: int = 200000,
        gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._gap_threshold = gap_threshold
        self._records: list[DetectionGapRecord] = []
        self._analyses: list[DetectionGapAnalysis] = []
        logger.info(
            "detection_gap_prioritizer.initialized",
            max_records=max_records,
            gap_threshold=gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_gap(
        self,
        gap_id: str,
        gap_category: GapCategory = GapCategory.TECHNIQUE_COVERAGE,
        prioritization_factor: PrioritizationFactor = PrioritizationFactor.LIKELIHOOD,
        gap_severity: GapSeverity = GapSeverity.MEDIUM,
        gap_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DetectionGapRecord:
        record = DetectionGapRecord(
            gap_id=gap_id,
            gap_category=gap_category,
            prioritization_factor=prioritization_factor,
            gap_severity=gap_severity,
            gap_score=gap_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "detection_gap_prioritizer.gap_recorded",
            record_id=record.id,
            gap_id=gap_id,
            gap_category=gap_category.value,
            prioritization_factor=prioritization_factor.value,
        )
        return record

    def get_gap(self, record_id: str) -> DetectionGapRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_gaps(
        self,
        gap_category: GapCategory | None = None,
        prioritization_factor: PrioritizationFactor | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DetectionGapRecord]:
        results = list(self._records)
        if gap_category is not None:
            results = [r for r in results if r.gap_category == gap_category]
        if prioritization_factor is not None:
            results = [r for r in results if r.prioritization_factor == prioritization_factor]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        gap_id: str,
        gap_category: GapCategory = GapCategory.TECHNIQUE_COVERAGE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DetectionGapAnalysis:
        analysis = DetectionGapAnalysis(
            gap_id=gap_id,
            gap_category=gap_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "detection_gap_prioritizer.analysis_added",
            gap_id=gap_id,
            gap_category=gap_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_category_distribution(self) -> dict[str, Any]:
        category_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.gap_category.value
            category_data.setdefault(key, []).append(r.gap_score)
        result: dict[str, Any] = {}
        for category, scores in category_data.items():
            result[category] = {
                "count": len(scores),
                "avg_gap_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gap_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.gap_score < self._gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "gap_id": r.gap_id,
                        "gap_category": r.gap_category.value,
                        "gap_score": r.gap_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["gap_score"])

    def rank_by_gap(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.gap_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_gap_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_gap_score"])
        return results

    def detect_gap_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> DetectionGapReport:
        by_category: dict[str, int] = {}
        by_factor: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_category[r.gap_category.value] = by_category.get(r.gap_category.value, 0) + 1
            by_factor[r.prioritization_factor.value] = (
                by_factor.get(r.prioritization_factor.value, 0) + 1
            )
            by_severity[r.gap_severity.value] = by_severity.get(r.gap_severity.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.gap_score < self._gap_threshold)
        scores = [r.gap_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gap_gaps()
        top_gaps = [o["gap_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} detection gap(s) below threshold ({self._gap_threshold})")
        if self._records and avg_score < self._gap_threshold:
            recs.append(f"Avg gap score {avg_score} below threshold ({self._gap_threshold})")
        if not recs:
            recs.append("Detection gap prioritization is healthy")
        return DetectionGapReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_gap_score=avg_score,
            by_category=by_category,
            by_factor=by_factor,
            by_severity=by_severity,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("detection_gap_prioritizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.gap_category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "gap_threshold": self._gap_threshold,
            "category_distribution": category_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
