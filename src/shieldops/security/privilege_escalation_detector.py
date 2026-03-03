"""Privilege Escalation Detector — detect and analyze privilege escalation attempts."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EscalationType(StrEnum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    LATERAL = "lateral"
    PRIVILEGE_ABUSE = "privilege_abuse"
    TOKEN_MANIPULATION = "token_manipulation"  # noqa: S105


class DetectionSource(StrEnum):
    AUDIT_LOG = "audit_log"
    BEHAVIORAL = "behavioral"
    RULE_BASED = "rule_based"
    ML_BASED = "ml_based"
    HONEYPOT = "honeypot"


class SeverityLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class EscalationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    escalation_id: str = ""
    escalation_type: EscalationType = EscalationType.VERTICAL
    detection_source: DetectionSource = DetectionSource.AUDIT_LOG
    severity_level: SeverityLevel = SeverityLevel.CRITICAL
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EscalationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    escalation_id: str = ""
    escalation_type: EscalationType = EscalationType.VERTICAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PrivilegeEscalationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_detection_score: float = 0.0
    by_escalation_type: dict[str, int] = Field(default_factory=dict)
    by_detection_source: dict[str, int] = Field(default_factory=dict)
    by_severity_level: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PrivilegeEscalationDetector:
    """Detect privilege escalation attempts, analyze patterns, and track detection effectiveness."""

    def __init__(
        self,
        max_records: int = 200000,
        detection_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._detection_gap_threshold = detection_gap_threshold
        self._records: list[EscalationRecord] = []
        self._analyses: list[EscalationAnalysis] = []
        logger.info(
            "privilege_escalation_detector.initialized",
            max_records=max_records,
            detection_gap_threshold=detection_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_escalation(
        self,
        escalation_id: str,
        escalation_type: EscalationType = EscalationType.VERTICAL,
        detection_source: DetectionSource = DetectionSource.AUDIT_LOG,
        severity_level: SeverityLevel = SeverityLevel.CRITICAL,
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EscalationRecord:
        record = EscalationRecord(
            escalation_id=escalation_id,
            escalation_type=escalation_type,
            detection_source=detection_source,
            severity_level=severity_level,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "privilege_escalation_detector.escalation_recorded",
            record_id=record.id,
            escalation_id=escalation_id,
            escalation_type=escalation_type.value,
            detection_source=detection_source.value,
        )
        return record

    def get_escalation(self, record_id: str) -> EscalationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_escalations(
        self,
        escalation_type: EscalationType | None = None,
        detection_source: DetectionSource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EscalationRecord]:
        results = list(self._records)
        if escalation_type is not None:
            results = [r for r in results if r.escalation_type == escalation_type]
        if detection_source is not None:
            results = [r for r in results if r.detection_source == detection_source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        escalation_id: str,
        escalation_type: EscalationType = EscalationType.VERTICAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> EscalationAnalysis:
        analysis = EscalationAnalysis(
            escalation_id=escalation_id,
            escalation_type=escalation_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "privilege_escalation_detector.analysis_added",
            escalation_id=escalation_id,
            escalation_type=escalation_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_escalation_distribution(self) -> dict[str, Any]:
        """Group by escalation_type; return count and avg detection_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.escalation_type.value
            type_data.setdefault(key, []).append(r.detection_score)
        result: dict[str, Any] = {}
        for etype, scores in type_data.items():
            result[etype] = {
                "count": len(scores),
                "avg_detection_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_escalation_gaps(self) -> list[dict[str, Any]]:
        """Return records where detection_score < detection_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.detection_score < self._detection_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "escalation_id": r.escalation_id,
                        "escalation_type": r.escalation_type.value,
                        "detection_score": r.detection_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["detection_score"])

    def rank_by_escalation(self) -> list[dict[str, Any]]:
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

    def detect_escalation_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> PrivilegeEscalationReport:
        by_escalation_type: dict[str, int] = {}
        by_detection_source: dict[str, int] = {}
        by_severity_level: dict[str, int] = {}
        for r in self._records:
            by_escalation_type[r.escalation_type.value] = (
                by_escalation_type.get(r.escalation_type.value, 0) + 1
            )
            by_detection_source[r.detection_source.value] = (
                by_detection_source.get(r.detection_source.value, 0) + 1
            )
            by_severity_level[r.severity_level.value] = (
                by_severity_level.get(r.severity_level.value, 0) + 1
            )
        gap_count = sum(
            1 for r in self._records if r.detection_score < self._detection_gap_threshold
        )
        scores = [r.detection_score for r in self._records]
        avg_detection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_escalation_gaps()
        top_gaps = [o["escalation_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} escalation(s) below detection threshold "
                f"({self._detection_gap_threshold})"
            )
        if self._records and avg_detection_score < self._detection_gap_threshold:
            recs.append(
                f"Avg detection score {avg_detection_score} below threshold "
                f"({self._detection_gap_threshold})"
            )
        if not recs:
            recs.append("Privilege escalation detection is healthy")
        return PrivilegeEscalationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_detection_score=avg_detection_score,
            by_escalation_type=by_escalation_type,
            by_detection_source=by_detection_source,
            by_severity_level=by_severity_level,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("privilege_escalation_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.escalation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "detection_gap_threshold": self._detection_gap_threshold,
            "escalation_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
