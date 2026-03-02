"""Alert Triage Scorer — automated Tier-1 alert triage scoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AlertPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class TriageDecision(StrEnum):
    ESCALATE = "escalate"
    INVESTIGATE = "investigate"
    SUPPRESS = "suppress"
    AUTO_RESOLVE = "auto_resolve"
    DEFER = "defer"


class AlertCategory(StrEnum):
    SECURITY = "security"
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    COMPLIANCE = "compliance"
    CONFIGURATION = "configuration"


# --- Models ---


class TriageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    alert_priority: AlertPriority = AlertPriority.CRITICAL
    triage_decision: TriageDecision = TriageDecision.ESCALATE
    alert_category: AlertCategory = AlertCategory.SECURITY
    triage_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TriageAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    alert_priority: AlertPriority = AlertPriority.CRITICAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertTriageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_score_count: int = 0
    avg_triage_score: float = 0.0
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_decision: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    top_low_score: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertTriageScorer:
    """Automated Tier-1 alert triage scoring."""

    def __init__(
        self,
        max_records: int = 200000,
        triage_score_threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._triage_score_threshold = triage_score_threshold
        self._records: list[TriageRecord] = []
        self._analyses: list[TriageAnalysis] = []
        logger.info(
            "alert_triage_scorer.initialized",
            max_records=max_records,
            triage_score_threshold=triage_score_threshold,
        )

    def record_triage(
        self,
        alert_name: str,
        alert_priority: AlertPriority = AlertPriority.CRITICAL,
        triage_decision: TriageDecision = TriageDecision.ESCALATE,
        alert_category: AlertCategory = AlertCategory.SECURITY,
        triage_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TriageRecord:
        record = TriageRecord(
            alert_name=alert_name,
            alert_priority=alert_priority,
            triage_decision=triage_decision,
            alert_category=alert_category,
            triage_score=triage_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_triage_scorer.triage_recorded",
            record_id=record.id,
            alert_name=alert_name,
            alert_priority=alert_priority.value,
            triage_decision=triage_decision.value,
        )
        return record

    def get_triage(self, record_id: str) -> TriageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_triages(
        self,
        alert_priority: AlertPriority | None = None,
        triage_decision: TriageDecision | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[TriageRecord]:
        results = list(self._records)
        if alert_priority is not None:
            results = [r for r in results if r.alert_priority == alert_priority]
        if triage_decision is not None:
            results = [r for r in results if r.triage_decision == triage_decision]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        alert_name: str,
        alert_priority: AlertPriority = AlertPriority.CRITICAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> TriageAnalysis:
        analysis = TriageAnalysis(
            alert_name=alert_name,
            alert_priority=alert_priority,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "alert_triage_scorer.analysis_added",
            alert_name=alert_name,
            alert_priority=alert_priority.value,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_triage_distribution(self) -> dict[str, Any]:
        priority_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.alert_priority.value
            priority_data.setdefault(key, []).append(r.triage_score)
        result: dict[str, Any] = {}
        for priority, scores in priority_data.items():
            result[priority] = {
                "count": len(scores),
                "avg_triage_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_score_triages(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.triage_score < self._triage_score_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "alert_name": r.alert_name,
                        "alert_priority": r.alert_priority.value,
                        "triage_score": r.triage_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["triage_score"])

    def rank_by_triage_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.triage_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {"service": svc, "avg_triage_score": round(sum(scores) / len(scores), 2)}
            )
        results.sort(key=lambda x: x["avg_triage_score"])
        return results

    def detect_triage_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> AlertTriageReport:
        by_priority: dict[str, int] = {}
        by_decision: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_priority[r.alert_priority.value] = by_priority.get(r.alert_priority.value, 0) + 1
            by_decision[r.triage_decision.value] = by_decision.get(r.triage_decision.value, 0) + 1
            by_category[r.alert_category.value] = by_category.get(r.alert_category.value, 0) + 1
        low_score_count = sum(
            1 for r in self._records if r.triage_score < self._triage_score_threshold
        )
        scores = [r.triage_score for r in self._records]
        avg_triage_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_score_triages()
        top_low_score = [o["alert_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_score_count > 0:
            recs.append(
                f"{low_score_count} triage(s) below score threshold "
                f"({self._triage_score_threshold})"
            )
        if self._records and avg_triage_score < self._triage_score_threshold:
            recs.append(
                f"Avg triage score {avg_triage_score} below threshold "
                f"({self._triage_score_threshold})"
            )
        if not recs:
            recs.append("Alert triage scoring is healthy")
        return AlertTriageReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_score_count=low_score_count,
            avg_triage_score=avg_triage_score,
            by_priority=by_priority,
            by_decision=by_decision,
            by_category=by_category,
            top_low_score=top_low_score,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("alert_triage_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        priority_dist: dict[str, int] = {}
        for r in self._records:
            key = r.alert_priority.value
            priority_dist[key] = priority_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "triage_score_threshold": self._triage_score_threshold,
            "priority_distribution": priority_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
