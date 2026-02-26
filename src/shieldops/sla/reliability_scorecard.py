"""Platform Reliability Scorecard — composite reliability scoring across services."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ScoreCategory(StrEnum):
    SLO_COMPLIANCE = "slo_compliance"
    INCIDENT_FREQUENCY = "incident_frequency"
    CHANGE_SUCCESS = "change_success"
    MONITORING_COVERAGE = "monitoring_coverage"
    RECOVERY_SPEED = "recovery_speed"


class ScoreGrade(StrEnum):
    A_EXCELLENT = "a_excellent"
    B_GOOD = "b_good"
    C_ADEQUATE = "c_adequate"
    D_POOR = "d_poor"
    F_FAILING = "f_failing"


class ScoreTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    VOLATILE = "volatile"
    NEW = "new"


# --- Models ---


class ScorecardRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    category: ScoreCategory = ScoreCategory.SLO_COMPLIANCE
    grade: ScoreGrade = ScoreGrade.C_ADEQUATE
    trend: ScoreTrend = ScoreTrend.NEW
    overall_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CategoryScore(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category_name: str = ""
    category: ScoreCategory = ScoreCategory.SLO_COMPLIANCE
    grade: ScoreGrade = ScoreGrade.C_ADEQUATE
    score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReliabilityScorecardReport(BaseModel):
    total_scorecards: int = 0
    total_categories: int = 0
    avg_score_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    low_score_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PlatformReliabilityScorecard:
    """Composite reliability scoring across services and categories."""

    def __init__(
        self,
        max_records: int = 200000,
        min_grade_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_grade_score = min_grade_score
        self._records: list[ScorecardRecord] = []
        self._categories: list[CategoryScore] = []
        logger.info(
            "reliability_scorecard.initialized",
            max_records=max_records,
            min_grade_score=min_grade_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_scorecard(
        self,
        service_name: str,
        category: ScoreCategory = ScoreCategory.SLO_COMPLIANCE,
        grade: ScoreGrade = ScoreGrade.C_ADEQUATE,
        trend: ScoreTrend = ScoreTrend.NEW,
        overall_score: float = 0.0,
        details: str = "",
    ) -> ScorecardRecord:
        record = ScorecardRecord(
            service_name=service_name,
            category=category,
            grade=grade,
            trend=trend,
            overall_score=overall_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "reliability_scorecard.scorecard_recorded",
            record_id=record.id,
            service_name=service_name,
            category=category.value,
            grade=grade.value,
        )
        return record

    def get_scorecard(self, record_id: str) -> ScorecardRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_scorecards(
        self,
        service_name: str | None = None,
        category: ScoreCategory | None = None,
        limit: int = 50,
    ) -> list[ScorecardRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if category is not None:
            results = [r for r in results if r.category == category]
        return results[-limit:]

    def add_category_score(
        self,
        category_name: str,
        category: ScoreCategory = ScoreCategory.SLO_COMPLIANCE,
        grade: ScoreGrade = ScoreGrade.C_ADEQUATE,
        score: float = 0.0,
        description: str = "",
    ) -> CategoryScore:
        cat_score = CategoryScore(
            category_name=category_name,
            category=category,
            grade=grade,
            score=score,
            description=description,
        )
        self._categories.append(cat_score)
        if len(self._categories) > self._max_records:
            self._categories = self._categories[-self._max_records :]
        logger.info(
            "reliability_scorecard.category_score_added",
            category_score_id=cat_score.id,
            category_name=category_name,
            category=category.value,
        )
        return cat_score

    # -- domain operations -----------------------------------------------

    def analyze_service_reliability(self, service_name: str) -> dict[str, Any]:
        """Analyze reliability for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_score = round(sum(r.overall_score for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "total": len(records),
            "avg_score": avg_score,
            "meets_threshold": avg_score >= self._min_grade_score,
        }

    def identify_low_scoring_services(self) -> list[dict[str, Any]]:
        """Find services with >1 D_POOR or F_FAILING grades, sorted desc."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.grade in (ScoreGrade.D_POOR, ScoreGrade.F_FAILING):
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 1:
                results.append({"service_name": svc, "low_grade_count": count})
        results.sort(key=lambda x: x["low_grade_count"], reverse=True)
        return results

    def rank_by_overall_score(self) -> list[dict[str, Any]]:
        """Average overall score per service, sorted desc."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service_name, []).append(r.overall_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append({"service_name": svc, "avg_overall_score": avg})
        results.sort(key=lambda x: x["avg_overall_score"], reverse=True)
        return results

    def detect_score_trends(self) -> list[dict[str, Any]]:
        """Detect services with >3 scorecard records (trending data)."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append({"service_name": svc, "scorecard_count": count})
        results.sort(key=lambda x: x["scorecard_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ReliabilityScorecardReport:
        by_category: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_grade[r.grade.value] = by_grade.get(r.grade.value, 0) + 1
        avg_score = (
            round(
                sum(r.overall_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        low_count = sum(1 for r in self._records if r.overall_score < self._min_grade_score)
        recs: list[str] = []
        failing = sum(1 for r in self._records if r.grade == ScoreGrade.F_FAILING)
        if failing > 0:
            recs.append(f"{failing} failing scorecard(s) require immediate attention")
        poor = sum(1 for r in self._records if r.grade == ScoreGrade.D_POOR)
        if poor > 0:
            recs.append(f"{poor} poor-grade scorecard(s) need improvement")
        if not recs:
            recs.append("Platform reliability scores are healthy")
        return ReliabilityScorecardReport(
            total_scorecards=len(self._records),
            total_categories=len(self._categories),
            avg_score_pct=avg_score,
            by_category=by_category,
            by_grade=by_grade,
            low_score_count=low_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._categories.clear()
        logger.info("reliability_scorecard.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_scorecards": len(self._records),
            "total_categories": len(self._categories),
            "min_grade_score": self._min_grade_score,
            "category_distribution": category_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
