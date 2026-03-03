"""Software License Resolver — resolve license conflicts and compliance strategies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LicenseType(StrEnum):
    PERMISSIVE = "permissive"
    COPYLEFT = "copyleft"
    WEAK_COPYLEFT = "weak_copyleft"
    PROPRIETARY = "proprietary"
    UNKNOWN = "unknown"


class ConflictSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ResolutionStrategy(StrEnum):
    REPLACE = "replace"
    WAIVER = "waiver"
    DUAL_LICENSE = "dual_license"
    REMOVE = "remove"
    ACCEPT = "accept"


# --- Models ---


class LicenseResolution(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_name: str = ""
    license_type: LicenseType = LicenseType.PERMISSIVE
    conflict_severity: ConflictSeverity = ConflictSeverity.NONE
    resolution_strategy: ResolutionStrategy = ResolutionStrategy.ACCEPT
    compliance_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ResolutionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_name: str = ""
    license_type: LicenseType = LicenseType.PERMISSIVE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LicenseResolutionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_compliance_score: float = 0.0
    by_license_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SoftwareLicenseResolver:
    """Resolve license conflicts and determine compliance strategies for packages."""

    def __init__(
        self,
        max_records: int = 200000,
        compliance_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._compliance_gap_threshold = compliance_gap_threshold
        self._records: list[LicenseResolution] = []
        self._analyses: list[ResolutionAnalysis] = []
        logger.info(
            "software_license_resolver.initialized",
            max_records=max_records,
            compliance_gap_threshold=compliance_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_resolution(
        self,
        package_name: str,
        license_type: LicenseType = LicenseType.PERMISSIVE,
        conflict_severity: ConflictSeverity = ConflictSeverity.NONE,
        resolution_strategy: ResolutionStrategy = ResolutionStrategy.ACCEPT,
        compliance_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> LicenseResolution:
        record = LicenseResolution(
            package_name=package_name,
            license_type=license_type,
            conflict_severity=conflict_severity,
            resolution_strategy=resolution_strategy,
            compliance_score=compliance_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "software_license_resolver.resolution_recorded",
            record_id=record.id,
            package_name=package_name,
            license_type=license_type.value,
            conflict_severity=conflict_severity.value,
        )
        return record

    def get_resolution(self, record_id: str) -> LicenseResolution | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_resolutions(
        self,
        license_type: LicenseType | None = None,
        conflict_severity: ConflictSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[LicenseResolution]:
        results = list(self._records)
        if license_type is not None:
            results = [r for r in results if r.license_type == license_type]
        if conflict_severity is not None:
            results = [r for r in results if r.conflict_severity == conflict_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        package_name: str,
        license_type: LicenseType = LicenseType.PERMISSIVE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ResolutionAnalysis:
        analysis = ResolutionAnalysis(
            package_name=package_name,
            license_type=license_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "software_license_resolver.analysis_added",
            package_name=package_name,
            license_type=license_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_license_distribution(self) -> dict[str, Any]:
        """Group by license_type; return count and avg compliance_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.license_type.value
            type_data.setdefault(key, []).append(r.compliance_score)
        result: dict[str, Any] = {}
        for ltype, scores in type_data.items():
            result[ltype] = {
                "count": len(scores),
                "avg_compliance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_license_gaps(self) -> list[dict[str, Any]]:
        """Return records where compliance_score < compliance_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_score < self._compliance_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "package_name": r.package_name,
                        "license_type": r.license_type.value,
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

    def generate_report(self) -> LicenseResolutionReport:
        by_license_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        for r in self._records:
            by_license_type[r.license_type.value] = by_license_type.get(r.license_type.value, 0) + 1
            by_severity[r.conflict_severity.value] = (
                by_severity.get(r.conflict_severity.value, 0) + 1
            )
            by_strategy[r.resolution_strategy.value] = (
                by_strategy.get(r.resolution_strategy.value, 0) + 1
            )
        gap_count = sum(
            1 for r in self._records if r.compliance_score < self._compliance_gap_threshold
        )
        scores = [r.compliance_score for r in self._records]
        avg_compliance_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_license_gaps()
        top_gaps = [o["package_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} package(s) below license compliance threshold "
                f"({self._compliance_gap_threshold})"
            )
        if self._records and avg_compliance_score < self._compliance_gap_threshold:
            recs.append(
                f"Avg compliance score {avg_compliance_score} below threshold "
                f"({self._compliance_gap_threshold})"
            )
        if not recs:
            recs.append("Software license compliance is healthy")
        return LicenseResolutionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_compliance_score=avg_compliance_score,
            by_license_type=by_license_type,
            by_severity=by_severity,
            by_strategy=by_strategy,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("software_license_resolver.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.license_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "compliance_gap_threshold": self._compliance_gap_threshold,
            "license_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
