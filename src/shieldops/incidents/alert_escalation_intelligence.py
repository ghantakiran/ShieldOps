"""Alert Escalation Intelligence — learn optimal escalation paths from history."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EscalationPath(StrEnum):
    DIRECT = "direct"
    TIERED = "tiered"
    AUTOMATED = "automated"
    HYBRID = "hybrid"
    SKIP_LEVEL = "skip_level"


class EscalationOutcome(StrEnum):
    RESOLVED = "resolved"
    REASSIGNED = "reassigned"
    TIMED_OUT = "timed_out"
    ESCALATED_FURTHER = "escalated_further"
    CLOSED_NO_ACTION = "closed_no_action"


class EscalationSpeed(StrEnum):
    IMMEDIATE = "immediate"
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"
    DELAYED = "delayed"


# --- Models ---


class EscalationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    escalation_name: str = ""
    escalation_path: EscalationPath = EscalationPath.DIRECT
    escalation_outcome: EscalationOutcome = EscalationOutcome.RESOLVED
    escalation_speed: EscalationSpeed = EscalationSpeed.IMMEDIATE
    effectiveness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EscalationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    escalation_name: str = ""
    escalation_path: EscalationPath = EscalationPath.DIRECT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EscalationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_effectiveness_count: int = 0
    avg_effectiveness_score: float = 0.0
    by_path: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_speed: dict[str, int] = Field(default_factory=dict)
    top_low_effectiveness: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertEscalationIntelligence:
    """Learn optimal escalation paths from historical escalation data."""

    def __init__(
        self,
        max_records: int = 200000,
        escalation_effectiveness_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._escalation_effectiveness_threshold = escalation_effectiveness_threshold
        self._records: list[EscalationRecord] = []
        self._analyses: list[EscalationAnalysis] = []
        logger.info(
            "alert_escalation_intelligence.initialized",
            max_records=max_records,
            escalation_effectiveness_threshold=escalation_effectiveness_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_escalation(
        self,
        escalation_name: str,
        escalation_path: EscalationPath = EscalationPath.DIRECT,
        escalation_outcome: EscalationOutcome = EscalationOutcome.RESOLVED,
        escalation_speed: EscalationSpeed = EscalationSpeed.IMMEDIATE,
        effectiveness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EscalationRecord:
        record = EscalationRecord(
            escalation_name=escalation_name,
            escalation_path=escalation_path,
            escalation_outcome=escalation_outcome,
            escalation_speed=escalation_speed,
            effectiveness_score=effectiveness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_escalation_intelligence.escalation_recorded",
            record_id=record.id,
            escalation_name=escalation_name,
            escalation_path=escalation_path.value,
            escalation_outcome=escalation_outcome.value,
        )
        return record

    def get_escalation(self, record_id: str) -> EscalationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_escalations(
        self,
        escalation_path: EscalationPath | None = None,
        escalation_outcome: EscalationOutcome | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EscalationRecord]:
        results = list(self._records)
        if escalation_path is not None:
            results = [r for r in results if r.escalation_path == escalation_path]
        if escalation_outcome is not None:
            results = [r for r in results if r.escalation_outcome == escalation_outcome]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        escalation_name: str,
        escalation_path: EscalationPath = EscalationPath.DIRECT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> EscalationAnalysis:
        analysis = EscalationAnalysis(
            escalation_name=escalation_name,
            escalation_path=escalation_path,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "alert_escalation_intelligence.analysis_added",
            escalation_name=escalation_name,
            escalation_path=escalation_path.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_escalation_distribution(self) -> dict[str, Any]:
        """Group by escalation_path; return count and avg effectiveness_score."""
        src_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.escalation_path.value
            src_data.setdefault(key, []).append(r.effectiveness_score)
        result: dict[str, Any] = {}
        for src, scores in src_data.items():
            result[src] = {
                "count": len(scores),
                "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_effectiveness_escalations(self) -> list[dict[str, Any]]:
        """Return records where effectiveness_score < escalation_effectiveness_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.effectiveness_score < self._escalation_effectiveness_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "escalation_name": r.escalation_name,
                        "escalation_path": r.escalation_path.value,
                        "effectiveness_score": r.effectiveness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["effectiveness_score"])

    def rank_by_effectiveness(self) -> list[dict[str, Any]]:
        """Group by service, avg effectiveness_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.effectiveness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_effectiveness_score"])
        return results

    def detect_escalation_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
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

    def generate_report(self) -> EscalationReport:
        by_path: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        by_speed: dict[str, int] = {}
        for r in self._records:
            by_path[r.escalation_path.value] = by_path.get(r.escalation_path.value, 0) + 1
            by_outcome[r.escalation_outcome.value] = (
                by_outcome.get(r.escalation_outcome.value, 0) + 1
            )
            by_speed[r.escalation_speed.value] = by_speed.get(r.escalation_speed.value, 0) + 1
        low_effectiveness_count = sum(
            1
            for r in self._records
            if r.effectiveness_score < self._escalation_effectiveness_threshold
        )
        scores = [r.effectiveness_score for r in self._records]
        avg_effectiveness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_effectiveness_escalations()
        top_low_effectiveness = [o["escalation_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_effectiveness_count > 0:
            recs.append(
                f"{low_effectiveness_count} escalation(s) below effectiveness threshold "
                f"({self._escalation_effectiveness_threshold})"
            )
        if self._records and avg_effectiveness_score < self._escalation_effectiveness_threshold:
            recs.append(
                f"Avg effectiveness score {avg_effectiveness_score} below threshold "
                f"({self._escalation_effectiveness_threshold})"
            )
        if not recs:
            recs.append("Alert escalation intelligence is healthy")
        return EscalationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_effectiveness_count=low_effectiveness_count,
            avg_effectiveness_score=avg_effectiveness_score,
            by_path=by_path,
            by_outcome=by_outcome,
            by_speed=by_speed,
            top_low_effectiveness=top_low_effectiveness,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("alert_escalation_intelligence.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        path_dist: dict[str, int] = {}
        for r in self._records:
            key = r.escalation_path.value
            path_dist[key] = path_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "escalation_effectiveness_threshold": self._escalation_effectiveness_threshold,
            "path_distribution": path_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
