"""Container Escape Detector — detect container escape attempts and breakout vectors."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EscapeVector(StrEnum):
    PRIVILEGED_CONTAINER = "privileged_container"
    HOST_PID = "host_pid"
    HOST_NETWORK = "host_network"
    VOLUME_MOUNT = "volume_mount"
    KERNEL_EXPLOIT = "kernel_exploit"


class DetectionMethod(StrEnum):
    SYSCALL_MONITORING = "syscall_monitoring"
    BEHAVIORAL = "behavioral"
    POLICY_CHECK = "policy_check"
    RUNTIME_SCAN = "runtime_scan"
    HONEYPOT = "honeypot"


class ThreatLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BENIGN = "benign"


# --- Models ---


class EscapeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    escape_id: str = ""
    escape_vector: EscapeVector = EscapeVector.PRIVILEGED_CONTAINER
    detection_method: DetectionMethod = DetectionMethod.SYSCALL_MONITORING
    threat_level: ThreatLevel = ThreatLevel.CRITICAL
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EscapeAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    escape_id: str = ""
    escape_vector: EscapeVector = EscapeVector.PRIVILEGED_CONTAINER
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ContainerEscapeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_detection_score: float = 0.0
    by_vector: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    by_threat_level: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ContainerEscapeDetector:
    """Detect container escape attempts, breakout vectors, and runtime threats."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._detection_gap_threshold = detection_gap_threshold
        self._records: list[EscapeRecord] = []
        self._analyses: list[EscapeAnalysis] = []
        logger.info(
            "container_escape_detector.initialized",
            max_records=max_records,
            detection_gap_threshold=detection_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_escape(
        self,
        escape_id: str,
        escape_vector: EscapeVector = EscapeVector.PRIVILEGED_CONTAINER,
        detection_method: DetectionMethod = DetectionMethod.SYSCALL_MONITORING,
        threat_level: ThreatLevel = ThreatLevel.CRITICAL,
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EscapeRecord:
        record = EscapeRecord(
            escape_id=escape_id,
            escape_vector=escape_vector,
            detection_method=detection_method,
            threat_level=threat_level,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "container_escape_detector.escape_recorded",
            record_id=record.id,
            escape_id=escape_id,
            escape_vector=escape_vector.value,
            detection_method=detection_method.value,
        )
        return record

    def get_escape(self, record_id: str) -> EscapeRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_escapes(
        self,
        escape_vector: EscapeVector | None = None,
        detection_method: DetectionMethod | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EscapeRecord]:
        results = list(self._records)
        if escape_vector is not None:
            results = [r for r in results if r.escape_vector == escape_vector]
        if detection_method is not None:
            results = [r for r in results if r.detection_method == detection_method]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        escape_id: str,
        escape_vector: EscapeVector = EscapeVector.PRIVILEGED_CONTAINER,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> EscapeAnalysis:
        analysis = EscapeAnalysis(
            escape_id=escape_id,
            escape_vector=escape_vector,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "container_escape_detector.analysis_added",
            escape_id=escape_id,
            escape_vector=escape_vector.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_vector_distribution(self) -> dict[str, Any]:
        """Group by escape_vector; return count and avg detection_score."""
        vector_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.escape_vector.value
            vector_data.setdefault(key, []).append(r.detection_score)
        result: dict[str, Any] = {}
        for vector, scores in vector_data.items():
            result[vector] = {
                "count": len(scores),
                "avg_detection_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_detection_gaps(self) -> list[dict[str, Any]]:
        """Return records where detection_score < detection_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.detection_score < self._detection_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "escape_id": r.escape_id,
                        "escape_vector": r.escape_vector.value,
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

    def generate_report(self) -> ContainerEscapeReport:
        by_vector: dict[str, int] = {}
        by_method: dict[str, int] = {}
        by_threat_level: dict[str, int] = {}
        for r in self._records:
            by_vector[r.escape_vector.value] = by_vector.get(r.escape_vector.value, 0) + 1
            by_method[r.detection_method.value] = by_method.get(r.detection_method.value, 0) + 1
            by_threat_level[r.threat_level.value] = by_threat_level.get(r.threat_level.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.detection_score < self._detection_gap_threshold
        )
        scores = [r.detection_score for r in self._records]
        avg_detection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_detection_gaps()
        top_gaps = [o["escape_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} escape(s) below detection threshold ({self._detection_gap_threshold})"
            )
        if self._records and avg_detection_score < self._detection_gap_threshold:
            recs.append(
                f"Avg detection score {avg_detection_score} below threshold "
                f"({self._detection_gap_threshold})"
            )
        if not recs:
            recs.append("Container escape detection is healthy")
        return ContainerEscapeReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_detection_score=avg_detection_score,
            by_vector=by_vector,
            by_method=by_method,
            by_threat_level=by_threat_level,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("container_escape_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        vector_dist: dict[str, int] = {}
        for r in self._records:
            key = r.escape_vector.value
            vector_dist[key] = vector_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_gap_threshold": self._detection_gap_threshold,
            "vector_distribution": vector_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
