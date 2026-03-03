"""Vendor Security Incident Tracker — track vendor security incidents."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VendorTier(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCLASSIFIED = "unclassified"


class IncidentImpact(StrEnum):
    DATA_BREACH = "data_breach"
    SERVICE_DISRUPTION = "service_disruption"
    COMPLIANCE_VIOLATION = "compliance_violation"
    REPUTATION = "reputation"
    FINANCIAL = "financial"


class ResponseStatus(StrEnum):
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


# --- Models ---


class VendorIncidentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    vendor_tier: VendorTier = VendorTier.CRITICAL
    incident_impact: IncidentImpact = IncidentImpact.DATA_BREACH
    response_status: ResponseStatus = ResponseStatus.ACKNOWLEDGED
    incident_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class VendorIncidentAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    vendor_tier: VendorTier = VendorTier.CRITICAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class VendorSecurityIncidentReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_incident_score: float = 0.0
    by_vendor_tier: dict[str, int] = Field(default_factory=dict)
    by_incident_impact: dict[str, int] = Field(default_factory=dict)
    by_response_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class VendorSecurityIncidentTracker:
    """Track and monitor vendor security incidents across tiers."""

    def __init__(
        self,
        max_records: int = 200000,
        incident_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._incident_gap_threshold = incident_gap_threshold
        self._records: list[VendorIncidentRecord] = []
        self._analyses: list[VendorIncidentAnalysis] = []
        logger.info(
            "vendor_security_incident_tracker.initialized",
            max_records=max_records,
            incident_gap_threshold=incident_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_incident(
        self,
        incident_id: str,
        vendor_tier: VendorTier = VendorTier.CRITICAL,
        incident_impact: IncidentImpact = IncidentImpact.DATA_BREACH,
        response_status: ResponseStatus = ResponseStatus.ACKNOWLEDGED,
        incident_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> VendorIncidentRecord:
        record = VendorIncidentRecord(
            incident_id=incident_id,
            vendor_tier=vendor_tier,
            incident_impact=incident_impact,
            response_status=response_status,
            incident_score=incident_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "vendor_security_incident_tracker.recorded",
            record_id=record.id,
            incident_id=incident_id,
            vendor_tier=vendor_tier.value,
            incident_impact=incident_impact.value,
        )
        return record

    def get_incident(self, record_id: str) -> VendorIncidentRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_incidents(
        self,
        vendor_tier: VendorTier | None = None,
        incident_impact: IncidentImpact | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[VendorIncidentRecord]:
        results = list(self._records)
        if vendor_tier is not None:
            results = [r for r in results if r.vendor_tier == vendor_tier]
        if incident_impact is not None:
            results = [r for r in results if r.incident_impact == incident_impact]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        incident_id: str,
        vendor_tier: VendorTier = VendorTier.CRITICAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> VendorIncidentAnalysis:
        analysis = VendorIncidentAnalysis(
            incident_id=incident_id,
            vendor_tier=vendor_tier,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "vendor_security_incident_tracker.analysis_added",
            incident_id=incident_id,
            vendor_tier=vendor_tier.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_incident_distribution(self) -> dict[str, Any]:
        data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.vendor_tier.value
            data.setdefault(key, []).append(r.incident_score)
        result: dict[str, Any] = {}
        for k, scores in data.items():
            result[k] = {
                "count": len(scores),
                "avg_incident_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_incident_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.incident_score < self._incident_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "incident_id": r.incident_id,
                        "vendor_tier": r.vendor_tier.value,
                        "incident_score": r.incident_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["incident_score"])

    def rank_by_incident(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.incident_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_incident_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_incident_score"])
        return results

    def detect_incident_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> VendorSecurityIncidentReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.vendor_tier.value] = by_e1.get(r.vendor_tier.value, 0) + 1
            by_e2[r.incident_impact.value] = by_e2.get(r.incident_impact.value, 0) + 1
            by_e3[r.response_status.value] = by_e3.get(r.response_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.incident_score < self._incident_gap_threshold)
        scores = [r.incident_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_incident_gaps()
        top_gaps = [o["incident_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} record(s) below threshold ({self._incident_gap_threshold})")
        if self._records and avg_score < self._incident_gap_threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._incident_gap_threshold})")
        if not recs:
            recs.append("VendorSecurityIncidentTracker metrics are healthy")
        return VendorSecurityIncidentReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_incident_score=avg_score,
            by_vendor_tier=by_e1,
            by_incident_impact=by_e2,
            by_response_status=by_e3,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("vendor_security_incident_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            key = r.vendor_tier.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "incident_gap_threshold": self._incident_gap_threshold,
            "vendor_tier_distribution": dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
