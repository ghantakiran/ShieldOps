"""Change Audit Analyzer — analyze change audits, identify non-compliant changes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ChangeType(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    CONFIGURATION = "configuration"
    DATABASE = "database"
    NETWORK = "network"


class AuditStatus(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PENDING_REVIEW = "pending_review"
    EXEMPTED = "exempted"
    REMEDIATED = "remediated"


class AuditFinding(StrEnum):
    UNAUTHORIZED_CHANGE = "unauthorized_change"
    MISSING_APPROVAL = "missing_approval"
    INCOMPLETE_TESTING = "incomplete_testing"
    NO_ROLLBACK_PLAN = "no_rollback_plan"
    DOCUMENTATION_GAP = "documentation_gap"


# --- Models ---


class ChangeAuditRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    change_type: ChangeType = ChangeType.INFRASTRUCTURE
    audit_status: AuditStatus = AuditStatus.PENDING_REVIEW
    audit_finding: AuditFinding = AuditFinding.UNAUTHORIZED_CHANGE
    compliance_pct: float = 0.0
    auditor: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditObservation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    observation_name: str = ""
    change_type: ChangeType = ChangeType.INFRASTRUCTURE
    severity_score: float = 0.0
    changes_reviewed: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ChangeAuditReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_observations: int = 0
    audited_changes: int = 0
    avg_compliance_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_finding: dict[str, int] = Field(default_factory=dict)
    non_compliant_changes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeAuditAnalyzer:
    """Analyze change audits, identify non-compliant changes, track audit compliance."""

    def __init__(
        self,
        max_records: int = 200000,
        min_audit_compliance_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_audit_compliance_pct = min_audit_compliance_pct
        self._records: list[ChangeAuditRecord] = []
        self._observations: list[AuditObservation] = []
        logger.info(
            "change_audit.initialized",
            max_records=max_records,
            min_audit_compliance_pct=min_audit_compliance_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_audit(
        self,
        change_id: str,
        change_type: ChangeType = ChangeType.INFRASTRUCTURE,
        audit_status: AuditStatus = AuditStatus.PENDING_REVIEW,
        audit_finding: AuditFinding = AuditFinding.UNAUTHORIZED_CHANGE,
        compliance_pct: float = 0.0,
        auditor: str = "",
    ) -> ChangeAuditRecord:
        record = ChangeAuditRecord(
            change_id=change_id,
            change_type=change_type,
            audit_status=audit_status,
            audit_finding=audit_finding,
            compliance_pct=compliance_pct,
            auditor=auditor,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "change_audit.audit_recorded",
            record_id=record.id,
            change_id=change_id,
            change_type=change_type.value,
            audit_status=audit_status.value,
        )
        return record

    def get_audit(self, record_id: str) -> ChangeAuditRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_audits(
        self,
        change_type: ChangeType | None = None,
        audit_status: AuditStatus | None = None,
        auditor: str | None = None,
        limit: int = 50,
    ) -> list[ChangeAuditRecord]:
        results = list(self._records)
        if change_type is not None:
            results = [r for r in results if r.change_type == change_type]
        if audit_status is not None:
            results = [r for r in results if r.audit_status == audit_status]
        if auditor is not None:
            results = [r for r in results if r.auditor == auditor]
        return results[-limit:]

    def add_observation(
        self,
        observation_name: str,
        change_type: ChangeType = ChangeType.INFRASTRUCTURE,
        severity_score: float = 0.0,
        changes_reviewed: int = 0,
        description: str = "",
    ) -> AuditObservation:
        observation = AuditObservation(
            observation_name=observation_name,
            change_type=change_type,
            severity_score=severity_score,
            changes_reviewed=changes_reviewed,
            description=description,
        )
        self._observations.append(observation)
        if len(self._observations) > self._max_records:
            self._observations = self._observations[-self._max_records :]
        logger.info(
            "change_audit.observation_added",
            observation_name=observation_name,
            change_type=change_type.value,
            severity_score=severity_score,
        )
        return observation

    # -- domain operations --------------------------------------------------

    def analyze_audit_compliance(self) -> dict[str, Any]:
        """Group by change_type; return count and avg compliance_pct per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.change_type.value
            type_data.setdefault(key, []).append(r.compliance_pct)
        result: dict[str, Any] = {}
        for ctype, pcts in type_data.items():
            result[ctype] = {
                "count": len(pcts),
                "avg_compliance_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_non_compliant_changes(self) -> list[dict[str, Any]]:
        """Return records where compliance_pct < min_audit_compliance_pct."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_pct < self._min_audit_compliance_pct:
                results.append(
                    {
                        "record_id": r.id,
                        "change_id": r.change_id,
                        "compliance_pct": r.compliance_pct,
                        "change_type": r.change_type.value,
                        "auditor": r.auditor,
                    }
                )
        return results

    def rank_by_severity(self) -> list[dict[str, Any]]:
        """Group by auditor, total compliance_pct, sort descending."""
        auditor_scores: dict[str, float] = {}
        for r in self._records:
            auditor_scores[r.auditor] = auditor_scores.get(r.auditor, 0) + r.compliance_pct
        results: list[dict[str, Any]] = []
        for auditor, total in auditor_scores.items():
            results.append(
                {
                    "auditor": auditor,
                    "total_compliance": total,
                }
            )
        results.sort(key=lambda x: x["total_compliance"], reverse=True)
        return results

    def detect_audit_trends(self) -> dict[str, Any]:
        """Split-half on compliance_pct; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        counts = [r.compliance_pct for r in self._records]
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

    def generate_report(self) -> ChangeAuditReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_finding: dict[str, int] = {}
        for r in self._records:
            by_type[r.change_type.value] = by_type.get(r.change_type.value, 0) + 1
            by_status[r.audit_status.value] = by_status.get(r.audit_status.value, 0) + 1
            by_finding[r.audit_finding.value] = by_finding.get(r.audit_finding.value, 0) + 1
        non_compliant_count = sum(
            1 for r in self._records if r.compliance_pct < self._min_audit_compliance_pct
        )
        audited_changes = len({r.change_id for r in self._records if r.compliance_pct > 0})
        avg_cov = (
            round(sum(r.compliance_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        non_compliant_ids = [
            r.change_id for r in self._records if r.compliance_pct < self._min_audit_compliance_pct
        ][:5]
        recs: list[str] = []
        if non_compliant_count > 0:
            recs.append(
                f"{non_compliant_count} change(s) below minimum compliance"
                f" ({self._min_audit_compliance_pct}%)"
            )
        if self._records and avg_cov < self._min_audit_compliance_pct:
            recs.append(
                f"Average compliance {avg_cov}% is below threshold"
                f" ({self._min_audit_compliance_pct}%)"
            )
        if not recs:
            recs.append("Change audit compliance levels are healthy")
        return ChangeAuditReport(
            total_records=len(self._records),
            total_observations=len(self._observations),
            audited_changes=audited_changes,
            avg_compliance_pct=avg_cov,
            by_type=by_type,
            by_status=by_status,
            by_finding=by_finding,
            non_compliant_changes=non_compliant_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._observations.clear()
        logger.info("change_audit.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.change_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_observations": len(self._observations),
            "min_audit_compliance_pct": self._min_audit_compliance_pct,
            "type_distribution": type_dist,
            "unique_changes": len({r.change_id for r in self._records}),
            "unique_auditors": len({r.auditor for r in self._records}),
        }
