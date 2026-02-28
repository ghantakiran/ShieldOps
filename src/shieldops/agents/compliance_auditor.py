"""Agent Compliance Auditor — audit agent actions against compliance frameworks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComplianceFramework(StrEnum):
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    GDPR = "gdpr"
    ISO_27001 = "iso_27001"


class AuditResult(StrEnum):
    PASS = "pass_result"  # noqa: S105
    FAIL = "fail"
    WARNING = "warning"
    NOT_APPLICABLE = "not_applicable"
    NEEDS_REVIEW = "needs_review"


class EvidenceType(StrEnum):
    LOG_ENTRY = "log_entry"
    CONFIGURATION = "configuration"
    ACCESS_RECORD = "access_record"
    POLICY_CHECK = "policy_check"
    APPROVAL_RECORD = "approval_record"


# --- Models ---


class AuditRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = ""
    compliance_framework: ComplianceFramework = ComplianceFramework.SOC2
    audit_result: AuditResult = AuditResult.PASS
    evidence_type: EvidenceType = EvidenceType.LOG_ENTRY
    finding_count: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditEvidence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_label: str = ""
    compliance_framework: ComplianceFramework = ComplianceFramework.PCI_DSS
    audit_result: AuditResult = AuditResult.WARNING
    confidence_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ComplianceAuditorReport(BaseModel):
    total_audits: int = 0
    total_evidence: int = 0
    pass_rate_pct: float = 0.0
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    failure_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentComplianceAuditor:
    """Audit agent actions against compliance frameworks."""

    def __init__(
        self,
        max_records: int = 200000,
        min_pass_rate_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_pass_rate_pct = min_pass_rate_pct
        self._records: list[AuditRecord] = []
        self._evidence: list[AuditEvidence] = []
        logger.info(
            "compliance_auditor.initialized",
            max_records=max_records,
            min_pass_rate_pct=min_pass_rate_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_audit(
        self,
        agent_name: str,
        compliance_framework: ComplianceFramework = ComplianceFramework.SOC2,
        audit_result: AuditResult = AuditResult.PASS,
        evidence_type: EvidenceType = EvidenceType.LOG_ENTRY,
        finding_count: int = 0,
        details: str = "",
    ) -> AuditRecord:
        record = AuditRecord(
            agent_name=agent_name,
            compliance_framework=compliance_framework,
            audit_result=audit_result,
            evidence_type=evidence_type,
            finding_count=finding_count,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "compliance_auditor.recorded",
            record_id=record.id,
            agent_name=agent_name,
            compliance_framework=compliance_framework.value,
            audit_result=audit_result.value,
        )
        return record

    def get_audit(self, record_id: str) -> AuditRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_audits(
        self,
        agent_name: str | None = None,
        compliance_framework: ComplianceFramework | None = None,
        limit: int = 50,
    ) -> list[AuditRecord]:
        results = list(self._records)
        if agent_name is not None:
            results = [r for r in results if r.agent_name == agent_name]
        if compliance_framework is not None:
            results = [r for r in results if r.compliance_framework == compliance_framework]
        return results[-limit:]

    def add_evidence(
        self,
        evidence_label: str,
        compliance_framework: ComplianceFramework = ComplianceFramework.PCI_DSS,
        audit_result: AuditResult = AuditResult.WARNING,
        confidence_score: float = 0.0,
    ) -> AuditEvidence:
        evidence = AuditEvidence(
            evidence_label=evidence_label,
            compliance_framework=compliance_framework,
            audit_result=audit_result,
            confidence_score=confidence_score,
        )
        self._evidence.append(evidence)
        if len(self._evidence) > self._max_records:
            self._evidence = self._evidence[-self._max_records :]
        logger.info(
            "compliance_auditor.evidence_added",
            evidence_label=evidence_label,
            compliance_framework=compliance_framework.value,
            audit_result=audit_result.value,
        )
        return evidence

    # -- domain operations -----------------------------------------------

    def analyze_agent_compliance(self, agent_name: str) -> dict[str, Any]:
        agent_records = [r for r in self._records if r.agent_name == agent_name]
        if not agent_records:
            return {"agent_name": agent_name, "status": "no_data"}
        pass_count = sum(1 for r in agent_records if r.audit_result == AuditResult.PASS)
        rate = round(pass_count / len(agent_records) * 100, 2)
        return {
            "agent_name": agent_name,
            "total_records": len(agent_records),
            "pass_count": pass_count,
            "pass_rate_pct": rate,
            "meets_threshold": rate >= self._min_pass_rate_pct,
        }

    def identify_non_compliant_agents(self) -> list[dict[str, Any]]:
        agent_counts: dict[str, int] = {}
        for r in self._records:
            if r.audit_result == AuditResult.FAIL:
                agent_counts[r.agent_name] = agent_counts.get(r.agent_name, 0) + 1
        results: list[dict[str, Any]] = []
        for agent, count in agent_counts.items():
            if count > 1:
                results.append({"agent_name": agent, "failure_count": count})
        results.sort(key=lambda x: x["failure_count"], reverse=True)
        return results

    def rank_by_compliance_score(self) -> list[dict[str, Any]]:
        agent_findings: dict[str, list[int]] = {}
        for r in self._records:
            agent_findings.setdefault(r.agent_name, []).append(r.finding_count)
        results: list[dict[str, Any]] = []
        for agent, findings in agent_findings.items():
            results.append(
                {
                    "agent_name": agent,
                    "avg_finding_count": round(sum(findings) / len(findings), 2),
                    "record_count": len(findings),
                }
            )
        results.sort(key=lambda x: x["avg_finding_count"], reverse=True)
        return results

    def detect_compliance_drift(self) -> list[dict[str, Any]]:
        agent_counts: dict[str, int] = {}
        for r in self._records:
            if r.audit_result == AuditResult.FAIL:
                agent_counts[r.agent_name] = agent_counts.get(r.agent_name, 0) + 1
        results: list[dict[str, Any]] = []
        for agent, count in agent_counts.items():
            if count > 3:
                results.append(
                    {
                        "agent_name": agent,
                        "failure_count": count,
                        "recurring": True,
                    }
                )
        results.sort(key=lambda x: x["failure_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ComplianceAuditorReport:
        by_framework: dict[str, int] = {}
        by_result: dict[str, int] = {}
        for r in self._records:
            by_framework[r.compliance_framework.value] = (
                by_framework.get(r.compliance_framework.value, 0) + 1
            )
            by_result[r.audit_result.value] = by_result.get(r.audit_result.value, 0) + 1
        pass_count = sum(1 for r in self._records if r.audit_result == AuditResult.PASS)
        rate = round(pass_count / len(self._records) * 100, 2) if self._records else 0.0
        failure_count = sum(1 for r in self._records if r.audit_result == AuditResult.FAIL)
        recs: list[str] = []
        if failure_count > 0:
            recs.append(f"{failure_count} compliance failure(s) detected")
        drift = len(self.detect_compliance_drift())
        if drift > 0:
            recs.append(f"{drift} agent(s) with recurring compliance drift")
        if not recs:
            recs.append("Agent compliance auditing meets targets")
        return ComplianceAuditorReport(
            total_audits=len(self._records),
            total_evidence=len(self._evidence),
            pass_rate_pct=rate,
            by_framework=by_framework,
            by_result=by_result,
            failure_count=failure_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._evidence.clear()
        logger.info("compliance_auditor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        framework_dist: dict[str, int] = {}
        for r in self._records:
            key = r.compliance_framework.value
            framework_dist[key] = framework_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_evidence": len(self._evidence),
            "min_pass_rate_pct": self._min_pass_rate_pct,
            "framework_distribution": framework_dist,
            "unique_agents": len({r.agent_name for r in self._records}),
        }
