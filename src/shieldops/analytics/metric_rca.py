"""Metric Root Cause Analyzer — trace metric anomalies to identify root cause."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CauseCategory(StrEnum):
    DEPLOYMENT = "deployment"
    CONFIG_CHANGE = "config_change"
    DEPENDENCY_DEGRADATION = "dependency_degradation"
    RESOURCE_CONTENTION = "resource_contention"
    EXTERNAL_FACTOR = "external_factor"


class CausalConfidence(StrEnum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"
    UNKNOWN = "unknown"


class MetricType(StrEnum):
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    THROUGHPUT = "throughput"


# --- Models ---


class MetricAnomaly(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    metric_type: MetricType = MetricType.LATENCY
    baseline_value: float = 0.0
    anomaly_value: float = 0.0
    deviation_pct: float = 0.0
    resolved: bool = False
    created_at: float = Field(default_factory=time.time)


class RootCauseHypothesis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    anomaly_id: str = ""
    cause_category: CauseCategory = CauseCategory.DEPLOYMENT
    confidence: CausalConfidence = CausalConfidence.UNKNOWN
    confidence_score: float = 0.0
    description: str = ""
    correlated_changes: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class MetricRCAReport(BaseModel):
    total_anomalies: int = 0
    resolved_count: int = 0
    total_hypotheses: int = 0
    by_cause_category: dict[str, int] = Field(default_factory=dict)
    by_metric_type: dict[str, int] = Field(default_factory=dict)
    avg_deviation_pct: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MetricRootCauseAnalyzer:
    """Trace metric anomalies backward through causal chains to identify root cause."""

    def __init__(
        self,
        max_records: int = 200000,
        deviation_threshold_pct: float = 25.0,
    ) -> None:
        self._max_records = max_records
        self._deviation_threshold_pct = deviation_threshold_pct
        self._anomalies: list[MetricAnomaly] = []
        self._hypotheses: list[RootCauseHypothesis] = []
        logger.info(
            "metric_rca.initialized",
            max_records=max_records,
            deviation_threshold_pct=deviation_threshold_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _score_to_confidence(self, score: float) -> CausalConfidence:
        if score >= 0.9:
            return CausalConfidence.CONFIRMED
        if score >= 0.7:
            return CausalConfidence.PROBABLE
        if score >= 0.5:
            return CausalConfidence.POSSIBLE
        if score >= 0.3:
            return CausalConfidence.UNLIKELY
        return CausalConfidence.UNKNOWN

    # -- record / get / list ---------------------------------------------

    def record_anomaly(
        self,
        service: str,
        metric_type: MetricType,
        baseline_value: float = 0.0,
        anomaly_value: float = 0.0,
    ) -> MetricAnomaly:
        deviation_pct = 0.0
        if baseline_value > 0:
            deviation_pct = round(abs(anomaly_value - baseline_value) / baseline_value * 100, 2)
        anomaly = MetricAnomaly(
            service=service,
            metric_type=metric_type,
            baseline_value=baseline_value,
            anomaly_value=anomaly_value,
            deviation_pct=deviation_pct,
        )
        self._anomalies.append(anomaly)
        if len(self._anomalies) > self._max_records:
            self._anomalies = self._anomalies[-self._max_records :]
        logger.info(
            "metric_rca.anomaly_recorded",
            anomaly_id=anomaly.id,
            service=service,
            metric_type=metric_type.value,
            deviation_pct=deviation_pct,
        )
        return anomaly

    def get_anomaly(self, anomaly_id: str) -> MetricAnomaly | None:
        for a in self._anomalies:
            if a.id == anomaly_id:
                return a
        return None

    def list_anomalies(
        self,
        service: str | None = None,
        metric_type: MetricType | None = None,
        limit: int = 50,
    ) -> list[MetricAnomaly]:
        results = list(self._anomalies)
        if service is not None:
            results = [a for a in results if a.service == service]
        if metric_type is not None:
            results = [a for a in results if a.metric_type == metric_type]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def analyze_root_cause(self, anomaly_id: str) -> RootCauseHypothesis:
        """Analyze potential root cause for a metric anomaly."""
        anomaly = self.get_anomaly(anomaly_id)
        if anomaly is None:
            hyp = RootCauseHypothesis(
                anomaly_id=anomaly_id,
                cause_category=CauseCategory.EXTERNAL_FACTOR,
                confidence=CausalConfidence.UNKNOWN,
                confidence_score=0.1,
                description="Anomaly not found",
            )
            self._hypotheses.append(hyp)
            return hyp

        # Heuristic: determine likely cause based on metric type and deviation
        if anomaly.deviation_pct > 100:
            cause = CauseCategory.DEPLOYMENT
            score = 0.85
            desc = f"Large deviation ({anomaly.deviation_pct}%) suggests deployment change"
        elif anomaly.metric_type in (MetricType.CPU_USAGE, MetricType.MEMORY_USAGE):
            cause = CauseCategory.RESOURCE_CONTENTION
            score = 0.7
            desc = f"Resource metric anomaly in {anomaly.service}"
        elif anomaly.metric_type == MetricType.LATENCY:
            cause = CauseCategory.DEPENDENCY_DEGRADATION
            score = 0.65
            desc = f"Latency increase in {anomaly.service} may indicate dependency issue"
        elif anomaly.metric_type == MetricType.ERROR_RATE:
            cause = CauseCategory.CONFIG_CHANGE
            score = 0.6
            desc = f"Error rate spike in {anomaly.service}"
        else:
            cause = CauseCategory.EXTERNAL_FACTOR
            score = 0.4
            desc = f"Throughput anomaly in {anomaly.service}"

        confidence = self._score_to_confidence(score)
        hyp = RootCauseHypothesis(
            anomaly_id=anomaly_id,
            cause_category=cause,
            confidence=confidence,
            confidence_score=score,
            description=desc,
        )
        self._hypotheses.append(hyp)
        if len(self._hypotheses) > self._max_records:
            self._hypotheses = self._hypotheses[-self._max_records :]
        logger.info(
            "metric_rca.root_cause_analyzed",
            hypothesis_id=hyp.id,
            anomaly_id=anomaly_id,
            cause=cause.value,
            confidence=confidence.value,
        )
        return hyp

    def correlate_with_changes(
        self,
        anomaly_id: str,
        changes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Correlate anomaly with recent changes."""
        anomaly = self.get_anomaly(anomaly_id)
        if anomaly is None:
            return {"anomaly_id": anomaly_id, "found": False}
        change_list = changes or []
        correlated = len(change_list) > 0
        score = 0.8 if correlated else 0.3
        return {
            "anomaly_id": anomaly_id,
            "found": True,
            "service": anomaly.service,
            "correlated": correlated,
            "changes": change_list,
            "correlation_score": score,
        }

    def rank_hypotheses(self, anomaly_id: str) -> list[dict[str, Any]]:
        """Rank all hypotheses for an anomaly by confidence."""
        hyps = [h for h in self._hypotheses if h.anomaly_id == anomaly_id]
        ranked = sorted(hyps, key=lambda h: h.confidence_score, reverse=True)
        return [
            {
                "hypothesis_id": h.id,
                "cause_category": h.cause_category.value,
                "confidence": h.confidence.value,
                "confidence_score": h.confidence_score,
                "description": h.description,
            }
            for h in ranked
        ]

    def mark_resolved(self, anomaly_id: str) -> dict[str, Any]:
        anomaly = self.get_anomaly(anomaly_id)
        if anomaly is None:
            return {"found": False, "anomaly_id": anomaly_id}
        anomaly.resolved = True
        logger.info("metric_rca.anomaly_resolved", anomaly_id=anomaly_id)
        return {"found": True, "anomaly_id": anomaly_id, "resolved": True}

    def get_cause_trends(self) -> dict[str, int]:
        """Get distribution of cause categories across all hypotheses."""
        trends: dict[str, int] = {}
        for h in self._hypotheses:
            key = h.cause_category.value
            trends[key] = trends.get(key, 0) + 1
        return trends

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> MetricRCAReport:
        by_cause: dict[str, int] = {}
        by_metric: dict[str, int] = {}
        for h in self._hypotheses:
            by_cause[h.cause_category.value] = by_cause.get(h.cause_category.value, 0) + 1
        total_dev = 0.0
        for a in self._anomalies:
            by_metric[a.metric_type.value] = by_metric.get(a.metric_type.value, 0) + 1
            total_dev += a.deviation_pct
        avg_dev = round(total_dev / len(self._anomalies), 2) if self._anomalies else 0.0
        resolved_count = sum(1 for a in self._anomalies if a.resolved)
        recs: list[str] = []
        unresolved = len(self._anomalies) - resolved_count
        if unresolved > 0:
            recs.append(f"{unresolved} anomaly(ies) unresolved")
        deployment_count = by_cause.get(CauseCategory.DEPLOYMENT.value, 0)
        if deployment_count > 0:
            recs.append(f"{deployment_count} anomaly(ies) linked to deployments")
        if avg_dev > self._deviation_threshold_pct:
            recs.append(
                f"Average deviation {avg_dev}% exceeds threshold {self._deviation_threshold_pct}%"
            )
        if not recs:
            recs.append("No significant metric anomalies detected")
        return MetricRCAReport(
            total_anomalies=len(self._anomalies),
            resolved_count=resolved_count,
            total_hypotheses=len(self._hypotheses),
            by_cause_category=by_cause,
            by_metric_type=by_metric,
            avg_deviation_pct=avg_dev,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._anomalies.clear()
        self._hypotheses.clear()
        logger.info("metric_rca.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cause_dist: dict[str, int] = {}
        for h in self._hypotheses:
            key = h.cause_category.value
            cause_dist[key] = cause_dist.get(key, 0) + 1
        return {
            "total_anomalies": len(self._anomalies),
            "total_hypotheses": len(self._hypotheses),
            "deviation_threshold_pct": self._deviation_threshold_pct,
            "cause_distribution": cause_dist,
            "unique_services": len({a.service for a in self._anomalies}),
            "resolved": sum(1 for a in self._anomalies if a.resolved),
        }
