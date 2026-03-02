"""Campaign Attribution Engine — attribute cyber campaigns to threat actors."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AttributionConfidence(StrEnum):
    CONFIRMED = "confirmed"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNATTRIBUTED = "unattributed"


class ThreatActorType(StrEnum):
    APT = "apt"
    CYBERCRIME = "cybercrime"
    HACKTIVISM = "hacktivism"
    INSIDER = "insider"
    UNKNOWN = "unknown"


class CampaignStatus(StrEnum):
    ACTIVE = "active"
    DORMANT = "dormant"
    CONCLUDED = "concluded"
    EMERGING = "emerging"
    HISTORICAL = "historical"


# --- Models ---


class CampaignRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_name: str = ""
    attribution_confidence: AttributionConfidence = AttributionConfidence.UNATTRIBUTED
    threat_actor_type: ThreatActorType = ThreatActorType.UNKNOWN
    campaign_status: CampaignStatus = CampaignStatus.EMERGING
    attribution_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CampaignAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_name: str = ""
    attribution_confidence: AttributionConfidence = AttributionConfidence.UNATTRIBUTED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CampaignAttributionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_attribution_score: float = 0.0
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_actor_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CampaignAttributionEngine:
    """Attribute cyber campaigns to threat actors with confidence scoring."""

    def __init__(self, max_records: int = 200000, quality_threshold: float = 50.0) -> None:
        self._max_records = max_records
        self._quality_threshold = quality_threshold
        self._records: list[CampaignRecord] = []
        self._analyses: list[CampaignAnalysis] = []
        logger.info(
            "campaign_attribution_engine.initialized",
            max_records=max_records,
            quality_threshold=quality_threshold,
        )

    def record_campaign(
        self,
        campaign_name: str,
        attribution_confidence: AttributionConfidence = AttributionConfidence.UNATTRIBUTED,
        threat_actor_type: ThreatActorType = ThreatActorType.UNKNOWN,
        campaign_status: CampaignStatus = CampaignStatus.EMERGING,
        attribution_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CampaignRecord:
        record = CampaignRecord(
            campaign_name=campaign_name,
            attribution_confidence=attribution_confidence,
            threat_actor_type=threat_actor_type,
            campaign_status=campaign_status,
            attribution_score=attribution_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "campaign_attribution_engine.recorded",
            record_id=record.id,
            campaign_name=campaign_name,
            attribution_confidence=attribution_confidence.value,
        )
        return record

    def get_record(self, record_id: str) -> CampaignRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        attribution_confidence: AttributionConfidence | None = None,
        threat_actor_type: ThreatActorType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CampaignRecord]:
        results = list(self._records)
        if attribution_confidence is not None:
            results = [r for r in results if r.attribution_confidence == attribution_confidence]
        if threat_actor_type is not None:
            results = [r for r in results if r.threat_actor_type == threat_actor_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        campaign_name: str,
        attribution_confidence: AttributionConfidence = AttributionConfidence.UNATTRIBUTED,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CampaignAnalysis:
        analysis = CampaignAnalysis(
            campaign_name=campaign_name,
            attribution_confidence=attribution_confidence,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "campaign_attribution_engine.analysis_added",
            campaign_name=campaign_name,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_confidence_distribution(self) -> dict[str, Any]:
        conf_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.attribution_confidence.value
            conf_data.setdefault(key, []).append(r.attribution_score)
        result: dict[str, Any] = {}
        for conf, scores in conf_data.items():
            result[conf] = {
                "count": len(scores),
                "avg_attribution_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.attribution_score < self._quality_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "campaign_name": r.campaign_name,
                        "attribution_confidence": r.attribution_confidence.value,
                        "attribution_score": r.attribution_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["attribution_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.attribution_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_attribution_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_attribution_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> CampaignAttributionReport:
        by_confidence: dict[str, int] = {}
        by_actor_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_confidence[r.attribution_confidence.value] = (
                by_confidence.get(r.attribution_confidence.value, 0) + 1
            )
            by_actor_type[r.threat_actor_type.value] = (
                by_actor_type.get(r.threat_actor_type.value, 0) + 1
            )
            by_status[r.campaign_status.value] = by_status.get(r.campaign_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.attribution_score < self._quality_threshold)
        scores = [r.attribution_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["campaign_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} campaign(s) below quality threshold ({self._quality_threshold})"
            )
        if self._records and avg_score < self._quality_threshold:
            recs.append(
                f"Avg attribution score {avg_score} below threshold ({self._quality_threshold})"
            )
        if not recs:
            recs.append("Campaign attribution is healthy")
        return CampaignAttributionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_attribution_score=avg_score,
            by_confidence=by_confidence,
            by_actor_type=by_actor_type,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("campaign_attribution_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        conf_dist: dict[str, int] = {}
        for r in self._records:
            key = r.attribution_confidence.value
            conf_dist[key] = conf_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_threshold": self._quality_threshold,
            "confidence_distribution": conf_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
