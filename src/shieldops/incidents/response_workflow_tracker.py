"""Response Workflow Tracker — track incident response workflow phases and status."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WorkflowPhase(StrEnum):
    DETECTION = "detection"
    CONTAINMENT = "containment"
    ERADICATION = "eradication"
    RECOVERY = "recovery"
    LESSONS_LEARNED = "lessons_learned"


class WorkflowStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


class WorkflowPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ROUTINE = "routine"


# --- Models ---


class WorkflowRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    workflow_phase: WorkflowPhase = WorkflowPhase.DETECTION
    workflow_status: WorkflowStatus = WorkflowStatus.ACTIVE
    workflow_priority: WorkflowPriority = WorkflowPriority.MEDIUM
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkflowAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    workflow_phase: WorkflowPhase = WorkflowPhase.DETECTION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkflowReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ResponseWorkflowTracker:
    """Track incident response workflows — phases and completion."""

    def __init__(
        self,
        max_records: int = 200000,
        score_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._score_threshold = score_threshold
        self._records: list[WorkflowRecord] = []
        self._analyses: list[WorkflowAnalysis] = []
        logger.info(
            "response_workflow_tracker.initialized",
            max_records=max_records,
            score_threshold=score_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_workflow(
        self,
        name: str,
        workflow_phase: WorkflowPhase = WorkflowPhase.DETECTION,
        workflow_status: WorkflowStatus = WorkflowStatus.ACTIVE,
        workflow_priority: WorkflowPriority = WorkflowPriority.MEDIUM,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> WorkflowRecord:
        record = WorkflowRecord(
            name=name,
            workflow_phase=workflow_phase,
            workflow_status=workflow_status,
            workflow_priority=workflow_priority,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "response_workflow_tracker.recorded",
            record_id=record.id,
            name=name,
            workflow_phase=workflow_phase.value,
            workflow_status=workflow_status.value,
        )
        return record

    def get_record(self, record_id: str) -> WorkflowRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        workflow_phase: WorkflowPhase | None = None,
        workflow_status: WorkflowStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowRecord]:
        results = list(self._records)
        if workflow_phase is not None:
            results = [r for r in results if r.workflow_phase == workflow_phase]
        if workflow_status is not None:
            results = [r for r in results if r.workflow_status == workflow_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        workflow_phase: WorkflowPhase = WorkflowPhase.DETECTION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> WorkflowAnalysis:
        analysis = WorkflowAnalysis(
            name=name,
            workflow_phase=workflow_phase,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "response_workflow_tracker.analysis_added",
            name=name,
            workflow_phase=workflow_phase.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_phase_distribution(self) -> dict[str, Any]:
        """Group by workflow_phase; return count and avg score."""
        phase_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.workflow_phase.value
            phase_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in phase_data.items():
            result[k] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where score < score_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._score_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "workflow_phase": r.workflow_phase.value,
                        "score": r.score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
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

    def generate_report(self) -> WorkflowReport:
        by_phase: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for r in self._records:
            by_phase[r.workflow_phase.value] = by_phase.get(r.workflow_phase.value, 0) + 1
            by_status[r.workflow_status.value] = by_status.get(r.workflow_status.value, 0) + 1
            by_priority[r.workflow_priority.value] = (
                by_priority.get(r.workflow_priority.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.score < self._score_threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} workflow(s) below threshold ({self._score_threshold})")
        if self._records and avg_score < self._score_threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._score_threshold})")
        if not recs:
            recs.append("Workflow metrics within healthy range")
        return WorkflowReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_phase=by_phase,
            by_status=by_status,
            by_priority=by_priority,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("response_workflow_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            key = r.workflow_phase.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "score_threshold": self._score_threshold,
            "phase_distribution": dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
