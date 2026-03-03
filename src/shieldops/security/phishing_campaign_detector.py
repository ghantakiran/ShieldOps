"""Phishing Campaign Detector — detect phishing campaigns via indicator and pattern analysis."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PhishingType(StrEnum):
    SPEAR_PHISHING = "spear_phishing"
    WHALING = "whaling"
    SMISHING = "smishing"
    VISHING = "vishing"
    BEC = "bec"


class CampaignIndicator(StrEnum):
    DOMAIN_SIMILARITY = "domain_similarity"
    HEADER_ANOMALY = "header_anomaly"
    CONTENT_PATTERN = "content_pattern"
    SENDER_REPUTATION = "sender_reputation"
    LINK_ANALYSIS = "link_analysis"


class CampaignStatus(StrEnum):
    ACTIVE = "active"
    CONTAINED = "contained"
    MITIGATED = "mitigated"
    MONITORING = "monitoring"
    CLOSED = "closed"


# --- Models ---


class PhishingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phishing_id: str = ""
    phishing_type: PhishingType = PhishingType.SPEAR_PHISHING
    campaign_indicator: CampaignIndicator = CampaignIndicator.DOMAIN_SIMILARITY
    campaign_status: CampaignStatus = CampaignStatus.ACTIVE
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PhishingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phishing_id: str = ""
    phishing_type: PhishingType = PhishingType.SPEAR_PHISHING
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PhishingCampaignReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_detection_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_indicator: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PhishingCampaignDetector:
    """Detect phishing campaigns via indicator analysis, pattern matching, and campaign tracking."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._detection_threshold = detection_threshold
        self._records: list[PhishingRecord] = []
        self._analyses: list[PhishingAnalysis] = []
        logger.info(
            "phishing_campaign_detector.initialized",
            max_records=max_records,
            detection_threshold=detection_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_phishing(
        self,
        phishing_id: str,
        phishing_type: PhishingType = PhishingType.SPEAR_PHISHING,
        campaign_indicator: CampaignIndicator = CampaignIndicator.DOMAIN_SIMILARITY,
        campaign_status: CampaignStatus = CampaignStatus.ACTIVE,
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PhishingRecord:
        record = PhishingRecord(
            phishing_id=phishing_id,
            phishing_type=phishing_type,
            campaign_indicator=campaign_indicator,
            campaign_status=campaign_status,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "phishing_campaign_detector.phishing_recorded",
            record_id=record.id,
            phishing_id=phishing_id,
            phishing_type=phishing_type.value,
            campaign_indicator=campaign_indicator.value,
        )
        return record

    def get_phishing(self, record_id: str) -> PhishingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_phishings(
        self,
        phishing_type: PhishingType | None = None,
        campaign_indicator: CampaignIndicator | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PhishingRecord]:
        results = list(self._records)
        if phishing_type is not None:
            results = [r for r in results if r.phishing_type == phishing_type]
        if campaign_indicator is not None:
            results = [r for r in results if r.campaign_indicator == campaign_indicator]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        phishing_id: str,
        phishing_type: PhishingType = PhishingType.SPEAR_PHISHING,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PhishingAnalysis:
        analysis = PhishingAnalysis(
            phishing_id=phishing_id,
            phishing_type=phishing_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "phishing_campaign_detector.analysis_added",
            phishing_id=phishing_id,
            phishing_type=phishing_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        """Group by phishing_type; return count and avg detection_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.phishing_type.value
            type_data.setdefault(key, []).append(r.detection_score)
        result: dict[str, Any] = {}
        for ptype, scores in type_data.items():
            result[ptype] = {
                "count": len(scores),
                "avg_detection_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_detection_gaps(self) -> list[dict[str, Any]]:
        """Return records where detection_score < detection_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.detection_score < self._detection_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "phishing_id": r.phishing_id,
                        "phishing_type": r.phishing_type.value,
                        "detection_score": r.detection_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["detection_score"])

    def rank_by_detection(self) -> list[dict[str, Any]]:
        """Group by service, avg detection_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.detection_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_detection_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_detection_score"])
        return results

    def detect_detection_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> PhishingCampaignReport:
        by_type: dict[str, int] = {}
        by_indicator: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.phishing_type.value] = by_type.get(r.phishing_type.value, 0) + 1
            by_indicator[r.campaign_indicator.value] = (
                by_indicator.get(r.campaign_indicator.value, 0) + 1
            )
            by_status[r.campaign_status.value] = by_status.get(r.campaign_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.detection_score < self._detection_threshold)
        scores = [r.detection_score for r in self._records]
        avg_detection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_detection_gaps()
        top_gaps = [o["phishing_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} phishing record(s) below detection threshold "
                f"({self._detection_threshold})"
            )
        if self._records and avg_detection_score < self._detection_threshold:
            recs.append(
                f"Avg detection score {avg_detection_score} below threshold "
                f"({self._detection_threshold})"
            )
        if not recs:
            recs.append("Phishing campaign detection is healthy")
        return PhishingCampaignReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_detection_score=avg_detection_score,
            by_type=by_type,
            by_indicator=by_indicator,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("phishing_campaign_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.phishing_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_threshold": self._detection_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
