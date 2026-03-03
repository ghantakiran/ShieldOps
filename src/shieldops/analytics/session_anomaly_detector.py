"""Session Anomaly Detector — detect anomalous session behaviors and patterns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SessionType(StrEnum):
    INTERACTIVE = "interactive"
    API = "api"
    SERVICE = "service"
    VPN = "vpn"
    REMOTE_DESKTOP = "remote_desktop"


class AnomalyType(StrEnum):
    IMPOSSIBLE_TRAVEL = "impossible_travel"
    UNUSUAL_TIME = "unusual_time"
    EXCESSIVE_DURATION = "excessive_duration"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    CONCURRENT_SESSION = "concurrent_session"


class DetectionMethod(StrEnum):
    STATISTICAL = "statistical"
    ML_BASED = "ml_based"
    RULE_BASED = "rule_based"
    BEHAVIORAL = "behavioral"
    HYBRID = "hybrid"


# --- Models ---


class SessionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_name: str = ""
    session_type: SessionType = SessionType.INTERACTIVE
    anomaly_type: AnomalyType = AnomalyType.IMPOSSIBLE_TRAVEL
    detection_method: DetectionMethod = DetectionMethod.STATISTICAL
    anomaly_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SessionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_name: str = ""
    session_type: SessionType = SessionType.INTERACTIVE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SessionAnomalyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_anomaly_score: float = 0.0
    by_session_type: dict[str, int] = Field(default_factory=dict)
    by_anomaly_type: dict[str, int] = Field(default_factory=dict)
    by_detection_method: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SessionAnomalyDetector:
    """Detect anomalous session behaviors, impossible travel, and suspicious patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[SessionRecord] = []
        self._analyses: list[SessionAnalysis] = []
        logger.info(
            "session_anomaly_detector.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_session(
        self,
        session_name: str,
        session_type: SessionType = SessionType.INTERACTIVE,
        anomaly_type: AnomalyType = AnomalyType.IMPOSSIBLE_TRAVEL,
        detection_method: DetectionMethod = DetectionMethod.STATISTICAL,
        anomaly_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SessionRecord:
        record = SessionRecord(
            session_name=session_name,
            session_type=session_type,
            anomaly_type=anomaly_type,
            detection_method=detection_method,
            anomaly_score=anomaly_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "session_anomaly_detector.session_recorded",
            record_id=record.id,
            session_name=session_name,
            session_type=session_type.value,
            anomaly_type=anomaly_type.value,
        )
        return record

    def get_record(self, record_id: str) -> SessionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        session_type: SessionType | None = None,
        anomaly_type: AnomalyType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SessionRecord]:
        results = list(self._records)
        if session_type is not None:
            results = [r for r in results if r.session_type == session_type]
        if anomaly_type is not None:
            results = [r for r in results if r.anomaly_type == anomaly_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        session_name: str,
        session_type: SessionType = SessionType.INTERACTIVE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SessionAnalysis:
        analysis = SessionAnalysis(
            session_name=session_name,
            session_type=session_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "session_anomaly_detector.analysis_added",
            session_name=session_name,
            session_type=session_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by session_type; return count and avg anomaly_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.session_type.value
            type_data.setdefault(key, []).append(r.anomaly_score)
        result: dict[str, Any] = {}
        for stype, scores in type_data.items():
            result[stype] = {
                "count": len(scores),
                "avg_anomaly_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where anomaly_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.anomaly_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "session_name": r.session_name,
                        "session_type": r.session_type.value,
                        "anomaly_score": r.anomaly_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["anomaly_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg anomaly_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.anomaly_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_anomaly_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_anomaly_score"])
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

    def generate_report(self) -> SessionAnomalyReport:
        by_session_type: dict[str, int] = {}
        by_anomaly_type: dict[str, int] = {}
        by_detection_method: dict[str, int] = {}
        for r in self._records:
            by_session_type[r.session_type.value] = by_session_type.get(r.session_type.value, 0) + 1
            by_anomaly_type[r.anomaly_type.value] = by_anomaly_type.get(r.anomaly_type.value, 0) + 1
            by_detection_method[r.detection_method.value] = (
                by_detection_method.get(r.detection_method.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.anomaly_score < self._threshold)
        scores = [r.anomaly_score for r in self._records]
        avg_anomaly_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["session_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} session(s) below anomaly threshold ({self._threshold})")
        if self._records and avg_anomaly_score < self._threshold:
            recs.append(
                f"Avg anomaly score {avg_anomaly_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Session anomaly detection is healthy")
        return SessionAnomalyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_anomaly_score=avg_anomaly_score,
            by_session_type=by_session_type,
            by_anomaly_type=by_anomaly_type,
            by_detection_method=by_detection_method,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("session_anomaly_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        session_type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.session_type.value
            session_type_dist[key] = session_type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "session_type_distribution": session_type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
