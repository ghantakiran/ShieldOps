"""Deploy Canary Analyzer — analyze canary deployment outcomes and detect regression signals."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CanaryOutcome(StrEnum):
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"
    EXTENDED = "extended"
    PAUSED = "paused"
    INCONCLUSIVE = "inconclusive"


class CanarySignal(StrEnum):
    LATENCY_INCREASE = "latency_increase"
    ERROR_SPIKE = "error_spike"
    RESOURCE_ANOMALY = "resource_anomaly"
    TRAFFIC_DROP = "traffic_drop"
    HEALTHY = "healthy"


class CanaryStrategy(StrEnum):
    PERCENTAGE = "percentage"
    TIME_BASED = "time_based"
    METRIC_BASED = "metric_based"
    REGION_BASED = "region_based"
    FEATURE_FLAG = "feature_flag"


# --- Models ---


class CanaryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    canary_id: str = ""
    canary_outcome: CanaryOutcome = CanaryOutcome.INCONCLUSIVE
    canary_signal: CanarySignal = CanarySignal.HEALTHY
    canary_strategy: CanaryStrategy = CanaryStrategy.PERCENTAGE
    success_rate: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CanaryMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    canary_id: str = ""
    canary_outcome: CanaryOutcome = CanaryOutcome.INCONCLUSIVE
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeployCanaryReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    failed_canaries: int = 0
    avg_success_rate: float = 0.0
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_signal: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    top_failed: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeployCanaryAnalyzer:
    """Analyze canary deployment outcomes, detect regression signals, track canary effectiveness."""

    def __init__(
        self,
        max_records: int = 200000,
        min_success_rate: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_success_rate = min_success_rate
        self._records: list[CanaryRecord] = []
        self._metrics: list[CanaryMetric] = []
        logger.info(
            "deploy_canary_analyzer.initialized",
            max_records=max_records,
            min_success_rate=min_success_rate,
        )

    # -- record / get / list ------------------------------------------------

    def record_canary(
        self,
        canary_id: str,
        canary_outcome: CanaryOutcome = CanaryOutcome.INCONCLUSIVE,
        canary_signal: CanarySignal = CanarySignal.HEALTHY,
        canary_strategy: CanaryStrategy = CanaryStrategy.PERCENTAGE,
        success_rate: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CanaryRecord:
        record = CanaryRecord(
            canary_id=canary_id,
            canary_outcome=canary_outcome,
            canary_signal=canary_signal,
            canary_strategy=canary_strategy,
            success_rate=success_rate,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deploy_canary_analyzer.canary_recorded",
            record_id=record.id,
            canary_id=canary_id,
            canary_outcome=canary_outcome.value,
            canary_signal=canary_signal.value,
        )
        return record

    def get_canary(self, record_id: str) -> CanaryRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_canaries(
        self,
        canary_outcome: CanaryOutcome | None = None,
        canary_signal: CanarySignal | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CanaryRecord]:
        results = list(self._records)
        if canary_outcome is not None:
            results = [r for r in results if r.canary_outcome == canary_outcome]
        if canary_signal is not None:
            results = [r for r in results if r.canary_signal == canary_signal]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        canary_id: str,
        canary_outcome: CanaryOutcome = CanaryOutcome.INCONCLUSIVE,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CanaryMetric:
        metric = CanaryMetric(
            canary_id=canary_id,
            canary_outcome=canary_outcome,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "deploy_canary_analyzer.metric_added",
            canary_id=canary_id,
            canary_outcome=canary_outcome.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_canary_distribution(self) -> dict[str, Any]:
        """Group by canary_outcome; return count and avg success_rate per outcome."""
        outcome_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.canary_outcome.value
            outcome_data.setdefault(key, []).append(r.success_rate)
        result: dict[str, Any] = {}
        for outcome, scores in outcome_data.items():
            result[outcome] = {
                "count": len(scores),
                "avg_success_rate": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_failed_canaries(self) -> list[dict[str, Any]]:
        """Return canaries where outcome is ROLLED_BACK or INCONCLUSIVE."""
        failed_outcomes = {
            CanaryOutcome.ROLLED_BACK,
            CanaryOutcome.INCONCLUSIVE,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.canary_outcome in failed_outcomes:
                results.append(
                    {
                        "record_id": r.id,
                        "canary_id": r.canary_id,
                        "canary_outcome": r.canary_outcome.value,
                        "canary_signal": r.canary_signal.value,
                        "success_rate": r.success_rate,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["success_rate"], reverse=False)
        return results

    def rank_by_success_rate(self) -> list[dict[str, Any]]:
        """Group by service, avg success_rate, sort asc (worst first)."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            service_scores.setdefault(r.service, []).append(r.success_rate)
        results: list[dict[str, Any]] = []
        for service, scores in service_scores.items():
            results.append(
                {
                    "service": service,
                    "avg_success_rate": round(sum(scores) / len(scores), 2),
                    "canary_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_success_rate"], reverse=False)
        return results

    def detect_canary_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [m.metric_score for m in self._metrics]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> DeployCanaryReport:
        by_outcome: dict[str, int] = {}
        by_signal: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        for r in self._records:
            by_outcome[r.canary_outcome.value] = by_outcome.get(r.canary_outcome.value, 0) + 1
            by_signal[r.canary_signal.value] = by_signal.get(r.canary_signal.value, 0) + 1
            by_strategy[r.canary_strategy.value] = by_strategy.get(r.canary_strategy.value, 0) + 1
        failed_canaries = sum(
            1
            for r in self._records
            if r.canary_outcome in {CanaryOutcome.ROLLED_BACK, CanaryOutcome.INCONCLUSIVE}
        )
        avg_success_rate = (
            round(
                sum(r.success_rate for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        failed = self.identify_failed_canaries()
        top_failed = [f["canary_id"] for f in failed]
        recs: list[str] = []
        if failed:
            recs.append(f"{len(failed)} failed canary(ies) detected — review deployment configs")
        low_rate = sum(1 for r in self._records if r.success_rate < self._min_success_rate)
        if low_rate > 0:
            recs.append(
                f"{low_rate} canary(ies) below success threshold ({self._min_success_rate}%)"
            )
        if not recs:
            recs.append("Canary deployment levels are acceptable")
        return DeployCanaryReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            failed_canaries=failed_canaries,
            avg_success_rate=avg_success_rate,
            by_outcome=by_outcome,
            by_signal=by_signal,
            by_strategy=by_strategy,
            top_failed=top_failed,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("deploy_canary_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        outcome_dist: dict[str, int] = {}
        for r in self._records:
            key = r.canary_outcome.value
            outcome_dist[key] = outcome_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_success_rate": self._min_success_rate,
            "outcome_distribution": outcome_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_canaries": len({r.canary_id for r in self._records}),
        }
