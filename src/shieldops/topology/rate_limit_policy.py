"""Rate Limit Policy Manager — manage service-to-service rate limit policies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PolicyScope(StrEnum):
    SERVICE = "service"
    ENDPOINT = "endpoint"
    CONSUMER = "consumer"
    GLOBAL = "global"
    TENANT = "tenant"


class ViolationType(StrEnum):
    SOFT_LIMIT = "soft_limit"
    HARD_LIMIT = "hard_limit"
    BURST = "burst"
    SUSTAINED = "sustained"
    CASCADING = "cascading"


class PolicyEffectiveness(StrEnum):
    OPTIMAL = "optimal"
    CONSERVATIVE = "conservative"
    AGGRESSIVE = "aggressive"
    INEFFECTIVE = "ineffective"
    UNTUNED = "untuned"


# --- Models ---


class RateLimitPolicyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    scope: PolicyScope = PolicyScope.SERVICE
    requests_per_second: int = 0
    burst_limit: int = 0
    effectiveness: PolicyEffectiveness = PolicyEffectiveness.UNTUNED
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RateLimitViolation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    violation_type: ViolationType = ViolationType.SOFT_LIMIT
    count: int = 0
    consumer: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RateLimitPolicyReport(BaseModel):
    total_policies: int = 0
    total_violations: int = 0
    avg_requests_per_second: float = 0.0
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_effectiveness: dict[str, int] = Field(default_factory=dict)
    untuned_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RateLimitPolicyManager:
    """Manage service-to-service rate limit policies and violations."""

    def __init__(
        self,
        max_records: int = 200000,
        violation_threshold: int = 100,
    ) -> None:
        self._max_records = max_records
        self._violation_threshold = violation_threshold
        self._records: list[RateLimitPolicyRecord] = []
        self._violations: list[RateLimitViolation] = []
        logger.info(
            "rate_limit_policy.initialized",
            max_records=max_records,
            violation_threshold=violation_threshold,
        )

    # -- record / get / list ---------------------------------------------

    def record_policy(
        self,
        service_name: str,
        scope: PolicyScope = PolicyScope.SERVICE,
        requests_per_second: int = 0,
        burst_limit: int = 0,
        effectiveness: PolicyEffectiveness = PolicyEffectiveness.UNTUNED,
        details: str = "",
    ) -> RateLimitPolicyRecord:
        record = RateLimitPolicyRecord(
            service_name=service_name,
            scope=scope,
            requests_per_second=requests_per_second,
            burst_limit=burst_limit,
            effectiveness=effectiveness,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "rate_limit_policy.policy_recorded",
            record_id=record.id,
            service_name=service_name,
            scope=scope.value,
        )
        return record

    def get_policy(self, record_id: str) -> RateLimitPolicyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_policies(
        self,
        service_name: str | None = None,
        scope: PolicyScope | None = None,
        limit: int = 50,
    ) -> list[RateLimitPolicyRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if scope is not None:
            results = [r for r in results if r.scope == scope]
        return results[-limit:]

    def record_violation(
        self,
        service_name: str,
        violation_type: ViolationType = ViolationType.SOFT_LIMIT,
        count: int = 0,
        consumer: str = "",
        details: str = "",
    ) -> RateLimitViolation:
        violation = RateLimitViolation(
            service_name=service_name,
            violation_type=violation_type,
            count=count,
            consumer=consumer,
            details=details,
        )
        self._violations.append(violation)
        if len(self._violations) > self._max_records:
            self._violations = self._violations[-self._max_records :]
        logger.info(
            "rate_limit_policy.violation_recorded",
            service_name=service_name,
            violation_type=violation_type.value,
            count=count,
        )
        return violation

    # -- domain operations -----------------------------------------------

    def analyze_policy_effectiveness(self, service_name: str) -> dict[str, Any]:
        """Analyze effectiveness of rate limit policies for a service."""
        policies = [r for r in self._records if r.service_name == service_name]
        if not policies:
            return {"service_name": service_name, "status": "no_data"}
        eff_breakdown: dict[str, int] = {}
        total_rps = 0
        for p in policies:
            key = p.effectiveness.value
            eff_breakdown[key] = eff_breakdown.get(key, 0) + 1
            total_rps += p.requests_per_second
        avg_rps = round(total_rps / len(policies), 2) if policies else 0.0
        return {
            "service_name": service_name,
            "total_policies": len(policies),
            "effectiveness_breakdown": eff_breakdown,
            "avg_requests_per_second": avg_rps,
        }

    def identify_untuned_policies(self) -> list[dict[str, Any]]:
        """Find policies with effectiveness == UNTUNED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.effectiveness == PolicyEffectiveness.UNTUNED:
                results.append(
                    {
                        "id": r.id,
                        "service_name": r.service_name,
                        "scope": r.scope.value,
                        "requests_per_second": r.requests_per_second,
                        "effectiveness": r.effectiveness.value,
                    }
                )
        return results

    def rank_most_violated_services(self) -> list[dict[str, Any]]:
        """Aggregate violations by service_name, sort desc by count."""
        svc_counts: dict[str, int] = {}
        for v in self._violations:
            svc_counts[v.service_name] = svc_counts.get(v.service_name, 0) + v.count
        results: list[dict[str, Any]] = [
            {"service_name": svc, "total_violations": cnt} for svc, cnt in svc_counts.items()
        ]
        results.sort(key=lambda x: x["total_violations"], reverse=True)
        return results

    def recommend_limit_adjustments(self) -> list[dict[str, Any]]:
        """For services with violations > threshold, recommend adjustment."""
        svc_counts: dict[str, int] = {}
        for v in self._violations:
            svc_counts[v.service_name] = svc_counts.get(v.service_name, 0) + v.count
        results: list[dict[str, Any]] = []
        for svc, cnt in svc_counts.items():
            if cnt > self._violation_threshold:
                results.append(
                    {
                        "service_name": svc,
                        "total_violations": cnt,
                        "recommendation": "increase_limit",
                        "reason": (
                            f"Violations ({cnt}) exceed threshold ({self._violation_threshold})"
                        ),
                    }
                )
        results.sort(key=lambda x: x["total_violations"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> RateLimitPolicyReport:
        by_scope: dict[str, int] = {}
        by_effectiveness: dict[str, int] = {}
        total_rps = 0
        for r in self._records:
            by_scope[r.scope.value] = by_scope.get(r.scope.value, 0) + 1
            by_effectiveness[r.effectiveness.value] = (
                by_effectiveness.get(r.effectiveness.value, 0) + 1
            )
            total_rps += r.requests_per_second
        avg_rps = round(total_rps / len(self._records), 2) if self._records else 0.0
        untuned = sum(1 for r in self._records if r.effectiveness == PolicyEffectiveness.UNTUNED)
        recs: list[str] = []
        if untuned > 0:
            recs.append(f"{untuned} policy(ies) need tuning")
        adjustments = len(self.recommend_limit_adjustments())
        if adjustments > 0:
            recs.append(f"{adjustments} service(s) need limit adjustments")
        if not recs:
            recs.append("Rate limit policies are well-tuned")
        return RateLimitPolicyReport(
            total_policies=len(self._records),
            total_violations=len(self._violations),
            avg_requests_per_second=avg_rps,
            by_scope=by_scope,
            by_effectiveness=by_effectiveness,
            untuned_count=untuned,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._violations.clear()
        logger.info("rate_limit_policy.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        scope_dist: dict[str, int] = {}
        for r in self._records:
            key = r.scope.value
            scope_dist[key] = scope_dist.get(key, 0) + 1
        return {
            "total_policies": len(self._records),
            "total_violations": len(self._violations),
            "violation_threshold": self._violation_threshold,
            "scope_distribution": scope_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
