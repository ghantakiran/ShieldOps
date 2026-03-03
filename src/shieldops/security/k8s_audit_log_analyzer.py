"""K8s Audit Log Analyzer — analyze Kubernetes audit logs for security risks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AuditLevel(StrEnum):
    REQUEST_RESPONSE = "request_response"
    REQUEST = "request"
    METADATA = "metadata"
    NONE = "none"
    CUSTOM = "custom"


class EventCategory(StrEnum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RESOURCE_CHANGE = "resource_change"
    EXEC = "exec"
    SECRET_ACCESS = "secret_access"  # noqa: S105


class RiskIndicator(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NORMAL = "normal"


# --- Models ---


class AuditLogRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_id: str = ""
    audit_level: AuditLevel = AuditLevel.REQUEST_RESPONSE
    event_category: EventCategory = EventCategory.AUTHENTICATION
    risk_indicator: RiskIndicator = RiskIndicator.CRITICAL
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditLogAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_id: str = ""
    audit_level: AuditLevel = AuditLevel.REQUEST_RESPONSE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class K8sAuditLogReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    by_level: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class K8sAuditLogAnalyzer:
    """Analyze Kubernetes audit logs for security risks, anomalous access, and compliance."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._risk_gap_threshold = risk_gap_threshold
        self._records: list[AuditLogRecord] = []
        self._analyses: list[AuditLogAnalysis] = []
        logger.info(
            "k8s_audit_log_analyzer.initialized",
            max_records=max_records,
            risk_gap_threshold=risk_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_audit(
        self,
        audit_id: str,
        audit_level: AuditLevel = AuditLevel.REQUEST_RESPONSE,
        event_category: EventCategory = EventCategory.AUTHENTICATION,
        risk_indicator: RiskIndicator = RiskIndicator.CRITICAL,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AuditLogRecord:
        record = AuditLogRecord(
            audit_id=audit_id,
            audit_level=audit_level,
            event_category=event_category,
            risk_indicator=risk_indicator,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "k8s_audit_log_analyzer.audit_recorded",
            record_id=record.id,
            audit_id=audit_id,
            audit_level=audit_level.value,
            event_category=event_category.value,
        )
        return record

    def get_audit(self, record_id: str) -> AuditLogRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_audits(
        self,
        audit_level: AuditLevel | None = None,
        event_category: EventCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AuditLogRecord]:
        results = list(self._records)
        if audit_level is not None:
            results = [r for r in results if r.audit_level == audit_level]
        if event_category is not None:
            results = [r for r in results if r.event_category == event_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        audit_id: str,
        audit_level: AuditLevel = AuditLevel.REQUEST_RESPONSE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AuditLogAnalysis:
        analysis = AuditLogAnalysis(
            audit_id=audit_id,
            audit_level=audit_level,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "k8s_audit_log_analyzer.analysis_added",
            audit_id=audit_id,
            audit_level=audit_level.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_level_distribution(self) -> dict[str, Any]:
        """Group by audit_level; return count and avg risk_score."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.audit_level.value
            level_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for level, scores in level_data.items():
            result[level] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_risk_gaps(self) -> list[dict[str, Any]]:
        """Return records where risk_score < risk_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score < self._risk_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "audit_id": r.audit_id,
                        "audit_level": r.audit_level.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"])

    def rank_by_risk(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"])
        return results

    def detect_risk_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> K8sAuditLogReport:
        by_level: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_level[r.audit_level.value] = by_level.get(r.audit_level.value, 0) + 1
            by_category[r.event_category.value] = by_category.get(r.event_category.value, 0) + 1
            by_risk[r.risk_indicator.value] = by_risk.get(r.risk_indicator.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.risk_score < self._risk_gap_threshold)
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_risk_gaps()
        top_gaps = [o["audit_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} audit(s) below risk threshold ({self._risk_gap_threshold})")
        if self._records and avg_risk_score < self._risk_gap_threshold:
            recs.append(
                f"Avg risk score {avg_risk_score} below threshold ({self._risk_gap_threshold})"
            )
        if not recs:
            recs.append("K8s audit log analysis is healthy")
        return K8sAuditLogReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_risk_score,
            by_level=by_level,
            by_category=by_category,
            by_risk=by_risk,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("k8s_audit_log_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.audit_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_gap_threshold": self._risk_gap_threshold,
            "level_distribution": level_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
