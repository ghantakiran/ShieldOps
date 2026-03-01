"""Security Compliance Mapper — map and track compliance controls."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComplianceFramework(StrEnum):
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    NIST = "nist"


class ControlStatus(StrEnum):
    COMPLIANT = "compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"
    UNDER_REVIEW = "under_review"


class ComplianceRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    ACCEPTABLE = "acceptable"


# --- Models ---


class ComplianceMapRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    framework: ComplianceFramework = ComplianceFramework.SOC2
    control_id: str = ""
    control_name: str = ""
    status: ControlStatus = ControlStatus.UNDER_REVIEW
    risk: ComplianceRisk = ComplianceRisk.MODERATE
    compliance_score: float = 0.0
    owner: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ControlEvidence(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    control_id: str = ""
    evidence_type: str = ""
    evidence_description: str = ""
    collected_at: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ComplianceMapperReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_evidence: int = 0
    avg_compliance_score: float = 0.0
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    non_compliant_controls: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityComplianceMapper:
    """Map and track security compliance controls."""

    def __init__(
        self,
        max_records: int = 200000,
        min_compliance_score: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_compliance_score = min_compliance_score
        self._records: list[ComplianceMapRecord] = []
        self._evidence: list[ControlEvidence] = []
        logger.info(
            "compliance_mapper.initialized",
            max_records=max_records,
            min_compliance_score=min_compliance_score,
        )

    # -- record / get / list -----------------------------------------

    def record_mapping(
        self,
        framework: ComplianceFramework = (ComplianceFramework.SOC2),
        control_id: str = "",
        control_name: str = "",
        status: ControlStatus = (ControlStatus.UNDER_REVIEW),
        risk: ComplianceRisk = ComplianceRisk.MODERATE,
        compliance_score: float = 0.0,
        owner: str = "",
        details: str = "",
    ) -> ComplianceMapRecord:
        record = ComplianceMapRecord(
            framework=framework,
            control_id=control_id,
            control_name=control_name,
            status=status,
            risk=risk,
            compliance_score=compliance_score,
            owner=owner,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "compliance_mapper.recorded",
            record_id=record.id,
            framework=framework.value,
            control_id=control_id,
            status=status.value,
        )
        return record

    def get_mapping(self, record_id: str) -> ComplianceMapRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_mappings(
        self,
        framework: ComplianceFramework | None = None,
        status: ControlStatus | None = None,
        risk: ComplianceRisk | None = None,
        limit: int = 50,
    ) -> list[ComplianceMapRecord]:
        results = list(self._records)
        if framework is not None:
            results = [r for r in results if r.framework == framework]
        if status is not None:
            results = [r for r in results if r.status == status]
        if risk is not None:
            results = [r for r in results if r.risk == risk]
        return results[-limit:]

    def add_evidence(
        self,
        control_id: str,
        evidence_type: str,
        evidence_description: str,
        collected_at: float,
    ) -> ControlEvidence:
        evidence = ControlEvidence(
            control_id=control_id,
            evidence_type=evidence_type,
            evidence_description=evidence_description,
            collected_at=collected_at,
        )
        self._evidence.append(evidence)
        if len(self._evidence) > self._max_records:
            self._evidence = self._evidence[-self._max_records :]
        logger.info(
            "compliance_mapper.evidence_added",
            evidence_id=evidence.id,
            control_id=control_id,
            evidence_type=evidence_type,
        )
        return evidence

    # -- domain operations -------------------------------------------

    def analyze_compliance_by_framework(
        self,
    ) -> dict[str, Any]:
        """Analyze compliance grouped by framework."""
        fw_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            fw = r.framework.value
            if fw not in fw_data:
                fw_data[fw] = {
                    "total": 0,
                    "scores": [],
                    "non_compliant": 0,
                }
            fw_data[fw]["total"] += 1
            fw_data[fw]["scores"].append(r.compliance_score)
            if r.status == ControlStatus.NON_COMPLIANT:
                fw_data[fw]["non_compliant"] += 1
        breakdown: list[dict[str, Any]] = []
        for fw, data in fw_data.items():
            scores = data["scores"]
            avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
            breakdown.append(
                {
                    "framework": fw,
                    "total_controls": data["total"],
                    "non_compliant_count": data["non_compliant"],
                    "avg_compliance_score": avg_score,
                }
            )
        breakdown.sort(
            key=lambda x: x["avg_compliance_score"],
            reverse=True,
        )
        return {
            "total_frameworks": len(fw_data),
            "breakdown": breakdown,
        }

    def identify_non_compliant_controls(
        self,
    ) -> list[dict[str, Any]]:
        """Find controls with NON_COMPLIANT status."""
        non_compliant = [r for r in self._records if r.status == ControlStatus.NON_COMPLIANT]
        return [
            {
                "record_id": r.id,
                "framework": r.framework.value,
                "control_id": r.control_id,
                "control_name": r.control_name,
                "risk": r.risk.value,
                "compliance_score": r.compliance_score,
            }
            for r in non_compliant
        ]

    def rank_by_compliance_score(
        self,
    ) -> list[dict[str, Any]]:
        """Rank controls by compliance score asc."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "control_id": r.control_id,
                    "framework": r.framework.value,
                    "compliance_score": (r.compliance_score),
                    "status": r.status.value,
                }
            )
        results.sort(
            key=lambda x: x["compliance_score"],
        )
        return results

    def detect_compliance_trends(
        self,
    ) -> dict[str, Any]:
        """Detect compliance trends via split-half."""
        if len(self._records) < 4:
            return {
                "trend": "insufficient_data",
                "sample_count": len(self._records),
            }
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]

        def _avg_score(
            records: list[ComplianceMapRecord],
        ) -> float:
            if not records:
                return 0.0
            return round(
                sum(r.compliance_score for r in records) / len(records),
                2,
            )

        first_score = _avg_score(first_half)
        second_score = _avg_score(second_half)
        delta = round(second_score - first_score, 2)
        if delta > 5.0:
            trend = "improving"
        elif delta < -5.0:
            trend = "worsening"
        else:
            trend = "stable"
        return {
            "trend": trend,
            "first_half_avg_score": first_score,
            "second_half_avg_score": second_score,
            "delta": delta,
            "total_records": len(self._records),
        }

    # -- report / stats ----------------------------------------------

    def generate_report(
        self,
    ) -> ComplianceMapperReport:
        by_framework: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_framework[r.framework.value] = by_framework.get(r.framework.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
            by_risk[r.risk.value] = by_risk.get(r.risk.value, 0) + 1
        avg_score = (
            round(
                sum(r.compliance_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        nc = self.identify_non_compliant_controls()
        nc_controls = [c["control_id"] for c in nc if c["control_id"]]
        recs: list[str] = []
        if nc_controls:
            recs.append(f"{len(nc_controls)} non-compliant control(s) require remediation")
        if avg_score < self._min_compliance_score:
            recs.append(
                f"Avg compliance score {avg_score} below {self._min_compliance_score} threshold"
            )
        if not recs:
            recs.append("Compliance posture meets required thresholds")
        return ComplianceMapperReport(
            total_records=len(self._records),
            total_evidence=len(self._evidence),
            avg_compliance_score=avg_score,
            by_framework=by_framework,
            by_status=by_status,
            by_risk=by_risk,
            non_compliant_controls=nc_controls,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._evidence.clear()
        logger.info("compliance_mapper.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        framework_dist: dict[str, int] = {}
        for r in self._records:
            key = r.framework.value
            framework_dist[key] = framework_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_evidence": len(self._evidence),
            "min_compliance_score": (self._min_compliance_score),
            "framework_distribution": framework_dist,
            "unique_controls": len({r.control_id for r in self._records if r.control_id}),
        }
