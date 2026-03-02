"""SOC Metrics Dashboard — SOC KPIs: MTTD, MTTC, MTTR, false positive rate."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MetricType(StrEnum):
    MTTD = "mttd"
    MTTC = "mttc"
    MTTR = "mttr"
    FALSE_POSITIVE_RATE = "false_positive_rate"
    ANALYST_EFFICIENCY = "analyst_efficiency"


class SOCTier(StrEnum):
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"
    AUTOMATION = "automation"
    MANAGEMENT = "management"


class PerformanceLevel(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    BELOW_AVERAGE = "below_average"
    CRITICAL = "critical"


# --- Models ---


class SOCMetricRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    metric_type: MetricType = MetricType.MTTD
    soc_tier: SOCTier = SOCTier.TIER_1
    performance_level: PerformanceLevel = PerformanceLevel.EXCELLENT
    metric_value: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MetricAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    metric_type: MetricType = MetricType.MTTD
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SOCMetricsReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    below_target_count: int = 0
    avg_metric_value: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_performance: dict[str, int] = Field(default_factory=dict)
    top_below_target: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SOCMetricsDashboard:
    """SOC KPIs: MTTD, MTTC, MTTR, false positive rate, analyst efficiency."""

    def __init__(
        self,
        max_records: int = 200000,
        metric_target_threshold: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._metric_target_threshold = metric_target_threshold
        self._records: list[SOCMetricRecord] = []
        self._analyses: list[MetricAnalysis] = []
        logger.info(
            "soc_metrics_dashboard.initialized",
            max_records=max_records,
            metric_target_threshold=metric_target_threshold,
        )

    def record_metric(
        self,
        metric_name: str,
        metric_type: MetricType = MetricType.MTTD,
        soc_tier: SOCTier = SOCTier.TIER_1,
        performance_level: PerformanceLevel = PerformanceLevel.EXCELLENT,
        metric_value: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SOCMetricRecord:
        record = SOCMetricRecord(
            metric_name=metric_name,
            metric_type=metric_type,
            soc_tier=soc_tier,
            performance_level=performance_level,
            metric_value=metric_value,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "soc_metrics_dashboard.metric_recorded",
            record_id=record.id,
            metric_name=metric_name,
            metric_type=metric_type.value,
            soc_tier=soc_tier.value,
        )
        return record

    def get_metric(self, record_id: str) -> SOCMetricRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_metrics(
        self,
        metric_type: MetricType | None = None,
        soc_tier: SOCTier | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SOCMetricRecord]:
        results = list(self._records)
        if metric_type is not None:
            results = [r for r in results if r.metric_type == metric_type]
        if soc_tier is not None:
            results = [r for r in results if r.soc_tier == soc_tier]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        metric_name: str,
        metric_type: MetricType = MetricType.MTTD,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MetricAnalysis:
        analysis = MetricAnalysis(
            metric_name=metric_name,
            metric_type=metric_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "soc_metrics_dashboard.analysis_added",
            metric_name=metric_name,
            metric_type=metric_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_metric_distribution(self) -> dict[str, Any]:
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.metric_type.value
            type_data.setdefault(key, []).append(r.metric_value)
        result: dict[str, Any] = {}
        for mtype, scores in type_data.items():
            result[mtype] = {
                "count": len(scores),
                "avg_metric_value": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_below_target_metrics(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.metric_value < self._metric_target_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "metric_name": r.metric_name,
                        "metric_type": r.metric_type.value,
                        "metric_value": r.metric_value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["metric_value"])

    def rank_by_metric_value(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.metric_value)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {"service": svc, "avg_metric_value": round(sum(scores) / len(scores), 2)}
            )
        results.sort(key=lambda x: x["avg_metric_value"])
        return results

    def detect_metric_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> SOCMetricsReport:
        by_type: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        by_performance: dict[str, int] = {}
        for r in self._records:
            by_type[r.metric_type.value] = by_type.get(r.metric_type.value, 0) + 1
            by_tier[r.soc_tier.value] = by_tier.get(r.soc_tier.value, 0) + 1
            by_performance[r.performance_level.value] = (
                by_performance.get(r.performance_level.value, 0) + 1
            )
        below_target_count = sum(
            1 for r in self._records if r.metric_value < self._metric_target_threshold
        )
        scores = [r.metric_value for r in self._records]
        avg_metric_value = round(sum(scores) / len(scores), 2) if scores else 0.0
        below_list = self.identify_below_target_metrics()
        top_below_target = [o["metric_name"] for o in below_list[:5]]
        recs: list[str] = []
        if self._records and below_target_count > 0:
            recs.append(
                f"{below_target_count} metric(s) below target threshold "
                f"({self._metric_target_threshold})"
            )
        if self._records and avg_metric_value < self._metric_target_threshold:
            recs.append(
                f"Avg metric value {avg_metric_value} below threshold "
                f"({self._metric_target_threshold})"
            )
        if not recs:
            recs.append("SOC metrics performance is healthy")
        return SOCMetricsReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            below_target_count=below_target_count,
            avg_metric_value=avg_metric_value,
            by_type=by_type,
            by_tier=by_tier,
            by_performance=by_performance,
            top_below_target=top_below_target,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("soc_metrics_dashboard.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.metric_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "metric_target_threshold": self._metric_target_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
