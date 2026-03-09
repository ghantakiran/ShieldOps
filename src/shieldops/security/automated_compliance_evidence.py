"""Automated Compliance Evidence
auto-collection, validation chains, freshness scoring, audit readiness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EvidenceType(StrEnum):
    CONFIGURATION = "configuration"
    ACCESS_LOG = "access_log"
    SCAN_RESULT = "scan_result"
    POLICY_CHECK = "policy_check"
    ATTESTATION = "attestation"


class ValidationStatus(StrEnum):
    VALID = "valid"
    EXPIRED = "expired"
    INVALID = "invalid"
    PENDING = "pending"
    PARTIAL = "partial"


class ComplianceFramework(StrEnum):
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    NIST = "nist"


# --- Models ---


class EvidenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    evidence_type: EvidenceType = EvidenceType.CONFIGURATION
    validation_status: ValidationStatus = ValidationStatus.PENDING
    framework: ComplianceFramework = ComplianceFramework.SOC2
    freshness_score: float = 0.0
    collection_method: str = "automated"
    last_validated_at: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    evidence_type: EvidenceType = EvidenceType.CONFIGURATION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_freshness: float = 0.0
    audit_readiness_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_validation: dict[str, int] = Field(default_factory=dict)
    by_framework: dict[str, int] = Field(default_factory=dict)
    stale_controls: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutomatedComplianceEvidence:
    """Evidence auto-collection, validation chains, freshness scoring, audit readiness."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[EvidenceRecord] = []
        self._analyses: list[EvidenceAnalysis] = []
        logger.info(
            "automated_compliance_evidence.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def add_record(
        self,
        control_id: str,
        evidence_type: EvidenceType = EvidenceType.CONFIGURATION,
        validation_status: ValidationStatus = ValidationStatus.PENDING,
        framework: ComplianceFramework = ComplianceFramework.SOC2,
        freshness_score: float = 0.0,
        collection_method: str = "automated",
        last_validated_at: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EvidenceRecord:
        record = EvidenceRecord(
            control_id=control_id,
            evidence_type=evidence_type,
            validation_status=validation_status,
            framework=framework,
            freshness_score=freshness_score,
            collection_method=collection_method,
            last_validated_at=last_validated_at or time.time(),
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "automated_compliance_evidence.record_added",
            record_id=record.id,
            control_id=control_id,
            framework=framework.value,
        )
        return record

    def get_record(self, record_id: str) -> EvidenceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        framework: ComplianceFramework | None = None,
        validation_status: ValidationStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EvidenceRecord]:
        results = list(self._records)
        if framework is not None:
            results = [r for r in results if r.framework == framework]
        if validation_status is not None:
            results = [r for r in results if r.validation_status == validation_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        control_id: str,
        evidence_type: EvidenceType = EvidenceType.CONFIGURATION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> EvidenceAnalysis:
        analysis = EvidenceAnalysis(
            control_id=control_id,
            evidence_type=evidence_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "automated_compliance_evidence.analysis_added",
            control_id=control_id,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def compute_audit_readiness(self) -> dict[str, Any]:
        if not self._records:
            return {"readiness_pct": 0.0, "total_controls": 0}
        valid_count = sum(
            1
            for r in self._records
            if r.validation_status == ValidationStatus.VALID
            and r.freshness_score >= self._threshold
        )
        partial = sum(1 for r in self._records if r.validation_status == ValidationStatus.PARTIAL)
        total = len(self._records)
        readiness = round((valid_count + partial * 0.5) / total * 100, 2)
        return {
            "readiness_pct": readiness,
            "fully_ready": valid_count,
            "partially_ready": partial,
            "not_ready": total - valid_count - partial,
            "total_controls": total,
        }

    def identify_stale_evidence(self, max_age_sec: float = 86400 * 30) -> list[dict[str, Any]]:
        now = time.time()
        results: list[dict[str, Any]] = []
        for r in self._records:
            age = now - r.last_validated_at
            if age > max_age_sec:
                results.append(
                    {
                        "control_id": r.control_id,
                        "framework": r.framework.value,
                        "age_days": round(age / 86400, 1),
                        "freshness_score": r.freshness_score,
                        "validation_status": r.validation_status.value,
                    }
                )
        return sorted(results, key=lambda x: x["age_days"], reverse=True)

    def framework_coverage(self) -> dict[str, Any]:
        fw_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            key = r.framework.value
            fw_data.setdefault(key, {"valid": 0, "total": 0})
            fw_data[key]["total"] += 1
            if r.validation_status == ValidationStatus.VALID:
                fw_data[key]["valid"] += 1
        results: dict[str, Any] = {}
        for fw, counts in fw_data.items():
            coverage = round(counts["valid"] / counts["total"] * 100, 2) if counts["total"] else 0
            results[fw] = {
                "coverage_pct": coverage,
                "valid": counts["valid"],
                "total": counts["total"],
            }
        return results

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def process(self, control_id: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.control_id == control_id]
        if not matching:
            return {"control_id": control_id, "status": "no_data"}
        scores = [r.freshness_score for r in matching]
        return {
            "control_id": control_id,
            "evidence_count": len(matching),
            "avg_freshness": round(sum(scores) / len(scores), 2),
            "valid_count": sum(
                1 for r in matching if r.validation_status == ValidationStatus.VALID
            ),
        }

    def generate_report(self) -> EvidenceReport:
        by_type: dict[str, int] = {}
        by_val: dict[str, int] = {}
        by_fw: dict[str, int] = {}
        for r in self._records:
            by_type[r.evidence_type.value] = by_type.get(r.evidence_type.value, 0) + 1
            by_val[r.validation_status.value] = by_val.get(r.validation_status.value, 0) + 1
            by_fw[r.framework.value] = by_fw.get(r.framework.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.freshness_score < self._threshold)
        scores = [r.freshness_score for r in self._records]
        avg_fresh = round(sum(scores) / len(scores), 2) if scores else 0.0
        readiness = self.compute_audit_readiness()
        stale = self.identify_stale_evidence()
        stale_controls = [s["control_id"] for s in stale[:5]]
        recs: list[str] = []
        if gap_count > 0:
            recs.append(f"{gap_count} control(s) below freshness threshold ({self._threshold})")
        if readiness["readiness_pct"] < 80.0:
            recs.append(f"Audit readiness at {readiness['readiness_pct']}% — target 80%+")
        expired = by_val.get("expired", 0)
        if expired > 0:
            recs.append(f"{expired} evidence item(s) expired — re-collect immediately")
        if not recs:
            recs.append("Compliance evidence collection is healthy")
        return EvidenceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_freshness=avg_fresh,
            audit_readiness_pct=readiness["readiness_pct"],
            by_type=by_type,
            by_validation=by_val,
            by_framework=by_fw,
            stale_controls=stale_controls,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        fw_dist: dict[str, int] = {}
        for r in self._records:
            key = r.framework.value
            fw_dist[key] = fw_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "framework_distribution": fw_dist,
            "unique_controls": len({r.control_id for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("automated_compliance_evidence.cleared")
        return {"status": "cleared"}
