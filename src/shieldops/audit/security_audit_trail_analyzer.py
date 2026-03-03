"""Security Audit Trail Analyzer — analyze security audit trails."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AuditEventType(StrEnum):
    ACCESS = "access"
    CHANGE = "change"
    POLICY = "policy"
    INCIDENT = "incident"
    COMPLIANCE = "compliance"


class AnalysisMethod(StrEnum):
    PATTERN_MATCHING = "pattern_matching"
    ANOMALY_DETECTION = "anomaly_detection"
    CORRELATION = "correlation"
    TIMELINE = "timeline"
    STATISTICAL = "statistical"


class FindingSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class AuditTrailRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trail_id: str = ""
    audit_event_type: AuditEventType = AuditEventType.ACCESS
    analysis_method: AnalysisMethod = AnalysisMethod.PATTERN_MATCHING
    finding_severity: FindingSeverity = FindingSeverity.CRITICAL
    analysis_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditTrailAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trail_id: str = ""
    audit_event_type: AuditEventType = AuditEventType.ACCESS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SecurityAuditTrailReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_analysis_score: float = 0.0
    by_audit_event_type: dict[str, int] = Field(default_factory=dict)
    by_analysis_method: dict[str, int] = Field(default_factory=dict)
    by_finding_severity: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityAuditTrailAnalyzer:
    """Analyze security audit trails for patterns and anomalies."""

    def __init__(
        self,
        max_records: int = 200000,
        analysis_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._analysis_gap_threshold = analysis_gap_threshold
        self._records: list[AuditTrailRecord] = []
        self._analyses: list[AuditTrailAnalysis] = []
        logger.info(
            "security_audit_trail_analyzer.initialized",
            max_records=max_records,
            analysis_gap_threshold=analysis_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_trail(
        self,
        trail_id: str,
        audit_event_type: AuditEventType = AuditEventType.ACCESS,
        analysis_method: AnalysisMethod = AnalysisMethod.PATTERN_MATCHING,
        finding_severity: FindingSeverity = FindingSeverity.CRITICAL,
        analysis_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AuditTrailRecord:
        record = AuditTrailRecord(
            trail_id=trail_id,
            audit_event_type=audit_event_type,
            analysis_method=analysis_method,
            finding_severity=finding_severity,
            analysis_score=analysis_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_audit_trail_analyzer.recorded",
            record_id=record.id,
            trail_id=trail_id,
            audit_event_type=audit_event_type.value,
            analysis_method=analysis_method.value,
        )
        return record

    def get_trail(self, record_id: str) -> AuditTrailRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_trails(
        self,
        audit_event_type: AuditEventType | None = None,
        analysis_method: AnalysisMethod | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AuditTrailRecord]:
        results = list(self._records)
        if audit_event_type is not None:
            results = [r for r in results if r.audit_event_type == audit_event_type]
        if analysis_method is not None:
            results = [r for r in results if r.analysis_method == analysis_method]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        trail_id: str,
        audit_event_type: AuditEventType = AuditEventType.ACCESS,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AuditTrailAnalysis:
        analysis = AuditTrailAnalysis(
            trail_id=trail_id,
            audit_event_type=audit_event_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_audit_trail_analyzer.analysis_added",
            trail_id=trail_id,
            audit_event_type=audit_event_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_trail_distribution(self) -> dict[str, Any]:
        data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.audit_event_type.value
            data.setdefault(key, []).append(r.analysis_score)
        result: dict[str, Any] = {}
        for k, scores in data.items():
            result[k] = {
                "count": len(scores),
                "avg_analysis_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_trail_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.analysis_score < self._analysis_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "trail_id": r.trail_id,
                        "audit_event_type": r.audit_event_type.value,
                        "analysis_score": r.analysis_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["analysis_score"])

    def rank_by_trail(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.analysis_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_analysis_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_analysis_score"])
        return results

    def detect_trail_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> SecurityAuditTrailReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.audit_event_type.value] = by_e1.get(r.audit_event_type.value, 0) + 1
            by_e2[r.analysis_method.value] = by_e2.get(r.analysis_method.value, 0) + 1
            by_e3[r.finding_severity.value] = by_e3.get(r.finding_severity.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.analysis_score < self._analysis_gap_threshold)
        scores = [r.analysis_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_trail_gaps()
        top_gaps = [o["trail_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} record(s) below threshold ({self._analysis_gap_threshold})")
        if self._records and avg_score < self._analysis_gap_threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._analysis_gap_threshold})")
        if not recs:
            recs.append("SecurityAuditTrailAnalyzer metrics are healthy")
        return SecurityAuditTrailReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_analysis_score=avg_score,
            by_audit_event_type=by_e1,
            by_analysis_method=by_e2,
            by_finding_severity=by_e3,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_audit_trail_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            key = r.audit_event_type.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "analysis_gap_threshold": self._analysis_gap_threshold,
            "audit_event_type_distribution": dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
