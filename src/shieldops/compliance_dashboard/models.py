"""Compliance Dashboard — Pydantic v2 data models."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ComplianceFramework(StrEnum):
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"


class ControlStatus(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"
    NOT_ASSESSED = "not_assessed"


class EvidenceType(StrEnum):
    LOG = "log"
    SCREENSHOT = "screenshot"
    CONFIG = "config"
    REPORT = "report"
    ATTESTATION = "attestation"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ComplianceControl(BaseModel):
    """A single compliance control within a framework."""

    control_id: str
    framework: ComplianceFramework
    category: str = ""
    title: str = ""
    description: str = ""
    status: ControlStatus = ControlStatus.NOT_ASSESSED
    evidence_ids: list[str] = Field(default_factory=list)
    last_assessed: float | None = None
    assessor: str = ""
    notes: str = ""
    remediation_steps: list[str] = Field(default_factory=list)


class EvidenceRecord(BaseModel):
    """An evidence artifact linked to a compliance control."""

    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    evidence_type: EvidenceType = EvidenceType.LOG
    title: str = ""
    description: str = ""
    file_path: str = ""
    collected_at: float = Field(default_factory=time.time)
    collector: str = ""
    verified: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComplianceSummary(BaseModel):
    """Aggregate compliance posture for a framework."""

    framework: ComplianceFramework
    total_controls: int = 0
    compliant: int = 0
    non_compliant: int = 0
    partial: int = 0
    not_assessed: int = 0
    compliance_percentage: float = 0.0
    last_full_assessment: float | None = None
    risk_score: float = 0.0
