"""Conditional Access Engine — evaluate conditional access policies and decisions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PolicyCondition(StrEnum):
    LOCATION = "location"
    DEVICE_STATE = "device_state"
    RISK_LEVEL = "risk_level"
    USER_GROUP = "user_group"
    APPLICATION = "application"


class AccessAction(StrEnum):
    GRANT = "grant"
    BLOCK = "block"
    REQUIRE_MFA = "require_mfa"
    LIMIT_ACCESS = "limit_access"
    SESSION_CONTROL = "session_control"


class EvaluationResult(StrEnum):
    PASSED = "passed"  # noqa: S105
    FAILED = "failed"
    CONDITIONAL = "conditional"
    SKIPPED = "skipped"
    ERROR = "error"


# --- Models ---


class AccessPolicyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str = ""
    policy_condition: PolicyCondition = PolicyCondition.LOCATION
    access_action: AccessAction = AccessAction.GRANT
    evaluation_result: EvaluationResult = EvaluationResult.PASSED
    policy_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AccessPolicyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str = ""
    policy_condition: PolicyCondition = PolicyCondition.LOCATION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ConditionalAccessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_policy_score: float = 0.0
    by_policy_condition: dict[str, int] = Field(default_factory=dict)
    by_access_action: dict[str, int] = Field(default_factory=dict)
    by_evaluation_result: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ConditionalAccessEngine:
    """Evaluate conditional access policies, track decisions, and analyze policy effectiveness."""

    def __init__(
        self,
        max_records: int = 200000,
        policy_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._policy_gap_threshold = policy_gap_threshold
        self._records: list[AccessPolicyRecord] = []
        self._analyses: list[AccessPolicyAnalysis] = []
        logger.info(
            "conditional_access_engine.initialized",
            max_records=max_records,
            policy_gap_threshold=policy_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_policy(
        self,
        policy_id: str,
        policy_condition: PolicyCondition = PolicyCondition.LOCATION,
        access_action: AccessAction = AccessAction.GRANT,
        evaluation_result: EvaluationResult = EvaluationResult.PASSED,
        policy_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AccessPolicyRecord:
        record = AccessPolicyRecord(
            policy_id=policy_id,
            policy_condition=policy_condition,
            access_action=access_action,
            evaluation_result=evaluation_result,
            policy_score=policy_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "conditional_access_engine.policy_recorded",
            record_id=record.id,
            policy_id=policy_id,
            policy_condition=policy_condition.value,
            access_action=access_action.value,
        )
        return record

    def get_policy(self, record_id: str) -> AccessPolicyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_policies(
        self,
        policy_condition: PolicyCondition | None = None,
        access_action: AccessAction | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AccessPolicyRecord]:
        results = list(self._records)
        if policy_condition is not None:
            results = [r for r in results if r.policy_condition == policy_condition]
        if access_action is not None:
            results = [r for r in results if r.access_action == access_action]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        policy_id: str,
        policy_condition: PolicyCondition = PolicyCondition.LOCATION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AccessPolicyAnalysis:
        analysis = AccessPolicyAnalysis(
            policy_id=policy_id,
            policy_condition=policy_condition,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "conditional_access_engine.analysis_added",
            policy_id=policy_id,
            policy_condition=policy_condition.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_policy_distribution(self) -> dict[str, Any]:
        """Group by policy_condition; return count and avg policy_score."""
        condition_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.policy_condition.value
            condition_data.setdefault(key, []).append(r.policy_score)
        result: dict[str, Any] = {}
        for condition, scores in condition_data.items():
            result[condition] = {
                "count": len(scores),
                "avg_policy_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_policy_gaps(self) -> list[dict[str, Any]]:
        """Return records where policy_score < policy_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.policy_score < self._policy_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "policy_id": r.policy_id,
                        "policy_condition": r.policy_condition.value,
                        "policy_score": r.policy_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["policy_score"])

    def rank_by_policy(self) -> list[dict[str, Any]]:
        """Group by service, avg policy_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.policy_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_policy_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_policy_score"])
        return results

    def detect_policy_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ConditionalAccessReport:
        by_policy_condition: dict[str, int] = {}
        by_access_action: dict[str, int] = {}
        by_evaluation_result: dict[str, int] = {}
        for r in self._records:
            by_policy_condition[r.policy_condition.value] = (
                by_policy_condition.get(r.policy_condition.value, 0) + 1
            )
            by_access_action[r.access_action.value] = (
                by_access_action.get(r.access_action.value, 0) + 1
            )
            by_evaluation_result[r.evaluation_result.value] = (
                by_evaluation_result.get(r.evaluation_result.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.policy_score < self._policy_gap_threshold)
        scores = [r.policy_score for r in self._records]
        avg_policy_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_policy_gaps()
        top_gaps = [o["policy_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} policy(ies) below policy threshold ({self._policy_gap_threshold})"
            )
        if self._records and avg_policy_score < self._policy_gap_threshold:
            recs.append(
                f"Avg policy score {avg_policy_score} below threshold "
                f"({self._policy_gap_threshold})"
            )
        if not recs:
            recs.append("Conditional access policy evaluation is healthy")
        return ConditionalAccessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_policy_score=avg_policy_score,
            by_policy_condition=by_policy_condition,
            by_access_action=by_access_action,
            by_evaluation_result=by_evaluation_result,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("conditional_access_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        condition_dist: dict[str, int] = {}
        for r in self._records:
            key = r.policy_condition.value
            condition_dist[key] = condition_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "policy_gap_threshold": self._policy_gap_threshold,
            "policy_condition_distribution": condition_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
