"""Secrets Sprawl Detector — detect hardcoded credentials across repos and configs."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SecretType(StrEnum):
    API_KEY = "api_key"
    PASSWORD = "password"  # noqa: S105
    TOKEN = "token"  # noqa: S105
    PRIVATE_KEY = "private_key"
    CONNECTION_STRING = "connection_string"
    CERTIFICATE = "certificate"


class DetectionSource(StrEnum):
    GIT_REPOSITORY = "git_repository"
    CONFIG_FILE = "config_file"
    ENVIRONMENT_VARIABLE = "environment_variable"
    CONTAINER_IMAGE = "container_image"
    CI_CD_PIPELINE = "ci_cd_pipeline"


class SecretSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# --- Models ---


class SecretFinding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    secret_type: SecretType = SecretType.API_KEY
    source: DetectionSource = DetectionSource.GIT_REPOSITORY
    severity: SecretSeverity = SecretSeverity.MEDIUM
    service_name: str = ""
    file_path: str = ""
    description: str = ""
    is_resolved: bool = False
    resolved_at: float = 0.0
    created_at: float = Field(default_factory=time.time)


class SecretRotationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_id: str = ""
    service_name: str = ""
    rotated_by: str = ""
    rotation_method: str = ""
    rotated_at: float = Field(default_factory=time.time)


class SecretsReport(BaseModel):
    total_findings: int = 0
    open_findings: int = 0
    resolved_findings: int = 0
    high_severity_count: int = 0
    rotation_count: int = 0
    type_distribution: dict[str, int] = Field(default_factory=dict)
    source_distribution: dict[str, int] = Field(default_factory=dict)
    services_at_risk: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecretsSprawlDetector:
    """Detect hardcoded credentials across repos, configs, and CI/CD pipelines."""

    def __init__(
        self,
        max_findings: int = 200000,
        high_severity_threshold: int = 10,
    ) -> None:
        self._max_findings = max_findings
        self._high_severity_threshold = high_severity_threshold
        self._findings: list[SecretFinding] = []
        self._rotations: list[SecretRotationRecord] = []
        logger.info(
            "secrets_detector.initialized",
            max_findings=max_findings,
            high_severity_threshold=high_severity_threshold,
        )

    def record_finding(
        self,
        secret_type: SecretType,
        source: DetectionSource,
        severity: SecretSeverity,
        service_name: str,
        file_path: str = "",
        description: str = "",
    ) -> SecretFinding:
        """Record a newly detected secret finding."""
        finding = SecretFinding(
            secret_type=secret_type,
            source=source,
            severity=severity,
            service_name=service_name,
            file_path=file_path,
            description=description,
        )
        self._findings.append(finding)
        if len(self._findings) > self._max_findings:
            self._findings = self._findings[-self._max_findings :]
        logger.info(
            "secrets_detector.finding_recorded",
            finding_id=finding.id,
            secret_type=secret_type,
            severity=severity,
            service_name=service_name,
        )
        return finding

    def get_finding(self, finding_id: str) -> SecretFinding | None:
        """Retrieve a single finding by ID."""
        for f in self._findings:
            if f.id == finding_id:
                return f
        return None

    def list_findings(
        self,
        secret_type: SecretType | None = None,
        severity: SecretSeverity | None = None,
        is_resolved: bool | None = None,
        limit: int = 100,
    ) -> list[SecretFinding]:
        """List findings with optional filtering."""
        results = list(self._findings)
        if secret_type is not None:
            results = [f for f in results if f.secret_type == secret_type]
        if severity is not None:
            results = [f for f in results if f.severity == severity]
        if is_resolved is not None:
            results = [f for f in results if f.is_resolved == is_resolved]
        return results[-limit:]

    def resolve_finding(self, finding_id: str) -> bool:
        """Mark a finding as resolved with a resolution timestamp."""
        finding = self.get_finding(finding_id)
        if finding is None:
            return False
        finding.is_resolved = True
        finding.resolved_at = time.time()
        logger.info(
            "secrets_detector.finding_resolved",
            finding_id=finding_id,
            service_name=finding.service_name,
        )
        return True

    def record_rotation(
        self,
        finding_id: str,
        service_name: str,
        rotated_by: str,
        rotation_method: str,
    ) -> SecretRotationRecord:
        """Record a secret rotation event linked to a finding."""
        record = SecretRotationRecord(
            finding_id=finding_id,
            service_name=service_name,
            rotated_by=rotated_by,
            rotation_method=rotation_method,
        )
        self._rotations.append(record)
        if len(self._rotations) > self._max_findings:
            self._rotations = self._rotations[-self._max_findings :]
        logger.info(
            "secrets_detector.rotation_recorded",
            rotation_id=record.id,
            finding_id=finding_id,
            service_name=service_name,
            rotated_by=rotated_by,
        )
        return record

    def detect_high_risk_services(self) -> list[dict[str, Any]]:
        """Group unresolved findings by service, identify those exceeding the severity threshold.

        A service is high-risk when it has more unresolved HIGH or CRITICAL findings
        than the configured threshold.
        """
        service_counts: dict[str, dict[str, Any]] = {}
        for f in self._findings:
            if f.is_resolved:
                continue
            svc = f.service_name
            if svc not in service_counts:
                service_counts[svc] = {
                    "service_name": svc,
                    "total_open": 0,
                    "high_critical_count": 0,
                    "finding_types": set(),
                }
            service_counts[svc]["total_open"] += 1
            if f.severity in (SecretSeverity.HIGH, SecretSeverity.CRITICAL):
                service_counts[svc]["high_critical_count"] += 1
            service_counts[svc]["finding_types"].add(f.secret_type.value)

        high_risk: list[dict[str, Any]] = []
        for svc, data in service_counts.items():
            if data["high_critical_count"] >= self._high_severity_threshold:
                high_risk.append(
                    {
                        "service_name": svc,
                        "total_open": data["total_open"],
                        "high_critical_count": data["high_critical_count"],
                        "finding_types": sorted(data["finding_types"]),
                    }
                )

        high_risk.sort(key=lambda x: x["high_critical_count"], reverse=True)
        logger.info(
            "secrets_detector.high_risk_detected",
            high_risk_count=len(high_risk),
        )
        return high_risk

    def analyze_sprawl_trends(self) -> dict[str, Any]:
        """Analyze findings over time — group by month, track open vs resolved trend.

        Returns monthly breakdown with cumulative open/resolved counts derived
        from finding creation and resolution timestamps.
        """
        if not self._findings:
            return {"monthly_findings": [], "open_vs_resolved": [], "total": 0}

        # Group findings by year-month based on created_at
        monthly_buckets: dict[str, dict[str, int]] = {}
        for f in self._findings:
            t = time.gmtime(f.created_at)
            key = f"{t.tm_year}-{t.tm_mon:02d}"
            if key not in monthly_buckets:
                monthly_buckets[key] = {"new": 0, "resolved_in_month": 0}
            monthly_buckets[key]["new"] += 1

        # Track resolutions by month
        for f in self._findings:
            if f.is_resolved and f.resolved_at > 0:
                t = time.gmtime(f.resolved_at)
                key = f"{t.tm_year}-{t.tm_mon:02d}"
                if key not in monthly_buckets:
                    monthly_buckets[key] = {"new": 0, "resolved_in_month": 0}
                monthly_buckets[key]["resolved_in_month"] += 1

        sorted_months = sorted(monthly_buckets.keys())
        monthly_findings: list[dict[str, Any]] = []
        open_vs_resolved: list[dict[str, Any]] = []
        cumulative_open = 0
        cumulative_resolved = 0

        for month in sorted_months:
            data = monthly_buckets[month]
            cumulative_open += data["new"] - data["resolved_in_month"]
            cumulative_resolved += data["resolved_in_month"]
            monthly_findings.append(
                {
                    "month": month,
                    "new_findings": data["new"],
                    "resolved_in_month": data["resolved_in_month"],
                }
            )
            open_vs_resolved.append(
                {
                    "month": month,
                    "cumulative_open": cumulative_open,
                    "cumulative_resolved": cumulative_resolved,
                }
            )

        return {
            "monthly_findings": monthly_findings,
            "open_vs_resolved": open_vs_resolved,
            "total": len(self._findings),
        }

    def identify_unrotated_secrets(self) -> list[SecretFinding]:
        """Find open findings that have no matching rotation record.

        An unrotated secret is one that remains unresolved and has never been
        rotated, meaning the compromised credential is still potentially active.
        """
        rotated_finding_ids: set[str] = {r.finding_id for r in self._rotations}
        unrotated = [
            f for f in self._findings if not f.is_resolved and f.id not in rotated_finding_ids
        ]
        logger.info(
            "secrets_detector.unrotated_identified",
            unrotated_count=len(unrotated),
        )
        return unrotated

    def generate_secrets_report(self) -> SecretsReport:
        """Generate a comprehensive secrets sprawl report."""
        total = len(self._findings)
        open_count = sum(1 for f in self._findings if not f.is_resolved)
        resolved_count = total - open_count
        high_sev = sum(
            1
            for f in self._findings
            if f.severity in (SecretSeverity.HIGH, SecretSeverity.CRITICAL) and not f.is_resolved
        )

        # Type distribution
        type_dist: dict[str, int] = {}
        for f in self._findings:
            key = f.secret_type.value
            type_dist[key] = type_dist.get(key, 0) + 1

        # Source distribution
        source_dist: dict[str, int] = {}
        for f in self._findings:
            key = f.source.value
            source_dist[key] = source_dist.get(key, 0) + 1

        # Services at risk (services with unresolved high/critical findings)
        risk_services: set[str] = set()
        for f in self._findings:
            if not f.is_resolved and f.severity in (SecretSeverity.HIGH, SecretSeverity.CRITICAL):
                risk_services.add(f.service_name)

        # Build recommendations
        recommendations: list[str] = []
        if high_sev > 0:
            recommendations.append(
                f"{high_sev} high/critical unresolved secret(s) require immediate rotation"
            )

        unrotated = self.identify_unrotated_secrets()
        if unrotated:
            recommendations.append(
                f"{len(unrotated)} secret(s) have not been rotated — initiate credential rotation"
            )

        high_risk_svcs = self.detect_high_risk_services()
        if high_risk_svcs:
            svc_names = [s["service_name"] for s in high_risk_svcs[:5]]
            recommendations.append(
                f"High-risk services requiring attention: {', '.join(svc_names)}"
            )

        git_findings = sum(
            1
            for f in self._findings
            if f.source == DetectionSource.GIT_REPOSITORY and not f.is_resolved
        )
        if git_findings > 0:
            recommendations.append(
                f"{git_findings} secret(s) found in git repositories — "
                f"enable pre-commit secret scanning hooks"
            )

        report = SecretsReport(
            total_findings=total,
            open_findings=open_count,
            resolved_findings=resolved_count,
            high_severity_count=high_sev,
            rotation_count=len(self._rotations),
            type_distribution=type_dist,
            source_distribution=source_dist,
            services_at_risk=sorted(risk_services),
            recommendations=recommendations,
        )
        logger.info(
            "secrets_detector.report_generated",
            total_findings=total,
            open_findings=open_count,
            high_severity_count=high_sev,
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored findings and rotations."""
        self._findings.clear()
        self._rotations.clear()
        logger.info("secrets_detector.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about stored findings and rotations."""
        severity_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        services: set[str] = set()
        for f in self._findings:
            severity_counts[f.severity.value] = severity_counts.get(f.severity.value, 0) + 1
            source_counts[f.source.value] = source_counts.get(f.source.value, 0) + 1
            services.add(f.service_name)
        return {
            "total_findings": len(self._findings),
            "total_rotations": len(self._rotations),
            "open_findings": sum(1 for f in self._findings if not f.is_resolved),
            "severity_distribution": severity_counts,
            "source_distribution": source_counts,
            "unique_services": len(services),
        }
