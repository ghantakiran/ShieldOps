"""Compliance as Code Engine — define and enforce compliance policies as code."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PolicyLanguage(StrEnum):
    REGO = "rego"
    YAML = "yaml"
    JSON = "json"
    PYTHON = "python"


class ComplianceStatus(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NOT_ASSESSED = "not_assessed"


class RemediationStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class FrameworkType(StrEnum):
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"
    ISO27001 = "iso27001"
    NIST = "nist"


# --- Models ---


class PolicyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    framework: FrameworkType = FrameworkType.SOC2
    language: PolicyLanguage = PolicyLanguage.REGO
    status: ComplianceStatus = ComplianceStatus.NOT_ASSESSED
    score: float = 0.0
    control_id: str = ""
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str = ""
    evidence_type: str = ""
    content_hash: str = ""
    valid: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_policies: int = 0
    total_evidence: int = 0
    compliance_rate: float = 0.0
    avg_score: float = 0.0
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceAsCodeEngine:
    """Define and enforce compliance policies as code."""

    def __init__(
        self,
        max_records: int = 200000,
        score_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._score_threshold = score_threshold
        self._policies: list[PolicyRecord] = []
        self._evidence: list[EvidenceRecord] = []
        logger.info(
            "compliance_as_code_engine.initialized",
            max_records=max_records,
            score_threshold=score_threshold,
        )

    def parse_policy(
        self,
        name: str,
        framework: FrameworkType = FrameworkType.SOC2,
        language: PolicyLanguage = PolicyLanguage.REGO,
        score: float = 0.0,
        control_id: str = "",
        service: str = "",
        team: str = "",
    ) -> PolicyRecord:
        """Parse and register a compliance policy."""
        record = PolicyRecord(
            name=name,
            framework=framework,
            language=language,
            score=score,
            control_id=control_id,
            service=service,
            team=team,
        )
        self._policies.append(record)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "compliance_as_code_engine.policy_parsed",
            policy_id=record.id,
            name=name,
            framework=framework.value,
        )
        return record

    def evaluate_compliance(self, policy_id: str, score: float = 0.0) -> dict[str, Any]:
        """Evaluate compliance status for a policy."""
        for p in self._policies:
            if p.id == policy_id:
                p.score = score
                if score >= 90:
                    p.status = ComplianceStatus.COMPLIANT
                elif score >= 50:
                    p.status = ComplianceStatus.PARTIALLY_COMPLIANT
                else:
                    p.status = ComplianceStatus.NON_COMPLIANT
                return {
                    "policy_id": policy_id,
                    "status": p.status.value,
                    "score": score,
                }
        return {"policy_id": policy_id, "status": "not_found", "score": 0.0}

    def generate_evidence(
        self,
        policy_id: str,
        evidence_type: str = "",
        content_hash: str = "",
        valid: bool = False,
        description: str = "",
    ) -> EvidenceRecord:
        """Generate and store evidence for a policy."""
        evidence = EvidenceRecord(
            policy_id=policy_id,
            evidence_type=evidence_type,
            content_hash=content_hash,
            valid=valid,
            description=description,
        )
        self._evidence.append(evidence)
        if len(self._evidence) > self._max_records:
            self._evidence = self._evidence[-self._max_records :]
        logger.info(
            "compliance_as_code_engine.evidence_generated",
            evidence_id=evidence.id,
            policy_id=policy_id,
        )
        return evidence

    def remediate_violations(self, policy_id: str) -> dict[str, Any]:
        """Attempt to remediate violations for a non-compliant policy."""
        for p in self._policies:
            if p.id == policy_id:
                if p.status == ComplianceStatus.NON_COMPLIANT:
                    p.status = ComplianceStatus.PARTIALLY_COMPLIANT
                    return {
                        "policy_id": policy_id,
                        "remediation": RemediationStatus.COMPLETED.value,
                        "new_status": p.status.value,
                    }
                return {
                    "policy_id": policy_id,
                    "remediation": RemediationStatus.SKIPPED.value,
                    "reason": "not_non_compliant",
                }
        return {
            "policy_id": policy_id,
            "remediation": RemediationStatus.FAILED.value,
            "reason": "not_found",
        }

    def get_compliance_dashboard(self) -> dict[str, Any]:
        """Compute compliance dashboard metrics."""
        if not self._policies:
            return {"total": 0, "compliance_rate": 0.0, "avg_score": 0.0}
        compliant = sum(1 for p in self._policies if p.status == ComplianceStatus.COMPLIANT)
        scores = [p.score for p in self._policies]
        avg_score = round(sum(scores) / len(scores), 2)
        rate = round(compliant / len(self._policies) * 100, 2)
        by_fw: dict[str, dict[str, int]] = {}
        for p in self._policies:
            fw = p.framework.value
            by_fw.setdefault(fw, {"compliant": 0, "total": 0})
            by_fw[fw]["total"] += 1
            if p.status == ComplianceStatus.COMPLIANT:
                by_fw[fw]["compliant"] += 1
        return {
            "total": len(self._policies),
            "compliance_rate": rate,
            "avg_score": avg_score,
            "by_framework": by_fw,
        }

    def list_policies(
        self,
        framework: FrameworkType | None = None,
        status: ComplianceStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PolicyRecord]:
        """List policies with optional filters."""
        results = list(self._policies)
        if framework is not None:
            results = [r for r in results if r.framework == framework]
        if status is not None:
            results = [r for r in results if r.status == status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def generate_report(self) -> ComplianceReport:
        """Generate a comprehensive compliance report."""
        by_fw: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for p in self._policies:
            by_fw[p.framework.value] = by_fw.get(p.framework.value, 0) + 1
            by_status[p.status.value] = by_status.get(p.status.value, 0) + 1
        scores = [p.score for p in self._policies]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        compliant = sum(1 for p in self._policies if p.status == ComplianceStatus.COMPLIANT)
        rate = round(compliant / len(self._policies) * 100, 2) if self._policies else 0.0
        gaps = [p.name for p in self._policies if p.score < self._score_threshold][:5]
        recs: list[str] = []
        if gaps:
            recs.append(f"{len(gaps)} policy(ies) below score threshold")
        if avg_score < self._score_threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._score_threshold})")
        if not recs:
            recs.append("Compliance metrics within healthy range")
        return ComplianceReport(
            total_policies=len(self._policies),
            total_evidence=len(self._evidence),
            compliance_rate=rate,
            avg_score=avg_score,
            by_framework=by_fw,
            by_status=by_status,
            top_gaps=gaps,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        dist: dict[str, int] = {}
        for p in self._policies:
            key = p.framework.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_policies": len(self._policies),
            "total_evidence": len(self._evidence),
            "score_threshold": self._score_threshold,
            "framework_distribution": dist,
            "unique_teams": len({p.team for p in self._policies}),
            "unique_services": len({p.service for p in self._policies}),
        }

    def clear_data(self) -> dict[str, str]:
        """Clear all stored data."""
        self._policies.clear()
        self._evidence.clear()
        logger.info("compliance_as_code_engine.cleared")
        return {"status": "cleared"}
