"""Log Quality Analyzer — assess log structure, completeness, and consistency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LogQualityDimension(StrEnum):
    STRUCTURE = "structure"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    SEARCHABILITY = "searchability"
    CONTEXT = "context"


class LogQualityLevel(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNUSABLE = "unusable"


class LogIssueType(StrEnum):
    UNSTRUCTURED = "unstructured"
    MISSING_FIELDS = "missing_fields"
    INCONSISTENT_FORMAT = "inconsistent_format"
    HIGH_NOISE = "high_noise"
    PII_EXPOSURE = "pii_exposure"


# --- Models ---


class LogQualityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    log_quality_dimension: LogQualityDimension = LogQualityDimension.STRUCTURE
    log_quality_level: LogQualityLevel = LogQualityLevel.ACCEPTABLE
    log_issue_type: LogIssueType = LogIssueType.UNSTRUCTURED
    quality_score: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class LogIssue(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    issue_name: str = ""
    log_quality_dimension: LogQualityDimension = LogQualityDimension.STRUCTURE
    quality_threshold: float = 0.0
    avg_quality_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LogQualityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_issues: int = 0
    poor_quality_logs: int = 0
    avg_quality_score: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_issue_type: dict[str, int] = Field(default_factory=dict)
    top_items: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class LogQualityAnalyzer:
    """Assess log structure, completeness, and consistency to improve observability."""

    def __init__(
        self,
        max_records: int = 200000,
        min_log_quality_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_log_quality_pct = min_log_quality_pct
        self._records: list[LogQualityRecord] = []
        self._issues: list[LogIssue] = []
        logger.info(
            "log_quality.initialized",
            max_records=max_records,
            min_log_quality_pct=min_log_quality_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_quality(
        self,
        service_id: str,
        log_quality_dimension: LogQualityDimension = LogQualityDimension.STRUCTURE,
        log_quality_level: LogQualityLevel = LogQualityLevel.ACCEPTABLE,
        log_issue_type: LogIssueType = LogIssueType.UNSTRUCTURED,
        quality_score: float = 0.0,
        team: str = "",
    ) -> LogQualityRecord:
        record = LogQualityRecord(
            service_id=service_id,
            log_quality_dimension=log_quality_dimension,
            log_quality_level=log_quality_level,
            log_issue_type=log_issue_type,
            quality_score=quality_score,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "log_quality.recorded",
            record_id=record.id,
            service_id=service_id,
            log_quality_dimension=log_quality_dimension.value,
            log_quality_level=log_quality_level.value,
        )
        return record

    def get_quality(self, record_id: str) -> LogQualityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_qualities(
        self,
        dimension: LogQualityDimension | None = None,
        level: LogQualityLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[LogQualityRecord]:
        results = list(self._records)
        if dimension is not None:
            results = [r for r in results if r.log_quality_dimension == dimension]
        if level is not None:
            results = [r for r in results if r.log_quality_level == level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_issue(
        self,
        issue_name: str,
        log_quality_dimension: LogQualityDimension = LogQualityDimension.STRUCTURE,
        quality_threshold: float = 0.0,
        avg_quality_score: float = 0.0,
        description: str = "",
    ) -> LogIssue:
        issue = LogIssue(
            issue_name=issue_name,
            log_quality_dimension=log_quality_dimension,
            quality_threshold=quality_threshold,
            avg_quality_score=avg_quality_score,
            description=description,
        )
        self._issues.append(issue)
        if len(self._issues) > self._max_records:
            self._issues = self._issues[-self._max_records :]
        logger.info(
            "log_quality.issue_added",
            issue_name=issue_name,
            log_quality_dimension=log_quality_dimension.value,
            quality_threshold=quality_threshold,
        )
        return issue

    # -- domain operations --------------------------------------------------

    def analyze_log_quality(self) -> dict[str, Any]:
        """Group by dimension; return count and avg quality score per dimension."""
        dimension_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.log_quality_dimension.value
            dimension_data.setdefault(key, []).append(r.quality_score)
        result: dict[str, Any] = {}
        for dimension, scores in dimension_data.items():
            result[dimension] = {
                "count": len(scores),
                "avg_quality_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_poor_quality_logs(self) -> list[dict[str, Any]]:
        """Return records where level is POOR or UNUSABLE."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.log_quality_level in (
                LogQualityLevel.POOR,
                LogQualityLevel.UNUSABLE,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "service_id": r.service_id,
                        "log_quality_level": r.log_quality_level.value,
                        "quality_score": r.quality_score,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_quality_score(self) -> list[dict[str, Any]]:
        """Group by team, avg quality score, sort descending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.quality_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team": team,
                    "avg_quality_score": round(sum(scores) / len(scores), 2),
                    "count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_quality_score"], reverse=True)
        return results

    def detect_quality_regression(self) -> dict[str, Any]:
        """Split-half on avg_quality_score; delta threshold 5.0."""
        if len(self._issues) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [i.avg_quality_score for i in self._issues]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> LogQualityReport:
        by_dimension: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_issue_type: dict[str, int] = {}
        for r in self._records:
            by_dimension[r.log_quality_dimension.value] = (
                by_dimension.get(r.log_quality_dimension.value, 0) + 1
            )
            by_level[r.log_quality_level.value] = by_level.get(r.log_quality_level.value, 0) + 1
            by_issue_type[r.log_issue_type.value] = by_issue_type.get(r.log_issue_type.value, 0) + 1
        poor_count = sum(
            1
            for r in self._records
            if r.log_quality_level in (LogQualityLevel.POOR, LogQualityLevel.UNUSABLE)
        )
        avg_score = (
            round(sum(r.quality_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_quality_score()
        top_items = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        if avg_score < self._min_log_quality_pct:
            recs.append(
                f"Avg quality score {avg_score}% is below threshold ({self._min_log_quality_pct}%)"
            )
        if poor_count > 0:
            recs.append(f"{poor_count} poor quality log(s) detected — review quality")
        if not recs:
            recs.append("Log quality is within acceptable limits")
        return LogQualityReport(
            total_records=len(self._records),
            total_issues=len(self._issues),
            poor_quality_logs=poor_count,
            avg_quality_score=avg_score,
            by_dimension=by_dimension,
            by_level=by_level,
            by_issue_type=by_issue_type,
            top_items=top_items,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._issues.clear()
        logger.info("log_quality.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dimension_dist: dict[str, int] = {}
        for r in self._records:
            key = r.log_quality_dimension.value
            dimension_dist[key] = dimension_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_issues": len(self._issues),
            "min_log_quality_pct": self._min_log_quality_pct,
            "dimension_distribution": dimension_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service_id for r in self._records}),
        }
