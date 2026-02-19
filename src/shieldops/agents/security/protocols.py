"""Abstract interfaces for Security Agent external dependencies.

Follows the protocol-based connector abstraction pattern from
connectors/base.py (ADR-002).
"""

import enum
from abc import ABC, abstractmethod
from typing import Any


class ScannerType(str, enum.Enum):
    """Categories of security scanner."""

    CVE = "cve"
    SECRET = "secret"
    IAC = "iac"
    NETWORK = "network"
    K8S_SECURITY = "k8s_security"
    CONTAINER = "container"


class SecurityScanner(ABC):
    """Abstract interface for non-CVE security scanners.

    Unlike CVESource which returns CVE-specific findings, SecurityScanner
    returns general security findings (misconfigurations, secrets, network issues).
    """

    scanner_name: str
    scanner_type: ScannerType

    @abstractmethod
    async def scan(self, target: str, **options: Any) -> list[dict[str, Any]]:
        """Scan a target for security issues.

        Args:
            target: Scanner-specific target (repo path, env name, directory, etc.).
            **options: Scanner-specific keyword options.

        Returns:
            List of finding dicts with keys:
                finding_id, scanner_type, severity, title, description,
                affected_resource, remediation, metadata
        """


class CVESource(ABC):
    """Abstract interface for CVE vulnerability databases.

    Implementations may wrap NVD, vendor advisories (GHSA), or commercial
    scanners (Snyk, Trivy).
    """

    source_name: str

    @abstractmethod
    async def scan(
        self,
        resource_id: str,
        severity_threshold: str = "medium",
    ) -> list[dict[str, Any]]:
        """Scan a resource for known CVEs at or above *severity_threshold*.

        Returns a list of finding dicts with keys:
            cve_id, severity, cvss_score, package_name,
            installed_version, fixed_version, affected_resource, description
        """


class CredentialStore(ABC):
    """Abstract interface for credential / secret management backends.

    Implementations may wrap HashiCorp Vault, AWS Secrets Manager,
    GCP Secret Manager, or Azure Key Vault.
    """

    store_name: str

    @abstractmethod
    async def list_credentials(self, environment: str | None = None) -> list[dict[str, Any]]:
        """List tracked credentials, optionally filtered by environment.

        Returns a list of credential dicts with keys:
            credential_id, credential_type, service,
            expires_at (datetime | None), last_rotated (datetime | None)
        """

    @abstractmethod
    async def rotate_credential(self, credential_id: str, credential_type: str) -> dict[str, Any]:
        """Rotate a single credential and return the result.

        Returns a dict with keys:
            credential_id, credential_type, service, success (bool),
            message, new_expiry (datetime | None)
        """
