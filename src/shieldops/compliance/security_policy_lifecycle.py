"""Security Policy Lifecycle — manage policy phases from draft to retirement."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PolicyPhase(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ENFORCED = "enforced"
    RETIRED = "retired"


class PolicyCategory(StrEnum):
    ACCESS_CONTROL = "access_control"
    DATA_PROTECTION = "data_protection"
    NETWORK_SECURITY = "network_security"
    INCIDENT_RESPONSE = "incident_response"
    COMPLIANCE = "compliance"


class PolicyScope(StrEnum):
    ORGANIZATION = "organization"
    DEPARTMENT = "department"
    TEAM = "team"
    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"


# --- Models ---


class PolicyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    policy_phase: PolicyPhase = PolicyPhase.DRAFT
    policy_category: PolicyCategory = PolicyCategory.ACCESS_CONTROL
    policy_scope: PolicyScope = PolicyScope.ORGANIZATION
    compliance_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    policy_phase: PolicyPhase = PolicyPhase.DRAFT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyLifecycleReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_compliance_score: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityPolicyLifecycle:
    """Track security policy phases from draft to retirement, compliance scoring, gap analysis."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[PolicyRecord] = []
        self._analyses: list[PolicyAnalysis] = []
        logger.info(
            "security_policy_lifecycle.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_policy(
        self,
        policy_name: str,
        policy_phase: PolicyPhase = PolicyPhase.DRAFT,
        policy_category: PolicyCategory = PolicyCategory.ACCESS_CONTROL,
        policy_scope: PolicyScope = PolicyScope.ORGANIZATION,
        compliance_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PolicyRecord:
        record = PolicyRecord(
            policy_name=policy_name,
            policy_phase=policy_phase,
            policy_category=policy_category,
            policy_scope=policy_scope,
            compliance_score=compliance_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_policy_lifecycle.policy_recorded",
            record_id=record.id,
            policy_name=policy_name,
            policy_phase=policy_phase.value,
            policy_category=policy_category.value,
        )
        return record

    def get_record(self, record_id: str) -> PolicyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        policy_phase: PolicyPhase | None = None,
        policy_category: PolicyCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PolicyRecord]:
        results = list(self._records)
        if policy_phase is not None:
            results = [r for r in results if r.policy_phase == policy_phase]
        if policy_category is not None:
            results = [r for r in results if r.policy_category == policy_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        policy_name: str,
        policy_phase: PolicyPhase = PolicyPhase.DRAFT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PolicyAnalysis:
        analysis = PolicyAnalysis(
            policy_name=policy_name,
            policy_phase=policy_phase,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_policy_lifecycle.analysis_added",
            policy_name=policy_name,
            policy_phase=policy_phase.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by policy_phase; return count and avg compliance_score."""
        phase_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.policy_phase.value
            phase_data.setdefault(key, []).append(r.compliance_score)
        result: dict[str, Any] = {}
        for phase, scores in phase_data.items():
            result[phase] = {
                "count": len(scores),
                "avg_compliance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where compliance_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "policy_name": r.policy_name,
                        "policy_phase": r.policy_phase.value,
                        "compliance_score": r.compliance_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["compliance_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg compliance_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.compliance_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_compliance_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_compliance_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> PolicyLifecycleReport:
        by_phase: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for r in self._records:
            by_phase[r.policy_phase.value] = by_phase.get(r.policy_phase.value, 0) + 1
            by_category[r.policy_category.value] = by_category.get(r.policy_category.value, 0) + 1
            by_scope[r.policy_scope.value] = by_scope.get(r.policy_scope.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.compliance_score < self._threshold)
        scores = [r.compliance_score for r in self._records]
        avg_compliance_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["policy_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} policy(ies) below compliance threshold ({self._threshold})")
        if self._records and avg_compliance_score < self._threshold:
            recs.append(
                f"Avg compliance score {avg_compliance_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Security policy lifecycle is healthy")
        return PolicyLifecycleReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_compliance_score=avg_compliance_score,
            by_phase=by_phase,
            by_category=by_category,
            by_scope=by_scope,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_policy_lifecycle.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            key = r.policy_phase.value
            phase_dist[key] = phase_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "phase_distribution": phase_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
