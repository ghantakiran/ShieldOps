"""Agent Telemetry Analyzer — analyze agent execution patterns and decision quality."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TelemetryMetric(StrEnum):
    LATENCY = "latency"
    TOKEN_USAGE = "token_usage"  # noqa: S105
    ACCURACY = "accuracy"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"


class PerformanceTier(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    CRITICAL = "critical"


class AnalysisScope(StrEnum):
    SINGLE_RUN = "single_run"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# --- Models ---


class TelemetryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = ""
    telemetry_metric: TelemetryMetric = TelemetryMetric.LATENCY
    performance_tier: PerformanceTier = PerformanceTier.GOOD
    analysis_scope: AnalysisScope = AnalysisScope.DAILY
    metric_value: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class TelemetryBaseline(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    baseline_name: str = ""
    telemetry_metric: TelemetryMetric = TelemetryMetric.TOKEN_USAGE
    performance_tier: PerformanceTier = PerformanceTier.ACCEPTABLE
    threshold_value: float = 0.0
    created_at: float = Field(default_factory=time.time)


class TelemetryAnalyzerReport(BaseModel):
    total_records: int = 0
    total_baselines: int = 0
    performance_rate_pct: float = 0.0
    by_metric: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    poor_performance_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentTelemetryAnalyzer:
    """Analyze agent execution patterns and decision quality."""

    def __init__(
        self,
        max_records: int = 200000,
        min_performance_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_performance_pct = min_performance_pct
        self._records: list[TelemetryRecord] = []
        self._baselines: list[TelemetryBaseline] = []
        logger.info(
            "telemetry_analyzer.initialized",
            max_records=max_records,
            min_performance_pct=min_performance_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_telemetry(
        self,
        agent_name: str,
        telemetry_metric: TelemetryMetric = TelemetryMetric.LATENCY,
        performance_tier: PerformanceTier = PerformanceTier.GOOD,
        analysis_scope: AnalysisScope = AnalysisScope.DAILY,
        metric_value: float = 0.0,
        details: str = "",
    ) -> TelemetryRecord:
        record = TelemetryRecord(
            agent_name=agent_name,
            telemetry_metric=telemetry_metric,
            performance_tier=performance_tier,
            analysis_scope=analysis_scope,
            metric_value=metric_value,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "telemetry_analyzer.recorded",
            record_id=record.id,
            agent_name=agent_name,
            telemetry_metric=telemetry_metric.value,
            performance_tier=performance_tier.value,
        )
        return record

    def get_telemetry(self, record_id: str) -> TelemetryRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_telemetry(
        self,
        agent_name: str | None = None,
        telemetry_metric: TelemetryMetric | None = None,
        limit: int = 50,
    ) -> list[TelemetryRecord]:
        results = list(self._records)
        if agent_name is not None:
            results = [r for r in results if r.agent_name == agent_name]
        if telemetry_metric is not None:
            results = [r for r in results if r.telemetry_metric == telemetry_metric]
        return results[-limit:]

    def add_baseline(
        self,
        baseline_name: str,
        telemetry_metric: TelemetryMetric = TelemetryMetric.TOKEN_USAGE,
        performance_tier: PerformanceTier = PerformanceTier.ACCEPTABLE,
        threshold_value: float = 0.0,
    ) -> TelemetryBaseline:
        baseline = TelemetryBaseline(
            baseline_name=baseline_name,
            telemetry_metric=telemetry_metric,
            performance_tier=performance_tier,
            threshold_value=threshold_value,
        )
        self._baselines.append(baseline)
        if len(self._baselines) > self._max_records:
            self._baselines = self._baselines[-self._max_records :]
        logger.info(
            "telemetry_analyzer.baseline_added",
            baseline_name=baseline_name,
            telemetry_metric=telemetry_metric.value,
            threshold_value=threshold_value,
        )
        return baseline

    # -- domain operations -----------------------------------------------

    def analyze_agent_performance(self, agent_name: str) -> dict[str, Any]:
        agent_records = [r for r in self._records if r.agent_name == agent_name]
        if not agent_records:
            return {"agent_name": agent_name, "status": "no_data"}
        good_count = sum(
            1
            for r in agent_records
            if r.performance_tier in (PerformanceTier.EXCELLENT, PerformanceTier.GOOD)
        )
        rate = round(good_count / len(agent_records) * 100, 2)
        return {
            "agent_name": agent_name,
            "total_records": len(agent_records),
            "good_performance_count": good_count,
            "performance_rate_pct": rate,
            "meets_threshold": rate >= self._min_performance_pct,
        }

    def identify_underperforming_agents(self) -> list[dict[str, Any]]:
        agent_counts: dict[str, int] = {}
        for r in self._records:
            if r.performance_tier in (PerformanceTier.POOR, PerformanceTier.CRITICAL):
                agent_counts[r.agent_name] = agent_counts.get(r.agent_name, 0) + 1
        results: list[dict[str, Any]] = []
        for agent, count in agent_counts.items():
            if count > 1:
                results.append({"agent_name": agent, "poor_count": count})
        results.sort(key=lambda x: x["poor_count"], reverse=True)
        return results

    def rank_by_efficiency(self) -> list[dict[str, Any]]:
        agent_values: dict[str, list[float]] = {}
        for r in self._records:
            agent_values.setdefault(r.agent_name, []).append(r.metric_value)
        results: list[dict[str, Any]] = []
        for agent, values in agent_values.items():
            results.append(
                {
                    "agent_name": agent,
                    "avg_metric_value": round(sum(values) / len(values), 2),
                    "record_count": len(values),
                }
            )
        results.sort(key=lambda x: x["avg_metric_value"], reverse=True)
        return results

    def detect_performance_degradation(self) -> list[dict[str, Any]]:
        agent_counts: dict[str, int] = {}
        for r in self._records:
            if r.performance_tier == PerformanceTier.CRITICAL:
                agent_counts[r.agent_name] = agent_counts.get(r.agent_name, 0) + 1
        results: list[dict[str, Any]] = []
        for agent, count in agent_counts.items():
            if count > 3:
                results.append(
                    {
                        "agent_name": agent,
                        "critical_count": count,
                        "recurring": True,
                    }
                )
        results.sort(key=lambda x: x["critical_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> TelemetryAnalyzerReport:
        by_metric: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        for r in self._records:
            by_metric[r.telemetry_metric.value] = by_metric.get(r.telemetry_metric.value, 0) + 1
            by_tier[r.performance_tier.value] = by_tier.get(r.performance_tier.value, 0) + 1
        good_count = sum(
            1
            for r in self._records
            if r.performance_tier in (PerformanceTier.EXCELLENT, PerformanceTier.GOOD)
        )
        rate = round(good_count / len(self._records) * 100, 2) if self._records else 0.0
        poor_count = sum(1 for r in self._records if r.performance_tier == PerformanceTier.POOR)
        recs: list[str] = []
        if poor_count > 0:
            recs.append(f"{poor_count} agent record(s) with poor performance detected")
        degradation = len(self.detect_performance_degradation())
        if degradation > 0:
            recs.append(f"{degradation} agent(s) with recurring performance degradation")
        if not recs:
            recs.append("Agent telemetry performance meets targets")
        return TelemetryAnalyzerReport(
            total_records=len(self._records),
            total_baselines=len(self._baselines),
            performance_rate_pct=rate,
            by_metric=by_metric,
            by_tier=by_tier,
            poor_performance_count=poor_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._baselines.clear()
        logger.info("telemetry_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        metric_dist: dict[str, int] = {}
        for r in self._records:
            key = r.telemetry_metric.value
            metric_dist[key] = metric_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_baselines": len(self._baselines),
            "min_performance_pct": self._min_performance_pct,
            "metric_distribution": metric_dist,
            "unique_agents": len({r.agent_name for r in self._records}),
        }
