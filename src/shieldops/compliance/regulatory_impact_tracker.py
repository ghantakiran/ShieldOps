"""Regulatory Impact Tracker — track regulatory changes, assess compliance impact."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RegulationType(StrEnum):
    DATA_PRIVACY = "data_privacy"
    FINANCIAL = "financial"
    HEALTHCARE = "healthcare"
    CYBERSECURITY = "cybersecurity"
    ENVIRONMENTAL = "environmental"


class ChangeImpact(StrEnum):
    MAJOR = "major"
    SIGNIFICANT = "significant"
    MODERATE = "moderate"
    MINOR = "minor"
    NO_IMPACT = "no_impact"


class ComplianceReadiness(StrEnum):
    COMPLIANT = "compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    IN_PROGRESS = "in_progress"
    GAP_IDENTIFIED = "gap_identified"
    NOT_ASSESSED = "not_assessed"


# --- Models ---


class RegulatoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    regulation_name: str = ""
    regulation_type: RegulationType = RegulationType.DATA_PRIVACY
    change_impact: ChangeImpact = ChangeImpact.MAJOR
    compliance_readiness: ComplianceReadiness = ComplianceReadiness.COMPLIANT
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RegulatoryAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    regulation_name: str = ""
    regulation_type: RegulationType = RegulationType.DATA_PRIVACY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RegulatoryImpactReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_impact_count: int = 0
    avg_impact_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    by_readiness: dict[str, int] = Field(default_factory=dict)
    top_high_impact: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RegulatoryImpactTracker:
    """Track regulatory changes, assess compliance impact, monitor readiness."""

    def __init__(
        self,
        max_records: int = 200000,
        impact_severity_threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._impact_severity_threshold = impact_severity_threshold
        self._records: list[RegulatoryRecord] = []
        self._analyses: list[RegulatoryAnalysis] = []
        logger.info(
            "regulatory_impact_tracker.initialized",
            max_records=max_records,
            impact_severity_threshold=impact_severity_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_regulatory(
        self,
        regulation_name: str,
        regulation_type: RegulationType = RegulationType.DATA_PRIVACY,
        change_impact: ChangeImpact = ChangeImpact.MAJOR,
        compliance_readiness: ComplianceReadiness = ComplianceReadiness.COMPLIANT,
        impact_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RegulatoryRecord:
        record = RegulatoryRecord(
            regulation_name=regulation_name,
            regulation_type=regulation_type,
            change_impact=change_impact,
            compliance_readiness=compliance_readiness,
            impact_score=impact_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "regulatory_impact_tracker.regulatory_recorded",
            record_id=record.id,
            regulation_name=regulation_name,
            regulation_type=regulation_type.value,
            change_impact=change_impact.value,
        )
        return record

    def get_regulatory(self, record_id: str) -> RegulatoryRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_regulatory_records(
        self,
        regulation_type: RegulationType | None = None,
        change_impact: ChangeImpact | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RegulatoryRecord]:
        results = list(self._records)
        if regulation_type is not None:
            results = [r for r in results if r.regulation_type == regulation_type]
        if change_impact is not None:
            results = [r for r in results if r.change_impact == change_impact]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        regulation_name: str,
        regulation_type: RegulationType = RegulationType.DATA_PRIVACY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RegulatoryAnalysis:
        analysis = RegulatoryAnalysis(
            regulation_name=regulation_name,
            regulation_type=regulation_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "regulatory_impact_tracker.analysis_added",
            regulation_name=regulation_name,
            regulation_type=regulation_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_regulatory_distribution(self) -> dict[str, Any]:
        """Group by regulation_type; return count and avg impact_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.regulation_type.value
            type_data.setdefault(key, []).append(r.impact_score)
        result: dict[str, Any] = {}
        for rtype, scores in type_data.items():
            result[rtype] = {
                "count": len(scores),
                "avg_impact_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_impact_regulations(self) -> list[dict[str, Any]]:
        """Return records where impact_score > impact_severity_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.impact_score > self._impact_severity_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "regulation_name": r.regulation_name,
                        "regulation_type": r.regulation_type.value,
                        "impact_score": r.impact_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["impact_score"], reverse=True)

    def rank_by_impact(self) -> list[dict[str, Any]]:
        """Group by service, avg impact_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_impact_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_impact_score"], reverse=True)
        return results

    def detect_regulatory_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> RegulatoryImpactReport:
        by_type: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        by_readiness: dict[str, int] = {}
        for r in self._records:
            by_type[r.regulation_type.value] = by_type.get(r.regulation_type.value, 0) + 1
            by_impact[r.change_impact.value] = by_impact.get(r.change_impact.value, 0) + 1
            by_readiness[r.compliance_readiness.value] = (
                by_readiness.get(r.compliance_readiness.value, 0) + 1
            )
        high_impact_count = sum(
            1 for r in self._records if r.impact_score > self._impact_severity_threshold
        )
        scores = [r.impact_score for r in self._records]
        avg_impact_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_impact_regulations()
        top_high_impact = [o["regulation_name"] for o in high_list[:5]]
        recs: list[str] = []
        if high_impact_count > 0:
            recs.append(f"{high_impact_count} high-impact regulation(s) — prioritize compliance")
        if self._records and avg_impact_score > self._impact_severity_threshold:
            recs.append(
                f"Avg impact score {avg_impact_score} above threshold "
                f"({self._impact_severity_threshold})"
            )
        if not recs:
            recs.append("Regulatory impact levels are healthy")
        return RegulatoryImpactReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_impact_count=high_impact_count,
            avg_impact_score=avg_impact_score,
            by_type=by_type,
            by_impact=by_impact,
            by_readiness=by_readiness,
            top_high_impact=top_high_impact,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("regulatory_impact_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.regulation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "impact_severity_threshold": self._impact_severity_threshold,
            "regulation_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
