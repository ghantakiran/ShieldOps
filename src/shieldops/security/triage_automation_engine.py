"""Triage Automation Engine — automate alert triage decisions with confidence scoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TriageDecision(StrEnum):
    ESCALATE = "escalate"
    INVESTIGATE = "investigate"
    SUPPRESS = "suppress"
    AUTO_RESOLVE = "auto_resolve"
    DEFER = "defer"


class TriageConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"
    MANUAL_REQUIRED = "manual_required"


class TriageCategory(StrEnum):
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    BENIGN = "benign"
    SUSPICIOUS = "suspicious"
    UNKNOWN = "unknown"


# --- Models ---


class TriageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    triage_decision: TriageDecision = TriageDecision.INVESTIGATE
    triage_confidence: TriageConfidence = TriageConfidence.MEDIUM
    triage_category: TriageCategory = TriageCategory.UNKNOWN
    triage_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TriageAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    triage_decision: TriageDecision = TriageDecision.INVESTIGATE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TriageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_decision: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TriageAutomationEngine:
    """Automate alert triage decisions with confidence scoring and category classification."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[TriageRecord] = []
        self._analyses: list[TriageAnalysis] = []
        logger.info(
            "triage_automation_engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_triage(
        self,
        alert_name: str,
        triage_decision: TriageDecision = TriageDecision.INVESTIGATE,
        triage_confidence: TriageConfidence = TriageConfidence.MEDIUM,
        triage_category: TriageCategory = TriageCategory.UNKNOWN,
        triage_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TriageRecord:
        record = TriageRecord(
            alert_name=alert_name,
            triage_decision=triage_decision,
            triage_confidence=triage_confidence,
            triage_category=triage_category,
            triage_score=triage_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "triage_automation_engine.triage_recorded",
            record_id=record.id,
            alert_name=alert_name,
            triage_decision=triage_decision.value,
            triage_confidence=triage_confidence.value,
        )
        return record

    def get_record(self, record_id: str) -> TriageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        triage_decision: TriageDecision | None = None,
        triage_confidence: TriageConfidence | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[TriageRecord]:
        results = list(self._records)
        if triage_decision is not None:
            results = [r for r in results if r.triage_decision == triage_decision]
        if triage_confidence is not None:
            results = [r for r in results if r.triage_confidence == triage_confidence]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        alert_name: str,
        triage_decision: TriageDecision = TriageDecision.INVESTIGATE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> TriageAnalysis:
        analysis = TriageAnalysis(
            alert_name=alert_name,
            triage_decision=triage_decision,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "triage_automation_engine.analysis_added",
            alert_name=alert_name,
            triage_decision=triage_decision.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by triage_decision; return count and avg triage_score."""
        decision_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.triage_decision.value
            decision_data.setdefault(key, []).append(r.triage_score)
        result: dict[str, Any] = {}
        for decision, scores in decision_data.items():
            result[decision] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where triage_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.triage_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "alert_name": r.alert_name,
                        "triage_decision": r.triage_decision.value,
                        "triage_score": r.triage_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["triage_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg triage_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.triage_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
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

    def generate_report(self) -> TriageReport:
        by_decision: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_decision[r.triage_decision.value] = by_decision.get(r.triage_decision.value, 0) + 1
            by_confidence[r.triage_confidence.value] = (
                by_confidence.get(r.triage_confidence.value, 0) + 1
            )
            by_category[r.triage_category.value] = by_category.get(r.triage_category.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.triage_score < self._threshold)
        scores = [r.triage_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["alert_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} triage(s) below score threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg triage score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Triage automation is healthy")
        return TriageReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_decision=by_decision,
            by_confidence=by_confidence,
            by_category=by_category,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("triage_automation_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        decision_dist: dict[str, int] = {}
        for r in self._records:
            key = r.triage_decision.value
            decision_dist[key] = decision_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "decision_distribution": decision_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
