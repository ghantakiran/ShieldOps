"""Security Compliance Scorer — score compliance posture, identify gaps across frameworks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComplianceArea(StrEnum):
    ACCESS_CONTROL = "access_control"
    DATA_PROTECTION = "data_protection"
    NETWORK_SECURITY = "network_security"
    INCIDENT_MANAGEMENT = "incident_management"
    VULNERABILITY_MANAGEMENT = "vulnerability_management"


class GapSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class FrameworkType(StrEnum):
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    ISO_27001 = "iso_27001"
    NIST = "nist"


# --- Models ---


class ComplianceScoreRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_name: str = ""
    compliance_area: ComplianceArea = ComplianceArea.ACCESS_CONTROL
    gap_severity: GapSeverity = GapSeverity.CRITICAL
    framework_type: FrameworkType = FrameworkType.SOC2
    compliance_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceGapAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_name: str = ""
    compliance_area: ComplianceArea = ComplianceArea.ACCESS_CONTROL
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SecurityComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    gap_count: int = 0
    avg_compliance_score: float = 0.0
    by_area: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_framework: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityComplianceScorer:
    """Score compliance posture, identify gaps across frameworks."""

    def __init__(
        self,
        max_records: int = 200000,
        compliance_gap_threshold: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._compliance_gap_threshold = compliance_gap_threshold
        self._records: list[ComplianceScoreRecord] = []
        self._assessments: list[ComplianceGapAssessment] = []
        logger.info(
            "security_compliance_scorer.initialized",
            max_records=max_records,
            compliance_gap_threshold=compliance_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_compliance(
        self,
        control_name: str,
        compliance_area: ComplianceArea = ComplianceArea.ACCESS_CONTROL,
        gap_severity: GapSeverity = GapSeverity.CRITICAL,
        framework_type: FrameworkType = FrameworkType.SOC2,
        compliance_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ComplianceScoreRecord:
        record = ComplianceScoreRecord(
            control_name=control_name,
            compliance_area=compliance_area,
            gap_severity=gap_severity,
            framework_type=framework_type,
            compliance_score=compliance_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_compliance_scorer.compliance_recorded",
            record_id=record.id,
            control_name=control_name,
            compliance_area=compliance_area.value,
            gap_severity=gap_severity.value,
        )
        return record

    def get_compliance(self, record_id: str) -> ComplianceScoreRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_compliance_records(
        self,
        compliance_area: ComplianceArea | None = None,
        gap_severity: GapSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ComplianceScoreRecord]:
        results = list(self._records)
        if compliance_area is not None:
            results = [r for r in results if r.compliance_area == compliance_area]
        if gap_severity is not None:
            results = [r for r in results if r.gap_severity == gap_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        control_name: str,
        compliance_area: ComplianceArea = ComplianceArea.ACCESS_CONTROL,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ComplianceGapAssessment:
        assessment = ComplianceGapAssessment(
            control_name=control_name,
            compliance_area=compliance_area,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "security_compliance_scorer.assessment_added",
            control_name=control_name,
            compliance_area=compliance_area.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_compliance_distribution(self) -> dict[str, Any]:
        """Group by compliance_area; return count and avg compliance_score."""
        area_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.compliance_area.value
            area_data.setdefault(key, []).append(r.compliance_score)
        result: dict[str, Any] = {}
        for area, scores in area_data.items():
            result[area] = {
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
                        "control_name": r.control_name,
                        "compliance_area": r.compliance_area.value,
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
        """Split-half comparison on assessment_score; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.assessment_score for a in self._assessments]
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

    def generate_report(self) -> SecurityComplianceReport:
        by_area: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_framework: dict[str, int] = {}
        for r in self._records:
            by_area[r.compliance_area.value] = by_area.get(r.compliance_area.value, 0) + 1
            by_severity[r.gap_severity.value] = by_severity.get(r.gap_severity.value, 0) + 1
            by_framework[r.framework_type.value] = by_framework.get(r.framework_type.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.compliance_score < self._compliance_gap_threshold
        )
        scores = [r.compliance_score for r in self._records]
        avg_compliance_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_compliance_gaps()
        top_gaps = [o["control_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} control(s) below compliance threshold "
                f"({self._compliance_gap_threshold})"
            )
        if self._records and avg_compliance_score < self._compliance_gap_threshold:
            recs.append(
                f"Avg compliance score {avg_compliance_score} below threshold "
                f"({self._compliance_gap_threshold})"
            )
        if not recs:
            recs.append("Security compliance score levels are healthy")
        return SecurityComplianceReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            gap_count=gap_count,
            avg_compliance_score=avg_compliance_score,
            by_area=by_area,
            by_severity=by_severity,
            by_framework=by_framework,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("security_compliance_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        area_dist: dict[str, int] = {}
        for r in self._records:
            key = r.compliance_area.value
            area_dist[key] = area_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "compliance_gap_threshold": self._compliance_gap_threshold,
            "area_distribution": area_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
