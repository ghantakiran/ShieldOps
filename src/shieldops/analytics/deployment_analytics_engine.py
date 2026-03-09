"""DeploymentAnalyticsEngine

DORA metrics intelligence, deployment frequency analysis,
lead time optimization, change failure tracking.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DORAMetric(StrEnum):
    DEPLOYMENT_FREQUENCY = "deployment_frequency"
    LEAD_TIME = "lead_time"
    CHANGE_FAILURE_RATE = "change_failure_rate"
    MTTR = "mttr"


class PerformanceLevel(StrEnum):
    ELITE = "elite"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class DeploymentClass(StrEnum):
    STANDARD = "standard"
    HOTFIX = "hotfix"
    ROLLBACK = "rollback"
    EMERGENCY = "emergency"
    SCHEDULED = "scheduled"


# --- Models ---


class DeploymentAnalyticsRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    dora_metric: DORAMetric = DORAMetric.DEPLOYMENT_FREQUENCY
    performance_level: PerformanceLevel = PerformanceLevel.UNKNOWN
    deployment_class: DeploymentClass = DeploymentClass.STANDARD
    metric_value: float = 0.0
    lead_time_hours: float = 0.0
    change_failure_rate_pct: float = 0.0
    mttr_minutes: float = 0.0
    deploys_per_day: float = 0.0
    pipeline_duration_minutes: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DeploymentAnalyticsAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    dora_metric: DORAMetric = DORAMetric.DEPLOYMENT_FREQUENCY
    analysis_score: float = 0.0
    benchmark_percentile: float = 0.0
    improvement_potential: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeploymentAnalyticsReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_lead_time_hours: float = 0.0
    avg_change_failure_rate: float = 0.0
    avg_mttr_minutes: float = 0.0
    avg_deploys_per_day: float = 0.0
    by_dora_metric: dict[str, int] = Field(default_factory=dict)
    by_performance_level: dict[str, int] = Field(default_factory=dict)
    by_deployment_class: dict[str, int] = Field(default_factory=dict)
    top_improving_teams: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


DORA_THRESHOLDS: dict[str, dict[str, float]] = {
    "elite": {"deploys_per_day": 1.0, "lead_time_hours": 24, "cfr_pct": 5, "mttr_min": 60},
    "high": {"deploys_per_day": 0.14, "lead_time_hours": 168, "cfr_pct": 15, "mttr_min": 1440},
    "medium": {"deploys_per_day": 0.033, "lead_time_hours": 720, "cfr_pct": 30, "mttr_min": 10080},
}


class DeploymentAnalyticsEngine:
    """DORA metrics intelligence with deployment frequency and lead time analysis."""

    def __init__(
        self,
        max_records: int = 200000,
        performance_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._performance_threshold = performance_threshold
        self._records: list[DeploymentAnalyticsRecord] = []
        self._analyses: list[DeploymentAnalyticsAnalysis] = []
        logger.info(
            "deployment.analytics.engine.initialized",
            max_records=max_records,
            performance_threshold=performance_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_item(
        self,
        name: str,
        dora_metric: DORAMetric = DORAMetric.DEPLOYMENT_FREQUENCY,
        performance_level: PerformanceLevel = PerformanceLevel.UNKNOWN,
        deployment_class: DeploymentClass = DeploymentClass.STANDARD,
        metric_value: float = 0.0,
        lead_time_hours: float = 0.0,
        change_failure_rate_pct: float = 0.0,
        mttr_minutes: float = 0.0,
        deploys_per_day: float = 0.0,
        pipeline_duration_minutes: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DeploymentAnalyticsRecord:
        record = DeploymentAnalyticsRecord(
            name=name,
            dora_metric=dora_metric,
            performance_level=performance_level,
            deployment_class=deployment_class,
            metric_value=metric_value,
            lead_time_hours=lead_time_hours,
            change_failure_rate_pct=change_failure_rate_pct,
            mttr_minutes=mttr_minutes,
            deploys_per_day=deploys_per_day,
            pipeline_duration_minutes=pipeline_duration_minutes,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deployment.analytics.engine.item_recorded",
            record_id=record.id,
            name=name,
            dora_metric=dora_metric.value,
            performance_level=performance_level.value,
        )
        return record

    def get_record(self, record_id: str) -> DeploymentAnalyticsRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        dora_metric: DORAMetric | None = None,
        performance_level: PerformanceLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DeploymentAnalyticsRecord]:
        results = list(self._records)
        if dora_metric is not None:
            results = [r for r in results if r.dora_metric == dora_metric]
        if performance_level is not None:
            results = [r for r in results if r.performance_level == performance_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        dora_metric: DORAMetric = DORAMetric.DEPLOYMENT_FREQUENCY,
        analysis_score: float = 0.0,
        benchmark_percentile: float = 0.0,
        improvement_potential: float = 0.0,
        description: str = "",
    ) -> DeploymentAnalyticsAnalysis:
        analysis = DeploymentAnalyticsAnalysis(
            name=name,
            dora_metric=dora_metric,
            analysis_score=analysis_score,
            benchmark_percentile=benchmark_percentile,
            improvement_potential=improvement_potential,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "deployment.analytics.engine.analysis_added",
            name=name,
            dora_metric=dora_metric.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def classify_dora_performance(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            level = "low"
            if (
                r.deploys_per_day >= DORA_THRESHOLDS["elite"]["deploys_per_day"]
                and r.lead_time_hours <= DORA_THRESHOLDS["elite"]["lead_time_hours"]
            ):
                level = "elite"
            elif (
                r.deploys_per_day >= DORA_THRESHOLDS["high"]["deploys_per_day"]
                and r.lead_time_hours <= DORA_THRESHOLDS["high"]["lead_time_hours"]
            ):
                level = "high"
            elif (
                r.deploys_per_day >= DORA_THRESHOLDS["medium"]["deploys_per_day"]
                and r.lead_time_hours <= DORA_THRESHOLDS["medium"]["lead_time_hours"]
            ):
                level = "medium"
            results.append(
                {
                    "record_id": r.id,
                    "name": r.name,
                    "team": r.team,
                    "classified_level": level,
                    "deploys_per_day": r.deploys_per_day,
                    "lead_time_hours": r.lead_time_hours,
                    "change_failure_rate": r.change_failure_rate_pct,
                    "mttr_minutes": r.mttr_minutes,
                }
            )
        return results

    def analyze_lead_time_bottlenecks(self) -> dict[str, Any]:
        team_times: dict[str, list[float]] = {}
        for r in self._records:
            team_times.setdefault(r.team, []).append(r.lead_time_hours)
        result: dict[str, Any] = {}
        for team, times in team_times.items():
            result[team] = {
                "avg_lead_time_hours": round(sum(times) / len(times), 2),
                "max_lead_time_hours": round(max(times), 2),
                "min_lead_time_hours": round(min(times), 2),
                "sample_count": len(times),
            }
        return result

    def track_change_failure_rate(self) -> dict[str, Any]:
        svc_failures: dict[str, list[float]] = {}
        for r in self._records:
            svc_failures.setdefault(r.service, []).append(r.change_failure_rate_pct)
        result: dict[str, Any] = {}
        for svc, rates in svc_failures.items():
            result[svc] = {
                "avg_cfr": round(sum(rates) / len(rates), 2),
                "max_cfr": round(max(rates), 2),
                "samples": len(rates),
            }
        return result

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
        delta = round(avg_second - avg_first, 2)
        trend = "stable" if abs(delta) < 5.0 else ("improving" if delta > 0 else "degrading")
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> DeploymentAnalyticsReport:
        by_metric: dict[str, int] = {}
        by_perf: dict[str, int] = {}
        by_class: dict[str, int] = {}
        for r in self._records:
            by_metric[r.dora_metric.value] = by_metric.get(r.dora_metric.value, 0) + 1
            by_perf[r.performance_level.value] = by_perf.get(r.performance_level.value, 0) + 1
            by_class[r.deployment_class.value] = by_class.get(r.deployment_class.value, 0) + 1
        lead_times = [r.lead_time_hours for r in self._records if r.lead_time_hours > 0]
        avg_lt = round(sum(lead_times) / len(lead_times), 2) if lead_times else 0.0
        cfrs = [r.change_failure_rate_pct for r in self._records]
        avg_cfr = round(sum(cfrs) / len(cfrs), 2) if cfrs else 0.0
        mttrs = [r.mttr_minutes for r in self._records if r.mttr_minutes > 0]
        avg_mttr = round(sum(mttrs) / len(mttrs), 2) if mttrs else 0.0
        dpds = [r.deploys_per_day for r in self._records if r.deploys_per_day > 0]
        avg_dpd = round(sum(dpds) / len(dpds), 2) if dpds else 0.0
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.metric_value)
        improving: list[str] = []
        for team, vals in team_scores.items():
            if len(vals) >= 2:
                mid = len(vals) // 2
                if sum(vals[mid:]) / len(vals[mid:]) > sum(vals[:mid]) / len(vals[:mid]):
                    improving.append(team)
        recs: list[str] = []
        if avg_cfr > 15.0:
            recs.append(f"Change failure rate {avg_cfr}% exceeds 15% — improve testing")
        if avg_lt > 168:
            recs.append(f"Avg lead time {avg_lt}h exceeds 1 week — streamline pipeline")
        if avg_mttr > 1440:
            recs.append(f"Avg MTTR {avg_mttr}m exceeds 24h — improve incident response")
        if not recs:
            recs.append("DORA metrics are healthy — team performing at or above targets")
        return DeploymentAnalyticsReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_lead_time_hours=avg_lt,
            avg_change_failure_rate=avg_cfr,
            avg_mttr_minutes=avg_mttr,
            avg_deploys_per_day=avg_dpd,
            by_dora_metric=by_metric,
            by_performance_level=by_perf,
            by_deployment_class=by_class,
            top_improving_teams=improving[:5],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("deployment.analytics.engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        metric_dist: dict[str, int] = {}
        for r in self._records:
            metric_dist[r.dora_metric.value] = metric_dist.get(r.dora_metric.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "performance_threshold": self._performance_threshold,
            "dora_metric_distribution": metric_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
