"""DPA BAA Tracker — track data processing agreements and business associate agreements."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AgreementType(StrEnum):
    DPA = "dpa"
    BAA = "baa"
    SCC = "scc"
    BCR = "bcr"
    CUSTOM = "custom"


class ComplianceFramework(StrEnum):
    GDPR = "gdpr"
    HIPAA = "hipaa"
    CCPA = "ccpa"
    SOC2 = "soc2"
    ISO27001 = "iso27001"


class AgreementStatus(StrEnum):
    ACTIVE = "active"
    EXPIRING = "expiring"
    EXPIRED = "expired"
    UNDER_REVIEW = "under_review"
    TERMINATED = "terminated"


# --- Models ---


class AgreementRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str = ""
    agreement_type: AgreementType = AgreementType.DPA
    compliance_framework: ComplianceFramework = ComplianceFramework.GDPR
    agreement_status: AgreementStatus = AgreementStatus.ACTIVE
    coverage_score: float = 0.0
    legal_owner: str = ""
    business_unit: str = ""
    created_at: float = Field(default_factory=time.time)


class AgreementAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str = ""
    agreement_type: AgreementType = AgreementType.DPA
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AgreementComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_coverage_score: float = 0.0
    by_agreement_type: dict[str, int] = Field(default_factory=dict)
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DPABAATracker:
    """Track DPAs, BAAs and related agreements; identify coverage and expiry gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[AgreementRecord] = []
        self._analyses: list[AgreementAnalysis] = []
        logger.info(
            "dpa_baa_tracker.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_agreement(
        self,
        vendor_id: str,
        agreement_type: AgreementType = AgreementType.DPA,
        compliance_framework: ComplianceFramework = ComplianceFramework.GDPR,
        agreement_status: AgreementStatus = AgreementStatus.ACTIVE,
        coverage_score: float = 0.0,
        legal_owner: str = "",
        business_unit: str = "",
    ) -> AgreementRecord:
        record = AgreementRecord(
            vendor_id=vendor_id,
            agreement_type=agreement_type,
            compliance_framework=compliance_framework,
            agreement_status=agreement_status,
            coverage_score=coverage_score,
            legal_owner=legal_owner,
            business_unit=business_unit,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dpa_baa_tracker.agreement_recorded",
            record_id=record.id,
            vendor_id=vendor_id,
            agreement_type=agreement_type.value,
            compliance_framework=compliance_framework.value,
        )
        return record

    def get_agreement(self, record_id: str) -> AgreementRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_agreements(
        self,
        agreement_type: AgreementType | None = None,
        compliance_framework: ComplianceFramework | None = None,
        business_unit: str | None = None,
        limit: int = 50,
    ) -> list[AgreementRecord]:
        results = list(self._records)
        if agreement_type is not None:
            results = [r for r in results if r.agreement_type == agreement_type]
        if compliance_framework is not None:
            results = [r for r in results if r.compliance_framework == compliance_framework]
        if business_unit is not None:
            results = [r for r in results if r.business_unit == business_unit]
        return results[-limit:]

    def add_analysis(
        self,
        vendor_id: str,
        agreement_type: AgreementType = AgreementType.DPA,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AgreementAnalysis:
        analysis = AgreementAnalysis(
            vendor_id=vendor_id,
            agreement_type=agreement_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "dpa_baa_tracker.analysis_added",
            vendor_id=vendor_id,
            agreement_type=agreement_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_framework_distribution(self) -> dict[str, Any]:
        """Group by compliance_framework; return count and avg coverage_score."""
        fw_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.compliance_framework.value
            fw_data.setdefault(key, []).append(r.coverage_score)
        result: dict[str, Any] = {}
        for fw, scores in fw_data.items():
            result[fw] = {
                "count": len(scores),
                "avg_coverage_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_agreement_gaps(self) -> list[dict[str, Any]]:
        """Return records where coverage_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.coverage_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "vendor_id": r.vendor_id,
                        "agreement_type": r.agreement_type.value,
                        "coverage_score": r.coverage_score,
                        "legal_owner": r.legal_owner,
                        "business_unit": r.business_unit,
                    }
                )
        return sorted(results, key=lambda x: x["coverage_score"])

    def rank_by_coverage(self) -> list[dict[str, Any]]:
        """Group by business_unit, avg coverage_score, sort ascending."""
        unit_scores: dict[str, list[float]] = {}
        for r in self._records:
            unit_scores.setdefault(r.business_unit, []).append(r.coverage_score)
        results: list[dict[str, Any]] = []
        for unit, scores in unit_scores.items():
            results.append(
                {
                    "business_unit": unit,
                    "avg_coverage_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_score"])
        return results

    def detect_agreement_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
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

    def generate_report(self) -> AgreementComplianceReport:
        by_agreement_type: dict[str, int] = {}
        by_framework: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_agreement_type[r.agreement_type.value] = (
                by_agreement_type.get(r.agreement_type.value, 0) + 1
            )
            by_framework[r.compliance_framework.value] = (
                by_framework.get(r.compliance_framework.value, 0) + 1
            )
            by_status[r.agreement_status.value] = by_status.get(r.agreement_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.coverage_score < self._threshold)
        scores = [r.coverage_score for r in self._records]
        avg_coverage_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_agreement_gaps()
        top_gaps = [o["vendor_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} agreement(s) below coverage threshold ({self._threshold})")
        if self._records and avg_coverage_score < self._threshold:
            recs.append(
                f"Avg coverage score {avg_coverage_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("DPA/BAA agreement coverage is healthy")
        return AgreementComplianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_coverage_score=avg_coverage_score,
            by_agreement_type=by_agreement_type,
            by_framework=by_framework,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("dpa_baa_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.agreement_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "agreement_type_distribution": type_dist,
            "unique_vendors": len({r.vendor_id for r in self._records}),
            "unique_units": len({r.business_unit for r in self._records}),
        }
