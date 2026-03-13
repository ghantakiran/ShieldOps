"""Incident Communication Effectiveness Engine — compute communication
scores, detect gaps, rank incidents by comms quality."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CommunicationChannel(StrEnum):
    SLACK = "slack"
    EMAIL = "email"
    PAGERDUTY = "pagerduty"
    STATUSPAGE = "statuspage"


class CommunicationQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class StakeholderType(StrEnum):
    ENGINEERING = "engineering"
    MANAGEMENT = "management"
    CUSTOMER = "customer"
    EXTERNAL = "external"


# --- Models ---


class CommunicationEffectivenessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    channel: CommunicationChannel = CommunicationChannel.SLACK
    quality: CommunicationQuality = CommunicationQuality.GOOD
    stakeholder_type: StakeholderType = StakeholderType.ENGINEERING
    response_time_seconds: float = 0.0
    update_count: int = 0
    comms_score: float = 0.0
    service: str = ""
    team: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CommunicationEffectivenessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    channel: CommunicationChannel = CommunicationChannel.SLACK
    avg_score: float = 0.0
    has_gaps: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CommunicationEffectivenessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_comms_score: float = 0.0
    by_channel: dict[str, int] = Field(default_factory=dict)
    by_quality: dict[str, int] = Field(default_factory=dict)
    by_stakeholder: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentCommunicationEffectivenessEngine:
    """Compute communication scores, detect communication gaps,
    rank incidents by comms quality."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CommunicationEffectivenessRecord] = []
        self._analyses: dict[str, CommunicationEffectivenessAnalysis] = {}
        logger.info(
            "incident_communication_effectiveness_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        incident_id: str = "",
        channel: CommunicationChannel = CommunicationChannel.SLACK,
        quality: CommunicationQuality = CommunicationQuality.GOOD,
        stakeholder_type: StakeholderType = StakeholderType.ENGINEERING,
        response_time_seconds: float = 0.0,
        update_count: int = 0,
        comms_score: float = 0.0,
        service: str = "",
        team: str = "",
        description: str = "",
    ) -> CommunicationEffectivenessRecord:
        record = CommunicationEffectivenessRecord(
            incident_id=incident_id,
            channel=channel,
            quality=quality,
            stakeholder_type=stakeholder_type,
            response_time_seconds=response_time_seconds,
            update_count=update_count,
            comms_score=comms_score,
            service=service,
            team=team,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_communication_effectiveness.record_added",
            record_id=record.id,
            incident_id=incident_id,
        )
        return record

    def process(self, key: str) -> CommunicationEffectivenessAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        related = [r for r in self._records if r.incident_id == rec.incident_id]
        avg_score = round(sum(r.comms_score for r in related) / len(related), 2) if related else 0.0
        has_gaps = rec.quality in (CommunicationQuality.FAIR, CommunicationQuality.POOR)
        analysis = CommunicationEffectivenessAnalysis(
            incident_id=rec.incident_id,
            channel=rec.channel,
            avg_score=avg_score,
            has_gaps=has_gaps,
            description=f"Incident {rec.incident_id} comms score {avg_score}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CommunicationEffectivenessReport:
        by_ch: dict[str, int] = {}
        by_qu: dict[str, int] = {}
        by_st: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            by_ch[r.channel.value] = by_ch.get(r.channel.value, 0) + 1
            by_qu[r.quality.value] = by_qu.get(r.quality.value, 0) + 1
            by_st[r.stakeholder_type.value] = by_st.get(r.stakeholder_type.value, 0) + 1
            scores.append(r.comms_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        recs: list[str] = []
        poor = by_qu.get("poor", 0) + by_qu.get("fair", 0)
        if poor > 0:
            recs.append(f"{poor} incidents with poor/fair communication quality")
        if not recs:
            recs.append("Communication effectiveness within acceptable levels")
        return CommunicationEffectivenessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_comms_score=avg,
            by_channel=by_ch,
            by_quality=by_qu,
            by_stakeholder=by_st,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        channel_dist: dict[str, int] = {}
        for r in self._records:
            k = r.channel.value
            channel_dist[k] = channel_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "channel_distribution": channel_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("incident_communication_effectiveness_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_communication_scores(self) -> list[dict[str, Any]]:
        """Compute communication scores per incident."""
        incident_data: dict[str, list[float]] = {}
        for r in self._records:
            incident_data.setdefault(r.incident_id, []).append(r.comms_score)
        results: list[dict[str, Any]] = []
        for iid, scores in incident_data.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "incident_id": iid,
                    "avg_comms_score": avg,
                    "update_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_comms_score"], reverse=True)
        return results

    def detect_communication_gaps(self) -> list[dict[str, Any]]:
        """Detect incidents with communication gaps."""
        incident_channels: dict[str, set[str]] = {}
        incident_quality: dict[str, list[str]] = {}
        for r in self._records:
            incident_channels.setdefault(r.incident_id, set()).add(r.channel.value)
            incident_quality.setdefault(r.incident_id, []).append(r.quality.value)
        all_channels = {c.value for c in CommunicationChannel}
        results: list[dict[str, Any]] = []
        for iid, channels in incident_channels.items():
            missing = all_channels - channels
            poor_count = sum(1 for q in incident_quality.get(iid, []) if q in ("poor", "fair"))
            if missing or poor_count > 0:
                results.append(
                    {
                        "incident_id": iid,
                        "missing_channels": list(missing),
                        "poor_quality_count": poor_count,
                        "channels_used": len(channels),
                    }
                )
        results.sort(key=lambda x: x["poor_quality_count"], reverse=True)
        return results

    def rank_incidents_by_comms_quality(self) -> list[dict[str, Any]]:
        """Rank incidents by overall communication quality."""
        incident_scores: dict[str, list[float]] = {}
        for r in self._records:
            incident_scores.setdefault(r.incident_id, []).append(r.comms_score)
        results: list[dict[str, Any]] = []
        for iid, scores in incident_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "incident_id": iid,
                    "avg_comms_score": avg,
                    "total_updates": len(scores),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["avg_comms_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
