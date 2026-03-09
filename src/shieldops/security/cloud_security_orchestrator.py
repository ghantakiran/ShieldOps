"""Cloud Security Orchestrator — orchestrate security controls across multi-cloud."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CloudProvider(StrEnum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    MULTI_CLOUD = "multi_cloud"


class GuardrailType(StrEnum):
    IAM = "iam"
    NETWORK = "network"
    ENCRYPTION = "encryption"
    LOGGING = "logging"
    STORAGE = "storage"


class MisconfigSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RemediationStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# --- Models ---


class CloudPosture(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    provider: CloudProvider = CloudProvider.AWS
    guardrail_type: GuardrailType = GuardrailType.IAM
    score: float = 0.0
    findings_count: int = 0
    service: str = ""
    team: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class Misconfiguration(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    provider: CloudProvider = CloudProvider.AWS
    severity: MisconfigSeverity = MisconfigSeverity.LOW
    resource: str = ""
    remediation_status: RemediationStatus = RemediationStatus.PENDING
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CloudSecurityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_postures: int = 0
    total_misconfigs: int = 0
    avg_score: float = 0.0
    risk_score: float = 0.0
    by_provider: dict[str, int] = Field(default_factory=dict)
    by_guardrail: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    top_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CloudSecurityOrchestrator:
    """Orchestrate security controls across multi-cloud environments."""

    def __init__(
        self,
        max_records: int = 200000,
        score_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._score_threshold = score_threshold
        self._postures: list[CloudPosture] = []
        self._misconfigs: list[Misconfiguration] = []
        logger.info(
            "cloud_security_orchestrator.initialized",
            max_records=max_records,
            score_threshold=score_threshold,
        )

    def assess_cloud_posture(
        self,
        provider: CloudProvider = CloudProvider.AWS,
        guardrail_type: GuardrailType = GuardrailType.IAM,
        score: float = 0.0,
        findings_count: int = 0,
        service: str = "",
        team: str = "",
        description: str = "",
    ) -> CloudPosture:
        """Assess security posture for a cloud environment."""
        posture = CloudPosture(
            provider=provider,
            guardrail_type=guardrail_type,
            score=score,
            findings_count=findings_count,
            service=service,
            team=team,
            description=description,
        )
        self._postures.append(posture)
        if len(self._postures) > self._max_records:
            self._postures = self._postures[-self._max_records :]
        logger.info(
            "cloud_security_orchestrator.posture_assessed",
            posture_id=posture.id,
            provider=provider.value,
            score=score,
        )
        return posture

    def enforce_guardrails(
        self,
        provider: CloudProvider,
        guardrail_type: GuardrailType,
    ) -> dict[str, Any]:
        """Enforce guardrails and flag non-compliant postures."""
        violations = [
            p
            for p in self._postures
            if p.provider == provider
            and p.guardrail_type == guardrail_type
            and p.score < self._score_threshold
        ]
        return {
            "provider": provider.value,
            "guardrail_type": guardrail_type.value,
            "violations_count": len(violations),
            "violation_ids": [v.id for v in violations],
        }

    def remediate_misconfigurations(
        self,
        provider: CloudProvider = CloudProvider.AWS,
        severity: MisconfigSeverity = MisconfigSeverity.LOW,
        resource: str = "",
        description: str = "",
    ) -> Misconfiguration:
        """Record and remediate a misconfiguration."""
        misconfig = Misconfiguration(
            provider=provider,
            severity=severity,
            resource=resource,
            remediation_status=RemediationStatus.IN_PROGRESS,
            description=description,
        )
        self._misconfigs.append(misconfig)
        if len(self._misconfigs) > self._max_records:
            self._misconfigs = self._misconfigs[-self._max_records :]
        logger.info(
            "cloud_security_orchestrator.misconfiguration_recorded",
            misconfig_id=misconfig.id,
            provider=provider.value,
            severity=severity.value,
        )
        return misconfig

    def validate_compliance(self, provider: CloudProvider) -> dict[str, Any]:
        """Validate compliance for a provider."""
        provider_postures = [p for p in self._postures if p.provider == provider]
        if not provider_postures:
            return {"provider": provider.value, "compliant": False, "reason": "no_data"}
        scores = [p.score for p in provider_postures]
        avg = round(sum(scores) / len(scores), 2)
        compliant = avg >= self._score_threshold
        return {
            "provider": provider.value,
            "compliant": compliant,
            "avg_score": avg,
            "total_postures": len(provider_postures),
        }

    def get_cloud_risk_score(self) -> dict[str, Any]:
        """Compute risk score across all cloud environments."""
        if not self._postures:
            return {"overall_risk": 0.0, "by_provider": {}}
        provider_scores: dict[str, list[float]] = {}
        for p in self._postures:
            provider_scores.setdefault(p.provider.value, []).append(p.score)
        by_provider = {k: round(100 - sum(v) / len(v), 2) for k, v in provider_scores.items()}
        all_scores = [p.score for p in self._postures]
        overall = round(100 - sum(all_scores) / len(all_scores), 2)
        misconfig_count = len(self._misconfigs)
        return {
            "overall_risk": overall,
            "by_provider": by_provider,
            "total_misconfigs": misconfig_count,
        }

    def list_postures(
        self,
        provider: CloudProvider | None = None,
        guardrail_type: GuardrailType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CloudPosture]:
        """List postures with optional filters."""
        results = list(self._postures)
        if provider is not None:
            results = [r for r in results if r.provider == provider]
        if guardrail_type is not None:
            results = [r for r in results if r.guardrail_type == guardrail_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def generate_report(self) -> CloudSecurityReport:
        """Generate a comprehensive cloud security report."""
        by_prov: dict[str, int] = {}
        by_guard: dict[str, int] = {}
        for p in self._postures:
            by_prov[p.provider.value] = by_prov.get(p.provider.value, 0) + 1
            by_guard[p.guardrail_type.value] = by_guard.get(p.guardrail_type.value, 0) + 1
        by_sev: dict[str, int] = {}
        for m in self._misconfigs:
            by_sev[m.severity.value] = by_sev.get(m.severity.value, 0) + 1
        scores = [p.score for p in self._postures]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        risk = round(100 - avg, 2) if scores else 0.0
        issues = [p.description for p in self._postures if p.score < self._score_threshold][:5]
        recs: list[str] = []
        if issues:
            recs.append(f"{len(issues)} posture(s) below threshold")
        if self._misconfigs:
            recs.append(f"{len(self._misconfigs)} misconfiguration(s) recorded")
        if not recs:
            recs.append("Cloud security posture within healthy range")
        return CloudSecurityReport(
            total_postures=len(self._postures),
            total_misconfigs=len(self._misconfigs),
            avg_score=avg,
            risk_score=risk,
            by_provider=by_prov,
            by_guardrail=by_guard,
            by_severity=by_sev,
            top_issues=issues,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        dist: dict[str, int] = {}
        for p in self._postures:
            key = p.provider.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_postures": len(self._postures),
            "total_misconfigs": len(self._misconfigs),
            "score_threshold": self._score_threshold,
            "provider_distribution": dist,
            "unique_teams": len({p.team for p in self._postures}),
            "unique_services": len({p.service for p in self._postures}),
        }

    def clear_data(self) -> dict[str, str]:
        """Clear all stored data."""
        self._postures.clear()
        self._misconfigs.clear()
        logger.info("cloud_security_orchestrator.cleared")
        return {"status": "cleared"}
