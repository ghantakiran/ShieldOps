"""Analyst Efficiency Tracker — measure and optimize SOC analyst performance metrics."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EfficiencyMetric(StrEnum):
    MEAN_TIME_TO_TRIAGE = "mean_time_to_triage"
    MEAN_TIME_TO_RESOLVE = "mean_time_to_resolve"
    ALERTS_PER_ANALYST = "alerts_per_analyst"
    FALSE_POSITIVE_RATE = "false_positive_rate"
    ESCALATION_RATE = "escalation_rate"


class AnalystTier(StrEnum):
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"
    LEAD = "lead"
    MANAGER = "manager"


class PerformanceBand(StrEnum):
    EXCEPTIONAL = "exceptional"
    ABOVE_AVERAGE = "above_average"
    AVERAGE = "average"
    BELOW_AVERAGE = "below_average"
    NEEDS_IMPROVEMENT = "needs_improvement"


# --- Models ---


class EfficiencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    analyst_name: str = ""
    efficiency_metric: EfficiencyMetric = EfficiencyMetric.MEAN_TIME_TO_TRIAGE
    analyst_tier: AnalystTier = AnalystTier.TIER_1
    performance_band: PerformanceBand = PerformanceBand.AVERAGE
    efficiency_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EfficiencyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    analyst_name: str = ""
    efficiency_metric: EfficiencyMetric = EfficiencyMetric.MEAN_TIME_TO_TRIAGE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EfficiencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_metric: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_band: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AnalystEfficiencyTracker:
    """Measure and optimize SOC analyst performance metrics across tiers."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[EfficiencyRecord] = []
        self._analyses: list[EfficiencyAnalysis] = []
        logger.info(
            "analyst_efficiency_tracker.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_efficiency(
        self,
        analyst_name: str,
        efficiency_metric: EfficiencyMetric = EfficiencyMetric.MEAN_TIME_TO_TRIAGE,
        analyst_tier: AnalystTier = AnalystTier.TIER_1,
        performance_band: PerformanceBand = PerformanceBand.AVERAGE,
        efficiency_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EfficiencyRecord:
        record = EfficiencyRecord(
            analyst_name=analyst_name,
            efficiency_metric=efficiency_metric,
            analyst_tier=analyst_tier,
            performance_band=performance_band,
            efficiency_score=efficiency_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "analyst_efficiency_tracker.efficiency_recorded",
            record_id=record.id,
            analyst_name=analyst_name,
            efficiency_metric=efficiency_metric.value,
            analyst_tier=analyst_tier.value,
        )
        return record

    def get_record(self, record_id: str) -> EfficiencyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        efficiency_metric: EfficiencyMetric | None = None,
        analyst_tier: AnalystTier | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EfficiencyRecord]:
        results = list(self._records)
        if efficiency_metric is not None:
            results = [r for r in results if r.efficiency_metric == efficiency_metric]
        if analyst_tier is not None:
            results = [r for r in results if r.analyst_tier == analyst_tier]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        analyst_name: str,
        efficiency_metric: EfficiencyMetric = EfficiencyMetric.MEAN_TIME_TO_TRIAGE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> EfficiencyAnalysis:
        analysis = EfficiencyAnalysis(
            analyst_name=analyst_name,
            efficiency_metric=efficiency_metric,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "analyst_efficiency_tracker.analysis_added",
            analyst_name=analyst_name,
            efficiency_metric=efficiency_metric.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by efficiency_metric; return count and avg efficiency_score."""
        metric_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.efficiency_metric.value
            metric_data.setdefault(key, []).append(r.efficiency_score)
        result: dict[str, Any] = {}
        for metric, scores in metric_data.items():
            result[metric] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where efficiency_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.efficiency_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "analyst_name": r.analyst_name,
                        "efficiency_metric": r.efficiency_metric.value,
                        "efficiency_score": r.efficiency_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["efficiency_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg efficiency_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.efficiency_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
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

    def generate_report(self) -> EfficiencyReport:
        by_metric: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        by_band: dict[str, int] = {}
        for r in self._records:
            by_metric[r.efficiency_metric.value] = by_metric.get(r.efficiency_metric.value, 0) + 1
            by_tier[r.analyst_tier.value] = by_tier.get(r.analyst_tier.value, 0) + 1
            by_band[r.performance_band.value] = by_band.get(r.performance_band.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.efficiency_score < self._threshold)
        scores = [r.efficiency_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["analyst_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} analyst(s) below efficiency threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg efficiency score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Analyst efficiency is healthy")
        return EfficiencyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_metric=by_metric,
            by_tier=by_tier,
            by_band=by_band,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("analyst_efficiency_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        metric_dist: dict[str, int] = {}
        for r in self._records:
            key = r.efficiency_metric.value
            metric_dist[key] = metric_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "metric_distribution": metric_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
