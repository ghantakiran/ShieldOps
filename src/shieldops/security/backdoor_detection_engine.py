"""Backdoor Detection Engine — detect backdoors via file, network, and behavioral analysis."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BackdoorType(StrEnum):
    WEB_SHELL = "web_shell"
    ROOTKIT = "rootkit"
    RAT = "rat"
    IMPLANT = "implant"
    BOOTKIT = "bootkit"


class DetectionVector(StrEnum):
    FILE_SCAN = "file_scan"
    NETWORK_MONITOR = "network_monitor"
    BEHAVIORAL = "behavioral"
    MEMORY_SCAN = "memory_scan"
    INTEGRITY_CHECK = "integrity_check"


class PersistenceLevel(StrEnum):
    KERNEL = "kernel"
    SERVICE = "service"
    SCHEDULED_TASK = "scheduled_task"
    REGISTRY = "registry"
    FIRMWARE = "firmware"


# --- Models ---


class BackdoorRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    backdoor_id: str = ""
    backdoor_type: BackdoorType = BackdoorType.WEB_SHELL
    detection_vector: DetectionVector = DetectionVector.FILE_SCAN
    persistence_level: PersistenceLevel = PersistenceLevel.KERNEL
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BackdoorAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    backdoor_id: str = ""
    backdoor_type: BackdoorType = BackdoorType.WEB_SHELL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BackdoorDetectionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_detection_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_vector: dict[str, int] = Field(default_factory=dict)
    by_persistence: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class BackdoorDetectionEngine:
    """Detect backdoors via file scanning, network monitoring, and behavioral analysis."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._detection_threshold = detection_threshold
        self._records: list[BackdoorRecord] = []
        self._analyses: list[BackdoorAnalysis] = []
        logger.info(
            "backdoor_detection_engine.initialized",
            max_records=max_records,
            detection_threshold=detection_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_backdoor(
        self,
        backdoor_id: str,
        backdoor_type: BackdoorType = BackdoorType.WEB_SHELL,
        detection_vector: DetectionVector = DetectionVector.FILE_SCAN,
        persistence_level: PersistenceLevel = PersistenceLevel.KERNEL,
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> BackdoorRecord:
        record = BackdoorRecord(
            backdoor_id=backdoor_id,
            backdoor_type=backdoor_type,
            detection_vector=detection_vector,
            persistence_level=persistence_level,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "backdoor_detection_engine.backdoor_recorded",
            record_id=record.id,
            backdoor_id=backdoor_id,
            backdoor_type=backdoor_type.value,
            detection_vector=detection_vector.value,
        )
        return record

    def get_backdoor(self, record_id: str) -> BackdoorRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_backdoors(
        self,
        backdoor_type: BackdoorType | None = None,
        detection_vector: DetectionVector | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BackdoorRecord]:
        results = list(self._records)
        if backdoor_type is not None:
            results = [r for r in results if r.backdoor_type == backdoor_type]
        if detection_vector is not None:
            results = [r for r in results if r.detection_vector == detection_vector]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        backdoor_id: str,
        backdoor_type: BackdoorType = BackdoorType.WEB_SHELL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> BackdoorAnalysis:
        analysis = BackdoorAnalysis(
            backdoor_id=backdoor_id,
            backdoor_type=backdoor_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "backdoor_detection_engine.analysis_added",
            backdoor_id=backdoor_id,
            backdoor_type=backdoor_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        """Group by backdoor_type; return count and avg detection_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.backdoor_type.value
            type_data.setdefault(key, []).append(r.detection_score)
        result: dict[str, Any] = {}
        for btype, scores in type_data.items():
            result[btype] = {
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
                        "backdoor_id": r.backdoor_id,
                        "backdoor_type": r.backdoor_type.value,
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

    def generate_report(self) -> BackdoorDetectionReport:
        by_type: dict[str, int] = {}
        by_vector: dict[str, int] = {}
        by_persistence: dict[str, int] = {}
        for r in self._records:
            by_type[r.backdoor_type.value] = by_type.get(r.backdoor_type.value, 0) + 1
            by_vector[r.detection_vector.value] = by_vector.get(r.detection_vector.value, 0) + 1
            by_persistence[r.persistence_level.value] = (
                by_persistence.get(r.persistence_level.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.detection_score < self._detection_threshold)
        scores = [r.detection_score for r in self._records]
        avg_detection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_detection_gaps()
        top_gaps = [o["backdoor_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} backdoor(s) below detection threshold ({self._detection_threshold})"
            )
        if self._records and avg_detection_score < self._detection_threshold:
            recs.append(
                f"Avg detection score {avg_detection_score} below threshold "
                f"({self._detection_threshold})"
            )
        if not recs:
            recs.append("Backdoor detection is healthy")
        return BackdoorDetectionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_detection_score=avg_detection_score,
            by_type=by_type,
            by_vector=by_vector,
            by_persistence=by_persistence,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("backdoor_detection_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.backdoor_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_threshold": self._detection_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
