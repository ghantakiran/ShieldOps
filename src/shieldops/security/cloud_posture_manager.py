"""Cloud Security Posture Manager — cloud misconfiguration detection across AWS/GCP/Azure."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MisconfigurationType(StrEnum):
    PUBLIC_ACCESS = "public_access"
    WEAK_ENCRYPTION = "weak_encryption"
    PERMISSIVE_IAM = "permissive_iam"
    MISSING_LOGGING = "missing_logging"
    UNPATCHED_RESOURCE = "unpatched_resource"
    NETWORK_EXPOSURE = "network_exposure"


class ComplianceBenchmark(StrEnum):
    CIS_AWS = "cis_aws"
    CIS_GCP = "cis_gcp"
    CIS_AZURE = "cis_azure"
    NIST_800_53 = "nist_800_53"
    SOC2_TYPE2 = "soc2_type2"


class RemediationPriority(StrEnum):
    IMMEDIATE = "immediate"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class CloudResource(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    resource_type: str = ""
    cloud_provider: str = ""
    region: str = ""
    account_id: str = ""
    compliance_benchmarks: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class MisconfigurationFinding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    finding_type: MisconfigurationType = MisconfigurationType.PUBLIC_ACCESS
    benchmark: ComplianceBenchmark = ComplianceBenchmark.CIS_AWS
    priority: RemediationPriority = RemediationPriority.MEDIUM
    description: str = ""
    is_resolved: bool = False
    resolved_at: float = 0.0
    created_at: float = Field(default_factory=time.time)


class PostureReport(BaseModel):
    total_resources: int = 0
    total_findings: int = 0
    open_findings: int = 0
    resolved_findings: int = 0
    compliance_score: float = 0.0
    critical_findings: int = 0
    provider_distribution: dict[str, int] = Field(default_factory=dict)
    finding_type_distribution: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CloudSecurityPostureManager:
    """Cloud misconfiguration detection and compliance scoring across AWS/GCP/Azure."""

    def __init__(
        self,
        max_resources: int = 200000,
        auto_resolve_days: int = 30,
    ) -> None:
        self._max_resources = max_resources
        self._auto_resolve_days = auto_resolve_days
        self._resources: list[CloudResource] = []
        self._findings: list[MisconfigurationFinding] = []
        logger.info(
            "cloud_posture.initialized",
            max_resources=max_resources,
            auto_resolve_days=auto_resolve_days,
        )

    def register_resource(
        self,
        resource_id: str,
        resource_type: str,
        cloud_provider: str,
        region: str = "",
        account_id: str = "",
        compliance_benchmarks: list[str] | None = None,
    ) -> CloudResource:
        """Register a cloud resource for posture management."""
        resource = CloudResource(
            resource_id=resource_id,
            resource_type=resource_type,
            cloud_provider=cloud_provider,
            region=region,
            account_id=account_id,
            compliance_benchmarks=compliance_benchmarks or [],
        )
        self._resources.append(resource)
        if len(self._resources) > self._max_resources:
            self._resources = self._resources[-self._max_resources :]
        logger.info(
            "cloud_posture.resource_registered",
            internal_id=resource.id,
            resource_id=resource_id,
            resource_type=resource_type,
            cloud_provider=cloud_provider,
        )
        return resource

    def get_resource(self, resource_id_str: str) -> CloudResource | None:
        """Retrieve a single resource by internal ID."""
        for r in self._resources:
            if r.id == resource_id_str:
                return r
        return None

    def list_resources(
        self,
        cloud_provider: str | None = None,
        resource_type: str | None = None,
        limit: int = 100,
    ) -> list[CloudResource]:
        """List resources with optional filtering by provider and resource type."""
        results = list(self._resources)
        if cloud_provider is not None:
            results = [r for r in results if r.cloud_provider == cloud_provider]
        if resource_type is not None:
            results = [r for r in results if r.resource_type == resource_type]
        return results[-limit:]

    def record_finding(
        self,
        resource_id: str,
        finding_type: MisconfigurationType = MisconfigurationType.PUBLIC_ACCESS,
        benchmark: ComplianceBenchmark = ComplianceBenchmark.CIS_AWS,
        priority: RemediationPriority = RemediationPriority.MEDIUM,
        description: str = "",
    ) -> MisconfigurationFinding:
        """Record a misconfiguration finding against a resource's internal ID."""
        finding = MisconfigurationFinding(
            resource_id=resource_id,
            finding_type=finding_type,
            benchmark=benchmark,
            priority=priority,
            description=description,
        )
        self._findings.append(finding)
        if len(self._findings) > self._max_resources * 5:
            self._findings = self._findings[-(self._max_resources * 5) :]

        severity_label = (
            "warning"
            if priority in (RemediationPriority.IMMEDIATE, RemediationPriority.HIGH)
            else "info"
        )
        log_fn = logger.warning if severity_label == "warning" else logger.info
        log_fn(
            "cloud_posture.finding_recorded",
            finding_id=finding.id,
            resource_id=resource_id,
            finding_type=finding_type,
            priority=priority,
            benchmark=benchmark,
        )
        return finding

    def evaluate_resource(self, resource_internal_id: str) -> list[MisconfigurationFinding]:
        """List all findings for a specific resource by its internal ID."""
        resource = self.get_resource(resource_internal_id)
        if resource is None:
            return []
        return [f for f in self._findings if f.resource_id == resource_internal_id]

    def calculate_compliance_score(self) -> dict[str, Any]:
        """Calculate compliance score per benchmark.

        Score formula: (total_findings - open_findings) / total_findings * 100
        A benchmark with zero findings scores 100% (fully compliant).
        """
        benchmark_stats: dict[str, dict[str, int]] = {}

        for finding in self._findings:
            key = finding.benchmark.value
            if key not in benchmark_stats:
                benchmark_stats[key] = {"total": 0, "open": 0, "resolved": 0}
            benchmark_stats[key]["total"] += 1
            if finding.is_resolved:
                benchmark_stats[key]["resolved"] += 1
            else:
                benchmark_stats[key]["open"] += 1

        scores: dict[str, Any] = {}
        for benchmark, stats in benchmark_stats.items():
            total = stats["total"]
            open_count = stats["open"]
            score = round((total - open_count) / total * 100, 1) if total > 0 else 100.0
            scores[benchmark] = {
                "score": score,
                "total_findings": total,
                "open_findings": open_count,
                "resolved_findings": stats["resolved"],
            }

        # Overall score
        total_all = sum(s["total"] for s in benchmark_stats.values())
        open_all = sum(s["open"] for s in benchmark_stats.values())
        overall = round((total_all - open_all) / total_all * 100, 1) if total_all > 0 else 100.0

        return {
            "overall_score": overall,
            "benchmark_scores": scores,
            "total_findings": total_all,
            "open_findings": open_all,
        }

    def detect_high_risk_resources(self) -> list[dict[str, Any]]:
        """Identify resources that have IMMEDIATE priority findings."""
        # Find resource IDs with IMMEDIATE findings
        immediate_findings: dict[str, list[MisconfigurationFinding]] = {}
        for f in self._findings:
            if f.priority == RemediationPriority.IMMEDIATE and not f.is_resolved:
                if f.resource_id not in immediate_findings:
                    immediate_findings[f.resource_id] = []
                immediate_findings[f.resource_id].append(f)

        high_risk: list[dict[str, Any]] = []
        for resource_id, findings in immediate_findings.items():
            resource = self.get_resource(resource_id)
            resource_info = ""
            cloud_provider = ""
            resource_type = ""
            if resource:
                resource_info = resource.resource_id
                cloud_provider = resource.cloud_provider
                resource_type = resource.resource_type

            finding_types = list({f.finding_type.value for f in findings})
            high_risk.append(
                {
                    "internal_id": resource_id,
                    "resource_id": resource_info,
                    "cloud_provider": cloud_provider,
                    "resource_type": resource_type,
                    "immediate_finding_count": len(findings),
                    "finding_types": finding_types,
                    "descriptions": [f.description for f in findings],
                }
            )

        # Sort by finding count descending
        high_risk.sort(key=lambda x: x["immediate_finding_count"], reverse=True)
        logger.info(
            "cloud_posture.high_risk_detected",
            high_risk_count=len(high_risk),
        )
        return high_risk

    def resolve_finding(self, finding_id: str) -> bool:
        """Mark a finding as resolved with a timestamp."""
        for f in self._findings:
            if f.id == finding_id:
                f.is_resolved = True
                f.resolved_at = time.time()
                logger.info(
                    "cloud_posture.finding_resolved",
                    finding_id=finding_id,
                    finding_type=f.finding_type,
                )
                return True
        return False

    def get_findings_by_type(
        self,
        finding_type: MisconfigurationType,
        include_resolved: bool = False,
    ) -> list[MisconfigurationFinding]:
        """List all findings of a specific type, optionally including resolved ones."""
        results = [f for f in self._findings if f.finding_type == finding_type]
        if not include_resolved:
            results = [f for f in results if not f.is_resolved]
        return results

    def get_provider_summary(self) -> list[dict[str, Any]]:
        """Summarize findings per cloud provider."""
        # Map resource internal IDs to providers
        resource_provider: dict[str, str] = {}
        for r in self._resources:
            resource_provider[r.id] = r.cloud_provider

        provider_stats: dict[str, dict[str, int]] = {}
        for f in self._findings:
            provider = resource_provider.get(f.resource_id, "unknown")
            if provider not in provider_stats:
                provider_stats[provider] = {"total": 0, "open": 0, "immediate": 0}
            provider_stats[provider]["total"] += 1
            if not f.is_resolved:
                provider_stats[provider]["open"] += 1
            if f.priority == RemediationPriority.IMMEDIATE and not f.is_resolved:
                provider_stats[provider]["immediate"] += 1

        results: list[dict[str, Any]] = []
        for provider, stats in provider_stats.items():
            resource_count = sum(1 for r in self._resources if r.cloud_provider == provider)
            results.append(
                {
                    "cloud_provider": provider,
                    "resource_count": resource_count,
                    "total_findings": stats["total"],
                    "open_findings": stats["open"],
                    "immediate_findings": stats["immediate"],
                }
            )

        results.sort(key=lambda x: x["open_findings"], reverse=True)
        return results

    def generate_posture_report(self) -> PostureReport:
        """Generate a comprehensive cloud security posture report."""
        total_resources = len(self._resources)
        total_findings = len(self._findings)
        open_findings = sum(1 for f in self._findings if not f.is_resolved)
        resolved_findings = sum(1 for f in self._findings if f.is_resolved)

        # Compliance score
        compliance_data = self.calculate_compliance_score()
        compliance_score = compliance_data["overall_score"]

        # Critical findings (IMMEDIATE priority, not resolved)
        critical_findings = sum(
            1
            for f in self._findings
            if f.priority == RemediationPriority.IMMEDIATE and not f.is_resolved
        )

        # Provider distribution
        provider_dist: dict[str, int] = {}
        for r in self._resources:
            provider_dist[r.cloud_provider] = provider_dist.get(r.cloud_provider, 0) + 1

        # Finding type distribution
        type_dist: dict[str, int] = {}
        for f in self._findings:
            if not f.is_resolved:
                key = f.finding_type.value
                type_dist[key] = type_dist.get(key, 0) + 1

        # Build recommendations
        recommendations: list[str] = []

        if critical_findings > 0:
            recommendations.append(
                f"{critical_findings} IMMEDIATE-priority finding(s) require urgent remediation — "
                f"address public access and permissive IAM issues first"
            )

        public_access_count = type_dist.get(MisconfigurationType.PUBLIC_ACCESS, 0)
        if public_access_count > 0:
            recommendations.append(
                f"{public_access_count} public access misconfiguration(s) detected — "
                f"audit S3 buckets, storage accounts, and GCS buckets for public exposure"
            )

        permissive_iam_count = type_dist.get(MisconfigurationType.PERMISSIVE_IAM, 0)
        if permissive_iam_count > 0:
            recommendations.append(
                f"{permissive_iam_count} permissive IAM finding(s) — "
                f"enforce least-privilege access and rotate overly broad service accounts"
            )

        missing_logging_count = type_dist.get(MisconfigurationType.MISSING_LOGGING, 0)
        if missing_logging_count > 0:
            recommendations.append(
                f"{missing_logging_count} resource(s) missing logging — "
                f"enable CloudTrail, VPC Flow Logs, or equivalent audit trails"
            )

        if compliance_score < 80.0:
            recommendations.append(
                f"Overall compliance score is {compliance_score:.1f}% — "
                f"target 80%+ by resolving high-priority findings across all benchmarks"
            )

        high_risk = self.detect_high_risk_resources()
        if high_risk:
            top = high_risk[0]
            recommendations.append(
                f"Highest-risk resource {top['resource_id']} ({top['cloud_provider']}) "
                f"has {top['immediate_finding_count']} IMMEDIATE finding(s) — "
                f"prioritize remediation"
            )

        report = PostureReport(
            total_resources=total_resources,
            total_findings=total_findings,
            open_findings=open_findings,
            resolved_findings=resolved_findings,
            compliance_score=compliance_score,
            critical_findings=critical_findings,
            provider_distribution=provider_dist,
            finding_type_distribution=type_dist,
            recommendations=recommendations,
        )
        logger.info(
            "cloud_posture.report_generated",
            total_resources=total_resources,
            total_findings=total_findings,
            open_findings=open_findings,
            compliance_score=compliance_score,
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored resources and findings."""
        self._resources.clear()
        self._findings.clear()
        logger.info("cloud_posture.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about resources and findings."""
        provider_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        for r in self._resources:
            provider_counts[r.cloud_provider] = provider_counts.get(r.cloud_provider, 0) + 1
            type_counts[r.resource_type] = type_counts.get(r.resource_type, 0) + 1

        finding_type_counts: dict[str, int] = {}
        priority_counts: dict[str, int] = {}
        benchmark_counts: dict[str, int] = {}
        for f in self._findings:
            finding_type_counts[f.finding_type.value] = (
                finding_type_counts.get(f.finding_type.value, 0) + 1
            )
            priority_counts[f.priority.value] = priority_counts.get(f.priority.value, 0) + 1
            benchmark_counts[f.benchmark.value] = benchmark_counts.get(f.benchmark.value, 0) + 1

        return {
            "total_resources": len(self._resources),
            "total_findings": len(self._findings),
            "open_findings": sum(1 for f in self._findings if not f.is_resolved),
            "resolved_findings": sum(1 for f in self._findings if f.is_resolved),
            "provider_distribution": provider_counts,
            "resource_type_distribution": type_counts,
            "finding_type_distribution": finding_type_counts,
            "priority_distribution": priority_counts,
            "benchmark_distribution": benchmark_counts,
            "max_resources": self._max_resources,
            "auto_resolve_days": self._auto_resolve_days,
        }
