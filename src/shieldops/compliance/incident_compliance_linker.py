"""Incident Compliance Linker — link incidents to compliance requirements."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IncidentCategory(StrEnum):
    DATA_BREACH = "data_breach"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    SERVICE_DISRUPTION = "service_disruption"
    POLICY_VIOLATION = "policy_violation"
    REGULATORY_FAILURE = "regulatory_failure"


class ComplianceImpact(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    NONE = "none"


class NotificationRequirement(StrEnum):
    MANDATORY = "mandatory"
    CONDITIONAL = "conditional"
    RECOMMENDED = "recommended"
    NONE_REQUIRED = "none_required"
    TBD = "tbd"


# --- Models ---


class LinkRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_name: str = ""
    incident_category: IncidentCategory = IncidentCategory.DATA_BREACH
    compliance_impact: ComplianceImpact = ComplianceImpact.CRITICAL
    notification_requirement: NotificationRequirement = NotificationRequirement.MANDATORY
    link_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class LinkAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_name: str = ""
    incident_category: IncidentCategory = IncidentCategory.DATA_BREACH
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_link_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    by_notification: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentComplianceLinker:
    """Link incidents to compliance requirements, track impact, identify notification gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[LinkRecord] = []
        self._analyses: list[LinkAnalysis] = []
        logger.info(
            "incident_compliance_linker.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_link(
        self,
        incident_name: str,
        incident_category: IncidentCategory = IncidentCategory.DATA_BREACH,
        compliance_impact: ComplianceImpact = ComplianceImpact.CRITICAL,
        notification_requirement: NotificationRequirement = NotificationRequirement.MANDATORY,
        link_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> LinkRecord:
        record = LinkRecord(
            incident_name=incident_name,
            incident_category=incident_category,
            compliance_impact=compliance_impact,
            notification_requirement=notification_requirement,
            link_score=link_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_compliance_linker.link_recorded",
            record_id=record.id,
            incident_name=incident_name,
            incident_category=incident_category.value,
            compliance_impact=compliance_impact.value,
        )
        return record

    def get_record(self, record_id: str) -> LinkRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        incident_category: IncidentCategory | None = None,
        compliance_impact: ComplianceImpact | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[LinkRecord]:
        results = list(self._records)
        if incident_category is not None:
            results = [r for r in results if r.incident_category == incident_category]
        if compliance_impact is not None:
            results = [r for r in results if r.compliance_impact == compliance_impact]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        incident_name: str,
        incident_category: IncidentCategory = IncidentCategory.DATA_BREACH,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> LinkAnalysis:
        analysis = LinkAnalysis(
            incident_name=incident_name,
            incident_category=incident_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "incident_compliance_linker.analysis_added",
            incident_name=incident_name,
            incident_category=incident_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by incident_category; return count and avg link_score."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.incident_category.value
            cat_data.setdefault(key, []).append(r.link_score)
        result: dict[str, Any] = {}
        for category, scores in cat_data.items():
            result[category] = {
                "count": len(scores),
                "avg_link_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where link_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.link_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "incident_name": r.incident_name,
                        "incident_category": r.incident_category.value,
                        "link_score": r.link_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["link_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg link_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.link_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_link_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_link_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> IncidentComplianceReport:
        by_category: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        by_notification: dict[str, int] = {}
        for r in self._records:
            by_category[r.incident_category.value] = (
                by_category.get(r.incident_category.value, 0) + 1
            )
            by_impact[r.compliance_impact.value] = by_impact.get(r.compliance_impact.value, 0) + 1
            by_notification[r.notification_requirement.value] = (
                by_notification.get(r.notification_requirement.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.link_score < self._threshold)
        scores = [r.link_score for r in self._records]
        avg_link_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["incident_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} incident link(s) below score threshold ({self._threshold})")
        if self._records and avg_link_score < self._threshold:
            recs.append(f"Avg link score {avg_link_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Incident compliance linking is healthy")
        return IncidentComplianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_link_score=avg_link_score,
            by_category=by_category,
            by_impact=by_impact,
            by_notification=by_notification,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("incident_compliance_linker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.incident_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
