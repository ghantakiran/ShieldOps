"""Data Exfiltration Detector — detect data exfiltration attempts and channels."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ExfilChannel(StrEnum):
    EMAIL = "email"
    CLOUD_STORAGE = "cloud_storage"
    USB = "usb"
    DNS_TUNNEL = "dns_tunnel"
    ENCRYPTED_CHANNEL = "encrypted_channel"


class ExfilIndicator(StrEnum):
    VOLUME_SPIKE = "volume_spike"
    UNUSUAL_DESTINATION = "unusual_destination"
    OFF_HOURS_TRANSFER = "off_hours_transfer"
    SENSITIVE_DATA = "sensitive_data"
    REPEATED_PATTERN = "repeated_pattern"


class DetectionConfidence(StrEnum):
    CONFIRMED = "confirmed"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SUSPECTED = "suspected"


# --- Models ---


class ExfilRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_name: str = ""
    exfil_channel: ExfilChannel = ExfilChannel.EMAIL
    exfil_indicator: ExfilIndicator = ExfilIndicator.VOLUME_SPIKE
    detection_confidence: DetectionConfidence = DetectionConfidence.SUSPECTED
    exfil_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ExfilAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_name: str = ""
    exfil_channel: ExfilChannel = ExfilChannel.EMAIL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DataExfiltrationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_exfil_score: float = 0.0
    by_exfil_channel: dict[str, int] = Field(default_factory=dict)
    by_exfil_indicator: dict[str, int] = Field(default_factory=dict)
    by_detection_confidence: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataExfiltrationDetector:
    """Detect data exfiltration attempts across multiple channels and indicators."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ExfilRecord] = []
        self._analyses: list[ExfilAnalysis] = []
        logger.info(
            "data_exfiltration_detector.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_exfil(
        self,
        entity_name: str,
        exfil_channel: ExfilChannel = ExfilChannel.EMAIL,
        exfil_indicator: ExfilIndicator = ExfilIndicator.VOLUME_SPIKE,
        detection_confidence: DetectionConfidence = DetectionConfidence.SUSPECTED,
        exfil_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ExfilRecord:
        record = ExfilRecord(
            entity_name=entity_name,
            exfil_channel=exfil_channel,
            exfil_indicator=exfil_indicator,
            detection_confidence=detection_confidence,
            exfil_score=exfil_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "data_exfiltration_detector.exfil_recorded",
            record_id=record.id,
            entity_name=entity_name,
            exfil_channel=exfil_channel.value,
            exfil_indicator=exfil_indicator.value,
        )
        return record

    def get_record(self, record_id: str) -> ExfilRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        exfil_channel: ExfilChannel | None = None,
        exfil_indicator: ExfilIndicator | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ExfilRecord]:
        results = list(self._records)
        if exfil_channel is not None:
            results = [r for r in results if r.exfil_channel == exfil_channel]
        if exfil_indicator is not None:
            results = [r for r in results if r.exfil_indicator == exfil_indicator]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        entity_name: str,
        exfil_channel: ExfilChannel = ExfilChannel.EMAIL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ExfilAnalysis:
        analysis = ExfilAnalysis(
            entity_name=entity_name,
            exfil_channel=exfil_channel,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "data_exfiltration_detector.analysis_added",
            entity_name=entity_name,
            exfil_channel=exfil_channel.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by exfil_channel; return count and avg exfil_score."""
        channel_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.exfil_channel.value
            channel_data.setdefault(key, []).append(r.exfil_score)
        result: dict[str, Any] = {}
        for channel, scores in channel_data.items():
            result[channel] = {
                "count": len(scores),
                "avg_exfil_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where exfil_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.exfil_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "entity_name": r.entity_name,
                        "exfil_channel": r.exfil_channel.value,
                        "exfil_score": r.exfil_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["exfil_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg exfil_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.exfil_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_exfil_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_exfil_score"])
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

    def generate_report(self) -> DataExfiltrationReport:
        by_exfil_channel: dict[str, int] = {}
        by_exfil_indicator: dict[str, int] = {}
        by_detection_confidence: dict[str, int] = {}
        for r in self._records:
            by_exfil_channel[r.exfil_channel.value] = (
                by_exfil_channel.get(r.exfil_channel.value, 0) + 1
            )
            by_exfil_indicator[r.exfil_indicator.value] = (
                by_exfil_indicator.get(r.exfil_indicator.value, 0) + 1
            )
            by_detection_confidence[r.detection_confidence.value] = (
                by_detection_confidence.get(r.detection_confidence.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.exfil_score < self._threshold)
        scores = [r.exfil_score for r in self._records]
        avg_exfil_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["entity_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} entity(s) below exfiltration threshold ({self._threshold})")
        if self._records and avg_exfil_score < self._threshold:
            recs.append(f"Avg exfil score {avg_exfil_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Data exfiltration detection is healthy")
        return DataExfiltrationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_exfil_score=avg_exfil_score,
            by_exfil_channel=by_exfil_channel,
            by_exfil_indicator=by_exfil_indicator,
            by_detection_confidence=by_detection_confidence,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("data_exfiltration_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        exfil_channel_dist: dict[str, int] = {}
        for r in self._records:
            key = r.exfil_channel.value
            exfil_channel_dist[key] = exfil_channel_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "exfil_channel_distribution": exfil_channel_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
