"""Continuous compliance validation against security benchmarks.

Validates infrastructure and application resources against compliance frameworks
(CIS, NIST, SOC2, PCI-DSS, HIPAA, ISO 27001) and tracks pass/fail results
with evidence and remediation recommendations.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class ComplianceFramework(enum.StrEnum):
    CIS = "cis"
    NIST_CSF = "nist_csf"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    ISO_27001 = "iso_27001"


class ValidationResult(enum.StrEnum):
    PASS = "pass"  # noqa: S105
    FAIL = "fail"
    WARNING = "warning"
    NOT_APPLICABLE = "not_applicable"


# -- Models --------------------------------------------------------------------


class ComplianceControl(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    framework: ComplianceFramework
    control_id: str
    title: str
    description: str = ""
    severity: str = "medium"
    auto_remediate: bool = False
    created_at: float = Field(default_factory=time.time)


class ValidationRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    control_id: str
    resource_id: str
    result: ValidationResult
    evidence: str = ""
    remediation_action: str = ""
    validated_at: float = Field(default_factory=time.time)


class ComplianceSnapshot(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    framework: ComplianceFramework
    total_controls: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    compliance_pct: float = 0.0
    snapshot_at: float = Field(default_factory=time.time)


# -- Engine --------------------------------------------------------------------


class ContinuousComplianceValidator:
    """Validate resources against compliance frameworks continuously.

    Parameters
    ----------
    max_controls:
        Maximum compliance controls to store.
    max_records:
        Maximum validation records to store.
    """

    def __init__(
        self,
        max_controls: int = 1000,
        max_records: int = 50000,
    ) -> None:
        self._controls: dict[str, ComplianceControl] = {}
        self._records: list[ValidationRecord] = []
        self._snapshots: list[ComplianceSnapshot] = []
        self._max_controls = max_controls
        self._max_records = max_records

    def register_control(
        self,
        framework: ComplianceFramework,
        control_id: str,
        title: str,
        description: str = "",
        severity: str = "medium",
        auto_remediate: bool = False,
    ) -> ComplianceControl:
        if len(self._controls) >= self._max_controls:
            raise ValueError(f"Maximum controls limit reached: {self._max_controls}")
        control = ComplianceControl(
            framework=framework,
            control_id=control_id,
            title=title,
            description=description,
            severity=severity,
            auto_remediate=auto_remediate,
        )
        self._controls[control.id] = control
        logger.info(
            "compliance_control_registered",
            control_id=control.id,
            framework=framework,
            title=title,
        )
        return control

    def validate_control(
        self,
        control_id: str,
        resource_id: str,
        result: ValidationResult,
        evidence: str = "",
        remediation_action: str = "",
    ) -> ValidationRecord:
        # Find the control by its internal id
        control = self._controls.get(control_id)
        if control is None:
            raise ValueError(f"Control not found: {control_id}")
        if len(self._records) >= self._max_records:
            raise ValueError(f"Maximum records limit reached: {self._max_records}")
        record = ValidationRecord(
            control_id=control_id,
            resource_id=resource_id,
            result=result,
            evidence=evidence,
            remediation_action=remediation_action,
        )
        self._records.append(record)
        logger.info(
            "compliance_validation_recorded",
            record_id=record.id,
            control_id=control_id,
            result=result,
        )
        return record

    def get_snapshot(self, framework: ComplianceFramework) -> ComplianceSnapshot:
        # Collect controls for this framework
        framework_controls = {
            cid: c for cid, c in self._controls.items() if c.framework == framework
        }
        if not framework_controls:
            snapshot = ComplianceSnapshot(framework=framework)
            self._snapshots.append(snapshot)
            return snapshot

        # Find latest validation record per control
        latest: dict[str, ValidationRecord] = {}
        for record in self._records:
            if record.control_id in framework_controls:
                existing = latest.get(record.control_id)
                if existing is None or record.validated_at > existing.validated_at:
                    latest[record.control_id] = record

        passed = sum(1 for r in latest.values() if r.result == ValidationResult.PASS)
        failed = sum(1 for r in latest.values() if r.result == ValidationResult.FAIL)
        warnings = sum(1 for r in latest.values() if r.result == ValidationResult.WARNING)
        total = len(framework_controls)
        compliance_pct = (passed / total * 100) if total > 0 else 0.0

        snapshot = ComplianceSnapshot(
            framework=framework,
            total_controls=total,
            passed=passed,
            failed=failed,
            warnings=warnings,
            compliance_pct=round(compliance_pct, 2),
        )
        self._snapshots.append(snapshot)
        logger.info(
            "compliance_snapshot_created",
            framework=framework,
            compliance_pct=snapshot.compliance_pct,
        )
        return snapshot

    def list_controls(
        self,
        framework: ComplianceFramework | None = None,
    ) -> list[ComplianceControl]:
        controls = list(self._controls.values())
        if framework:
            controls = [c for c in controls if c.framework == framework]
        return controls

    def delete_control(self, control_id: str) -> bool:
        return self._controls.pop(control_id, None) is not None

    def get_failing_controls(
        self,
        framework: ComplianceFramework | None = None,
    ) -> list[ValidationRecord]:
        # Build set of relevant control ids
        if framework:
            relevant = {cid for cid, c in self._controls.items() if c.framework == framework}
        else:
            relevant = set(self._controls.keys())

        # Find latest record per control
        latest: dict[str, ValidationRecord] = {}
        for record in self._records:
            if record.control_id not in relevant:
                continue
            existing = latest.get(record.control_id)
            if existing is None or record.validated_at > existing.validated_at:
                latest[record.control_id] = record

        return [r for r in latest.values() if r.result == ValidationResult.FAIL]

    def list_records(
        self,
        control_id: str | None = None,
        result: ValidationResult | None = None,
        limit: int = 100,
    ) -> list[ValidationRecord]:
        records = list(self._records)
        if control_id:
            records = [r for r in records if r.control_id == control_id]
        if result:
            records = [r for r in records if r.result == result]
        return records[-limit:]

    def get_remediation_candidates(self) -> list[ComplianceControl]:
        # Controls with auto_remediate=True that have a recent FAIL
        auto_controls = {cid: c for cid, c in self._controls.items() if c.auto_remediate}
        if not auto_controls:
            return []

        # Find latest record per auto-remediate control
        latest: dict[str, ValidationRecord] = {}
        for record in self._records:
            if record.control_id not in auto_controls:
                continue
            existing = latest.get(record.control_id)
            if existing is None or record.validated_at > existing.validated_at:
                latest[record.control_id] = record

        return [
            auto_controls[cid] for cid, r in latest.items() if r.result == ValidationResult.FAIL
        ]

    def get_stats(self) -> dict[str, Any]:
        total_pass = sum(1 for r in self._records if r.result == ValidationResult.PASS)
        total_fail = sum(1 for r in self._records if r.result == ValidationResult.FAIL)
        frameworks = {c.framework for c in self._controls.values()}
        return {
            "total_controls": len(self._controls),
            "total_records": len(self._records),
            "total_snapshots": len(self._snapshots),
            "total_pass": total_pass,
            "total_fail": total_fail,
            "frameworks": sorted(frameworks),
        }
