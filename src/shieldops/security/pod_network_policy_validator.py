"""Pod Network Policy Validator — validate Kubernetes network policies for compliance."""

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
    INGRESS = "ingress"
    EGRESS = "egress"
    BOTH = "both"
    NONE = "none"
    DEFAULT = "default"


class ValidationResult(StrEnum):
    COMPLIANT = "compliant"
    VIOLATION = "violation"
    MISSING = "missing"
    OVERPERMISSIVE = "overpermissive"
    REDUNDANT = "redundant"


class PolicyAction(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    LOG = "log"
    ALERT = "alert"
    QUARANTINE = "quarantine"


# --- Models ---


class NetworkPolicyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str = ""
    policy_scope: PolicyScope = PolicyScope.INGRESS
    validation_result: ValidationResult = ValidationResult.COMPLIANT
    policy_action: PolicyAction = PolicyAction.ALLOW
    validation_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class NetworkPolicyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str = ""
    policy_scope: PolicyScope = PolicyScope.INGRESS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PodNetworkPolicyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_validation_score: float = 0.0
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PodNetworkPolicyValidator:
    """Validate Kubernetes network policies for compliance, overpermissive rules, and gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        validation_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._validation_gap_threshold = validation_gap_threshold
        self._records: list[NetworkPolicyRecord] = []
        self._analyses: list[NetworkPolicyAnalysis] = []
        logger.info(
            "pod_network_policy_validator.initialized",
            max_records=max_records,
            validation_gap_threshold=validation_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_validation(
        self,
        policy_id: str,
        policy_scope: PolicyScope = PolicyScope.INGRESS,
        validation_result: ValidationResult = ValidationResult.COMPLIANT,
        policy_action: PolicyAction = PolicyAction.ALLOW,
        validation_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> NetworkPolicyRecord:
        record = NetworkPolicyRecord(
            policy_id=policy_id,
            policy_scope=policy_scope,
            validation_result=validation_result,
            policy_action=policy_action,
            validation_score=validation_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "pod_network_policy_validator.validation_recorded",
            record_id=record.id,
            policy_id=policy_id,
            policy_scope=policy_scope.value,
            validation_result=validation_result.value,
        )
        return record

    def get_validation(self, record_id: str) -> NetworkPolicyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_validations(
        self,
        policy_scope: PolicyScope | None = None,
        validation_result: ValidationResult | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[NetworkPolicyRecord]:
        results = list(self._records)
        if policy_scope is not None:
            results = [r for r in results if r.policy_scope == policy_scope]
        if validation_result is not None:
            results = [r for r in results if r.validation_result == validation_result]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        policy_id: str,
        policy_scope: PolicyScope = PolicyScope.INGRESS,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> NetworkPolicyAnalysis:
        analysis = NetworkPolicyAnalysis(
            policy_id=policy_id,
            policy_scope=policy_scope,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "pod_network_policy_validator.analysis_added",
            policy_id=policy_id,
            policy_scope=policy_scope.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_scope_distribution(self) -> dict[str, Any]:
        """Group by policy_scope; return count and avg validation_score."""
        scope_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.policy_scope.value
            scope_data.setdefault(key, []).append(r.validation_score)
        result: dict[str, Any] = {}
        for scope, scores in scope_data.items():
            result[scope] = {
                "count": len(scores),
                "avg_validation_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_validation_gaps(self) -> list[dict[str, Any]]:
        """Return records where validation_score < validation_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.validation_score < self._validation_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "policy_id": r.policy_id,
                        "policy_scope": r.policy_scope.value,
                        "validation_score": r.validation_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["validation_score"])

    def rank_by_validation(self) -> list[dict[str, Any]]:
        """Group by service, avg validation_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.validation_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_validation_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_validation_score"])
        return results

    def detect_validation_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
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

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> PodNetworkPolicyReport:
        by_scope: dict[str, int] = {}
        by_result: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_scope[r.policy_scope.value] = by_scope.get(r.policy_scope.value, 0) + 1
            by_result[r.validation_result.value] = by_result.get(r.validation_result.value, 0) + 1
            by_action[r.policy_action.value] = by_action.get(r.policy_action.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.validation_score < self._validation_gap_threshold
        )
        scores = [r.validation_score for r in self._records]
        avg_validation_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_validation_gaps()
        top_gaps = [o["policy_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} policy(ies) below validation threshold "
                f"({self._validation_gap_threshold})"
            )
        if self._records and avg_validation_score < self._validation_gap_threshold:
            recs.append(
                f"Avg validation score {avg_validation_score} below threshold "
                f"({self._validation_gap_threshold})"
            )
        if not recs:
            recs.append("Pod network policy validation is healthy")
        return PodNetworkPolicyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_validation_score=avg_validation_score,
            by_scope=by_scope,
            by_result=by_result,
            by_action=by_action,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("pod_network_policy_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        scope_dist: dict[str, int] = {}
        for r in self._records:
            key = r.policy_scope.value
            scope_dist[key] = scope_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "validation_gap_threshold": self._validation_gap_threshold,
            "scope_distribution": scope_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
