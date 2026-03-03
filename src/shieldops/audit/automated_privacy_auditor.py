"""Automated Privacy Auditor — audit privacy controls and generate findings."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AuditType(StrEnum):
    SCHEDULED = "scheduled"
    TRIGGERED = "triggered"
    CONTINUOUS = "continuous"
    SPOT_CHECK = "spot_check"
    ANNUAL = "annual"


class PrivacyControl(StrEnum):
    DATA_MINIMIZATION = "data_minimization"
    PURPOSE_LIMITATION = "purpose_limitation"
    STORAGE_LIMITATION = "storage_limitation"
    ACCURACY = "accuracy"
    INTEGRITY = "integrity"


class AuditFinding(StrEnum):
    COMPLIANT = "compliant"
    MINOR_GAP = "minor_gap"
    MAJOR_GAP = "major_gap"
    CRITICAL_VIOLATION = "critical_violation"
    NOT_APPLICABLE = "not_applicable"


# --- Models ---


class AuditRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_id: str = ""
    audit_type: AuditType = AuditType.SCHEDULED
    privacy_control: PrivacyControl = PrivacyControl.DATA_MINIMIZATION
    audit_finding: AuditFinding = AuditFinding.COMPLIANT
    control_score: float = 0.0
    auditor: str = ""
    business_unit: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_id: str = ""
    audit_type: AuditType = AuditType.SCHEDULED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PrivacyAuditReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_control_score: float = 0.0
    by_audit_type: dict[str, int] = Field(default_factory=dict)
    by_control: dict[str, int] = Field(default_factory=dict)
    by_finding: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutomatedPrivacyAuditor:
    """Automate privacy audits; track control effectiveness and identify violations."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[AuditRecord] = []
        self._analyses: list[AuditAnalysis] = []
        logger.info(
            "automated_privacy_auditor.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_audit(
        self,
        audit_id: str,
        audit_type: AuditType = AuditType.SCHEDULED,
        privacy_control: PrivacyControl = PrivacyControl.DATA_MINIMIZATION,
        audit_finding: AuditFinding = AuditFinding.COMPLIANT,
        control_score: float = 0.0,
        auditor: str = "",
        business_unit: str = "",
    ) -> AuditRecord:
        record = AuditRecord(
            audit_id=audit_id,
            audit_type=audit_type,
            privacy_control=privacy_control,
            audit_finding=audit_finding,
            control_score=control_score,
            auditor=auditor,
            business_unit=business_unit,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "automated_privacy_auditor.audit_recorded",
            record_id=record.id,
            audit_id=audit_id,
            audit_type=audit_type.value,
            privacy_control=privacy_control.value,
        )
        return record

    def get_audit(self, record_id: str) -> AuditRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_audits(
        self,
        audit_type: AuditType | None = None,
        privacy_control: PrivacyControl | None = None,
        business_unit: str | None = None,
        limit: int = 50,
    ) -> list[AuditRecord]:
        results = list(self._records)
        if audit_type is not None:
            results = [r for r in results if r.audit_type == audit_type]
        if privacy_control is not None:
            results = [r for r in results if r.privacy_control == privacy_control]
        if business_unit is not None:
            results = [r for r in results if r.business_unit == business_unit]
        return results[-limit:]

    def add_analysis(
        self,
        audit_id: str,
        audit_type: AuditType = AuditType.SCHEDULED,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AuditAnalysis:
        analysis = AuditAnalysis(
            audit_id=audit_id,
            audit_type=audit_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "automated_privacy_auditor.analysis_added",
            audit_id=audit_id,
            audit_type=audit_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_control_distribution(self) -> dict[str, Any]:
        """Group by privacy_control; return count and avg control_score."""
        ctrl_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.privacy_control.value
            ctrl_data.setdefault(key, []).append(r.control_score)
        result: dict[str, Any] = {}
        for ctrl, scores in ctrl_data.items():
            result[ctrl] = {
                "count": len(scores),
                "avg_control_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_audit_gaps(self) -> list[dict[str, Any]]:
        """Return records where control_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.control_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "audit_id": r.audit_id,
                        "privacy_control": r.privacy_control.value,
                        "control_score": r.control_score,
                        "auditor": r.auditor,
                        "business_unit": r.business_unit,
                    }
                )
        return sorted(results, key=lambda x: x["control_score"])

    def rank_by_control(self) -> list[dict[str, Any]]:
        """Group by business_unit, avg control_score, sort ascending."""
        unit_scores: dict[str, list[float]] = {}
        for r in self._records:
            unit_scores.setdefault(r.business_unit, []).append(r.control_score)
        results: list[dict[str, Any]] = []
        for unit, scores in unit_scores.items():
            results.append(
                {
                    "business_unit": unit,
                    "avg_control_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_control_score"])
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

    def generate_report(self) -> PrivacyAuditReport:
        by_audit_type: dict[str, int] = {}
        by_control: dict[str, int] = {}
        by_finding: dict[str, int] = {}
        for r in self._records:
            by_audit_type[r.audit_type.value] = by_audit_type.get(r.audit_type.value, 0) + 1
            by_control[r.privacy_control.value] = by_control.get(r.privacy_control.value, 0) + 1
            by_finding[r.audit_finding.value] = by_finding.get(r.audit_finding.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.control_score < self._threshold)
        scores = [r.control_score for r in self._records]
        avg_control_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_audit_gaps()
        top_gaps = [o["audit_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} audit(s) below control threshold ({self._threshold})")
        if self._records and avg_control_score < self._threshold:
            recs.append(
                f"Avg control score {avg_control_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Privacy audit coverage is healthy")
        return PrivacyAuditReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_control_score=avg_control_score,
            by_audit_type=by_audit_type,
            by_control=by_control,
            by_finding=by_finding,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("automated_privacy_auditor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.audit_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "audit_type_distribution": type_dist,
            "unique_auditors": len({r.auditor for r in self._records}),
            "unique_units": len({r.business_unit for r in self._records}),
        }
