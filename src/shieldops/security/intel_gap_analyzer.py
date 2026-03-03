"""Intel Gap Analyzer — identify and assess gaps in intelligence coverage."""

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
    COLLECTION = "collection"
    ANALYSIS = "analysis"
    DISSEMINATION = "dissemination"
    COVERAGE = "coverage"
    TIMELINESS = "timeliness"


class GapSeverity(StrEnum):
    CRITICAL = "critical"
    SIGNIFICANT = "significant"
    MODERATE = "moderate"
    MINOR = "minor"
    NEGLIGIBLE = "negligible"


class GapStatus(StrEnum):
    IDENTIFIED = "identified"
    ASSESSED = "assessed"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"


# --- Models ---


class GapRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_name: str = ""
    gap_category: GapCategory = GapCategory.COVERAGE
    gap_severity: GapSeverity = GapSeverity.MODERATE
    gap_status: GapStatus = GapStatus.IDENTIFIED
    coverage_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class GapAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_name: str = ""
    gap_category: GapCategory = GapCategory.COVERAGE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class GapAnalysisReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_coverage_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IntelGapAnalyzer:
    """Identify and assess gaps in intelligence coverage."""

    def __init__(self, max_records: int = 200000, quality_threshold: float = 50.0) -> None:
        self._max_records = max_records
        self._quality_threshold = quality_threshold
        self._records: list[GapRecord] = []
        self._analyses: list[GapAnalysis] = []
        logger.info(
            "intel_gap_analyzer.initialized",
            max_records=max_records,
            quality_threshold=quality_threshold,
        )

    def record_gap(
        self,
        gap_name: str,
        gap_category: GapCategory = GapCategory.COVERAGE,
        gap_severity: GapSeverity = GapSeverity.MODERATE,
        gap_status: GapStatus = GapStatus.IDENTIFIED,
        coverage_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> GapRecord:
        record = GapRecord(
            gap_name=gap_name,
            gap_category=gap_category,
            gap_severity=gap_severity,
            gap_status=gap_status,
            coverage_score=coverage_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "intel_gap_analyzer.recorded",
            record_id=record.id,
            gap_name=gap_name,
            gap_category=gap_category.value,
        )
        return record

    def get_record(self, record_id: str) -> GapRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        gap_category: GapCategory | None = None,
        gap_severity: GapSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[GapRecord]:
        results = list(self._records)
        if gap_category is not None:
            results = [r for r in results if r.gap_category == gap_category]
        if gap_severity is not None:
            results = [r for r in results if r.gap_severity == gap_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        gap_name: str,
        gap_category: GapCategory = GapCategory.COVERAGE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> GapAnalysis:
        analysis = GapAnalysis(
            gap_name=gap_name,
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
            "intel_gap_analyzer.analysis_added",
            gap_name=gap_name,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_category_distribution(self) -> dict[str, Any]:
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.gap_category.value
            cat_data.setdefault(key, []).append(r.coverage_score)
        result: dict[str, Any] = {}
        for cat, scores in cat_data.items():
            result[cat] = {
                "count": len(scores),
                "avg_coverage_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.coverage_score < self._quality_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "gap_name": r.gap_name,
                        "gap_category": r.gap_category.value,
                        "coverage_score": r.coverage_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["coverage_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.coverage_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_coverage_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_score"])
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

    def generate_report(self) -> GapAnalysisReport:
        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_category[r.gap_category.value] = by_category.get(r.gap_category.value, 0) + 1
            by_severity[r.gap_severity.value] = by_severity.get(r.gap_severity.value, 0) + 1
            by_status[r.gap_status.value] = by_status.get(r.gap_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.coverage_score < self._quality_threshold)
        scores = [r.coverage_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["gap_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} gap(s) below quality threshold ({self._quality_threshold})")
        if self._records and avg_score < self._quality_threshold:
            recs.append(
                f"Avg coverage score {avg_score} below threshold ({self._quality_threshold})"
            )
        if not recs:
            recs.append("Intel gap analysis is healthy")
        return GapAnalysisReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_coverage_score=avg_score,
            by_category=by_category,
            by_severity=by_severity,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("intel_gap_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.gap_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_threshold": self._quality_threshold,
            "category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
