"""Dashboard Effectiveness Scorer — score dashboards, track usage, and identify ineffective ones."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DashboardType(StrEnum):
    OPERATIONAL = "operational"
    EXECUTIVE = "executive"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    PERFORMANCE = "performance"


class UsageFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    RARELY = "rarely"
    NEVER = "never"


class DashboardIssue(StrEnum):
    STALE_DATA = "stale_data"
    TOO_COMPLEX = "too_complex"
    MISSING_CONTEXT = "missing_context"
    WRONG_AUDIENCE = "wrong_audience"
    NO_ACTIONABILITY = "no_actionability"


# --- Models ---


class DashboardRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dashboard_name: str = ""
    dashboard_type: DashboardType = DashboardType.OPERATIONAL
    usage_frequency: UsageFrequency = UsageFrequency.WEEKLY
    dashboard_issue: DashboardIssue = DashboardIssue.STALE_DATA
    effectiveness_score: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class UsageMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    dashboard_type: DashboardType = DashboardType.OPERATIONAL
    view_count: int = 0
    avg_session_duration: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DashboardEffectivenessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    ineffective_dashboards: int = 0
    avg_effectiveness_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_frequency: dict[str, int] = Field(default_factory=dict)
    by_issue: dict[str, int] = Field(default_factory=dict)
    top_items: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DashboardEffectivenessScorer:
    """Score dashboards, track usage metrics, and identify ineffective dashboards."""

    def __init__(
        self,
        max_records: int = 200000,
        min_effectiveness_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_effectiveness_score = min_effectiveness_score
        self._records: list[DashboardRecord] = []
        self._metrics: list[UsageMetric] = []
        logger.info(
            "dashboard_effectiveness.initialized",
            max_records=max_records,
            min_effectiveness_score=min_effectiveness_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_dashboard(
        self,
        dashboard_name: str,
        dashboard_type: DashboardType = DashboardType.OPERATIONAL,
        usage_frequency: UsageFrequency = UsageFrequency.WEEKLY,
        dashboard_issue: DashboardIssue = DashboardIssue.STALE_DATA,
        effectiveness_score: float = 0.0,
        team: str = "",
    ) -> DashboardRecord:
        record = DashboardRecord(
            dashboard_name=dashboard_name,
            dashboard_type=dashboard_type,
            usage_frequency=usage_frequency,
            dashboard_issue=dashboard_issue,
            effectiveness_score=effectiveness_score,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dashboard_effectiveness.recorded",
            record_id=record.id,
            dashboard_name=dashboard_name,
            dashboard_type=dashboard_type.value,
            usage_frequency=usage_frequency.value,
        )
        return record

    def get_dashboard(self, record_id: str) -> DashboardRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_dashboards(
        self,
        dashboard_type: DashboardType | None = None,
        frequency: UsageFrequency | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DashboardRecord]:
        results = list(self._records)
        if dashboard_type is not None:
            results = [r for r in results if r.dashboard_type == dashboard_type]
        if frequency is not None:
            results = [r for r in results if r.usage_frequency == frequency]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        metric_name: str,
        dashboard_type: DashboardType = DashboardType.OPERATIONAL,
        view_count: int = 0,
        avg_session_duration: float = 0.0,
        description: str = "",
    ) -> UsageMetric:
        metric = UsageMetric(
            metric_name=metric_name,
            dashboard_type=dashboard_type,
            view_count=view_count,
            avg_session_duration=avg_session_duration,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "dashboard_effectiveness.metric_added",
            metric_name=metric_name,
            dashboard_type=dashboard_type.value,
            view_count=view_count,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_dashboard_usage(self) -> dict[str, Any]:
        """Group by type; return count and avg effectiveness score per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.dashboard_type.value
            type_data.setdefault(key, []).append(r.effectiveness_score)
        result: dict[str, Any] = {}
        for dtype, scores in type_data.items():
            result[dtype] = {
                "count": len(scores),
                "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_ineffective_dashboards(self) -> list[dict[str, Any]]:
        """Return records where frequency is RARELY or NEVER."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.usage_frequency in (
                UsageFrequency.RARELY,
                UsageFrequency.NEVER,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "dashboard_name": r.dashboard_name,
                        "usage_frequency": r.usage_frequency.value,
                        "effectiveness_score": r.effectiveness_score,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_effectiveness(self) -> list[dict[str, Any]]:
        """Group by team, avg effectiveness score, sort descending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.effectiveness_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team": team,
                    "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
                    "count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_effectiveness_score"], reverse=True)
        return results

    def detect_usage_trends(self) -> dict[str, Any]:
        """Split-half on avg_session_duration; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [m.avg_session_duration for m in self._metrics]
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

    def generate_report(self) -> DashboardEffectivenessReport:
        by_type: dict[str, int] = {}
        by_frequency: dict[str, int] = {}
        by_issue: dict[str, int] = {}
        for r in self._records:
            by_type[r.dashboard_type.value] = by_type.get(r.dashboard_type.value, 0) + 1
            by_frequency[r.usage_frequency.value] = by_frequency.get(r.usage_frequency.value, 0) + 1
            by_issue[r.dashboard_issue.value] = by_issue.get(r.dashboard_issue.value, 0) + 1
        ineffective_count = sum(
            1
            for r in self._records
            if r.usage_frequency in (UsageFrequency.RARELY, UsageFrequency.NEVER)
        )
        avg_score = (
            round(sum(r.effectiveness_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_effectiveness()
        top_items = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        if self._records and avg_score < self._min_effectiveness_score:
            recs.append(
                f"Avg effectiveness {avg_score} below threshold ({self._min_effectiveness_score})"
            )
        if ineffective_count > 0:
            recs.append(f"{ineffective_count} ineffective dashboard(s) detected — review usage")
        if not recs:
            recs.append("Dashboard effectiveness is within acceptable limits")
        return DashboardEffectivenessReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            ineffective_dashboards=ineffective_count,
            avg_effectiveness_score=avg_score,
            by_type=by_type,
            by_frequency=by_frequency,
            by_issue=by_issue,
            top_items=top_items,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("dashboard_effectiveness.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dashboard_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_effectiveness_score": self._min_effectiveness_score,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_dashboards": len({r.dashboard_name for r in self._records}),
        }
