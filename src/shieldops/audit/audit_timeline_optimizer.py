"""Audit Timeline Optimizer
compute optimal timeline, detect preparation bottlenecks,
rank audit tasks by critical path."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TaskPhase(StrEnum):
    PLANNING = "planning"
    EVIDENCE_COLLECTION = "evidence_collection"
    TESTING = "testing"
    REPORTING = "reporting"


class TimelineStatus(StrEnum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    DELAYED = "delayed"
    COMPLETED = "completed"


class TaskPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class AuditTimelineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    task_phase: TaskPhase = TaskPhase.PLANNING
    timeline_status: TimelineStatus = TimelineStatus.ON_TRACK
    task_priority: TaskPriority = TaskPriority.MEDIUM
    duration_days: float = 0.0
    planned_days: float = 0.0
    slack_days: float = 0.0
    audit_id: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditTimelineAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    task_phase: TaskPhase = TaskPhase.PLANNING
    computed_duration: float = 0.0
    is_bottleneck: bool = False
    critical_path_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditTimelineReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_duration_days: float = 0.0
    by_task_phase: dict[str, int] = Field(default_factory=dict)
    by_timeline_status: dict[str, int] = Field(default_factory=dict)
    by_task_priority: dict[str, int] = Field(default_factory=dict)
    delayed_tasks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditTimelineOptimizer:
    """Compute optimal timeline, detect preparation
    bottlenecks, rank audit tasks by critical path."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AuditTimelineRecord] = []
        self._analyses: dict[str, AuditTimelineAnalysis] = {}
        logger.info(
            "audit_timeline_optimizer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        task_id: str = "",
        task_phase: TaskPhase = TaskPhase.PLANNING,
        timeline_status: TimelineStatus = TimelineStatus.ON_TRACK,
        task_priority: TaskPriority = TaskPriority.MEDIUM,
        duration_days: float = 0.0,
        planned_days: float = 0.0,
        slack_days: float = 0.0,
        audit_id: str = "",
        description: str = "",
    ) -> AuditTimelineRecord:
        record = AuditTimelineRecord(
            task_id=task_id,
            task_phase=task_phase,
            timeline_status=timeline_status,
            task_priority=task_priority,
            duration_days=duration_days,
            planned_days=planned_days,
            slack_days=slack_days,
            audit_id=audit_id,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "audit_timeline_optimizer.record_added",
            record_id=record.id,
            task_id=task_id,
        )
        return record

    def process(self, key: str) -> AuditTimelineAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_bottleneck = rec.duration_days > rec.planned_days and rec.slack_days <= 0
        cp_score = round(rec.duration_days / max(rec.planned_days, 1.0), 2)
        analysis = AuditTimelineAnalysis(
            task_id=rec.task_id,
            task_phase=rec.task_phase,
            computed_duration=round(rec.duration_days, 2),
            is_bottleneck=is_bottleneck,
            critical_path_score=cp_score,
            description=f"Task {rec.task_id} duration {rec.duration_days}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> AuditTimelineReport:
        by_tp: dict[str, int] = {}
        by_ts: dict[str, int] = {}
        by_pr: dict[str, int] = {}
        durations: list[float] = []
        for r in self._records:
            k = r.task_phase.value
            by_tp[k] = by_tp.get(k, 0) + 1
            k2 = r.timeline_status.value
            by_ts[k2] = by_ts.get(k2, 0) + 1
            k3 = r.task_priority.value
            by_pr[k3] = by_pr.get(k3, 0) + 1
            durations.append(r.duration_days)
        avg = round(sum(durations) / len(durations), 2) if durations else 0.0
        delayed = list(
            {
                r.task_id
                for r in self._records
                if r.timeline_status in (TimelineStatus.DELAYED, TimelineStatus.AT_RISK)
            }
        )[:10]
        recs: list[str] = []
        if delayed:
            recs.append(f"{len(delayed)} delayed/at-risk tasks detected")
        if not recs:
            recs.append("All audit tasks on track")
        return AuditTimelineReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_duration_days=avg,
            by_task_phase=by_tp,
            by_timeline_status=by_ts,
            by_task_priority=by_pr,
            delayed_tasks=delayed,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        tp_dist: dict[str, int] = {}
        for r in self._records:
            k = r.task_phase.value
            tp_dist[k] = tp_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "task_phase_distribution": tp_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("audit_timeline_optimizer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_optimal_timeline(
        self,
    ) -> list[dict[str, Any]]:
        """Compute optimal timeline per audit."""
        audit_tasks: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            audit_tasks.setdefault(r.audit_id, []).append(
                {
                    "task_id": r.task_id,
                    "phase": r.task_phase.value,
                    "duration": r.duration_days,
                    "planned": r.planned_days,
                }
            )
        results: list[dict[str, Any]] = []
        for aid, tasks in audit_tasks.items():
            total_duration = sum(t["duration"] for t in tasks)
            total_planned = sum(t["planned"] for t in tasks)
            results.append(
                {
                    "audit_id": aid,
                    "total_duration": round(total_duration, 2),
                    "total_planned": round(total_planned, 2),
                    "task_count": len(tasks),
                    "efficiency": round(total_planned / max(total_duration, 1.0), 2),
                }
            )
        results.sort(key=lambda x: x["efficiency"])
        return results

    def detect_preparation_bottlenecks(
        self,
    ) -> list[dict[str, Any]]:
        """Detect tasks that are preparation bottlenecks."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.duration_days > r.planned_days and r.slack_days <= 0 and r.task_id not in seen:
                seen.add(r.task_id)
                results.append(
                    {
                        "task_id": r.task_id,
                        "task_phase": r.task_phase.value,
                        "duration_days": r.duration_days,
                        "planned_days": r.planned_days,
                        "overrun": round(r.duration_days - r.planned_days, 2),
                    }
                )
        results.sort(key=lambda x: x["overrun"], reverse=True)
        return results

    def rank_audit_tasks_by_critical_path(
        self,
    ) -> list[dict[str, Any]]:
        """Rank tasks by critical path importance."""
        task_scores: dict[str, float] = {}
        task_phases: dict[str, str] = {}
        for r in self._records:
            cp = r.duration_days / max(r.planned_days, 1.0)
            if r.slack_days <= 0:
                cp *= 1.5
            task_scores[r.task_id] = max(task_scores.get(r.task_id, 0.0), cp)
            task_phases[r.task_id] = r.task_phase.value
        results: list[dict[str, Any]] = []
        for tid, score in task_scores.items():
            results.append(
                {
                    "task_id": tid,
                    "task_phase": task_phases[tid],
                    "critical_path_score": round(score, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["critical_path_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
