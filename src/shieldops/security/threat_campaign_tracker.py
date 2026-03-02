"""Threat Campaign Tracker — track campaigns, link alerts/hunts to campaigns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CampaignType(StrEnum):
    APT = "apt"
    RANSOMWARE = "ransomware"
    PHISHING = "phishing"
    SUPPLY_CHAIN = "supply_chain"
    INSIDER_THREAT = "insider_threat"


class CampaignStatus(StrEnum):
    ACTIVE = "active"
    CONTAINED = "contained"
    ERADICATED = "eradicated"
    MONITORING = "monitoring"
    CLOSED = "closed"


class CampaignSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class CampaignRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_name: str = ""
    campaign_type: CampaignType = CampaignType.APT
    campaign_status: CampaignStatus = CampaignStatus.ACTIVE
    campaign_severity: CampaignSeverity = CampaignSeverity.CRITICAL
    threat_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CampaignAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_name: str = ""
    campaign_type: CampaignType = CampaignType.APT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CampaignReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_threat_count: int = 0
    avg_threat_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    top_high_threat: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatCampaignTracker:
    """Track threat campaigns and link alerts/hunts to campaigns."""

    def __init__(
        self,
        max_records: int = 200000,
        threat_score_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._threat_score_threshold = threat_score_threshold
        self._records: list[CampaignRecord] = []
        self._analyses: list[CampaignAnalysis] = []
        logger.info(
            "threat_campaign_tracker.initialized",
            max_records=max_records,
            threat_score_threshold=threat_score_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_campaign(
        self,
        campaign_name: str,
        campaign_type: CampaignType = CampaignType.APT,
        campaign_status: CampaignStatus = CampaignStatus.ACTIVE,
        campaign_severity: CampaignSeverity = CampaignSeverity.CRITICAL,
        threat_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CampaignRecord:
        record = CampaignRecord(
            campaign_name=campaign_name,
            campaign_type=campaign_type,
            campaign_status=campaign_status,
            campaign_severity=campaign_severity,
            threat_score=threat_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "threat_campaign_tracker.campaign_recorded",
            record_id=record.id,
            campaign_name=campaign_name,
            campaign_type=campaign_type.value,
            campaign_status=campaign_status.value,
        )
        return record

    def get_campaign(self, record_id: str) -> CampaignRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_campaigns(
        self,
        campaign_type: CampaignType | None = None,
        campaign_status: CampaignStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CampaignRecord]:
        results = list(self._records)
        if campaign_type is not None:
            results = [r for r in results if r.campaign_type == campaign_type]
        if campaign_status is not None:
            results = [r for r in results if r.campaign_status == campaign_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        campaign_name: str,
        campaign_type: CampaignType = CampaignType.APT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CampaignAnalysis:
        analysis = CampaignAnalysis(
            campaign_name=campaign_name,
            campaign_type=campaign_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "threat_campaign_tracker.analysis_added",
            campaign_name=campaign_name,
            campaign_type=campaign_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_campaign_distribution(self) -> dict[str, Any]:
        """Group by campaign_type; return count and avg threat_score."""
        src_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.campaign_type.value
            src_data.setdefault(key, []).append(r.threat_score)
        result: dict[str, Any] = {}
        for src, scores in src_data.items():
            result[src] = {
                "count": len(scores),
                "avg_threat_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_threat_campaigns(self) -> list[dict[str, Any]]:
        """Return records where threat_score > threat_score_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.threat_score > self._threat_score_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "campaign_name": r.campaign_name,
                        "campaign_type": r.campaign_type.value,
                        "threat_score": r.threat_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["threat_score"], reverse=True)

    def rank_by_threat(self) -> list[dict[str, Any]]:
        """Group by service, avg threat_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.threat_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_threat_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_threat_score"], reverse=True)
        return results

    def detect_campaign_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
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

    def generate_report(self) -> CampaignReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_type[r.campaign_type.value] = by_type.get(r.campaign_type.value, 0) + 1
            by_status[r.campaign_status.value] = by_status.get(r.campaign_status.value, 0) + 1
            by_severity[r.campaign_severity.value] = (
                by_severity.get(r.campaign_severity.value, 0) + 1
            )
        high_threat_count = sum(
            1 for r in self._records if r.threat_score > self._threat_score_threshold
        )
        scores = [r.threat_score for r in self._records]
        avg_threat_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_threat_campaigns()
        top_high_threat = [o["campaign_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_threat_count > 0:
            recs.append(
                f"{high_threat_count} campaign(s) above threat score threshold "
                f"({self._threat_score_threshold})"
            )
        if self._records and avg_threat_score > self._threat_score_threshold:
            recs.append(
                f"Avg threat score {avg_threat_score} above threshold "
                f"({self._threat_score_threshold})"
            )
        if not recs:
            recs.append("Threat campaign tracking is healthy")
        return CampaignReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_threat_count=high_threat_count,
            avg_threat_score=avg_threat_score,
            by_type=by_type,
            by_status=by_status,
            by_severity=by_severity,
            top_high_threat=top_high_threat,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("threat_campaign_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.campaign_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threat_score_threshold": self._threat_score_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
