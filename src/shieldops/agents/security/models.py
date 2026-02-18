"""State models for the Security Agent."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from shieldops.models.base import AlertContext, Environment


class CVEFinding(BaseModel):
    """A CVE vulnerability detected on infrastructure."""

    cve_id: str  # e.g. CVE-2024-1234
    severity: str  # critical, high, medium, low
    cvss_score: float = Field(ge=0.0, le=10.0)
    package_name: str
    installed_version: str
    fixed_version: str | None = None
    affected_resource: str  # namespace/pod or host
    description: str = ""
    published_at: datetime | None = None


class CredentialStatus(BaseModel):
    """Status of a tracked credential."""

    credential_id: str
    credential_type: str  # database_password, api_key, tls_certificate, ssh_key
    service: str
    environment: Environment
    expires_at: datetime | None = None
    days_until_expiry: int | None = None
    last_rotated: datetime | None = None
    needs_rotation: bool = False
    rotation_result: str | None = None  # success, failed, pending


class ComplianceControl(BaseModel):
    """Status of a single compliance control."""

    control_id: str  # e.g. SOC2-CC6.1, PCI-DSS-6.2
    framework: str  # soc2, pci_dss, hipaa, cis
    title: str
    status: str  # passing, failing, not_applicable
    severity: str  # critical, high, medium, low
    evidence: list[str] = Field(default_factory=list)
    remediation: str | None = None


class SecurityPosture(BaseModel):
    """Overall security posture snapshot."""

    overall_score: float = Field(ge=0.0, le=100.0, default=0.0)
    critical_cves: int = 0
    high_cves: int = 0
    pending_patches: int = 0
    credentials_expiring_soon: int = 0
    compliance_scores: dict[str, float] = Field(default_factory=dict)
    top_risks: list[str] = Field(default_factory=list)


class SecurityStep(BaseModel):
    """A single step in the security agent's reasoning chain."""

    step_number: int
    action: str  # scan_cves, assess_findings, check_credentials, etc.
    input_summary: str
    output_summary: str
    duration_ms: int
    tool_used: str | None = None


class SecurityScanState(BaseModel):
    """Full state of a security scan workflow (LangGraph state)."""

    # Input
    scan_id: str = ""
    scan_type: str = "full"  # full, cve_only, credentials_only, compliance_only
    target_resources: list[str] = Field(default_factory=list)
    target_environment: Environment = Environment.PRODUCTION
    compliance_frameworks: list[str] = Field(default_factory=list)

    # CVE findings
    cve_findings: list[CVEFinding] = Field(default_factory=list)
    critical_cve_count: int = 0
    patches_available: int = 0

    # Credential status
    credential_statuses: list[CredentialStatus] = Field(default_factory=list)
    credentials_needing_rotation: int = 0

    # Compliance
    compliance_controls: list[ComplianceControl] = Field(default_factory=list)
    compliance_score: float = 0.0

    # Overall posture
    posture: SecurityPosture | None = None

    # Metadata
    scan_start: datetime | None = None
    scan_duration_ms: int = 0
    reasoning_chain: list[SecurityStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
