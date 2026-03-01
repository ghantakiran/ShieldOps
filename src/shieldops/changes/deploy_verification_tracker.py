"""Deploy Verification Tracker — track deployment verification steps, detect skipped checks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VerificationStep(StrEnum):
    SMOKE_TEST = "smoke_test"
    INTEGRATION_TEST = "integration_test"
    CANARY_CHECK = "canary_check"
    HEALTH_PROBE = "health_probe"
    ROLLBACK_TEST = "rollback_test"


class VerificationResult(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    PARTIAL = "partial"


class VerificationScope(StrEnum):
    UNIT = "unit"
    SERVICE = "service"
    CLUSTER = "cluster"
    REGION = "region"
    GLOBAL = "global"


# --- Models ---


class VerificationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deploy_id: str = ""
    verification_step: VerificationStep = VerificationStep.SMOKE_TEST
    verification_result: VerificationResult = VerificationResult.PASSED
    verification_scope: VerificationScope = VerificationScope.UNIT
    coverage_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class VerificationMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deploy_id: str = ""
    verification_step: VerificationStep = VerificationStep.SMOKE_TEST
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeployVerificationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    failed_verifications: int = 0
    avg_coverage_pct: float = 0.0
    by_step: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    top_failing: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeployVerificationTracker:
    """Track deployment verification steps, detect skipped checks."""

    def __init__(
        self,
        max_records: int = 200000,
        min_coverage_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_coverage_pct = min_coverage_pct
        self._records: list[VerificationRecord] = []
        self._metrics: list[VerificationMetric] = []
        logger.info(
            "deploy_verification_tracker.initialized",
            max_records=max_records,
            min_coverage_pct=min_coverage_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_verification(
        self,
        deploy_id: str,
        verification_step: VerificationStep = VerificationStep.SMOKE_TEST,
        verification_result: VerificationResult = VerificationResult.PASSED,
        verification_scope: VerificationScope = VerificationScope.UNIT,
        coverage_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> VerificationRecord:
        record = VerificationRecord(
            deploy_id=deploy_id,
            verification_step=verification_step,
            verification_result=verification_result,
            verification_scope=verification_scope,
            coverage_pct=coverage_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deploy_verification_tracker.verification_recorded",
            record_id=record.id,
            deploy_id=deploy_id,
            verification_step=verification_step.value,
            verification_result=verification_result.value,
        )
        return record

    def get_verification(self, record_id: str) -> VerificationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_verifications(
        self,
        step: VerificationStep | None = None,
        result: VerificationResult | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[VerificationRecord]:
        results = list(self._records)
        if step is not None:
            results = [r for r in results if r.verification_step == step]
        if result is not None:
            results = [r for r in results if r.verification_result == result]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        deploy_id: str,
        verification_step: VerificationStep = VerificationStep.SMOKE_TEST,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> VerificationMetric:
        metric = VerificationMetric(
            deploy_id=deploy_id,
            verification_step=verification_step,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "deploy_verification_tracker.metric_added",
            deploy_id=deploy_id,
            verification_step=verification_step.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_verification_distribution(self) -> dict[str, Any]:
        """Group by verification_step; return count and avg coverage_pct."""
        step_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.verification_step.value
            step_data.setdefault(key, []).append(r.coverage_pct)
        result: dict[str, Any] = {}
        for step, scores in step_data.items():
            result[step] = {
                "count": len(scores),
                "avg_coverage_pct": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_failed_verifications(self) -> list[dict[str, Any]]:
        """Return records where verification_result is FAILED or SKIPPED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.verification_result in (
                VerificationResult.FAILED,
                VerificationResult.SKIPPED,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "deploy_id": r.deploy_id,
                        "verification_step": r.verification_step.value,
                        "verification_result": r.verification_result.value,
                        "coverage_pct": r.coverage_pct,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_coverage(self) -> list[dict[str, Any]]:
        """Group by service, avg coverage_pct, sort ascending (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.coverage_pct)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_coverage_pct": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_pct"])
        return results

    def detect_verification_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [m.metric_score for m in self._metrics]
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

    def generate_report(self) -> DeployVerificationReport:
        by_step: dict[str, int] = {}
        by_result: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for r in self._records:
            by_step[r.verification_step.value] = by_step.get(r.verification_step.value, 0) + 1
            by_result[r.verification_result.value] = (
                by_result.get(r.verification_result.value, 0) + 1
            )
            by_scope[r.verification_scope.value] = by_scope.get(r.verification_scope.value, 0) + 1
        failed_verifications = sum(
            1
            for r in self._records
            if r.verification_result in (VerificationResult.FAILED, VerificationResult.SKIPPED)
        )
        scores = [r.coverage_pct for r in self._records]
        avg_coverage_pct = round(sum(scores) / len(scores), 2) if scores else 0.0
        failed_list = self.identify_failed_verifications()
        top_failing = [o["deploy_id"] for o in failed_list[:5]]
        recs: list[str] = []
        if self._records and avg_coverage_pct < self._min_coverage_pct:
            recs.append(
                f"Avg coverage {avg_coverage_pct}% below threshold ({self._min_coverage_pct}%)"
            )
        if failed_verifications > 0:
            recs.append(
                f"{failed_verifications} failed/skipped verification(s) — review deployment checks"
            )
        if not recs:
            recs.append("Deployment verification coverage is healthy")
        return DeployVerificationReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            failed_verifications=failed_verifications,
            avg_coverage_pct=avg_coverage_pct,
            by_step=by_step,
            by_result=by_result,
            by_scope=by_scope,
            top_failing=top_failing,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("deploy_verification_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        step_dist: dict[str, int] = {}
        for r in self._records:
            key = r.verification_step.value
            step_dist[key] = step_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_coverage_pct": self._min_coverage_pct,
            "step_distribution": step_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
