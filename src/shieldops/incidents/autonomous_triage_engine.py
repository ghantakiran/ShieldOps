"""Autonomous Triage Engine — autonomous incident triage and classification."""

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
    INVESTIGATE = "investigate"
    ESCALATE = "escalate"
    AUTO_RESOLVE = "auto_resolve"
    DEFER = "defer"


class UrgencyLevel(StrEnum):
    IMMEDIATE = "immediate"
    URGENT = "urgent"
    STANDARD = "standard"
    LOW = "low"


class TriageConfidence(StrEnum):
    CERTAIN = "certain"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


# --- Models ---


class TriageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    triage_decision: TriageDecision = TriageDecision.INVESTIGATE
    urgency_level: UrgencyLevel = UrgencyLevel.STANDARD
    triage_confidence: TriageConfidence = TriageConfidence.MODERATE
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TriageAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    triage_decision: TriageDecision = TriageDecision.INVESTIGATE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AutonomousTriageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_triage_decision: dict[str, int] = Field(default_factory=dict)
    by_urgency_level: dict[str, int] = Field(default_factory=dict)
    by_triage_confidence: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutonomousTriageEngine:
    """Autonomous Triage Engine
    for incident triage and classification.
    """

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
            "autonomous_triage_engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        triage_decision: TriageDecision = (TriageDecision.INVESTIGATE),
        urgency_level: UrgencyLevel = (UrgencyLevel.STANDARD),
        triage_confidence: TriageConfidence = (TriageConfidence.MODERATE),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TriageRecord:
        record = TriageRecord(
            name=name,
            triage_decision=triage_decision,
            urgency_level=urgency_level,
            triage_confidence=triage_confidence,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "autonomous_triage_engine.record_added",
            record_id=record.id,
            name=name,
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
        urgency_level: UrgencyLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[TriageRecord]:
        results = list(self._records)
        if triage_decision is not None:
            results = [r for r in results if r.triage_decision == triage_decision]
        if urgency_level is not None:
            results = [r for r in results if r.urgency_level == urgency_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        triage_decision: TriageDecision = (TriageDecision.INVESTIGATE),
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> TriageAnalysis:
        analysis = TriageAnalysis(
            name=name,
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
            "autonomous_triage_engine.analysis_added",
            name=name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------

    def auto_triage_incident(
        self,
    ) -> list[dict[str, Any]]:
        """Auto-triage incidents by urgency and confidence."""
        urgency_weight = {
            "immediate": 4.0,
            "urgent": 3.0,
            "standard": 2.0,
            "low": 1.0,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            weight = urgency_weight.get(r.urgency_level.value, 1.0)
            triage_score = round(r.score * weight / 4.0, 2)
            results.append(
                {
                    "record_id": r.id,
                    "name": r.name,
                    "decision": r.triage_decision.value,
                    "urgency": r.urgency_level.value,
                    "confidence": r.triage_confidence.value,
                    "triage_score": triage_score,
                    "service": r.service,
                }
            )
        results.sort(key=lambda x: x["triage_score"], reverse=True)
        return results

    def compute_triage_accuracy(
        self,
    ) -> dict[str, Any]:
        """Compute accuracy of triage decisions."""
        decision_data: dict[str, list[float]] = {}
        conf_data: dict[str, list[float]] = {}
        for r in self._records:
            decision_data.setdefault(r.triage_decision.value, []).append(r.score)
            conf_data.setdefault(r.triage_confidence.value, []).append(r.score)
        by_decision: dict[str, Any] = {}
        for dec, scores in decision_data.items():
            avg = round(sum(scores) / len(scores), 2)
            by_decision[dec] = {
                "count": len(scores),
                "avg_score": avg,
                "accuracy": round(
                    sum(1 for s in scores if s >= self._threshold) / len(scores) * 100, 2
                ),
            }
        by_confidence: dict[str, Any] = {}
        for conf, scores in conf_data.items():
            by_confidence[conf] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return {
            "by_decision": by_decision,
            "by_confidence": by_confidence,
            "total_triaged": len(self._records),
        }

    def detect_triage_drift(
        self,
    ) -> dict[str, Any]:
        """Detect drift in triage patterns over time."""
        if len(self._records) < 4:
            return {
                "drift_detected": False,
                "reason": "insufficient_data",
            }
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]
        first_scores = [r.score for r in first_half]
        second_scores = [r.score for r in second_half]
        avg_first = round(sum(first_scores) / len(first_scores), 2)
        avg_second = round(sum(second_scores) / len(second_scores), 2)
        delta = round(avg_second - avg_first, 2)
        first_decisions: dict[str, int] = {}
        for r in first_half:
            first_decisions[r.triage_decision.value] = (
                first_decisions.get(r.triage_decision.value, 0) + 1
            )
        second_decisions: dict[str, int] = {}
        for r in second_half:
            second_decisions[r.triage_decision.value] = (
                second_decisions.get(r.triage_decision.value, 0) + 1
            )
        return {
            "drift_detected": abs(delta) > 10,
            "score_delta": delta,
            "avg_first_half": avg_first,
            "avg_second_half": avg_second,
            "first_half_decisions": first_decisions,
            "second_half_decisions": second_decisions,
        }

    # -- report / stats -----------------------------------------------

    def generate_report(self) -> AutonomousTriageReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.triage_decision.value] = by_e1.get(r.triage_decision.value, 0) + 1
            by_e2[r.urgency_level.value] = by_e2.get(r.urgency_level.value, 0) + 1
            by_e3[r.triage_confidence.value] = by_e3.get(r.triage_confidence.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gaps = [r.name for r in self._records if r.score < self._threshold][:5]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Autonomous Triage Engine is healthy")
        return AutonomousTriageReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_triage_decision=by_e1,
            by_urgency_level=by_e2,
            by_triage_confidence=by_e3,
            top_gaps=gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("autonomous_triage_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.triage_decision.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "triage_decision_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
