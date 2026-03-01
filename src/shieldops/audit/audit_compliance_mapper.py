"""Audit Compliance Mapper — map audit findings to compliance frameworks."""

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
    ISO27001 = "iso27001"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"


class MappingStatus(StrEnum):
    MAPPED = "mapped"
    PARTIALLY_MAPPED = "partially_mapped"
    UNMAPPED = "unmapped"
    REVIEW_NEEDED = "review_needed"
    EXEMPT = "exempt"


class MappingConfidence(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    SPECULATIVE = "speculative"
    NONE = "none"


# --- Models ---


class ComplianceMappingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mapping_id: str = ""
    compliance_framework: ComplianceFramework = ComplianceFramework.SOC2
    mapping_status: MappingStatus = MappingStatus.UNMAPPED
    mapping_confidence: MappingConfidence = MappingConfidence.NONE
    coverage_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MappingAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mapping_id: str = ""
    compliance_framework: ComplianceFramework = ComplianceFramework.SOC2
    assessment_score: float = 0.0
    threshold: float = 85.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    unmapped_count: int = 0
    avg_coverage_score: float = 0.0
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    top_unmapped: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditComplianceMapper:
    """Map audit findings to compliance frameworks, track coverage."""

    def __init__(
        self,
        max_records: int = 200000,
        min_coverage_score: float = 85.0,
    ) -> None:
        self._max_records = max_records
        self._min_coverage_score = min_coverage_score
        self._records: list[ComplianceMappingRecord] = []
        self._assessments: list[MappingAssessment] = []
        logger.info(
            "audit_compliance_mapper.initialized",
            max_records=max_records,
            min_coverage_score=min_coverage_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_mapping(
        self,
        mapping_id: str,
        compliance_framework: ComplianceFramework = ComplianceFramework.SOC2,
        mapping_status: MappingStatus = MappingStatus.UNMAPPED,
        mapping_confidence: MappingConfidence = MappingConfidence.NONE,
        coverage_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ComplianceMappingRecord:
        record = ComplianceMappingRecord(
            mapping_id=mapping_id,
            compliance_framework=compliance_framework,
            mapping_status=mapping_status,
            mapping_confidence=mapping_confidence,
            coverage_score=coverage_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "audit_compliance_mapper.mapping_recorded",
            record_id=record.id,
            mapping_id=mapping_id,
            compliance_framework=compliance_framework.value,
            mapping_status=mapping_status.value,
        )
        return record

    def get_mapping(self, record_id: str) -> ComplianceMappingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_mappings(
        self,
        compliance_framework: ComplianceFramework | None = None,
        mapping_status: MappingStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ComplianceMappingRecord]:
        results = list(self._records)
        if compliance_framework is not None:
            results = [r for r in results if r.compliance_framework == compliance_framework]
        if mapping_status is not None:
            results = [r for r in results if r.mapping_status == mapping_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        mapping_id: str,
        compliance_framework: ComplianceFramework = ComplianceFramework.SOC2,
        assessment_score: float = 0.0,
        threshold: float = 85.0,
        description: str = "",
    ) -> MappingAssessment:
        breached = assessment_score < threshold
        assessment = MappingAssessment(
            mapping_id=mapping_id,
            compliance_framework=compliance_framework,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "audit_compliance_mapper.assessment_added",
            mapping_id=mapping_id,
            compliance_framework=compliance_framework.value,
            assessment_score=assessment_score,
            breached=breached,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_mapping_distribution(self) -> dict[str, Any]:
        """Group by compliance_framework; return count and avg coverage."""
        framework_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.compliance_framework.value
            framework_data.setdefault(key, []).append(r.coverage_score)
        result: dict[str, Any] = {}
        for framework, scores in framework_data.items():
            result[framework] = {
                "count": len(scores),
                "avg_coverage_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_unmapped_controls(self) -> list[dict[str, Any]]:
        """Return mappings where status is UNMAPPED or REVIEW_NEEDED."""
        unmapped_statuses = {
            MappingStatus.UNMAPPED,
            MappingStatus.REVIEW_NEEDED,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.mapping_status in unmapped_statuses:
                results.append(
                    {
                        "record_id": r.id,
                        "mapping_id": r.mapping_id,
                        "compliance_framework": r.compliance_framework.value,
                        "mapping_status": r.mapping_status.value,
                        "coverage_score": r.coverage_score,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["coverage_score"], reverse=False)
        return results

    def rank_by_coverage(self) -> list[dict[str, Any]]:
        """Group by service, avg coverage_score, sort asc — worst first."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            service_scores.setdefault(r.service, []).append(r.coverage_score)
        results: list[dict[str, Any]] = []
        for svc, scores in service_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_coverage_score": round(sum(scores) / len(scores), 2),
                    "mapping_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_score"], reverse=False)
        return results

    def detect_mapping_trends(self) -> dict[str, Any]:
        """Split-half comparison on assessment_score; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [a.assessment_score for a in self._assessments]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> AuditComplianceReport:
        by_framework: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for r in self._records:
            by_framework[r.compliance_framework.value] = (
                by_framework.get(r.compliance_framework.value, 0) + 1
            )
            by_status[r.mapping_status.value] = by_status.get(r.mapping_status.value, 0) + 1
            by_confidence[r.mapping_confidence.value] = (
                by_confidence.get(r.mapping_confidence.value, 0) + 1
            )
        unmapped_count = sum(
            1
            for r in self._records
            if r.mapping_status in {MappingStatus.UNMAPPED, MappingStatus.REVIEW_NEEDED}
        )
        avg_coverage = (
            round(
                sum(r.coverage_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        unmapped_list = self.identify_unmapped_controls()
        top_unmapped = [u["mapping_id"] for u in unmapped_list]
        recs: list[str] = []
        if unmapped_count > 0:
            recs.append(f"{unmapped_count} unmapped/review-needed control(s) — complete mapping")
        low_cov = sum(1 for r in self._records if r.coverage_score < self._min_coverage_score)
        if low_cov > 0:
            recs.append(
                f"{low_cov} mapping(s) below coverage threshold ({self._min_coverage_score}%)"
            )
        if not recs:
            recs.append("Compliance mapping levels are acceptable")
        return AuditComplianceReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            unmapped_count=unmapped_count,
            avg_coverage_score=avg_coverage,
            by_framework=by_framework,
            by_status=by_status,
            by_confidence=by_confidence,
            top_unmapped=top_unmapped,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("audit_compliance_mapper.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        framework_dist: dict[str, int] = {}
        for r in self._records:
            key = r.compliance_framework.value
            framework_dist[key] = framework_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "min_coverage_score": self._min_coverage_score,
            "framework_distribution": framework_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
