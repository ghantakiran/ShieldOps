"""Automation Gap Identifier — identify manual processes that should be automated."""

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
    MANUAL_PROCESS = "manual_process"
    REPETITIVE_TASK = "repetitive_task"
    ERROR_PRONE = "error_prone"
    TIME_CONSUMING = "time_consuming"
    COMPLIANCE_REQUIRED = "compliance_required"


class AutomationFeasibility(StrEnum):
    EASY = "easy"
    MODERATE = "moderate"
    DIFFICULT = "difficult"
    REQUIRES_RESEARCH = "requires_research"
    NOT_FEASIBLE = "not_feasible"


class GapImpact(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


# --- Models ---


class AutomationGapRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_name: str = ""
    category: GapCategory = GapCategory.MANUAL_PROCESS
    feasibility: AutomationFeasibility = AutomationFeasibility.MODERATE
    impact: GapImpact = GapImpact.MEDIUM
    hours_per_week: float = 0.0
    roi_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class AutomationCandidate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    candidate_name: str = ""
    gap_name: str = ""
    feasibility: AutomationFeasibility = AutomationFeasibility.MODERATE
    estimated_savings_hours: float = 0.0
    implementation_effort_days: float = 0.0
    created_at: float = Field(default_factory=time.time)


class AutomationGapReport(BaseModel):
    total_gaps: int = 0
    total_candidates: int = 0
    avg_roi_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_feasibility: dict[str, int] = Field(default_factory=dict)
    quick_win_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutomationGapIdentifier:
    """Identify manual processes that should be automated."""

    def __init__(
        self,
        max_records: int = 200000,
        min_roi_score: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._min_roi_score = min_roi_score
        self._records: list[AutomationGapRecord] = []
        self._candidates: list[AutomationCandidate] = []
        logger.info(
            "automation_gap.initialized",
            max_records=max_records,
            min_roi_score=min_roi_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_gap(
        self,
        gap_name: str,
        category: GapCategory = GapCategory.MANUAL_PROCESS,
        feasibility: AutomationFeasibility = AutomationFeasibility.MODERATE,
        impact: GapImpact = GapImpact.MEDIUM,
        hours_per_week: float = 0.0,
        roi_score: float = 0.0,
        details: str = "",
    ) -> AutomationGapRecord:
        record = AutomationGapRecord(
            gap_name=gap_name,
            category=category,
            feasibility=feasibility,
            impact=impact,
            hours_per_week=hours_per_week,
            roi_score=roi_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "automation_gap.gap_recorded",
            record_id=record.id,
            gap_name=gap_name,
            category=category.value,
        )
        return record

    def get_gap(self, record_id: str) -> AutomationGapRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_gaps(
        self,
        category: GapCategory | None = None,
        feasibility: AutomationFeasibility | None = None,
        limit: int = 50,
    ) -> list[AutomationGapRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.category == category]
        if feasibility is not None:
            results = [r for r in results if r.feasibility == feasibility]
        return results[-limit:]

    def add_candidate(
        self,
        candidate_name: str,
        gap_name: str = "",
        feasibility: AutomationFeasibility = AutomationFeasibility.MODERATE,
        estimated_savings_hours: float = 0.0,
        implementation_effort_days: float = 0.0,
    ) -> AutomationCandidate:
        candidate = AutomationCandidate(
            candidate_name=candidate_name,
            gap_name=gap_name,
            feasibility=feasibility,
            estimated_savings_hours=estimated_savings_hours,
            implementation_effort_days=implementation_effort_days,
        )
        self._candidates.append(candidate)
        if len(self._candidates) > self._max_records:
            self._candidates = self._candidates[-self._max_records :]
        logger.info(
            "automation_gap.candidate_added",
            candidate_name=candidate_name,
            gap_name=gap_name,
        )
        return candidate

    # -- domain operations -----------------------------------------------

    def analyze_gap_category(self, category: str) -> dict[str, Any]:
        """Analyze gaps for a specific category."""
        records = [r for r in self._records if r.category.value == category]
        if not records:
            return {"category": category, "status": "no_data"}
        return {
            "category": category,
            "total_gaps": len(records),
            "avg_roi_score": round(sum(r.roi_score for r in records) / len(records), 2),
            "total_hours_per_week": round(sum(r.hours_per_week for r in records), 2),
        }

    def identify_quick_wins(self) -> list[dict[str, Any]]:
        """Find gaps that are easy to automate with high ROI."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.feasibility == AutomationFeasibility.EASY and r.roi_score >= self._min_roi_score:
                results.append(
                    {
                        "gap_name": r.gap_name,
                        "category": r.category.value,
                        "roi_score": r.roi_score,
                        "hours_per_week": r.hours_per_week,
                    }
                )
        results.sort(key=lambda x: x["roi_score"], reverse=True)
        return results

    def rank_by_roi(self) -> list[dict[str, Any]]:
        """Rank gaps by ROI score descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "gap_name": r.gap_name,
                    "roi_score": r.roi_score,
                    "category": r.category.value,
                    "feasibility": r.feasibility.value,
                }
            )
        results.sort(key=lambda x: x["roi_score"], reverse=True)
        return results

    def detect_repetitive_patterns(self) -> list[dict[str, Any]]:
        """Detect repetitive task patterns."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.category == GapCategory.REPETITIVE_TASK:
                results.append(
                    {
                        "gap_name": r.gap_name,
                        "hours_per_week": r.hours_per_week,
                        "roi_score": r.roi_score,
                        "feasibility": r.feasibility.value,
                    }
                )
        results.sort(key=lambda x: x["hours_per_week"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> AutomationGapReport:
        by_category: dict[str, int] = {}
        by_feasibility: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_feasibility[r.feasibility.value] = by_feasibility.get(r.feasibility.value, 0) + 1
        avg_roi = (
            round(
                sum(r.roi_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        quick_wins = sum(
            1
            for r in self._records
            if r.feasibility == AutomationFeasibility.EASY and r.roi_score >= self._min_roi_score
        )
        recs: list[str] = []
        if quick_wins > 0:
            recs.append(f"{quick_wins} quick-win automation opportunity(ies)")
        high_impact = sum(
            1 for r in self._records if r.impact in (GapImpact.CRITICAL, GapImpact.HIGH)
        )
        if high_impact > 0:
            recs.append(f"{high_impact} high-impact gap(s) need attention")
        if not recs:
            recs.append("No significant automation gaps identified")
        return AutomationGapReport(
            total_gaps=len(self._records),
            total_candidates=len(self._candidates),
            avg_roi_score=avg_roi,
            by_category=by_category,
            by_feasibility=by_feasibility,
            quick_win_count=quick_wins,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._candidates.clear()
        logger.info("automation_gap.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_gaps": len(self._records),
            "total_candidates": len(self._candidates),
            "min_roi_score": self._min_roi_score,
            "category_distribution": cat_dist,
            "unique_gaps": len({r.gap_name for r in self._records}),
        }
