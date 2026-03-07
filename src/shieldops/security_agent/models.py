"""Pydantic v2 models for the Security Agent MVP."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class VulnerabilitySeverity(StrEnum):
    """Severity levels for vulnerabilities."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityStatus(StrEnum):
    """Lifecycle status of a vulnerability."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    FIXED = "fixed"
    WONT_FIX = "wont_fix"
    FALSE_POSITIVE = "false_positive"


class VulnerabilityRecord(BaseModel):
    """A single CVE or vulnerability finding from a container/image scan."""

    cve_id: str = Field(..., description="CVE identifier, e.g. CVE-2024-1234")
    package_name: str = Field(..., description="Affected package name")
    installed_version: str = Field(..., description="Currently installed version")
    fixed_version: str | None = Field(None, description="Version that contains the fix")
    severity: VulnerabilitySeverity
    description: str = ""
    cvss_score: float = Field(0.0, ge=0.0, le=10.0, description="CVSS v3 base score")
    affected_service: str = ""
    namespace: str = ""
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    remediated_at: datetime | None = None
    status: VulnerabilityStatus = VulnerabilityStatus.OPEN


class FindingType(StrEnum):
    """Types of secret findings."""

    API_KEY = "api_key"
    PASSWORD = "password"  # noqa: S105
    PRIVATE_KEY = "private_key"
    TOKEN = "token"  # noqa: S105
    CERTIFICATE = "certificate"


class SecretFinding(BaseModel):
    """A hardcoded secret detected during scanning."""

    finding_type: FindingType
    location: str = Field(..., description="Human-readable location, e.g. repo:path")
    file_path: str = ""
    line_number: int | None = None
    snippet_masked: str = Field("", description="Context snippet with the secret value masked")
    severity: VulnerabilitySeverity = VulnerabilitySeverity.HIGH
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = False


class CertificateStatus(BaseModel):
    """TLS certificate status for a domain or Kubernetes secret."""

    domain: str
    issuer: str = ""
    not_before: datetime | None = None
    not_after: datetime | None = None
    days_until_expiry: int = 0
    is_expired: bool = False
    serial_number: str = ""
    fingerprint: str = ""


class SecurityScanResult(BaseModel):
    """Aggregated result from a full security scan."""

    scan_id: str = Field(..., description="Unique identifier for this scan run")
    scan_type: str = Field("full", description="full | cve | secrets | certificates")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    vulnerabilities: list[VulnerabilityRecord] = Field(default_factory=list)
    secrets: list[SecretFinding] = Field(default_factory=list)
    certificates: list[CertificateStatus] = Field(default_factory=list)
    summary: dict[str, int | str] = Field(default_factory=dict)
