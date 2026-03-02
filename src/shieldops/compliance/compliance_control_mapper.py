"""Compliance Control Mapper — map compliance controls, detect coverage gaps."""

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
    ISO_27001 = "iso_27001"
    GDPR = "gdpr"


class ControlStatus(StrEnum):
    IMPLEMENTED = "implemented"
    PARTIALLY_IMPLEMENTED = "partially_implemented"
    PLANNED = "planned"
    NOT_APPLICABLE = "not_applicable"
    GAP = "gap"


class MappingConfidence(StrEnum):
    EXACT_MATCH = "exact_match"
    STRONG_MATCH = "strong_match"
    PARTIAL_MATCH = "partial_match"
    WEAK_MATCH = "weak_match"
    UNMAPPED = "unmapped"


# --- Models ---


class MappingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_name: str = ""
    compliance_framework: ComplianceFramework = ComplianceFramework.SOC2
    control_status: ControlStatus = ControlStatus.IMPLEMENTED
    mapping_confidence: MappingConfidence = MappingConfidence.EXACT_MATCH
    coverage_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MappingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_name: str = ""
    compliance_framework: ComplianceFramework = ComplianceFramework.SOC2
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceControlReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_coverage_score: float = 0.0
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceControlMapper:
    """Map compliance controls across frameworks, detect coverage gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        coverage_gap_threshold: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._coverage_gap_threshold = coverage_gap_threshold
        self._records: list[MappingRecord] = []
        self._analyses: list[MappingAnalysis] = []
        logger.info(
            "compliance_control_mapper.initialized",
            max_records=max_records,
            coverage_gap_threshold=coverage_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_mapping(
        self,
        control_name: str,
        compliance_framework: ComplianceFramework = ComplianceFramework.SOC2,
        control_status: ControlStatus = ControlStatus.IMPLEMENTED,
        mapping_confidence: MappingConfidence = MappingConfidence.EXACT_MATCH,
        coverage_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MappingRecord:
        record = MappingRecord(
            control_name=control_name,
            compliance_framework=compliance_framework,
            control_status=control_status,
            mapping_confidence=mapping_confidence,
            coverage_score=coverage_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "compliance_control_mapper.mapping_recorded",
            record_id=record.id,
            control_name=control_name,
            compliance_framework=compliance_framework.value,
            control_status=control_status.value,
        )
        return record

    def get_mapping(self, record_id: str) -> MappingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_mappings(
        self,
        compliance_framework: ComplianceFramework | None = None,
        control_status: ControlStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MappingRecord]:
        results = list(self._records)
        if compliance_framework is not None:
            results = [r for r in results if r.compliance_framework == compliance_framework]
        if control_status is not None:
            results = [r for r in results if r.control_status == control_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        control_name: str,
        compliance_framework: ComplianceFramework = ComplianceFramework.SOC2,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MappingAnalysis:
        analysis = MappingAnalysis(
            control_name=control_name,
            compliance_framework=compliance_framework,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "compliance_control_mapper.analysis_added",
            control_name=control_name,
            compliance_framework=compliance_framework.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_mapping_distribution(self) -> dict[str, Any]:
        """Group by compliance_framework; return count and avg coverage_score."""
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

    def identify_coverage_gaps(self) -> list[dict[str, Any]]:
        """Return records where coverage_score < coverage_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.coverage_score < self._coverage_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "control_name": r.control_name,
                        "compliance_framework": r.compliance_framework.value,
                        "coverage_score": r.coverage_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["coverage_score"])

    def rank_by_coverage(self) -> list[dict[str, Any]]:
        """Group by service, avg coverage_score, sort ascending (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.coverage_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_coverage_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_score"])
        return results

    def detect_mapping_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ComplianceControlReport:
        by_framework: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for r in self._records:
            by_framework[r.compliance_framework.value] = (
                by_framework.get(r.compliance_framework.value, 0) + 1
            )
            by_status[r.control_status.value] = by_status.get(r.control_status.value, 0) + 1
            by_confidence[r.mapping_confidence.value] = (
                by_confidence.get(r.mapping_confidence.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.coverage_score < self._coverage_gap_threshold)
        scores = [r.coverage_score for r in self._records]
        avg_coverage_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_coverage_gaps()
        top_gaps = [o["control_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if gap_count > 0:
            recs.append(f"{gap_count} coverage gap(s) — address immediately")
        if self._records and avg_coverage_score < self._coverage_gap_threshold:
            recs.append(
                f"Avg coverage score {avg_coverage_score} below threshold "
                f"({self._coverage_gap_threshold})"
            )
        if not recs:
            recs.append("Compliance control mapping levels are healthy")
        return ComplianceControlReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_coverage_score=avg_coverage_score,
            by_framework=by_framework,
            by_status=by_status,
            by_confidence=by_confidence,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("compliance_control_mapper.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        framework_dist: dict[str, int] = {}
        for r in self._records:
            key = r.compliance_framework.value
            framework_dist[key] = framework_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "coverage_gap_threshold": self._coverage_gap_threshold,
            "framework_distribution": framework_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
