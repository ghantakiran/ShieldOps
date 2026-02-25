"""Compliance Audit Trail Analyzer — analyze audit trail for suspicious patterns and gaps."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AuditPatternType(StrEnum):
    NORMAL = "normal"
    SUSPICIOUS_MODIFICATION = "suspicious_modification"
    PRIVILEGE_MISUSE = "privilege_misuse"
    AUDIT_GAP = "audit_gap"
    BULK_CHANGE = "bulk_change"


class CompletenessLevel(StrEnum):
    COMPLETE = "complete"
    MOSTLY_COMPLETE = "mostly_complete"
    PARTIAL = "partial"
    SPARSE = "sparse"
    MISSING = "missing"


class AuditScope(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    DATABASE = "database"
    SECURITY = "security"
    COMPLIANCE = "compliance"


# --- Models ---


class AuditTrailFinding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scope: AuditScope = AuditScope.INFRASTRUCTURE
    pattern_type: AuditPatternType = AuditPatternType.NORMAL
    actor: str = ""
    resource: str = ""
    description: str = ""
    severity_score: float = 0.0
    investigated: bool = False
    created_at: float = Field(default_factory=time.time)


class AuditCompletenessScore(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scope: AuditScope = AuditScope.INFRASTRUCTURE
    completeness: CompletenessLevel = CompletenessLevel.COMPLETE
    completeness_pct: float = 100.0
    gap_count: int = 0
    total_expected_events: int = 0
    total_actual_events: int = 0
    created_at: float = Field(default_factory=time.time)


class AuditTrailReport(BaseModel):
    total_findings: int = 0
    suspicious_count: int = 0
    avg_completeness_pct: float = 0.0
    by_pattern_type: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    actors_of_concern: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceAuditTrailAnalyzer:
    """Analyze audit trail for suspicious patterns, gaps, and completeness scoring."""

    def __init__(
        self,
        max_records: int = 200000,
        min_completeness_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_completeness_pct = min_completeness_pct
        self._findings: list[AuditTrailFinding] = []
        self._completeness_scores: list[AuditCompletenessScore] = []
        logger.info(
            "audit_trail_analyzer.initialized",
            max_records=max_records,
            min_completeness_pct=min_completeness_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _pct_to_completeness(self, pct: float) -> CompletenessLevel:
        if pct >= 95:
            return CompletenessLevel.COMPLETE
        if pct >= 80:
            return CompletenessLevel.MOSTLY_COMPLETE
        if pct >= 60:
            return CompletenessLevel.PARTIAL
        if pct >= 30:
            return CompletenessLevel.SPARSE
        return CompletenessLevel.MISSING

    # -- record / get / list ---------------------------------------------

    def record_finding(
        self,
        scope: AuditScope,
        pattern_type: AuditPatternType,
        actor: str = "",
        resource: str = "",
        description: str = "",
        severity_score: float = 0.5,
    ) -> AuditTrailFinding:
        finding = AuditTrailFinding(
            scope=scope,
            pattern_type=pattern_type,
            actor=actor,
            resource=resource,
            description=description,
            severity_score=severity_score,
        )
        self._findings.append(finding)
        if len(self._findings) > self._max_records:
            self._findings = self._findings[-self._max_records :]
        logger.info(
            "audit_trail_analyzer.finding_recorded",
            finding_id=finding.id,
            scope=scope.value,
            pattern_type=pattern_type.value,
            actor=actor,
        )
        return finding

    def get_finding(self, finding_id: str) -> AuditTrailFinding | None:
        for f in self._findings:
            if f.id == finding_id:
                return f
        return None

    def list_findings(
        self,
        scope: AuditScope | None = None,
        pattern_type: AuditPatternType | None = None,
        limit: int = 50,
    ) -> list[AuditTrailFinding]:
        results = list(self._findings)
        if scope is not None:
            results = [f for f in results if f.scope == scope]
        if pattern_type is not None:
            results = [f for f in results if f.pattern_type == pattern_type]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def evaluate_completeness(
        self,
        scope: AuditScope,
        total_expected_events: int = 100,
        total_actual_events: int = 100,
    ) -> AuditCompletenessScore:
        """Evaluate audit trail completeness for a scope."""
        pct = (
            round(total_actual_events / total_expected_events * 100, 2)
            if total_expected_events > 0
            else 0.0
        )
        completeness = self._pct_to_completeness(pct)
        gap_count = max(0, total_expected_events - total_actual_events)
        score = AuditCompletenessScore(
            scope=scope,
            completeness=completeness,
            completeness_pct=pct,
            gap_count=gap_count,
            total_expected_events=total_expected_events,
            total_actual_events=total_actual_events,
        )
        self._completeness_scores.append(score)
        if len(self._completeness_scores) > self._max_records:
            self._completeness_scores = self._completeness_scores[-self._max_records :]
        logger.info(
            "audit_trail_analyzer.completeness_evaluated",
            scope=scope.value,
            completeness_pct=pct,
            completeness=completeness.value,
        )
        return score

    def detect_gaps(self) -> list[dict[str, Any]]:
        """Detect audit trail gaps across all scopes."""
        gaps: list[dict[str, Any]] = []
        for s in self._completeness_scores:
            if s.completeness_pct < self._min_completeness_pct:
                gaps.append(
                    {
                        "score_id": s.id,
                        "scope": s.scope.value,
                        "completeness_pct": s.completeness_pct,
                        "gap_count": s.gap_count,
                        "completeness": s.completeness.value,
                    }
                )
        gaps.sort(key=lambda x: x["completeness_pct"])
        return gaps

    def detect_suspicious_patterns(self) -> list[dict[str, Any]]:
        """Find suspicious patterns in audit findings."""
        suspicious = [
            f
            for f in self._findings
            if f.pattern_type
            in (
                AuditPatternType.SUSPICIOUS_MODIFICATION,
                AuditPatternType.PRIVILEGE_MISUSE,
                AuditPatternType.BULK_CHANGE,
            )
        ]
        return [
            {
                "finding_id": f.id,
                "scope": f.scope.value,
                "pattern_type": f.pattern_type.value,
                "actor": f.actor,
                "resource": f.resource,
                "severity_score": f.severity_score,
            }
            for f in suspicious
        ]

    def score_audit_integrity(self) -> dict[str, Any]:
        """Score overall audit trail integrity."""
        if not self._completeness_scores:
            return {"integrity_score": 0.0, "completeness_avg_pct": 0.0, "scopes_evaluated": 0}
        avg_pct = round(
            sum(s.completeness_pct for s in self._completeness_scores)
            / len(self._completeness_scores),
            2,
        )
        suspicious_count = sum(
            1 for f in self._findings if f.pattern_type != AuditPatternType.NORMAL
        )
        # Integrity = completeness adjusted down by suspicious findings
        penalty = min(30, suspicious_count * 2)
        integrity = round(max(0, avg_pct - penalty), 2)
        return {
            "integrity_score": integrity,
            "completeness_avg_pct": avg_pct,
            "suspicious_findings": suspicious_count,
            "scopes_evaluated": len(self._completeness_scores),
            "penalty_applied": penalty,
        }

    def identify_actors_of_concern(self) -> list[dict[str, Any]]:
        """Find actors with suspicious patterns."""
        actor_scores: dict[str, list[float]] = {}
        actor_counts: dict[str, int] = {}
        for f in self._findings:
            if f.pattern_type != AuditPatternType.NORMAL and f.actor:
                actor_scores.setdefault(f.actor, []).append(f.severity_score)
                actor_counts[f.actor] = actor_counts.get(f.actor, 0) + 1
        results: list[dict[str, Any]] = []
        for actor, scores in actor_scores.items():
            max_score = max(scores)
            avg_score = round(sum(scores) / len(scores), 4)
            results.append(
                {
                    "actor": actor,
                    "finding_count": actor_counts[actor],
                    "max_severity": max_score,
                    "avg_severity": avg_score,
                }
            )
        results.sort(key=lambda x: x["max_severity"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> AuditTrailReport:
        by_pattern: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for f in self._findings:
            by_pattern[f.pattern_type.value] = by_pattern.get(f.pattern_type.value, 0) + 1
            by_scope[f.scope.value] = by_scope.get(f.scope.value, 0) + 1
        suspicious_count = sum(
            1 for f in self._findings if f.pattern_type != AuditPatternType.NORMAL
        )
        avg_pct = (
            round(
                sum(s.completeness_pct for s in self._completeness_scores)
                / len(self._completeness_scores),
                2,
            )
            if self._completeness_scores
            else 0.0
        )
        actors = self.identify_actors_of_concern()
        actor_names = [a["actor"] for a in actors[:5]]
        recs: list[str] = []
        if suspicious_count > 0:
            recs.append(f"{suspicious_count} suspicious finding(s) detected")
        if avg_pct < self._min_completeness_pct:
            recs.append(
                f"Average completeness {avg_pct}% below target {self._min_completeness_pct}%"
            )
        gaps = self.detect_gaps()
        if gaps:
            recs.append(f"{len(gaps)} scope(s) with audit gaps")
        if not recs:
            recs.append("Audit trail integrity within acceptable parameters")
        return AuditTrailReport(
            total_findings=len(self._findings),
            suspicious_count=suspicious_count,
            avg_completeness_pct=avg_pct,
            by_pattern_type=by_pattern,
            by_scope=by_scope,
            actors_of_concern=actor_names,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._findings.clear()
        self._completeness_scores.clear()
        logger.info("audit_trail_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        pattern_dist: dict[str, int] = {}
        for f in self._findings:
            key = f.pattern_type.value
            pattern_dist[key] = pattern_dist.get(key, 0) + 1
        return {
            "total_findings": len(self._findings),
            "total_completeness_scores": len(self._completeness_scores),
            "min_completeness_pct": self._min_completeness_pct,
            "pattern_distribution": pattern_dist,
            "unique_actors": len({f.actor for f in self._findings if f.actor}),
        }
