"""Security Metrics Dashboard — track and visualize security metrics."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MetricCategory(StrEnum):
    VULNERABILITY = "vulnerability"
    INCIDENT = "incident"
    COMPLIANCE = "compliance"
    ACCESS = "access"
    THREAT = "threat"


class MetricTimeframe(StrEnum):
    REALTIME = "realtime"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class MetricStatus(StrEnum):
    ON_TARGET = "on_target"
    AT_RISK = "at_risk"
    OFF_TARGET = "off_target"
    IMPROVING = "improving"
    DEGRADING = "degrading"


# --- Models ---


class MetricRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    metric_category: MetricCategory = MetricCategory.VULNERABILITY
    metric_timeframe: MetricTimeframe = MetricTimeframe.REALTIME
    metric_status: MetricStatus = MetricStatus.ON_TARGET
    metric_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MetricAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    metric_category: MetricCategory = MetricCategory.VULNERABILITY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SecurityMetricsReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_metric_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_timeframe: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityMetricsDashboard:
    """Track security metrics across categories, timeframes, identify metric gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[MetricRecord] = []
        self._analyses: list[MetricAnalysis] = []
        logger.info(
            "security_metrics_dashboard.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_metric(
        self,
        metric_name: str,
        metric_category: MetricCategory = MetricCategory.VULNERABILITY,
        metric_timeframe: MetricTimeframe = MetricTimeframe.REALTIME,
        metric_status: MetricStatus = MetricStatus.ON_TARGET,
        metric_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MetricRecord:
        record = MetricRecord(
            metric_name=metric_name,
            metric_category=metric_category,
            metric_timeframe=metric_timeframe,
            metric_status=metric_status,
            metric_score=metric_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_metrics_dashboard.metric_recorded",
            record_id=record.id,
            metric_name=metric_name,
            metric_category=metric_category.value,
            metric_timeframe=metric_timeframe.value,
        )
        return record

    def get_record(self, record_id: str) -> MetricRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        metric_category: MetricCategory | None = None,
        metric_status: MetricStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MetricRecord]:
        results = list(self._records)
        if metric_category is not None:
            results = [r for r in results if r.metric_category == metric_category]
        if metric_status is not None:
            results = [r for r in results if r.metric_status == metric_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        metric_name: str,
        metric_category: MetricCategory = MetricCategory.VULNERABILITY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MetricAnalysis:
        analysis = MetricAnalysis(
            metric_name=metric_name,
            metric_category=metric_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_metrics_dashboard.analysis_added",
            metric_name=metric_name,
            metric_category=metric_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by metric_category; return count and avg metric_score."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.metric_category.value
            cat_data.setdefault(key, []).append(r.metric_score)
        result: dict[str, Any] = {}
        for category, scores in cat_data.items():
            result[category] = {
                "count": len(scores),
                "avg_metric_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where metric_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.metric_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "metric_name": r.metric_name,
                        "metric_category": r.metric_category.value,
                        "metric_score": r.metric_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["metric_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg metric_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.metric_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_metric_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_metric_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
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

    def generate_report(self) -> SecurityMetricsReport:
        by_category: dict[str, int] = {}
        by_timeframe: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_category[r.metric_category.value] = by_category.get(r.metric_category.value, 0) + 1
            by_timeframe[r.metric_timeframe.value] = (
                by_timeframe.get(r.metric_timeframe.value, 0) + 1
            )
            by_status[r.metric_status.value] = by_status.get(r.metric_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.metric_score < self._threshold)
        scores = [r.metric_score for r in self._records]
        avg_metric_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["metric_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} metric(s) below score threshold ({self._threshold})")
        if self._records and avg_metric_score < self._threshold:
            recs.append(f"Avg metric score {avg_metric_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Security metrics are healthy")
        return SecurityMetricsReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_metric_score=avg_metric_score,
            by_category=by_category,
            by_timeframe=by_timeframe,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_metrics_dashboard.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.metric_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
