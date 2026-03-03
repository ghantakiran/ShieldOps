"""SOC Performance Optimizer — optimize SOC performance across metrics and workflows."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PerformanceMetric(StrEnum):
    MTTD = "mttd"
    MTTR = "mttr"
    FALSE_POSITIVE_RATE = "false_positive_rate"
    ANALYST_UTILIZATION = "analyst_utilization"
    COVERAGE = "coverage"


class OptimizationArea(StrEnum):
    WORKFLOW = "workflow"
    TOOLING = "tooling"
    TRAINING = "training"
    AUTOMATION = "automation"
    STAFFING = "staffing"


class PerformanceTier(StrEnum):
    ELITE = "elite"
    HIGH = "high"
    AVERAGE = "average"
    BELOW_AVERAGE = "below_average"
    CRITICAL = "critical"


# --- Models ---


class SOCPerformanceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    performance_id: str = ""
    performance_metric: PerformanceMetric = PerformanceMetric.MTTD
    optimization_area: OptimizationArea = OptimizationArea.WORKFLOW
    performance_tier: PerformanceTier = PerformanceTier.AVERAGE
    performance_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SOCPerformanceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    performance_id: str = ""
    performance_metric: PerformanceMetric = PerformanceMetric.MTTD
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SOCPerformanceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_performance_score: float = 0.0
    by_metric: dict[str, int] = Field(default_factory=dict)
    by_area: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SOCPerformanceOptimizer:
    """Optimize SOC performance across metrics, workflows, and staffing."""

    def __init__(
        self,
        max_records: int = 200000,
        performance_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._performance_threshold = performance_threshold
        self._records: list[SOCPerformanceRecord] = []
        self._analyses: list[SOCPerformanceAnalysis] = []
        logger.info(
            "soc_performance_optimizer.initialized",
            max_records=max_records,
            performance_threshold=performance_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_performance(
        self,
        performance_id: str,
        performance_metric: PerformanceMetric = PerformanceMetric.MTTD,
        optimization_area: OptimizationArea = OptimizationArea.WORKFLOW,
        performance_tier: PerformanceTier = PerformanceTier.AVERAGE,
        performance_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SOCPerformanceRecord:
        record = SOCPerformanceRecord(
            performance_id=performance_id,
            performance_metric=performance_metric,
            optimization_area=optimization_area,
            performance_tier=performance_tier,
            performance_score=performance_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "soc_performance_optimizer.performance_recorded",
            record_id=record.id,
            performance_id=performance_id,
            performance_metric=performance_metric.value,
            optimization_area=optimization_area.value,
        )
        return record

    def get_performance(self, record_id: str) -> SOCPerformanceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_performances(
        self,
        performance_metric: PerformanceMetric | None = None,
        optimization_area: OptimizationArea | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SOCPerformanceRecord]:
        results = list(self._records)
        if performance_metric is not None:
            results = [r for r in results if r.performance_metric == performance_metric]
        if optimization_area is not None:
            results = [r for r in results if r.optimization_area == optimization_area]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        performance_id: str,
        performance_metric: PerformanceMetric = PerformanceMetric.MTTD,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SOCPerformanceAnalysis:
        analysis = SOCPerformanceAnalysis(
            performance_id=performance_id,
            performance_metric=performance_metric,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "soc_performance_optimizer.analysis_added",
            performance_id=performance_id,
            performance_metric=performance_metric.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_metric_distribution(self) -> dict[str, Any]:
        metric_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.performance_metric.value
            metric_data.setdefault(key, []).append(r.performance_score)
        result: dict[str, Any] = {}
        for metric, scores in metric_data.items():
            result[metric] = {
                "count": len(scores),
                "avg_performance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_performance_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.performance_score < self._performance_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "performance_id": r.performance_id,
                        "performance_metric": r.performance_metric.value,
                        "performance_score": r.performance_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["performance_score"])

    def rank_by_performance(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.performance_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_performance_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_performance_score"])
        return results

    def detect_performance_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> SOCPerformanceReport:
        by_metric: dict[str, int] = {}
        by_area: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        for r in self._records:
            by_metric[r.performance_metric.value] = by_metric.get(r.performance_metric.value, 0) + 1
            by_area[r.optimization_area.value] = by_area.get(r.optimization_area.value, 0) + 1
            by_tier[r.performance_tier.value] = by_tier.get(r.performance_tier.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.performance_score < self._performance_threshold
        )
        scores = [r.performance_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_performance_gaps()
        top_gaps = [o["performance_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} performance metric(s) below threshold ({self._performance_threshold})"
            )
        if self._records and avg_score < self._performance_threshold:
            recs.append(
                f"Avg performance score {avg_score} below threshold ({self._performance_threshold})"
            )
        if not recs:
            recs.append("SOC performance is healthy")
        return SOCPerformanceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_performance_score=avg_score,
            by_metric=by_metric,
            by_area=by_area,
            by_tier=by_tier,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("soc_performance_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        metric_dist: dict[str, int] = {}
        for r in self._records:
            key = r.performance_metric.value
            metric_dist[key] = metric_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "performance_threshold": self._performance_threshold,
            "metric_distribution": metric_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
