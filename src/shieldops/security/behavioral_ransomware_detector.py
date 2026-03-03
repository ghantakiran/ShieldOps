"""Behavioral Ransomware Detector — detect ransomware via behavioral analysis."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RansomwareBehavior(StrEnum):
    FILE_ENCRYPTION = "file_encryption"
    KEY_EXCHANGE = "key_exchange"
    SHADOW_DELETE = "shadow_delete"
    LATERAL_SPREAD = "lateral_spread"
    RANSOM_NOTE = "ransom_note"


class DetectionStage(StrEnum):
    INITIAL_ACCESS = "initial_access"
    EXECUTION = "execution"
    ENCRYPTION = "encryption"
    EXFILTRATION = "exfiltration"
    RANSOM = "ransom"


class ResponseUrgency(StrEnum):
    IMMEDIATE = "immediate"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MONITORING = "monitoring"


# --- Models ---


class RansomwareRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ransomware_id: str = ""
    ransomware_behavior: RansomwareBehavior = RansomwareBehavior.FILE_ENCRYPTION
    detection_stage: DetectionStage = DetectionStage.INITIAL_ACCESS
    response_urgency: ResponseUrgency = ResponseUrgency.IMMEDIATE
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RansomwareAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ransomware_id: str = ""
    ransomware_behavior: RansomwareBehavior = RansomwareBehavior.FILE_ENCRYPTION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RansomwareDetectionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_detection_score: float = 0.0
    by_behavior: dict[str, int] = Field(default_factory=dict)
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_urgency: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class BehavioralRansomwareDetector:
    """Detect ransomware via behavioral analysis, stage tracking, and response urgency."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._detection_threshold = detection_threshold
        self._records: list[RansomwareRecord] = []
        self._analyses: list[RansomwareAnalysis] = []
        logger.info(
            "behavioral_ransomware_detector.initialized",
            max_records=max_records,
            detection_threshold=detection_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_detection(
        self,
        ransomware_id: str,
        ransomware_behavior: RansomwareBehavior = RansomwareBehavior.FILE_ENCRYPTION,
        detection_stage: DetectionStage = DetectionStage.INITIAL_ACCESS,
        response_urgency: ResponseUrgency = ResponseUrgency.IMMEDIATE,
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RansomwareRecord:
        record = RansomwareRecord(
            ransomware_id=ransomware_id,
            ransomware_behavior=ransomware_behavior,
            detection_stage=detection_stage,
            response_urgency=response_urgency,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "behavioral_ransomware_detector.detection_recorded",
            record_id=record.id,
            ransomware_id=ransomware_id,
            ransomware_behavior=ransomware_behavior.value,
            detection_stage=detection_stage.value,
        )
        return record

    def get_detection(self, record_id: str) -> RansomwareRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_detections(
        self,
        ransomware_behavior: RansomwareBehavior | None = None,
        detection_stage: DetectionStage | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RansomwareRecord]:
        results = list(self._records)
        if ransomware_behavior is not None:
            results = [r for r in results if r.ransomware_behavior == ransomware_behavior]
        if detection_stage is not None:
            results = [r for r in results if r.detection_stage == detection_stage]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        ransomware_id: str,
        ransomware_behavior: RansomwareBehavior = RansomwareBehavior.FILE_ENCRYPTION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RansomwareAnalysis:
        analysis = RansomwareAnalysis(
            ransomware_id=ransomware_id,
            ransomware_behavior=ransomware_behavior,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "behavioral_ransomware_detector.analysis_added",
            ransomware_id=ransomware_id,
            ransomware_behavior=ransomware_behavior.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_behavior_distribution(self) -> dict[str, Any]:
        """Group by ransomware_behavior; return count and avg detection_score."""
        behavior_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.ransomware_behavior.value
            behavior_data.setdefault(key, []).append(r.detection_score)
        result: dict[str, Any] = {}
        for behavior, scores in behavior_data.items():
            result[behavior] = {
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
                        "ransomware_id": r.ransomware_id,
                        "ransomware_behavior": r.ransomware_behavior.value,
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

    def generate_report(self) -> RansomwareDetectionReport:
        by_behavior: dict[str, int] = {}
        by_stage: dict[str, int] = {}
        by_urgency: dict[str, int] = {}
        for r in self._records:
            by_behavior[r.ransomware_behavior.value] = (
                by_behavior.get(r.ransomware_behavior.value, 0) + 1
            )
            by_stage[r.detection_stage.value] = by_stage.get(r.detection_stage.value, 0) + 1
            by_urgency[r.response_urgency.value] = by_urgency.get(r.response_urgency.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.detection_score < self._detection_threshold)
        scores = [r.detection_score for r in self._records]
        avg_detection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_detection_gaps()
        top_gaps = [o["ransomware_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} detection(s) below detection threshold ({self._detection_threshold})"
            )
        if self._records and avg_detection_score < self._detection_threshold:
            recs.append(
                f"Avg detection score {avg_detection_score} below threshold "
                f"({self._detection_threshold})"
            )
        if not recs:
            recs.append("Behavioral ransomware detection is healthy")
        return RansomwareDetectionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_detection_score=avg_detection_score,
            by_behavior=by_behavior,
            by_stage=by_stage,
            by_urgency=by_urgency,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("behavioral_ransomware_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        behavior_dist: dict[str, int] = {}
        for r in self._records:
            key = r.ransomware_behavior.value
            behavior_dist[key] = behavior_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_threshold": self._detection_threshold,
            "behavior_distribution": behavior_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
