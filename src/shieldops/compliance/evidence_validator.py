"""Compliance Evidence Validator — validate and track compliance evidence quality."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EvidenceType(StrEnum):
    AUTOMATED_SCAN = "automated_scan"
    MANUAL_REVIEW = "manual_review"
    SYSTEM_LOG = "system_log"
    CONFIGURATION_SNAPSHOT = "configuration_snapshot"
    ATTESTATION = "attestation"


class ValidationStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    INCOMPLETE = "incomplete"
    PENDING_REVIEW = "pending_review"


class EvidenceFramework(StrEnum):
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"
    ISO27001 = "iso27001"


# --- Models ---


class ValidationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_id: str = ""
    control_id: str = ""
    evidence_type: EvidenceType = EvidenceType.AUTOMATED_SCAN
    status: ValidationStatus = ValidationStatus.PENDING_REVIEW
    framework: EvidenceFramework = EvidenceFramework.SOC2
    validity_score: float = 0.0
    reviewer: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ValidationFinding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_id: str = ""
    control_id: str = ""
    framework: EvidenceFramework = EvidenceFramework.SOC2
    finding_type: str = ""
    severity: str = "low"
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceValidatorReport(BaseModel):
    total_records: int = 0
    total_findings: int = 0
    avg_validity_score: float = 0.0
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    invalid_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceEvidenceValidator:
    """Validate and track compliance evidence quality across frameworks."""

    def __init__(
        self,
        max_records: int = 200000,
        min_validity_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_validity_pct = min_validity_pct
        self._records: list[ValidationRecord] = []
        self._findings: list[ValidationFinding] = []
        logger.info(
            "evidence_validator.initialized",
            max_records=max_records,
            min_validity_pct=min_validity_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _score_to_status(self, validity_score: float) -> ValidationStatus:
        if validity_score >= self._min_validity_pct:
            return ValidationStatus.VALID
        if validity_score >= 50:
            return ValidationStatus.INCOMPLETE
        if validity_score > 0:
            return ValidationStatus.INVALID
        return ValidationStatus.PENDING_REVIEW

    # -- record / get / list ---------------------------------------------

    def record_validation(
        self,
        evidence_id: str,
        control_id: str,
        evidence_type: EvidenceType = EvidenceType.AUTOMATED_SCAN,
        status: ValidationStatus | None = None,
        framework: EvidenceFramework = EvidenceFramework.SOC2,
        validity_score: float = 0.0,
        reviewer: str = "",
        details: str = "",
    ) -> ValidationRecord:
        if status is None:
            status = self._score_to_status(validity_score)
        record = ValidationRecord(
            evidence_id=evidence_id,
            control_id=control_id,
            evidence_type=evidence_type,
            status=status,
            framework=framework,
            validity_score=validity_score,
            reviewer=reviewer,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "evidence_validator.validation_recorded",
            record_id=record.id,
            evidence_id=evidence_id,
            framework=framework.value,
            status=status.value,
        )
        return record

    def get_validation(self, record_id: str) -> ValidationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_validations(
        self,
        framework: EvidenceFramework | None = None,
        status: ValidationStatus | None = None,
        limit: int = 50,
    ) -> list[ValidationRecord]:
        results = list(self._records)
        if framework is not None:
            results = [r for r in results if r.framework == framework]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results[-limit:]

    def add_finding(
        self,
        evidence_id: str,
        control_id: str,
        framework: EvidenceFramework = EvidenceFramework.SOC2,
        finding_type: str = "",
        severity: str = "low",
        description: str = "",
    ) -> ValidationFinding:
        finding = ValidationFinding(
            evidence_id=evidence_id,
            control_id=control_id,
            framework=framework,
            finding_type=finding_type,
            severity=severity,
            description=description,
        )
        self._findings.append(finding)
        if len(self._findings) > self._max_records:
            self._findings = self._findings[-self._max_records :]
        logger.info(
            "evidence_validator.finding_added",
            evidence_id=evidence_id,
            framework=framework.value,
            severity=severity,
        )
        return finding

    # -- domain operations -----------------------------------------------

    def analyze_validation_by_framework(self, framework: EvidenceFramework) -> dict[str, Any]:
        """Analyze validation results for a specific compliance framework."""
        records = [r for r in self._records if r.framework == framework]
        if not records:
            return {"framework": framework.value, "status": "no_data"}
        avg_score = round(sum(r.validity_score for r in records) / len(records), 2)
        valid_count = sum(1 for r in records if r.status == ValidationStatus.VALID)
        invalid_count = sum(1 for r in records if r.status == ValidationStatus.INVALID)
        return {
            "framework": framework.value,
            "total_evidence": len(records),
            "avg_validity_score": avg_score,
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "meets_threshold": avg_score >= self._min_validity_pct,
        }

    def identify_invalid_evidence(self) -> list[dict[str, Any]]:
        """Find evidence that is INVALID, EXPIRED, or INCOMPLETE."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.status in (
                ValidationStatus.INVALID,
                ValidationStatus.EXPIRED,
                ValidationStatus.INCOMPLETE,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "evidence_id": r.evidence_id,
                        "control_id": r.control_id,
                        "framework": r.framework.value,
                        "status": r.status.value,
                        "validity_score": r.validity_score,
                        "evidence_type": r.evidence_type.value,
                    }
                )
        results.sort(key=lambda x: x["validity_score"])
        return results

    def rank_by_validity_score(self) -> list[dict[str, Any]]:
        """Rank all records by validity score ascending (worst first)."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "record_id": r.id,
                    "evidence_id": r.evidence_id,
                    "framework": r.framework.value,
                    "validity_score": r.validity_score,
                    "status": r.status.value,
                    "evidence_type": r.evidence_type.value,
                }
            )
        results.sort(key=lambda x: x["validity_score"])
        return results

    def detect_validation_gaps(self) -> list[dict[str, Any]]:
        """Detect frameworks and controls with validation coverage gaps."""
        framework_controls: dict[str, set[str]] = {}
        framework_invalid: dict[str, int] = {}
        for r in self._records:
            fw = r.framework.value
            framework_controls.setdefault(fw, set()).add(r.control_id)
            if r.status in (ValidationStatus.INVALID, ValidationStatus.EXPIRED):
                framework_invalid[fw] = framework_invalid.get(fw, 0) + 1
        gaps: list[dict[str, Any]] = []
        for fw, controls in framework_controls.items():
            invalid = framework_invalid.get(fw, 0)
            total = len([r for r in self._records if r.framework.value == fw])
            if invalid > 0 or total == 0:
                gaps.append(
                    {
                        "framework": fw,
                        "unique_controls": len(controls),
                        "invalid_or_expired": invalid,
                        "total_evidence": total,
                        "gap_detected": invalid > 0,
                    }
                )
        gaps.sort(key=lambda x: x["invalid_or_expired"], reverse=True)
        return gaps

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> EvidenceValidatorReport:
        by_framework: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_framework[r.framework.value] = by_framework.get(r.framework.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        avg_score = (
            round(sum(r.validity_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        invalid_count = sum(
            1
            for r in self._records
            if r.status
            in (
                ValidationStatus.INVALID,
                ValidationStatus.EXPIRED,
                ValidationStatus.INCOMPLETE,
            )
        )
        recs: list[str] = []
        if self._records and avg_score < self._min_validity_pct:
            recs.append(
                f"Average validity score {avg_score}% is below {self._min_validity_pct}% threshold"
            )
        if invalid_count > 0:
            recs.append(f"{invalid_count} evidence item(s) are invalid, expired, or incomplete")
        gaps = self.detect_validation_gaps()
        if gaps:
            recs.append(f"{len(gaps)} framework(s) have validation coverage gaps")
        if not recs:
            recs.append("All compliance evidence meets validity requirements")
        return EvidenceValidatorReport(
            total_records=len(self._records),
            total_findings=len(self._findings),
            avg_validity_score=avg_score,
            by_framework=by_framework,
            by_status=by_status,
            invalid_count=invalid_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._findings.clear()
        logger.info("evidence_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        framework_dist: dict[str, int] = {}
        for r in self._records:
            key = r.framework.value
            framework_dist[key] = framework_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_findings": len(self._findings),
            "min_validity_pct": self._min_validity_pct,
            "framework_distribution": framework_dist,
            "unique_controls": len({r.control_id for r in self._records}),
        }
