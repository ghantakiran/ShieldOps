"""Deployment Canary Scorer — score canary deployments and metric comparisons."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CanaryMetric(StrEnum):
    ERROR_RATE = "error_rate"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    RESOURCE_USAGE = "resource_usage"
    CUSTOM = "custom"


class CanaryVerdict(StrEnum):
    PROMOTE = "promote"
    ROLLBACK = "rollback"
    EXTEND = "extend"
    MANUAL_REVIEW = "manual_review"
    INCONCLUSIVE = "inconclusive"


class CanaryStage(StrEnum):
    BASELINE = "baseline"
    CANARY_1PCT = "canary_1pct"
    CANARY_5PCT = "canary_5pct"
    CANARY_25PCT = "canary_25pct"
    FULL_ROLLOUT = "full_rollout"


# --- Models ---


class CanaryRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    deployment_id: str = ""
    service: str = ""
    stage: CanaryStage = CanaryStage.BASELINE
    canary_score: float = 0.0
    verdict: CanaryVerdict = CanaryVerdict.INCONCLUSIVE
    team: str = ""
    duration_minutes: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class MetricComparison(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    deployment_id: str = ""
    metric: CanaryMetric = CanaryMetric.ERROR_RATE
    baseline_value: float = 0.0
    canary_value: float = 0.0
    deviation_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class CanaryScorerReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_comparisons: int = 0
    avg_canary_score: float = 0.0
    by_verdict: dict[str, int] = Field(default_factory=dict)
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_metric: dict[str, int] = Field(default_factory=dict)
    failed_canaries: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentCanaryScorer:
    """Score canary deployments and compare metrics."""

    def __init__(
        self,
        max_records: int = 200000,
        min_canary_score: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_canary_score = min_canary_score
        self._records: list[CanaryRecord] = []
        self._comparisons: list[MetricComparison] = []
        logger.info(
            "canary_scorer.initialized",
            max_records=max_records,
            min_canary_score=min_canary_score,
        )

    # -- record / get / list -----------------------------------------

    def record_canary(
        self,
        deployment_id: str,
        service: str,
        stage: CanaryStage = CanaryStage.BASELINE,
        canary_score: float = 0.0,
        verdict: CanaryVerdict = (CanaryVerdict.INCONCLUSIVE),
        team: str = "",
        duration_minutes: float = 0.0,
        details: str = "",
    ) -> CanaryRecord:
        record = CanaryRecord(
            deployment_id=deployment_id,
            service=service,
            stage=stage,
            canary_score=canary_score,
            verdict=verdict,
            team=team,
            duration_minutes=duration_minutes,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "canary_scorer.canary_recorded",
            record_id=record.id,
            deployment_id=deployment_id,
            service=service,
            verdict=verdict.value,
        )
        return record

    def get_canary(self, record_id: str) -> CanaryRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_canaries(
        self,
        verdict: CanaryVerdict | None = None,
        stage: CanaryStage | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[CanaryRecord]:
        results = list(self._records)
        if verdict is not None:
            results = [r for r in results if r.verdict == verdict]
        if stage is not None:
            results = [r for r in results if r.stage == stage]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def add_comparison(
        self,
        deployment_id: str,
        metric: CanaryMetric = CanaryMetric.ERROR_RATE,
        baseline_value: float = 0.0,
        canary_value: float = 0.0,
        deviation_pct: float = 0.0,
    ) -> MetricComparison:
        comparison = MetricComparison(
            deployment_id=deployment_id,
            metric=metric,
            baseline_value=baseline_value,
            canary_value=canary_value,
            deviation_pct=deviation_pct,
        )
        self._comparisons.append(comparison)
        if len(self._comparisons) > self._max_records:
            self._comparisons = self._comparisons[-self._max_records :]
        logger.info(
            "canary_scorer.comparison_added",
            comparison_id=comparison.id,
            deployment_id=deployment_id,
            metric=metric.value,
        )
        return comparison

    # -- domain operations -------------------------------------------

    def analyze_canary_success_rate(
        self,
    ) -> dict[str, Any]:
        """Calculate overall canary success rate."""
        total = len(self._records)
        if total == 0:
            return {"status": "no_data"}
        promoted = sum(1 for r in self._records if r.verdict == CanaryVerdict.PROMOTE)
        rolled_back = sum(1 for r in self._records if r.verdict == CanaryVerdict.ROLLBACK)
        success_rate = round(promoted / total * 100.0, 2)
        return {
            "total": total,
            "promoted": promoted,
            "rolled_back": rolled_back,
            "success_rate_pct": success_rate,
        }

    def identify_failed_canaries(
        self,
    ) -> list[dict[str, Any]]:
        """Find canaries with score below threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.canary_score < self._min_canary_score:
                results.append(
                    {
                        "deployment_id": (r.deployment_id),
                        "service": r.service,
                        "canary_score": r.canary_score,
                        "verdict": r.verdict.value,
                    }
                )
        results.sort(key=lambda x: x["canary_score"])
        return results

    def rank_by_canary_score(
        self,
    ) -> list[dict[str, Any]]:
        """Average canary score per service, desc."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.canary_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service": svc,
                    "avg_canary_score": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_canary_score"],
            reverse=True,
        )
        return results

    def detect_canary_trends(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with >3 canary records."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service] = svc_counts.get(r.service, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service": svc,
                        "canary_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["canary_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> CanaryScorerReport:
        by_verdict: dict[str, int] = {}
        by_stage: dict[str, int] = {}
        by_metric: dict[str, int] = {}
        for r in self._records:
            vd = r.verdict.value
            by_verdict[vd] = by_verdict.get(vd, 0) + 1
            sg = r.stage.value
            by_stage[sg] = by_stage.get(sg, 0) + 1
        for c in self._comparisons:
            mt = c.metric.value
            by_metric[mt] = by_metric.get(mt, 0) + 1
        total = len(self._records)
        avg_score = (
            round(
                sum(r.canary_score for r in self._records) / total,
                2,
            )
            if total
            else 0.0
        )
        failed = self.identify_failed_canaries()
        failed_ids = [f["deployment_id"] for f in failed[:10]]
        recs: list[str] = []
        if failed:
            recs.append(f"{len(failed)} canary(ies) below {self._min_canary_score} score threshold")
        rollback_count = sum(1 for r in self._records if r.verdict == CanaryVerdict.ROLLBACK)
        if rollback_count > 0:
            recs.append(f"{rollback_count} canary rollback(s) recorded")
        if not recs:
            recs.append("Canary scores within acceptable limits")
        return CanaryScorerReport(
            total_records=total,
            total_comparisons=len(self._comparisons),
            avg_canary_score=avg_score,
            by_verdict=by_verdict,
            by_stage=by_stage,
            by_metric=by_metric,
            failed_canaries=failed_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._comparisons.clear()
        logger.info("canary_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        verdict_dist: dict[str, int] = {}
        for r in self._records:
            key = r.verdict.value
            verdict_dist[key] = verdict_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_comparisons": len(self._comparisons),
            "min_canary_score": (self._min_canary_score),
            "verdict_distribution": verdict_dist,
            "unique_services": len({r.service for r in self._records}),
        }
