"""Dashboard Quality Scorer — evaluate dashboard effectiveness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DashboardGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    FAILING = "failing"


class QualityDimension(StrEnum):
    LOAD_TIME = "load_time"
    PANEL_COUNT = "panel_count"
    QUERY_EFFICIENCY = "query_efficiency"
    USAGE_FREQUENCY = "usage_frequency"
    STALENESS = "staleness"


class DashboardAction(StrEnum):
    NO_ACTION = "no_action"
    OPTIMIZE_QUERIES = "optimize_queries"
    REDUCE_PANELS = "reduce_panels"
    ARCHIVE = "archive"
    REBUILD = "rebuild"


# --- Models ---


class DashboardScoreRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dashboard_name: str = ""
    owner: str = ""
    grade: DashboardGrade = DashboardGrade.ACCEPTABLE
    score: float = 50.0
    load_time_ms: float = 0.0
    panel_count: int = 0
    query_count: int = 0
    usage_count_30d: int = 0
    last_modified_days_ago: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class DashboardIssue(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dashboard_name: str = ""
    dimension: QualityDimension = QualityDimension.LOAD_TIME
    action: DashboardAction = DashboardAction.NO_ACTION
    description: str = ""
    severity: str = "medium"
    created_at: float = Field(default_factory=time.time)


class DashboardQualityReport(BaseModel):
    total_dashboards: int = 0
    total_issues: int = 0
    avg_score: float = 0.0
    by_grade: dict[str, int] = Field(default_factory=dict)
    stale_count: int = 0
    poor_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DashboardQualityScorer:
    """Evaluate dashboard effectiveness."""

    def __init__(
        self,
        max_records: int = 200000,
        min_quality_score: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_quality_score = min_quality_score
        self._records: list[DashboardScoreRecord] = []
        self._issues: list[DashboardIssue] = []
        logger.info(
            "dashboard_quality.initialized",
            max_records=max_records,
            min_quality_score=min_quality_score,
        )

    # -- internal helpers ------------------------------------------------

    def _score_to_grade(self, score: float) -> DashboardGrade:
        if score >= 90:
            return DashboardGrade.EXCELLENT
        if score >= 75:
            return DashboardGrade.GOOD
        if score >= 60:
            return DashboardGrade.ACCEPTABLE
        if score >= 40:
            return DashboardGrade.POOR
        return DashboardGrade.FAILING

    def _calculate_score(self, record: DashboardScoreRecord) -> float:
        """Calculate composite quality score from dimensions."""
        score = 100.0
        # Load time penalty
        if record.load_time_ms > 5000:
            score -= 30
        elif record.load_time_ms > 3000:
            score -= 20
        elif record.load_time_ms > 1000:
            score -= 10
        # Panel count penalty
        if record.panel_count > 30:
            score -= 25
        elif record.panel_count > 20:
            score -= 15
        elif record.panel_count > 10:
            score -= 5
        # Usage frequency bonus/penalty
        if record.usage_count_30d == 0:
            score -= 20
        elif record.usage_count_30d < 5:
            score -= 10
        # Staleness penalty
        if record.last_modified_days_ago > 365:
            score -= 20
        elif record.last_modified_days_ago > 180:
            score -= 10
        return max(0.0, min(100.0, round(score, 2)))

    # -- record / get / list ---------------------------------------------

    def record_dashboard(
        self,
        dashboard_name: str,
        owner: str = "",
        load_time_ms: float = 0.0,
        panel_count: int = 0,
        query_count: int = 0,
        usage_count_30d: int = 0,
        last_modified_days_ago: int = 0,
        details: str = "",
    ) -> DashboardScoreRecord:
        record = DashboardScoreRecord(
            dashboard_name=dashboard_name,
            owner=owner,
            load_time_ms=load_time_ms,
            panel_count=panel_count,
            query_count=query_count,
            usage_count_30d=usage_count_30d,
            last_modified_days_ago=last_modified_days_ago,
            details=details,
        )
        score = self._calculate_score(record)
        record.score = score
        record.grade = self._score_to_grade(score)
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dashboard_quality.dashboard_recorded",
            record_id=record.id,
            dashboard_name=dashboard_name,
            score=score,
            grade=record.grade.value,
        )
        return record

    def get_dashboard(self, record_id: str) -> DashboardScoreRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_dashboards(
        self,
        dashboard_name: str | None = None,
        grade: DashboardGrade | None = None,
        limit: int = 50,
    ) -> list[DashboardScoreRecord]:
        results = list(self._records)
        if dashboard_name is not None:
            results = [r for r in results if r.dashboard_name == dashboard_name]
        if grade is not None:
            results = [r for r in results if r.grade == grade]
        return results[-limit:]

    def record_issue(
        self,
        dashboard_name: str,
        dimension: QualityDimension = QualityDimension.LOAD_TIME,
        action: DashboardAction = DashboardAction.NO_ACTION,
        description: str = "",
        severity: str = "medium",
    ) -> DashboardIssue:
        issue = DashboardIssue(
            dashboard_name=dashboard_name,
            dimension=dimension,
            action=action,
            description=description,
            severity=severity,
        )
        self._issues.append(issue)
        if len(self._issues) > self._max_records:
            self._issues = self._issues[-self._max_records :]
        logger.info(
            "dashboard_quality.issue_recorded",
            issue_id=issue.id,
            dashboard_name=dashboard_name,
            dimension=dimension.value,
        )
        return issue

    # -- domain operations -----------------------------------------------

    def score_dashboard(self, dashboard_name: str) -> dict[str, Any]:
        """Get quality score for a specific dashboard."""
        records = [r for r in self._records if r.dashboard_name == dashboard_name]
        if not records:
            return {"dashboard_name": dashboard_name, "score": 0.0, "grade": "failing"}
        latest = records[-1]
        return {
            "dashboard_name": dashboard_name,
            "score": latest.score,
            "grade": latest.grade.value,
            "load_time_ms": latest.load_time_ms,
            "panel_count": latest.panel_count,
            "usage_count_30d": latest.usage_count_30d,
        }

    def identify_stale_dashboards(self, stale_days: int = 180) -> list[dict[str, Any]]:
        """Find dashboards not modified in stale_days."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.last_modified_days_ago >= stale_days:
                results.append(
                    {
                        "dashboard_name": r.dashboard_name,
                        "last_modified_days_ago": r.last_modified_days_ago,
                        "usage_count_30d": r.usage_count_30d,
                        "grade": r.grade.value,
                    }
                )
        results.sort(key=lambda x: x["last_modified_days_ago"], reverse=True)
        return results

    def rank_dashboards_by_quality(self) -> list[dict[str, Any]]:
        """Rank dashboards by quality score."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "dashboard_name": r.dashboard_name,
                    "score": r.score,
                    "grade": r.grade.value,
                    "owner": r.owner,
                }
            )
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def analyze_query_efficiency(self) -> list[dict[str, Any]]:
        """Analyze query efficiency across dashboards."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            ratio = round(r.query_count / max(r.panel_count, 1), 2)
            efficiency = "good" if ratio <= 1.5 else "poor" if ratio > 3.0 else "fair"
            results.append(
                {
                    "dashboard_name": r.dashboard_name,
                    "panel_count": r.panel_count,
                    "query_count": r.query_count,
                    "query_per_panel_ratio": ratio,
                    "efficiency": efficiency,
                }
            )
        results.sort(key=lambda x: x["query_per_panel_ratio"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> DashboardQualityReport:
        by_grade: dict[str, int] = {}
        for r in self._records:
            by_grade[r.grade.value] = by_grade.get(r.grade.value, 0) + 1
        avg_score = (
            round(sum(r.score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        stale = len(self.identify_stale_dashboards())
        poor = sum(1 for r in self._records if r.score < self._min_quality_score)
        recs: list[str] = []
        if poor > 0:
            recs.append(f"{poor} dashboard(s) below quality threshold of {self._min_quality_score}")
        if stale > 0:
            recs.append(f"{stale} stale dashboard(s) should be reviewed")
        if not recs:
            recs.append("Dashboard quality meets standards")
        return DashboardQualityReport(
            total_dashboards=len(self._records),
            total_issues=len(self._issues),
            avg_score=avg_score,
            by_grade=by_grade,
            stale_count=stale,
            poor_count=poor,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._issues.clear()
        logger.info("dashboard_quality.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        grade_dist: dict[str, int] = {}
        for r in self._records:
            key = r.grade.value
            grade_dist[key] = grade_dist.get(key, 0) + 1
        return {
            "total_dashboards": len(self._records),
            "total_issues": len(self._issues),
            "min_quality_score": self._min_quality_score,
            "grade_distribution": grade_dist,
            "unique_dashboards": len({r.dashboard_name for r in self._records}),
        }
