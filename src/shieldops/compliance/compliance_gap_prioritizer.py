"""Compliance Gap Prioritizer — gap prioritization by impact and effort."""

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
    POLICY = "policy"
    TECHNICAL = "technical"
    PROCESS = "process"
    PEOPLE = "people"
    DOCUMENTATION = "documentation"


class PriorityLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class RemediationEffort(StrEnum):
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTENSIVE = "extensive"


# --- Models ---


class GapRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_name: str = ""
    gap_category: GapCategory = GapCategory.POLICY
    priority_level: PriorityLevel = PriorityLevel.CRITICAL
    remediation_effort: RemediationEffort = RemediationEffort.MINIMAL
    gap_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class GapAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_name: str = ""
    gap_category: GapCategory = GapCategory.POLICY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class GapPrioritizationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_priority_count: int = 0
    avg_gap_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_effort: dict[str, int] = Field(default_factory=dict)
    top_high_priority: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceGapPrioritizer:
    """Compliance gap prioritization by impact and remediation effort."""

    def __init__(
        self,
        max_records: int = 200000,
        gap_priority_threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._gap_priority_threshold = gap_priority_threshold
        self._records: list[GapRecord] = []
        self._analyses: list[GapAnalysis] = []
        logger.info(
            "compliance_gap_prioritizer.initialized",
            max_records=max_records,
            gap_priority_threshold=gap_priority_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_gap(
        self,
        gap_name: str,
        gap_category: GapCategory = GapCategory.POLICY,
        priority_level: PriorityLevel = PriorityLevel.CRITICAL,
        remediation_effort: RemediationEffort = RemediationEffort.MINIMAL,
        gap_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> GapRecord:
        record = GapRecord(
            gap_name=gap_name,
            gap_category=gap_category,
            priority_level=priority_level,
            remediation_effort=remediation_effort,
            gap_score=gap_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "compliance_gap_prioritizer.gap_recorded",
            record_id=record.id,
            gap_name=gap_name,
            gap_category=gap_category.value,
            priority_level=priority_level.value,
        )
        return record

    def get_gap(self, record_id: str) -> GapRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_gaps(
        self,
        gap_category: GapCategory | None = None,
        priority_level: PriorityLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[GapRecord]:
        results = list(self._records)
        if gap_category is not None:
            results = [r for r in results if r.gap_category == gap_category]
        if priority_level is not None:
            results = [r for r in results if r.priority_level == priority_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        gap_name: str,
        gap_category: GapCategory = GapCategory.POLICY,
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
            "compliance_gap_prioritizer.analysis_added",
            gap_name=gap_name,
            gap_category=gap_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_category_distribution(self) -> dict[str, Any]:
        """Group by gap_category; return count and avg gap_score."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.gap_category.value
            cat_data.setdefault(key, []).append(r.gap_score)
        result: dict[str, Any] = {}
        for cat, scores in cat_data.items():
            result[cat] = {
                "count": len(scores),
                "avg_gap_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_priority_gaps(self) -> list[dict[str, Any]]:
        """Return records where gap_score > gap_priority_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.gap_score > self._gap_priority_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "gap_name": r.gap_name,
                        "gap_category": r.gap_category.value,
                        "gap_score": r.gap_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["gap_score"], reverse=True)

    def rank_by_gap_score(self) -> list[dict[str, Any]]:
        """Group by service, avg gap_score, sort descending (highest first)."""
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
        results.sort(key=lambda x: x["avg_gap_score"], reverse=True)
        return results

    def detect_gap_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
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

    def generate_report(self) -> GapPrioritizationReport:
        by_category: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        by_effort: dict[str, int] = {}
        for r in self._records:
            by_category[r.gap_category.value] = by_category.get(r.gap_category.value, 0) + 1
            by_priority[r.priority_level.value] = by_priority.get(r.priority_level.value, 0) + 1
            by_effort[r.remediation_effort.value] = by_effort.get(r.remediation_effort.value, 0) + 1
        high_priority_count = sum(
            1 for r in self._records if r.gap_score > self._gap_priority_threshold
        )
        scores = [r.gap_score for r in self._records]
        avg_gap_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_priority_gaps()
        top_high_priority = [o["gap_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_priority_count > 0:
            recs.append(
                f"{high_priority_count} gap(s) above priority threshold "
                f"({self._gap_priority_threshold})"
            )
        if self._records and avg_gap_score > self._gap_priority_threshold:
            recs.append(
                f"Avg gap score {avg_gap_score} above threshold ({self._gap_priority_threshold})"
            )
        if not recs:
            recs.append("Compliance gap prioritization posture is healthy")
        return GapPrioritizationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_priority_count=high_priority_count,
            avg_gap_score=avg_gap_score,
            by_category=by_category,
            by_priority=by_priority,
            by_effort=by_effort,
            top_high_priority=top_high_priority,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("compliance_gap_prioritizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.gap_category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "gap_priority_threshold": self._gap_priority_threshold,
            "category_distribution": category_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
