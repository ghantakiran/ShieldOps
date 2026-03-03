"""Organizational SLA Tracker — track SLA compliance across stakeholder levels."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SLAType(StrEnum):
    AVAILABILITY = "availability"
    RESPONSE_TIME = "response_time"
    RESOLUTION_TIME = "resolution_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"


class ComplianceStatus(StrEnum):
    MEETING = "meeting"
    AT_RISK = "at_risk"
    BREACHING = "breaching"
    BREACHED = "breached"
    EXEMPT = "exempt"


class StakeholderLevel(StrEnum):
    EXECUTIVE = "executive"
    DIRECTOR = "director"
    MANAGER = "manager"
    TEAM = "team"
    INDIVIDUAL = "individual"


# --- Models ---


class SLARecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    team: str = ""
    sla_type: SLAType = SLAType.AVAILABILITY
    compliance_status: ComplianceStatus = ComplianceStatus.MEETING
    stakeholder_level: StakeholderLevel = StakeholderLevel.TEAM
    compliance_score: float = 0.0
    target_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class SLAAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    sla_type: SLAType = SLAType.AVAILABILITY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SLAReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_compliance_score: float = 0.0
    by_sla_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_stakeholder: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class OrganizationalSLATracker:
    """Track SLA compliance across services, teams, and stakeholder levels."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[SLARecord] = []
        self._analyses: list[SLAAnalysis] = []
        logger.info(
            "organizational_sla_tracker.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_sla(
        self,
        service: str,
        team: str = "",
        sla_type: SLAType = SLAType.AVAILABILITY,
        compliance_status: ComplianceStatus = ComplianceStatus.MEETING,
        stakeholder_level: StakeholderLevel = StakeholderLevel.TEAM,
        compliance_score: float = 0.0,
        target_pct: float = 0.0,
    ) -> SLARecord:
        record = SLARecord(
            service=service,
            team=team,
            sla_type=sla_type,
            compliance_status=compliance_status,
            stakeholder_level=stakeholder_level,
            compliance_score=compliance_score,
            target_pct=target_pct,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "organizational_sla_tracker.sla_recorded",
            record_id=record.id,
            service=service,
            sla_type=sla_type.value,
            compliance_status=compliance_status.value,
        )
        return record

    def get_sla(self, record_id: str) -> SLARecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_slas(
        self,
        sla_type: SLAType | None = None,
        compliance_status: ComplianceStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SLARecord]:
        results = list(self._records)
        if sla_type is not None:
            results = [r for r in results if r.sla_type == sla_type]
        if compliance_status is not None:
            results = [r for r in results if r.compliance_status == compliance_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        service: str,
        sla_type: SLAType = SLAType.AVAILABILITY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SLAAnalysis:
        analysis = SLAAnalysis(
            service=service,
            sla_type=sla_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "organizational_sla_tracker.analysis_added",
            service=service,
            sla_type=sla_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by sla_type; return count and avg compliance_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.sla_type.value
            type_data.setdefault(key, []).append(r.compliance_score)
        result: dict[str, Any] = {}
        for sla_type, scores in type_data.items():
            result[sla_type] = {
                "count": len(scores),
                "avg_compliance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_sla_gaps(self) -> list[dict[str, Any]]:
        """Return records where compliance_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "service": r.service,
                        "sla_type": r.sla_type.value,
                        "compliance_score": r.compliance_score,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["compliance_score"])

    def rank_by_compliance(self) -> list[dict[str, Any]]:
        """Group by service, avg compliance_score, sort ascending."""
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

    def detect_sla_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> SLAReport:
        by_sla_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_stakeholder: dict[str, int] = {}
        for r in self._records:
            by_sla_type[r.sla_type.value] = by_sla_type.get(r.sla_type.value, 0) + 1
            by_status[r.compliance_status.value] = by_status.get(r.compliance_status.value, 0) + 1
            by_stakeholder[r.stakeholder_level.value] = (
                by_stakeholder.get(r.stakeholder_level.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.compliance_score < self._threshold)
        scores = [r.compliance_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_sla_gaps()
        top_gaps = [o["service"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} SLA(s) below compliance threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg compliance score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("SLA compliance is healthy")
        return SLAReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_compliance_score=avg_score,
            by_sla_type=by_sla_type,
            by_status=by_status,
            by_stakeholder=by_stakeholder,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("organizational_sla_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.sla_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "sla_type_distribution": type_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
