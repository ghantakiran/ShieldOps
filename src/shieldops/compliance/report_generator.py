"""Compliance report generator.

Generates consolidated multi-framework compliance reports with evidence
tracking for SOC2, PCI-DSS, HIPAA, ISO27001, and NIST frameworks.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class ComplianceFramework(enum.StrEnum):
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    ISO27001 = "iso27001"
    NIST = "nist"


class ControlStatus(enum.StrEnum):
    PASSING = "passing"
    FAILING = "failing"
    NOT_ASSESSED = "not_assessed"
    NOT_APPLICABLE = "not_applicable"


# ── Models ───────────────────────────────────────────────────────────


class ControlEvidence(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    control_id: str
    description: str
    source: str = ""
    collected_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComplianceControl(BaseModel):
    id: str
    name: str
    description: str = ""
    framework: ComplianceFramework
    status: ControlStatus = ControlStatus.NOT_ASSESSED
    evidence: list[ControlEvidence] = Field(default_factory=list)
    notes: str = ""
    assessed_at: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    framework: ComplianceFramework
    title: str = ""
    controls: list[ComplianceControl] = Field(default_factory=list)
    overall_score: float = 0.0
    passing_count: int = 0
    failing_count: int = 0
    not_assessed_count: int = 0
    generated_at: float = Field(default_factory=time.time)
    generated_by: str = ""
    period_start: str = ""
    period_end: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Framework control templates ──────────────────────────────────────

_FRAMEWORK_CONTROLS: dict[ComplianceFramework, list[dict[str, str]]] = {
    ComplianceFramework.SOC2: [
        {
            "id": "CC1.1",
            "name": "Control Environment",
            "description": "Commitment to integrity and ethics",
        },
        {
            "id": "CC2.1",
            "name": "Information and Communication",
            "description": "Relevant quality information",
        },
        {"id": "CC3.1", "name": "Risk Assessment", "description": "Identifies and assesses risk"},
        {"id": "CC4.1", "name": "Monitoring", "description": "Evaluates control performance"},
        {
            "id": "CC5.1",
            "name": "Control Activities",
            "description": "Selects and develops controls",
        },
        {"id": "CC6.1", "name": "Logical Access", "description": "Logical access security"},
        {
            "id": "CC7.1",
            "name": "System Operations",
            "description": "Detects and responds to anomalies",
        },
        {
            "id": "CC8.1",
            "name": "Change Management",
            "description": "Manages infrastructure changes",
        },
        {"id": "CC9.1", "name": "Risk Mitigation", "description": "Identifies and mitigates risks"},
    ],
    ComplianceFramework.PCI_DSS: [
        {
            "id": "PCI-1",
            "name": "Firewall Configuration",
            "description": "Install and maintain firewall",
        },
        {"id": "PCI-2", "name": "Default Passwords", "description": "No vendor-supplied defaults"},
        {"id": "PCI-3", "name": "Stored Data", "description": "Protect stored cardholder data"},
        {
            "id": "PCI-4",
            "name": "Encryption",
            "description": "Encrypt cardholder data transmission",
        },
        {"id": "PCI-5", "name": "Anti-Virus", "description": "Use and update anti-virus software"},
        {
            "id": "PCI-6",
            "name": "Secure Systems",
            "description": "Develop and maintain secure systems",
        },
    ],
    ComplianceFramework.HIPAA: [
        {
            "id": "HIPAA-164.308",
            "name": "Administrative Safeguards",
            "description": "Security management process",
        },
        {
            "id": "HIPAA-164.310",
            "name": "Physical Safeguards",
            "description": "Facility access controls",
        },
        {
            "id": "HIPAA-164.312",
            "name": "Technical Safeguards",
            "description": "Access control and audit",
        },
        {
            "id": "HIPAA-164.314",
            "name": "Organization Requirements",
            "description": "Business associate agreements",
        },
    ],
    ComplianceFramework.ISO27001: [
        {
            "id": "ISO-A5",
            "name": "Information Security Policies",
            "description": "Management direction for infosec",
        },
        {
            "id": "ISO-A6",
            "name": "Organization of InfoSec",
            "description": "Internal organization and mobile",
        },
        {
            "id": "ISO-A7",
            "name": "Human Resource Security",
            "description": "Employment lifecycle security",
        },
        {
            "id": "ISO-A8",
            "name": "Asset Management",
            "description": "Asset classification and responsibility",
        },
        {"id": "ISO-A9", "name": "Access Control", "description": "User access management"},
    ],
    ComplianceFramework.NIST: [
        {
            "id": "NIST-ID",
            "name": "Identify",
            "description": "Asset management and risk assessment",
        },
        {"id": "NIST-PR", "name": "Protect", "description": "Access control and data security"},
        {"id": "NIST-DE", "name": "Detect", "description": "Anomalies and continuous monitoring"},
        {"id": "NIST-RS", "name": "Respond", "description": "Response planning and communications"},
        {"id": "NIST-RC", "name": "Recover", "description": "Recovery planning and improvements"},
    ],
}


# ── Generator ────────────────────────────────────────────────────────


class ComplianceReportGenerator:
    """Generate compliance reports for multiple frameworks.

    Parameters
    ----------
    max_reports:
        Maximum reports to store.
    """

    def __init__(self, max_reports: int = 500) -> None:
        self._reports: dict[str, ComplianceReport] = {}
        self._max_reports = max_reports

    def generate_report(
        self,
        framework: ComplianceFramework,
        title: str = "",
        control_statuses: dict[str, ControlStatus] | None = None,
        generated_by: str = "",
        period_start: str = "",
        period_end: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ComplianceReport:
        if len(self._reports) >= self._max_reports:
            raise ValueError(f"Maximum reports limit reached: {self._max_reports}")

        statuses = control_statuses or {}
        template = _FRAMEWORK_CONTROLS.get(framework, [])
        controls: list[ComplianceControl] = []
        for ctrl_def in template:
            ctrl_id = ctrl_def["id"]
            status = statuses.get(ctrl_id, ControlStatus.NOT_ASSESSED)
            ctrl = ComplianceControl(
                id=ctrl_id,
                name=ctrl_def["name"],
                description=ctrl_def["description"],
                framework=framework,
                status=status,
                assessed_at=time.time() if status != ControlStatus.NOT_ASSESSED else None,
            )
            controls.append(ctrl)

        passing = sum(1 for c in controls if c.status == ControlStatus.PASSING)
        failing = sum(1 for c in controls if c.status == ControlStatus.FAILING)
        not_assessed = sum(1 for c in controls if c.status == ControlStatus.NOT_ASSESSED)
        applicable = len(controls) - sum(
            1 for c in controls if c.status == ControlStatus.NOT_APPLICABLE
        )
        score = (passing / applicable * 100) if applicable > 0 else 0.0

        report = ComplianceReport(
            framework=framework,
            title=title or f"{framework.value.upper()} Compliance Report",
            controls=controls,
            overall_score=round(score, 2),
            passing_count=passing,
            failing_count=failing,
            not_assessed_count=not_assessed,
            generated_by=generated_by,
            period_start=period_start,
            period_end=period_end,
            metadata=metadata or {},
        )
        self._reports[report.id] = report
        logger.info(
            "compliance_report_generated",
            report_id=report.id,
            framework=framework,
            score=score,
        )
        return report

    def add_evidence(
        self,
        report_id: str,
        control_id: str,
        description: str,
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ControlEvidence | None:
        report = self._reports.get(report_id)
        if report is None:
            return None
        for ctrl in report.controls:
            if ctrl.id == control_id:
                evidence = ControlEvidence(
                    control_id=control_id,
                    description=description,
                    source=source,
                    metadata=metadata or {},
                )
                ctrl.evidence.append(evidence)
                return evidence
        return None

    def get_report(self, report_id: str) -> ComplianceReport | None:
        return self._reports.get(report_id)

    def list_reports(
        self,
        framework: ComplianceFramework | None = None,
        limit: int = 50,
    ) -> list[ComplianceReport]:
        reports = sorted(self._reports.values(), key=lambda r: r.generated_at, reverse=True)
        if framework:
            reports = [r for r in reports if r.framework == framework]
        return reports[:limit]

    def get_compliance_score(self, report_id: str) -> dict[str, Any] | None:
        report = self._reports.get(report_id)
        if report is None:
            return None
        return {
            "report_id": report.id,
            "framework": report.framework.value,
            "overall_score": report.overall_score,
            "passing": report.passing_count,
            "failing": report.failing_count,
            "not_assessed": report.not_assessed_count,
            "total_controls": len(report.controls),
        }

    def get_stats(self) -> dict[str, Any]:
        by_framework: dict[str, int] = {}
        avg_score = 0.0
        for r in self._reports.values():
            by_framework[r.framework.value] = by_framework.get(r.framework.value, 0) + 1
            avg_score += r.overall_score
        return {
            "total_reports": len(self._reports),
            "by_framework": by_framework,
            "avg_score": round(avg_score / len(self._reports), 2) if self._reports else 0.0,
        }
