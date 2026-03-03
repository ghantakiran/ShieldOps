"""Automated Policy Enforcer — enforce policies with automated actions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EnforcementAction(StrEnum):
    BLOCK = "block"
    ALERT = "alert"
    REMEDIATE = "remediate"
    AUDIT = "audit"
    EXEMPT = "exempt"


class EnforcementScope(StrEnum):
    REALTIME = "realtime"
    SCHEDULED = "scheduled"
    ON_DEMAND = "on_demand"
    CONTINUOUS = "continuous"
    EVENT_DRIVEN = "event_driven"


class ViolationSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class EnforcementRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    enforcement_action: EnforcementAction = EnforcementAction.BLOCK
    enforcement_scope: EnforcementScope = EnforcementScope.REALTIME
    violation_severity: ViolationSeverity = ViolationSeverity.CRITICAL
    enforcement_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EnforcementAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    enforcement_action: EnforcementAction = EnforcementAction.BLOCK
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EnforcementReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_enforcement_score: float = 0.0
    by_action: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutomatedPolicyEnforcer:
    """Enforce policies with automated actions, track violations, analyze enforcement gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[EnforcementRecord] = []
        self._analyses: list[EnforcementAnalysis] = []
        logger.info(
            "automated_policy_enforcer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_enforcement(
        self,
        policy_name: str,
        enforcement_action: EnforcementAction = EnforcementAction.BLOCK,
        enforcement_scope: EnforcementScope = EnforcementScope.REALTIME,
        violation_severity: ViolationSeverity = ViolationSeverity.CRITICAL,
        enforcement_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EnforcementRecord:
        record = EnforcementRecord(
            policy_name=policy_name,
            enforcement_action=enforcement_action,
            enforcement_scope=enforcement_scope,
            violation_severity=violation_severity,
            enforcement_score=enforcement_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "automated_policy_enforcer.enforcement_recorded",
            record_id=record.id,
            policy_name=policy_name,
            enforcement_action=enforcement_action.value,
            enforcement_scope=enforcement_scope.value,
        )
        return record

    def get_record(self, record_id: str) -> EnforcementRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        enforcement_action: EnforcementAction | None = None,
        violation_severity: ViolationSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EnforcementRecord]:
        results = list(self._records)
        if enforcement_action is not None:
            results = [r for r in results if r.enforcement_action == enforcement_action]
        if violation_severity is not None:
            results = [r for r in results if r.violation_severity == violation_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        policy_name: str,
        enforcement_action: EnforcementAction = EnforcementAction.BLOCK,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> EnforcementAnalysis:
        analysis = EnforcementAnalysis(
            policy_name=policy_name,
            enforcement_action=enforcement_action,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "automated_policy_enforcer.analysis_added",
            policy_name=policy_name,
            enforcement_action=enforcement_action.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by enforcement_action; return count and avg enforcement_score."""
        action_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.enforcement_action.value
            action_data.setdefault(key, []).append(r.enforcement_score)
        result: dict[str, Any] = {}
        for action, scores in action_data.items():
            result[action] = {
                "count": len(scores),
                "avg_enforcement_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where enforcement_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.enforcement_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "policy_name": r.policy_name,
                        "enforcement_action": r.enforcement_action.value,
                        "enforcement_score": r.enforcement_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["enforcement_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg enforcement_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.enforcement_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_enforcement_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_enforcement_score"])
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

    def generate_report(self) -> EnforcementReport:
        by_action: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_action[r.enforcement_action.value] = by_action.get(r.enforcement_action.value, 0) + 1
            by_scope[r.enforcement_scope.value] = by_scope.get(r.enforcement_scope.value, 0) + 1
            by_severity[r.violation_severity.value] = (
                by_severity.get(r.violation_severity.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.enforcement_score < self._threshold)
        scores = [r.enforcement_score for r in self._records]
        avg_enforcement_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["policy_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} enforcement(s) below threshold ({self._threshold})")
        if self._records and avg_enforcement_score < self._threshold:
            recs.append(
                f"Avg enforcement score {avg_enforcement_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Automated policy enforcement is healthy")
        return EnforcementReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_enforcement_score=avg_enforcement_score,
            by_action=by_action,
            by_scope=by_scope,
            by_severity=by_severity,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("automated_policy_enforcer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        action_dist: dict[str, int] = {}
        for r in self._records:
            key = r.enforcement_action.value
            action_dist[key] = action_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "action_distribution": action_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
