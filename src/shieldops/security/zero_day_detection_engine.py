"""Zero-Day Detection Engine — behavioral zero-day detection without signatures."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DetectionType(StrEnum):
    BEHAVIORAL = "behavioral"
    HEURISTIC = "heuristic"
    SANDBOX = "sandbox"
    MEMORY_ANALYSIS = "memory_analysis"
    NETWORK_ANOMALY = "network_anomaly"


class ThreatConfidence(StrEnum):
    CONFIRMED = "confirmed"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCONFIRMED = "unconfirmed"


class ResponseAction(StrEnum):
    QUARANTINE = "quarantine"
    BLOCK = "block"
    ALERT = "alert"
    MONITOR = "monitor"
    ALLOW = "allow"


# --- Models ---


class ZeroDayRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    detection_name: str = ""
    detection_type: DetectionType = DetectionType.BEHAVIORAL
    threat_confidence: ThreatConfidence = ThreatConfidence.CONFIRMED
    response_action: ResponseAction = ResponseAction.QUARANTINE
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ZeroDayAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    detection_name: str = ""
    detection_type: DetectionType = DetectionType.BEHAVIORAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ZeroDayReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_confidence_count: int = 0
    avg_detection_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    top_low_confidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ZeroDayDetectionEngine:
    """Behavioral zero-day detection without relying on known signatures."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_confidence_threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._detection_confidence_threshold = detection_confidence_threshold
        self._records: list[ZeroDayRecord] = []
        self._analyses: list[ZeroDayAnalysis] = []
        logger.info(
            "zero_day_detection_engine.initialized",
            max_records=max_records,
            detection_confidence_threshold=detection_confidence_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_detection(
        self,
        detection_name: str,
        detection_type: DetectionType = DetectionType.BEHAVIORAL,
        threat_confidence: ThreatConfidence = ThreatConfidence.CONFIRMED,
        response_action: ResponseAction = ResponseAction.QUARANTINE,
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ZeroDayRecord:
        record = ZeroDayRecord(
            detection_name=detection_name,
            detection_type=detection_type,
            threat_confidence=threat_confidence,
            response_action=response_action,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "zero_day_detection_engine.detection_recorded",
            record_id=record.id,
            detection_name=detection_name,
            detection_type=detection_type.value,
            threat_confidence=threat_confidence.value,
        )
        return record

    def get_detection(self, record_id: str) -> ZeroDayRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_detections(
        self,
        detection_type: DetectionType | None = None,
        threat_confidence: ThreatConfidence | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ZeroDayRecord]:
        results = list(self._records)
        if detection_type is not None:
            results = [r for r in results if r.detection_type == detection_type]
        if threat_confidence is not None:
            results = [r for r in results if r.threat_confidence == threat_confidence]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        detection_name: str,
        detection_type: DetectionType = DetectionType.BEHAVIORAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ZeroDayAnalysis:
        analysis = ZeroDayAnalysis(
            detection_name=detection_name,
            detection_type=detection_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "zero_day_detection_engine.analysis_added",
            detection_name=detection_name,
            detection_type=detection_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_detection_distribution(self) -> dict[str, Any]:
        """Group by detection_type; return count and avg detection_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.detection_type.value
            type_data.setdefault(key, []).append(r.detection_score)
        result: dict[str, Any] = {}
        for dtype, scores in type_data.items():
            result[dtype] = {
                "count": len(scores),
                "avg_detection_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_confidence_detections(self) -> list[dict[str, Any]]:
        """Return records where detection_score < detection_confidence_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.detection_score < self._detection_confidence_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "detection_name": r.detection_name,
                        "detection_type": r.detection_type.value,
                        "detection_score": r.detection_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["detection_score"])

    def rank_by_detection_score(self) -> list[dict[str, Any]]:
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

    def generate_report(self) -> ZeroDayReport:
        by_type: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_type[r.detection_type.value] = by_type.get(r.detection_type.value, 0) + 1
            by_confidence[r.threat_confidence.value] = (
                by_confidence.get(r.threat_confidence.value, 0) + 1
            )
            by_action[r.response_action.value] = by_action.get(r.response_action.value, 0) + 1
        low_confidence_count = sum(
            1 for r in self._records if r.detection_score < self._detection_confidence_threshold
        )
        scores = [r.detection_score for r in self._records]
        avg_detection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_confidence_detections()
        top_low_confidence = [o["detection_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_confidence_count > 0:
            recs.append(
                f"{low_confidence_count} detection(s) below confidence threshold "
                f"({self._detection_confidence_threshold})"
            )
        if self._records and avg_detection_score < self._detection_confidence_threshold:
            recs.append(
                f"Avg detection score {avg_detection_score} below threshold "
                f"({self._detection_confidence_threshold})"
            )
        if not recs:
            recs.append("Zero-day detection confidence is healthy")
        return ZeroDayReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_confidence_count=low_confidence_count,
            avg_detection_score=avg_detection_score,
            by_type=by_type,
            by_confidence=by_confidence,
            by_action=by_action,
            top_low_confidence=top_low_confidence,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("zero_day_detection_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.detection_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_confidence_threshold": self._detection_confidence_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
