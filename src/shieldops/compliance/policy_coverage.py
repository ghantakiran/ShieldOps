"""Policy Coverage Analyzer — analyze policy coverage, identify gaps, track compliance."""

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
    ORGANIZATION_WIDE = "organization_wide"
    DEPARTMENT = "department"
    TEAM = "team"
    SERVICE = "service"
    ENVIRONMENT = "environment"


class CoverageStatus(StrEnum):
    FULLY_COVERED = "fully_covered"
    PARTIALLY_COVERED = "partially_covered"
    GAP_IDENTIFIED = "gap_identified"
    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"


class PolicyType(StrEnum):
    ACCESS_CONTROL = "access_control"
    DATA_HANDLING = "data_handling"
    CHANGE_MANAGEMENT = "change_management"
    INCIDENT_RESPONSE = "incident_response"
    ENCRYPTION = "encryption"


# --- Models ---


class PolicyCoverageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    policy_scope: PolicyScope = PolicyScope.ORGANIZATION_WIDE
    coverage_status: CoverageStatus = CoverageStatus.PENDING
    policy_type: PolicyType = PolicyType.ACCESS_CONTROL
    coverage_pct: float = 0.0
    owner: str = ""
    created_at: float = Field(default_factory=time.time)


class CoverageAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_name: str = ""
    policy_scope: PolicyScope = PolicyScope.ORGANIZATION_WIDE
    assessment_score: float = 0.0
    policies_evaluated: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyCoverageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    covered_scopes: int = 0
    avg_coverage_pct: float = 0.0
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    gap_policies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PolicyCoverageAnalyzer:
    """Analyze policy coverage, identify gaps, track compliance across scopes."""

    def __init__(
        self,
        max_records: int = 200000,
        min_policy_coverage_pct: float = 85.0,
    ) -> None:
        self._max_records = max_records
        self._min_policy_coverage_pct = min_policy_coverage_pct
        self._records: list[PolicyCoverageRecord] = []
        self._assessments: list[CoverageAssessment] = []
        logger.info(
            "policy_coverage.initialized",
            max_records=max_records,
            min_policy_coverage_pct=min_policy_coverage_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_coverage(
        self,
        policy_name: str,
        policy_scope: PolicyScope = PolicyScope.ORGANIZATION_WIDE,
        coverage_status: CoverageStatus = CoverageStatus.PENDING,
        policy_type: PolicyType = PolicyType.ACCESS_CONTROL,
        coverage_pct: float = 0.0,
        owner: str = "",
    ) -> PolicyCoverageRecord:
        record = PolicyCoverageRecord(
            policy_name=policy_name,
            policy_scope=policy_scope,
            coverage_status=coverage_status,
            policy_type=policy_type,
            coverage_pct=coverage_pct,
            owner=owner,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "policy_coverage.coverage_recorded",
            record_id=record.id,
            policy_name=policy_name,
            policy_scope=policy_scope.value,
            coverage_status=coverage_status.value,
        )
        return record

    def get_coverage(self, record_id: str) -> PolicyCoverageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_coverages(
        self,
        policy_scope: PolicyScope | None = None,
        coverage_status: CoverageStatus | None = None,
        owner: str | None = None,
        limit: int = 50,
    ) -> list[PolicyCoverageRecord]:
        results = list(self._records)
        if policy_scope is not None:
            results = [r for r in results if r.policy_scope == policy_scope]
        if coverage_status is not None:
            results = [r for r in results if r.coverage_status == coverage_status]
        if owner is not None:
            results = [r for r in results if r.owner == owner]
        return results[-limit:]

    def add_assessment(
        self,
        assessment_name: str,
        policy_scope: PolicyScope = PolicyScope.ORGANIZATION_WIDE,
        assessment_score: float = 0.0,
        policies_evaluated: int = 0,
        description: str = "",
    ) -> CoverageAssessment:
        assessment = CoverageAssessment(
            assessment_name=assessment_name,
            policy_scope=policy_scope,
            assessment_score=assessment_score,
            policies_evaluated=policies_evaluated,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "policy_coverage.assessment_added",
            assessment_name=assessment_name,
            policy_scope=policy_scope.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_policy_coverage(self) -> dict[str, Any]:
        """Group by policy_scope; return count and avg coverage_pct per scope."""
        scope_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.policy_scope.value
            scope_data.setdefault(key, []).append(r.coverage_pct)
        result: dict[str, Any] = {}
        for scope, pcts in scope_data.items():
            result[scope] = {
                "count": len(pcts),
                "avg_coverage_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_coverage_gaps(self) -> list[dict[str, Any]]:
        """Return records where coverage_pct < min_policy_coverage_pct."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.coverage_pct < self._min_policy_coverage_pct:
                results.append(
                    {
                        "record_id": r.id,
                        "policy_name": r.policy_name,
                        "coverage_pct": r.coverage_pct,
                        "policy_scope": r.policy_scope.value,
                        "owner": r.owner,
                    }
                )
        return results

    def rank_by_coverage_score(self) -> list[dict[str, Any]]:
        """Group by owner, total coverage_pct, sort descending."""
        owner_scores: dict[str, float] = {}
        for r in self._records:
            owner_scores[r.owner] = owner_scores.get(r.owner, 0) + r.coverage_pct
        results: list[dict[str, Any]] = []
        for owner, total in owner_scores.items():
            results.append(
                {
                    "owner": owner,
                    "total_coverage": total,
                }
            )
        results.sort(key=lambda x: x["total_coverage"], reverse=True)
        return results

    def detect_coverage_trends(self) -> dict[str, Any]:
        """Split-half on coverage_pct; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        counts = [r.coverage_pct for r in self._records]
        mid = len(counts) // 2
        first_half = counts[:mid]
        second_half = counts[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> PolicyCoverageReport:
        by_scope: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for r in self._records:
            by_scope[r.policy_scope.value] = by_scope.get(r.policy_scope.value, 0) + 1
            by_status[r.coverage_status.value] = by_status.get(r.coverage_status.value, 0) + 1
            by_type[r.policy_type.value] = by_type.get(r.policy_type.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.coverage_pct < self._min_policy_coverage_pct)
        covered_scopes = len({r.policy_scope for r in self._records if r.coverage_pct > 0})
        avg_cov = (
            round(sum(r.coverage_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        gap_policy_names = [
            r.policy_name for r in self._records if r.coverage_pct < self._min_policy_coverage_pct
        ][:5]
        recs: list[str] = []
        if gap_count > 0:
            recs.append(
                f"{gap_count} policy(ies) below minimum coverage ({self._min_policy_coverage_pct}%)"
            )
        if self._records and avg_cov < self._min_policy_coverage_pct:
            recs.append(
                f"Average coverage {avg_cov}% is below threshold ({self._min_policy_coverage_pct}%)"
            )
        if not recs:
            recs.append("Policy coverage levels are healthy")
        return PolicyCoverageReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            covered_scopes=covered_scopes,
            avg_coverage_pct=avg_cov,
            by_scope=by_scope,
            by_status=by_status,
            by_type=by_type,
            gap_policies=gap_policy_names,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("policy_coverage.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        scope_dist: dict[str, int] = {}
        for r in self._records:
            key = r.policy_scope.value
            scope_dist[key] = scope_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "min_policy_coverage_pct": self._min_policy_coverage_pct,
            "scope_distribution": scope_dist,
            "unique_owners": len({r.owner for r in self._records}),
            "unique_policies": len({r.policy_name for r in self._records}),
        }
