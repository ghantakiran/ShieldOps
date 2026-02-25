"""Deployment Canary Analyzer — analyze canary-specific metrics and promotion/rollback decisions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CanaryDecision(StrEnum):
    PROMOTE = "promote"
    ROLLBACK = "rollback"
    EXTEND = "extend"
    PAUSE = "pause"
    MANUAL_REVIEW = "manual_review"


class CanaryMetricType(StrEnum):
    ERROR_RATE = "error_rate"
    LATENCY_P99 = "latency_p99"
    SUCCESS_RATE = "success_rate"
    THROUGHPUT = "throughput"
    SATURATION = "saturation"


class CanaryPhase(StrEnum):
    INITIALIZING = "initializing"
    TRAFFIC_SHIFTING = "traffic_shifting"
    OBSERVING = "observing"
    DECIDING = "deciding"
    COMPLETED = "completed"


# --- Models ---


class CanaryAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    service_name: str = ""
    canary_version: str = ""
    baseline_version: str = ""
    phase: CanaryPhase = CanaryPhase.INITIALIZING
    decision: CanaryDecision = CanaryDecision.MANUAL_REVIEW
    traffic_pct: float = 0.0
    canary_metrics: dict[str, float] = Field(default_factory=dict)
    baseline_metrics: dict[str, float] = Field(default_factory=dict)
    deviation_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class CanaryComparison(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    analysis_id: str = ""
    metric_type: CanaryMetricType = CanaryMetricType.ERROR_RATE
    canary_value: float = 0.0
    baseline_value: float = 0.0
    deviation_pct: float = 0.0
    within_threshold: bool = True
    created_at: float = Field(default_factory=time.time)


class CanaryReport(BaseModel):
    total_analyses: int = 0
    promotion_rate_pct: float = 0.0
    rollback_rate_pct: float = 0.0
    by_decision: dict[str, int] = Field(default_factory=dict)
    by_phase: dict[str, int] = Field(default_factory=dict)
    flaky_services: list[str] = Field(default_factory=list)
    avg_deviation_pct: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentCanaryAnalyzer:
    """Analyze canary-specific metrics and promotion/rollback decisions."""

    def __init__(
        self,
        max_records: int = 200000,
        deviation_threshold_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._deviation_threshold_pct = deviation_threshold_pct
        self._records: list[CanaryAnalysis] = []
        self._comparisons: list[CanaryComparison] = []
        logger.info(
            "canary_analyzer.initialized",
            max_records=max_records,
            deviation_threshold_pct=deviation_threshold_pct,
        )

    # -- CRUD --

    def create_analysis(
        self,
        deployment_id: str,
        service_name: str,
        canary_version: str,
        baseline_version: str,
        traffic_pct: float = 5.0,
    ) -> CanaryAnalysis:
        analysis = CanaryAnalysis(
            deployment_id=deployment_id,
            service_name=service_name,
            canary_version=canary_version,
            baseline_version=baseline_version,
            traffic_pct=traffic_pct,
        )
        self._records.append(analysis)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "canary_analyzer.created",
            analysis_id=analysis.id,
            deployment_id=deployment_id,
            service_name=service_name,
        )
        return analysis

    def get_analysis(self, analysis_id: str) -> CanaryAnalysis | None:
        for a in self._records:
            if a.id == analysis_id:
                return a
        return None

    def list_analyses(
        self,
        service_name: str | None = None,
        decision: CanaryDecision | None = None,
        limit: int = 50,
    ) -> list[CanaryAnalysis]:
        results = list(self._records)
        if service_name is not None:
            results = [a for a in results if a.service_name == service_name]
        if decision is not None:
            results = [a for a in results if a.decision == decision]
        return results[-limit:]

    # -- Domain operations --

    def compare_metrics(
        self,
        analysis_id: str,
        metric_type: CanaryMetricType,
        canary_value: float,
        baseline_value: float,
    ) -> CanaryComparison:
        deviation_pct = abs(canary_value - baseline_value) / max(baseline_value, 0.001) * 100.0
        deviation_pct = round(deviation_pct, 2)
        within_threshold = deviation_pct <= self._deviation_threshold_pct
        comparison = CanaryComparison(
            analysis_id=analysis_id,
            metric_type=metric_type,
            canary_value=canary_value,
            baseline_value=baseline_value,
            deviation_pct=deviation_pct,
            within_threshold=within_threshold,
        )
        self._comparisons.append(comparison)
        if len(self._comparisons) > self._max_records:
            self._comparisons = self._comparisons[-self._max_records :]
        # Update analysis metrics
        analysis = self.get_analysis(analysis_id)
        if analysis is not None:
            analysis.canary_metrics[metric_type.value] = canary_value
            analysis.baseline_metrics[metric_type.value] = baseline_value
        logger.info(
            "canary_analyzer.compared",
            analysis_id=analysis_id,
            metric_type=metric_type.value,
            deviation_pct=deviation_pct,
            within_threshold=within_threshold,
        )
        return comparison

    def decide_promotion(
        self,
        analysis_id: str,
    ) -> dict[str, Any]:
        analysis = self.get_analysis(analysis_id)
        if analysis is None:
            return {"error": "analysis_not_found"}
        comparisons = [c for c in self._comparisons if c.analysis_id == analysis_id]
        if not comparisons:
            analysis.decision = CanaryDecision.MANUAL_REVIEW
            return {
                "analysis_id": analysis_id,
                "decision": CanaryDecision.MANUAL_REVIEW.value,
                "reason": "no_comparisons_available",
            }
        double_threshold = self._deviation_threshold_pct * 2.0
        has_severe = any(c.deviation_pct > double_threshold for c in comparisons)
        has_exceeded = any(c.deviation_pct > self._deviation_threshold_pct for c in comparisons)
        all_within = all(c.within_threshold for c in comparisons)
        if has_severe:
            decision = CanaryDecision.ROLLBACK
            reason = "severe_deviation_detected"
        elif has_exceeded:
            decision = CanaryDecision.EXTEND
            reason = "deviation_above_threshold"
        elif all_within:
            decision = CanaryDecision.PROMOTE
            reason = "all_metrics_within_threshold"
        else:
            decision = CanaryDecision.MANUAL_REVIEW
            reason = "mixed_signals"
        analysis.decision = decision
        analysis.phase = CanaryPhase.DECIDING
        # Compute max deviation for the analysis
        max_dev = max(c.deviation_pct for c in comparisons)
        analysis.deviation_pct = max_dev
        logger.info(
            "canary_analyzer.decided",
            analysis_id=analysis_id,
            decision=decision.value,
            reason=reason,
        )
        return {
            "analysis_id": analysis_id,
            "decision": decision.value,
            "reason": reason,
            "comparisons_count": len(comparisons),
            "max_deviation_pct": max_dev,
        }

    def advance_phase(
        self,
        analysis_id: str,
        phase: CanaryPhase,
    ) -> dict[str, Any]:
        analysis = self.get_analysis(analysis_id)
        if analysis is None:
            return {"error": "analysis_not_found"}
        old_phase = analysis.phase.value
        analysis.phase = phase
        logger.info(
            "canary_analyzer.phase_advanced",
            analysis_id=analysis_id,
            old_phase=old_phase,
            new_phase=phase.value,
        )
        return {
            "analysis_id": analysis_id,
            "old_phase": old_phase,
            "new_phase": phase.value,
        }

    def calculate_promotion_rate(self) -> dict[str, Any]:
        if not self._records:
            return {"promotion_rate_pct": 0.0, "total": 0}
        decided = [a for a in self._records if a.decision != CanaryDecision.MANUAL_REVIEW]
        if not decided:
            return {"promotion_rate_pct": 0.0, "total": 0}
        promoted = sum(1 for a in decided if a.decision == CanaryDecision.PROMOTE)
        rolled_back = sum(1 for a in decided if a.decision == CanaryDecision.ROLLBACK)
        rate = round(promoted / len(decided) * 100.0, 2)
        rollback_rate = round(rolled_back / len(decided) * 100.0, 2)
        return {
            "promotion_rate_pct": rate,
            "rollback_rate_pct": rollback_rate,
            "promoted": promoted,
            "rolled_back": rolled_back,
            "total": len(decided),
        }

    def identify_flaky_services(self) -> list[dict[str, Any]]:
        by_service: dict[str, list[CanaryAnalysis]] = {}
        for a in self._records:
            by_service.setdefault(a.service_name, []).append(a)
        flaky: list[dict[str, Any]] = []
        for svc, analyses in sorted(by_service.items()):
            total = len(analyses)
            rollbacks = sum(1 for a in analyses if a.decision == CanaryDecision.ROLLBACK)
            if total > 0 and rollbacks > 0:
                rollback_rate = round(rollbacks / total * 100.0, 2)
                if rollback_rate > 30.0:
                    flaky.append(
                        {
                            "service_name": svc,
                            "total_analyses": total,
                            "rollback_count": rollbacks,
                            "rollback_rate_pct": rollback_rate,
                        }
                    )
        flaky.sort(key=lambda x: x["rollback_rate_pct"], reverse=True)
        return flaky

    # -- Report --

    def generate_canary_report(self) -> CanaryReport:
        by_decision: dict[str, int] = {}
        by_phase: dict[str, int] = {}
        for a in self._records:
            by_decision[a.decision.value] = by_decision.get(a.decision.value, 0) + 1
            by_phase[a.phase.value] = by_phase.get(a.phase.value, 0) + 1
        total = len(self._records)
        rate_info = self.calculate_promotion_rate()
        flaky = self.identify_flaky_services()
        flaky_names = [f["service_name"] for f in flaky[:10]]
        avg_dev = round(sum(a.deviation_pct for a in self._records) / total, 2) if total else 0.0
        recs: list[str] = []
        rollback_rate = rate_info.get("rollback_rate_pct", 0.0)
        if rollback_rate > 30.0:
            recs.append("High rollback rate — review pre-deployment validation")
        if flaky_names:
            recs.append(f"{len(flaky_names)} flaky service(s) with high rollback rates")
        if avg_dev > self._deviation_threshold_pct:
            recs.append("Average deviation exceeds threshold — tighten canary criteria")
        if not recs:
            recs.append("Canary analysis results within acceptable parameters")
        return CanaryReport(
            total_analyses=total,
            promotion_rate_pct=rate_info.get("promotion_rate_pct", 0.0),
            rollback_rate_pct=rollback_rate,
            by_decision=by_decision,
            by_phase=by_phase,
            flaky_services=flaky_names,
            avg_deviation_pct=avg_dev,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._comparisons.clear()
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        decision_dist: dict[str, int] = {}
        for a in self._records:
            key = a.decision.value
            decision_dist[key] = decision_dist.get(key, 0) + 1
        return {
            "total_analyses": len(self._records),
            "total_comparisons": len(self._comparisons),
            "deviation_threshold_pct": self._deviation_threshold_pct,
            "unique_services": len({a.service_name for a in self._records}),
            "decision_distribution": decision_dist,
        }
