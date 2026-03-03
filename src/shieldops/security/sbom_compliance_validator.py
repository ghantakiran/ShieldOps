"""SBOM Compliance Validator — validate SBOM completeness and compliance levels."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SBOMFormat(StrEnum):
    SPDX = "spdx"
    CYCLONEDX = "cyclonedx"
    SWID = "swid"
    CSV = "csv"
    CUSTOM = "custom"


class ComplianceLevel(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"
    UNKNOWN = "unknown"


class ValidationScope(StrEnum):
    DIRECT = "direct"
    TRANSITIVE = "transitive"
    DEV = "dev"
    OPTIONAL = "optional"
    ALL = "all"


# --- Models ---


class SBOMValidation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    component_name: str = ""
    sbom_format: SBOMFormat = SBOMFormat.SPDX
    compliance_level: ComplianceLevel = ComplianceLevel.FULL
    validation_scope: ValidationScope = ValidationScope.ALL
    compliance_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    component_name: str = ""
    sbom_format: SBOMFormat = SBOMFormat.SPDX
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SBOMComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_compliance_score: float = 0.0
    by_format: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SBOMComplianceValidator:
    """Validate SBOM completeness, compliance levels, and coverage across components."""

    def __init__(
        self,
        max_records: int = 200000,
        compliance_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._compliance_gap_threshold = compliance_gap_threshold
        self._records: list[SBOMValidation] = []
        self._analyses: list[ComplianceAnalysis] = []
        logger.info(
            "sbom_compliance_validator.initialized",
            max_records=max_records,
            compliance_gap_threshold=compliance_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_validation(
        self,
        component_name: str,
        sbom_format: SBOMFormat = SBOMFormat.SPDX,
        compliance_level: ComplianceLevel = ComplianceLevel.FULL,
        validation_scope: ValidationScope = ValidationScope.ALL,
        compliance_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SBOMValidation:
        record = SBOMValidation(
            component_name=component_name,
            sbom_format=sbom_format,
            compliance_level=compliance_level,
            validation_scope=validation_scope,
            compliance_score=compliance_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "sbom_compliance_validator.validation_recorded",
            record_id=record.id,
            component_name=component_name,
            sbom_format=sbom_format.value,
            compliance_level=compliance_level.value,
        )
        return record

    def get_validation(self, record_id: str) -> SBOMValidation | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_validations(
        self,
        sbom_format: SBOMFormat | None = None,
        compliance_level: ComplianceLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SBOMValidation]:
        results = list(self._records)
        if sbom_format is not None:
            results = [r for r in results if r.sbom_format == sbom_format]
        if compliance_level is not None:
            results = [r for r in results if r.compliance_level == compliance_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        component_name: str,
        sbom_format: SBOMFormat = SBOMFormat.SPDX,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ComplianceAnalysis:
        analysis = ComplianceAnalysis(
            component_name=component_name,
            sbom_format=sbom_format,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "sbom_compliance_validator.analysis_added",
            component_name=component_name,
            sbom_format=sbom_format.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_format_distribution(self) -> dict[str, Any]:
        """Group by sbom_format; return count and avg compliance_score."""
        format_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.sbom_format.value
            format_data.setdefault(key, []).append(r.compliance_score)
        result: dict[str, Any] = {}
        for fmt, scores in format_data.items():
            result[fmt] = {
                "count": len(scores),
                "avg_compliance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_compliance_gaps(self) -> list[dict[str, Any]]:
        """Return records where compliance_score < compliance_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_score < self._compliance_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "component_name": r.component_name,
                        "sbom_format": r.sbom_format.value,
                        "compliance_score": r.compliance_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["compliance_score"])

    def rank_by_compliance(self) -> list[dict[str, Any]]:
        """Group by service, avg compliance_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.compliance_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_compliance_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_compliance_score"])
        return results

    def detect_compliance_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> SBOMComplianceReport:
        by_format: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for r in self._records:
            by_format[r.sbom_format.value] = by_format.get(r.sbom_format.value, 0) + 1
            by_level[r.compliance_level.value] = by_level.get(r.compliance_level.value, 0) + 1
            by_scope[r.validation_scope.value] = by_scope.get(r.validation_scope.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.compliance_score < self._compliance_gap_threshold
        )
        scores = [r.compliance_score for r in self._records]
        avg_compliance_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_compliance_gaps()
        top_gaps = [o["component_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} component(s) below compliance threshold "
                f"({self._compliance_gap_threshold})"
            )
        if self._records and avg_compliance_score < self._compliance_gap_threshold:
            recs.append(
                f"Avg compliance score {avg_compliance_score} below threshold "
                f"({self._compliance_gap_threshold})"
            )
        if not recs:
            recs.append("SBOM compliance is healthy")
        return SBOMComplianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_compliance_score=avg_compliance_score,
            by_format=by_format,
            by_level=by_level,
            by_scope=by_scope,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("sbom_compliance_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        format_dist: dict[str, int] = {}
        for r in self._records:
            key = r.sbom_format.value
            format_dist[key] = format_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "compliance_gap_threshold": self._compliance_gap_threshold,
            "format_distribution": format_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
