"""Adaptive Retry Strategy Engine —
evaluate retry policies, detect persistent failures,
and optimize backoff parameters with learning."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RetryPolicy(StrEnum):
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    JITTERED = "jittered"
    ADAPTIVE = "adaptive"


class FailureCategory(StrEnum):
    TRANSIENT = "transient"
    PERSISTENT = "persistent"
    INTERMITTENT = "intermittent"
    CASCADING = "cascading"


class RetryOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    EXHAUSTED = "exhausted"
    CIRCUIT_BROKEN = "circuit_broken"
    ESCALATED = "escalated"


# --- Models ---


class AdaptiveRetryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    retry_policy: RetryPolicy = RetryPolicy.EXPONENTIAL
    failure_category: FailureCategory = FailureCategory.TRANSIENT
    outcome: RetryOutcome = RetryOutcome.SUCCEEDED
    retry_count: int = 0
    total_delay_ms: float = 0.0
    success_rate: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AdaptiveRetryAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    avg_retry_count: float = 0.0
    best_policy: RetryPolicy = RetryPolicy.EXPONENTIAL
    dominant_failure: FailureCategory = FailureCategory.TRANSIENT
    avg_success_rate: float = 0.0
    record_count: int = 0
    efficiency_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AdaptiveRetryReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_success_rate: float = 0.0
    by_retry_policy: dict[str, int] = Field(default_factory=dict)
    by_failure_category: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    top_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AdaptiveRetryStrategyEngine:
    """Optimize retry strategies with learning, detect persistent
    failures, and tune backoff parameters per service."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AdaptiveRetryRecord] = []
        self._analyses: dict[str, AdaptiveRetryAnalysis] = {}
        logger.info(
            "adaptive_retry_strategy.init",
            max_records=max_records,
        )

    def add_record(
        self,
        service_id: str = "",
        retry_policy: RetryPolicy = RetryPolicy.EXPONENTIAL,
        failure_category: FailureCategory = FailureCategory.TRANSIENT,
        outcome: RetryOutcome = RetryOutcome.SUCCEEDED,
        retry_count: int = 0,
        total_delay_ms: float = 0.0,
        success_rate: float = 0.0,
        description: str = "",
    ) -> AdaptiveRetryRecord:
        record = AdaptiveRetryRecord(
            service_id=service_id,
            retry_policy=retry_policy,
            failure_category=failure_category,
            outcome=outcome,
            retry_count=retry_count,
            total_delay_ms=total_delay_ms,
            success_rate=success_rate,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "adaptive_retry.record_added",
            record_id=record.id,
            service_id=service_id,
        )
        return record

    def process(self, key: str) -> AdaptiveRetryAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        svc_recs = [r for r in self._records if r.service_id == rec.service_id]
        retry_counts = [r.retry_count for r in svc_recs]
        success_rates = [r.success_rate for r in svc_recs]
        avg_retries = round(sum(retry_counts) / len(retry_counts), 2) if retry_counts else 0.0
        avg_success = round(sum(success_rates) / len(success_rates), 2) if success_rates else 0.0
        policy_success: dict[str, list[float]] = {}
        for r in svc_recs:
            policy_success.setdefault(r.retry_policy.value, []).append(r.success_rate)
        best_policy_val = (
            max(
                policy_success,
                key=lambda x: sum(policy_success[x]) / len(policy_success[x]),
            )
            if policy_success
            else RetryPolicy.EXPONENTIAL.value
        )
        best_policy = RetryPolicy(best_policy_val)
        failure_counts: dict[str, int] = {}
        for r in svc_recs:
            failure_counts[r.failure_category.value] = (
                failure_counts.get(r.failure_category.value, 0) + 1
            )
        dominant_failure = (
            FailureCategory(max(failure_counts, key=lambda x: failure_counts[x]))
            if failure_counts
            else FailureCategory.TRANSIENT
        )
        efficiency = round(avg_success / max(avg_retries, 1) * 100, 2)
        analysis = AdaptiveRetryAnalysis(
            service_id=rec.service_id,
            avg_retry_count=avg_retries,
            best_policy=best_policy,
            dominant_failure=dominant_failure,
            avg_success_rate=avg_success,
            record_count=len(svc_recs),
            efficiency_score=efficiency,
            description=f"Service {rec.service_id} best policy {best_policy.value}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> AdaptiveRetryReport:
        by_rp: dict[str, int] = {}
        by_fc: dict[str, int] = {}
        by_oc: dict[str, int] = {}
        success_rates: list[float] = []
        for r in self._records:
            by_rp[r.retry_policy.value] = by_rp.get(r.retry_policy.value, 0) + 1
            by_fc[r.failure_category.value] = by_fc.get(r.failure_category.value, 0) + 1
            by_oc[r.outcome.value] = by_oc.get(r.outcome.value, 0) + 1
            success_rates.append(r.success_rate)
        avg = round(sum(success_rates) / len(success_rates), 2) if success_rates else 0.0
        svc_totals: dict[str, float] = {}
        for r in self._records:
            svc_totals[r.service_id] = svc_totals.get(r.service_id, 0.0) + r.success_rate
        ranked = sorted(
            svc_totals,
            key=lambda x: svc_totals[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        persistent = by_fc.get("persistent", 0)
        if persistent > 0:
            recs.append(f"{persistent} persistent failures — escalate to on-call")
        cascading = by_fc.get("cascading", 0)
        if cascading > 0:
            recs.append(f"{cascading} cascading failures — enable circuit breaker")
        if not recs:
            recs.append("Retry strategy performance is healthy")
        return AdaptiveRetryReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_success_rate=avg,
            by_retry_policy=by_rp,
            by_failure_category=by_fc,
            by_outcome=by_oc,
            top_services=ranked,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            dist[r.retry_policy.value] = dist.get(r.retry_policy.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "retry_policy_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("adaptive_retry_strategy.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def evaluate_retry_policies(self) -> list[dict[str, Any]]:
        """Evaluate success rate and efficiency of each retry policy."""
        policy_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            entry = policy_data.setdefault(
                r.retry_policy.value,
                {"success_rates": [], "retry_counts": [], "delays": []},
            )
            entry["success_rates"].append(r.success_rate)
            entry["retry_counts"].append(r.retry_count)
            entry["delays"].append(r.total_delay_ms)
        results: list[dict[str, Any]] = []
        for policy, data in policy_data.items():
            avg_success = (
                round(sum(data["success_rates"]) / len(data["success_rates"]), 2)
                if data["success_rates"]
                else 0.0
            )
            avg_retries = (
                round(sum(data["retry_counts"]) / len(data["retry_counts"]), 1)
                if data["retry_counts"]
                else 1.0
            )
            avg_delay = (
                round(sum(data["delays"]) / len(data["delays"]), 1) if data["delays"] else 0.0
            )
            efficiency = round(avg_success / max(avg_retries, 1) * 100, 2)
            results.append(
                {
                    "policy": policy,
                    "avg_success_rate": avg_success,
                    "avg_retries": avg_retries,
                    "avg_delay_ms": avg_delay,
                    "efficiency": efficiency,
                    "sample_count": len(data["success_rates"]),
                }
            )
        results.sort(key=lambda x: x["efficiency"], reverse=True)
        return results

    def detect_persistent_failures(self) -> list[dict[str, Any]]:
        """Detect services with persistent or recurring failure patterns."""
        svc_data: dict[str, list[AdaptiveRetryRecord]] = {}
        for r in self._records:
            svc_data.setdefault(r.service_id, []).append(r)
        results: list[dict[str, Any]] = []
        for svc, recs in svc_data.items():
            persistent_count = sum(
                1 for r in recs if r.failure_category == FailureCategory.PERSISTENT
            )
            exhausted_count = sum(1 for r in recs if r.outcome == RetryOutcome.EXHAUSTED)
            success_rates = [r.success_rate for r in recs]
            avg_success = (
                round(sum(success_rates) / len(success_rates), 2) if success_rates else 0.0
            )
            persistent_rate = round(persistent_count / max(len(recs), 1), 2)
            is_persistent = persistent_rate > 0.3 or avg_success < 0.5
            results.append(
                {
                    "service_id": svc,
                    "persistent_failure_rate": persistent_rate,
                    "exhausted_retries": exhausted_count,
                    "avg_success_rate": avg_success,
                    "is_persistent_failure": is_persistent,
                    "severity": "critical"
                    if avg_success < 0.3
                    else "high"
                    if is_persistent
                    else "low",
                    "record_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["persistent_failure_rate"], reverse=True)
        return results

    def optimize_backoff_parameters(self) -> list[dict[str, Any]]:
        """Recommend optimal backoff parameters per failure category."""
        category_data: dict[str, list[AdaptiveRetryRecord]] = {}
        for r in self._records:
            category_data.setdefault(r.failure_category.value, []).append(r)
        base_delays = {
            "transient": 100,
            "intermittent": 500,
            "persistent": 2000,
            "cascading": 5000,
        }
        results: list[dict[str, Any]] = []
        for category, recs in category_data.items():
            success_rates = [r.success_rate for r in recs]
            delays = [r.total_delay_ms for r in recs]
            avg_success = (
                round(sum(success_rates) / len(success_rates), 2) if success_rates else 0.0
            )
            avg_delay = round(sum(delays) / len(delays), 1) if delays else 0.0
            base = base_delays.get(category, 1000)
            multiplier = 2.0 if avg_success < 0.5 else 1.0
            recommended_base_ms = round(base * multiplier, 0)
            results.append(
                {
                    "failure_category": category,
                    "avg_success_rate": avg_success,
                    "avg_delay_ms": avg_delay,
                    "recommended_base_delay_ms": recommended_base_ms,
                    "recommended_policy": ("adaptive" if avg_success < 0.5 else "jittered"),
                    "sample_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["avg_success_rate"])
        return results
