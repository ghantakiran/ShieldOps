"""Policy Conflict Detector — detect conflicts between security and compliance policies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ConflictType(StrEnum):
    DIRECT_CONTRADICTION = "direct_contradiction"
    OVERLAP = "overlap"
    GAP = "gap"
    AMBIGUITY = "ambiguity"
    PRECEDENCE = "precedence"


class PolicyDomain(StrEnum):
    SECURITY = "security"
    COMPLIANCE = "compliance"
    ACCESS = "access"
    DATA = "data"
    NETWORK = "network"


class ConflictSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class PolicyConflictRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conflict_id: str = ""
    conflict_type: ConflictType = ConflictType.DIRECT_CONTRADICTION
    policy_domain: PolicyDomain = PolicyDomain.SECURITY
    conflict_severity: ConflictSeverity = ConflictSeverity.MEDIUM
    conflict_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyConflictAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conflict_id: str = ""
    conflict_type: ConflictType = ConflictType.DIRECT_CONTRADICTION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyConflictReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_conflict_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PolicyConflictDetector:
    """Detect conflicts between security and compliance policies across domains."""

    def __init__(
        self,
        max_records: int = 200000,
        conflict_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._conflict_threshold = conflict_threshold
        self._records: list[PolicyConflictRecord] = []
        self._analyses: list[PolicyConflictAnalysis] = []
        logger.info(
            "policy_conflict_detector.initialized",
            max_records=max_records,
            conflict_threshold=conflict_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_conflict(
        self,
        conflict_id: str,
        conflict_type: ConflictType = ConflictType.DIRECT_CONTRADICTION,
        policy_domain: PolicyDomain = PolicyDomain.SECURITY,
        conflict_severity: ConflictSeverity = ConflictSeverity.MEDIUM,
        conflict_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PolicyConflictRecord:
        record = PolicyConflictRecord(
            conflict_id=conflict_id,
            conflict_type=conflict_type,
            policy_domain=policy_domain,
            conflict_severity=conflict_severity,
            conflict_score=conflict_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "policy_conflict_detector.conflict_recorded",
            record_id=record.id,
            conflict_id=conflict_id,
            conflict_type=conflict_type.value,
            policy_domain=policy_domain.value,
        )
        return record

    def get_conflict(self, record_id: str) -> PolicyConflictRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_conflicts(
        self,
        conflict_type: ConflictType | None = None,
        policy_domain: PolicyDomain | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PolicyConflictRecord]:
        results = list(self._records)
        if conflict_type is not None:
            results = [r for r in results if r.conflict_type == conflict_type]
        if policy_domain is not None:
            results = [r for r in results if r.policy_domain == policy_domain]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        conflict_id: str,
        conflict_type: ConflictType = ConflictType.DIRECT_CONTRADICTION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PolicyConflictAnalysis:
        analysis = PolicyConflictAnalysis(
            conflict_id=conflict_id,
            conflict_type=conflict_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "policy_conflict_detector.analysis_added",
            conflict_id=conflict_id,
            conflict_type=conflict_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.conflict_type.value
            type_data.setdefault(key, []).append(r.conflict_score)
        result: dict[str, Any] = {}
        for ctype, scores in type_data.items():
            result[ctype] = {
                "count": len(scores),
                "avg_conflict_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_conflict_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.conflict_score < self._conflict_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "conflict_id": r.conflict_id,
                        "conflict_type": r.conflict_type.value,
                        "conflict_score": r.conflict_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["conflict_score"])

    def rank_by_conflict(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.conflict_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_conflict_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_conflict_score"])
        return results

    def detect_conflict_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> PolicyConflictReport:
        by_type: dict[str, int] = {}
        by_domain: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_type[r.conflict_type.value] = by_type.get(r.conflict_type.value, 0) + 1
            by_domain[r.policy_domain.value] = by_domain.get(r.policy_domain.value, 0) + 1
            by_severity[r.conflict_severity.value] = (
                by_severity.get(r.conflict_severity.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.conflict_score < self._conflict_threshold)
        scores = [r.conflict_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_conflict_gaps()
        top_gaps = [o["conflict_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} conflict(s) below threshold ({self._conflict_threshold})")
        if self._records and avg_score < self._conflict_threshold:
            recs.append(
                f"Avg conflict score {avg_score} below threshold ({self._conflict_threshold})"
            )
        if not recs:
            recs.append("Policy conflict detection is healthy")
        return PolicyConflictReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_conflict_score=avg_score,
            by_type=by_type,
            by_domain=by_domain,
            by_severity=by_severity,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("policy_conflict_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.conflict_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "conflict_threshold": self._conflict_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
