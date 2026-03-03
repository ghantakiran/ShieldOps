"""Workload Identity Auditor — audit Kubernetes workload identity configurations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IdentityType(StrEnum):
    SERVICE_ACCOUNT = "service_account"
    POD_IDENTITY = "pod_identity"
    IRSA = "irsa"
    WORKLOAD_IDENTITY = "workload_identity"
    CUSTOM = "custom"


class AuditFinding(StrEnum):
    OVERPRIVILEGED = "overprivileged"
    UNUSED = "unused"
    SHARED = "shared"
    MISCONFIGURED = "misconfigured"
    COMPLIANT = "compliant"


class RemediationAction(StrEnum):
    RESTRICT = "restrict"
    ROTATE = "rotate"
    DELETE = "delete"
    SCOPE_DOWN = "scope_down"
    ACCEPT = "accept"


# --- Models ---


class WorkloadIdentityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    identity_audit_id: str = ""
    identity_type: IdentityType = IdentityType.SERVICE_ACCOUNT
    audit_finding: AuditFinding = AuditFinding.OVERPRIVILEGED
    remediation_action: RemediationAction = RemediationAction.RESTRICT
    audit_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkloadIdentityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    identity_audit_id: str = ""
    identity_type: IdentityType = IdentityType.SERVICE_ACCOUNT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkloadIdentityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_audit_score: float = 0.0
    by_identity_type: dict[str, int] = Field(default_factory=dict)
    by_finding: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class WorkloadIdentityAuditor:
    """Audit workload identities for overprivilege, misconfiguration, and compliance."""

    def __init__(
        self,
        max_records: int = 200000,
        audit_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._audit_gap_threshold = audit_gap_threshold
        self._records: list[WorkloadIdentityRecord] = []
        self._analyses: list[WorkloadIdentityAnalysis] = []
        logger.info(
            "workload_identity_auditor.initialized",
            max_records=max_records,
            audit_gap_threshold=audit_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_identity(
        self,
        identity_audit_id: str,
        identity_type: IdentityType = IdentityType.SERVICE_ACCOUNT,
        audit_finding: AuditFinding = AuditFinding.OVERPRIVILEGED,
        remediation_action: RemediationAction = RemediationAction.RESTRICT,
        audit_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> WorkloadIdentityRecord:
        record = WorkloadIdentityRecord(
            identity_audit_id=identity_audit_id,
            identity_type=identity_type,
            audit_finding=audit_finding,
            remediation_action=remediation_action,
            audit_score=audit_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "workload_identity_auditor.identity_recorded",
            record_id=record.id,
            identity_audit_id=identity_audit_id,
            identity_type=identity_type.value,
            audit_finding=audit_finding.value,
        )
        return record

    def get_identity(self, record_id: str) -> WorkloadIdentityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_identities(
        self,
        identity_type: IdentityType | None = None,
        audit_finding: AuditFinding | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[WorkloadIdentityRecord]:
        results = list(self._records)
        if identity_type is not None:
            results = [r for r in results if r.identity_type == identity_type]
        if audit_finding is not None:
            results = [r for r in results if r.audit_finding == audit_finding]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        identity_audit_id: str,
        identity_type: IdentityType = IdentityType.SERVICE_ACCOUNT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> WorkloadIdentityAnalysis:
        analysis = WorkloadIdentityAnalysis(
            identity_audit_id=identity_audit_id,
            identity_type=identity_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "workload_identity_auditor.analysis_added",
            identity_audit_id=identity_audit_id,
            identity_type=identity_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_identity_distribution(self) -> dict[str, Any]:
        """Group by identity_type; return count and avg audit_score."""
        identity_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.identity_type.value
            identity_data.setdefault(key, []).append(r.audit_score)
        result: dict[str, Any] = {}
        for identity, scores in identity_data.items():
            result[identity] = {
                "count": len(scores),
                "avg_audit_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_audit_gaps(self) -> list[dict[str, Any]]:
        """Return records where audit_score < audit_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.audit_score < self._audit_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "identity_audit_id": r.identity_audit_id,
                        "identity_type": r.identity_type.value,
                        "audit_score": r.audit_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["audit_score"])

    def rank_by_audit(self) -> list[dict[str, Any]]:
        """Group by service, avg audit_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.audit_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_audit_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_audit_score"])
        return results

    def detect_audit_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> WorkloadIdentityReport:
        by_identity_type: dict[str, int] = {}
        by_finding: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_identity_type[r.identity_type.value] = (
                by_identity_type.get(r.identity_type.value, 0) + 1
            )
            by_finding[r.audit_finding.value] = by_finding.get(r.audit_finding.value, 0) + 1
            by_action[r.remediation_action.value] = by_action.get(r.remediation_action.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.audit_score < self._audit_gap_threshold)
        scores = [r.audit_score for r in self._records]
        avg_audit_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_audit_gaps()
        top_gaps = [o["identity_audit_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} identity(ies) below audit threshold ({self._audit_gap_threshold})"
            )
        if self._records and avg_audit_score < self._audit_gap_threshold:
            recs.append(
                f"Avg audit score {avg_audit_score} below threshold ({self._audit_gap_threshold})"
            )
        if not recs:
            recs.append("Workload identity audit is healthy")
        return WorkloadIdentityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_audit_score=avg_audit_score,
            by_identity_type=by_identity_type,
            by_finding=by_finding,
            by_action=by_action,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("workload_identity_auditor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        identity_dist: dict[str, int] = {}
        for r in self._records:
            key = r.identity_type.value
            identity_dist[key] = identity_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "audit_gap_threshold": self._audit_gap_threshold,
            "identity_distribution": identity_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
