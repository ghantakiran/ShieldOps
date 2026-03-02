"""SOC Shift Handoff Engine — manage shift transitions and handoff completeness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HandoffType(StrEnum):
    SHIFT_CHANGE = "shift_change"
    ESCALATION = "escalation"
    TEAM_TRANSFER = "team_transfer"
    ON_CALL_ROTATION = "on_call_rotation"
    EMERGENCY = "emergency"


class HandoffStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    MISSED = "missed"
    DELAYED = "delayed"


class HandoffPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ROUTINE = "routine"


# --- Models ---


class HandoffRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    handoff_name: str = ""
    handoff_type: HandoffType = HandoffType.SHIFT_CHANGE
    handoff_status: HandoffStatus = HandoffStatus.PENDING
    handoff_priority: HandoffPriority = HandoffPriority.MEDIUM
    completeness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class HandoffAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    handoff_name: str = ""
    handoff_type: HandoffType = HandoffType.SHIFT_CHANGE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class HandoffReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SOCShiftHandoffEngine:
    """Manage SOC shift transitions, handoff completeness, and information continuity."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[HandoffRecord] = []
        self._analyses: list[HandoffAnalysis] = []
        logger.info(
            "soc_shift_handoff_engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_handoff(
        self,
        handoff_name: str,
        handoff_type: HandoffType = HandoffType.SHIFT_CHANGE,
        handoff_status: HandoffStatus = HandoffStatus.PENDING,
        handoff_priority: HandoffPriority = HandoffPriority.MEDIUM,
        completeness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> HandoffRecord:
        record = HandoffRecord(
            handoff_name=handoff_name,
            handoff_type=handoff_type,
            handoff_status=handoff_status,
            handoff_priority=handoff_priority,
            completeness_score=completeness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "soc_shift_handoff_engine.handoff_recorded",
            record_id=record.id,
            handoff_name=handoff_name,
            handoff_type=handoff_type.value,
            handoff_status=handoff_status.value,
        )
        return record

    def get_record(self, record_id: str) -> HandoffRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        handoff_type: HandoffType | None = None,
        handoff_status: HandoffStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[HandoffRecord]:
        results = list(self._records)
        if handoff_type is not None:
            results = [r for r in results if r.handoff_type == handoff_type]
        if handoff_status is not None:
            results = [r for r in results if r.handoff_status == handoff_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        handoff_name: str,
        handoff_type: HandoffType = HandoffType.SHIFT_CHANGE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> HandoffAnalysis:
        analysis = HandoffAnalysis(
            handoff_name=handoff_name,
            handoff_type=handoff_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "soc_shift_handoff_engine.analysis_added",
            handoff_name=handoff_name,
            handoff_type=handoff_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by handoff_type; return count and avg completeness_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.handoff_type.value
            type_data.setdefault(key, []).append(r.completeness_score)
        result: dict[str, Any] = {}
        for htype, scores in type_data.items():
            result[htype] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where completeness_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.completeness_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "handoff_name": r.handoff_name,
                        "handoff_type": r.handoff_type.value,
                        "completeness_score": r.completeness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["completeness_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg completeness_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.completeness_score)
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

    def generate_report(self) -> HandoffReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for r in self._records:
            by_type[r.handoff_type.value] = by_type.get(r.handoff_type.value, 0) + 1
            by_status[r.handoff_status.value] = by_status.get(r.handoff_status.value, 0) + 1
            by_priority[r.handoff_priority.value] = by_priority.get(r.handoff_priority.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.completeness_score < self._threshold)
        scores = [r.completeness_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["handoff_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} handoff(s) below completeness threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg completeness score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("SOC shift handoff management is healthy")
        return HandoffReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_type=by_type,
            by_status=by_status,
            by_priority=by_priority,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("soc_shift_handoff_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.handoff_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
