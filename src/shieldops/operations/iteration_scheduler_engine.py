"""Iteration Scheduler Engine

Schedule and manage experiment iterations with
throughput tracking and bottleneck detection.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ScheduleStrategy(StrEnum):
    ROUND_ROBIN = "round_robin"
    PRIORITY = "priority"
    DEADLINE = "deadline"
    ADAPTIVE = "adaptive"


class IterationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TimeConstraint(StrEnum):
    MINUTES_5 = "minutes_5"
    MINUTES_15 = "minutes_15"
    HOUR_1 = "hour_1"
    UNLIMITED = "unlimited"


# --- Models ---


class IterationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy: ScheduleStrategy = ScheduleStrategy.ROUND_ROBIN
    status: IterationStatus = IterationStatus.QUEUED
    constraint: TimeConstraint = TimeConstraint.MINUTES_15
    duration_seconds: float = 0.0
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class IterationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy: ScheduleStrategy = ScheduleStrategy.ROUND_ROBIN
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IterationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    completed_count: int = 0
    avg_duration: float = 0.0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_constraint: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IterationSchedulerEngine:
    """Schedule experiment iterations with throughput
    tracking and bottleneck detection.
    """

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[IterationRecord] = []
        self._analyses: dict[str, IterationAnalysis] = {}
        logger.info(
            "iteration_scheduler_engine.initialized",
            max_records=max_records,
        )

    def record_item(
        self,
        name: str = "",
        strategy: ScheduleStrategy = (ScheduleStrategy.ROUND_ROBIN),
        status: IterationStatus = IterationStatus.QUEUED,
        constraint: TimeConstraint = (TimeConstraint.MINUTES_15),
        duration_seconds: float = 0.0,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> IterationRecord:
        record = IterationRecord(
            name=name,
            strategy=strategy,
            status=status,
            constraint=constraint,
            duration_seconds=duration_seconds,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "iteration_scheduler_engine.item_recorded",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.id == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        rec = matching[0]
        analysis = IterationAnalysis(
            name=rec.name,
            strategy=rec.strategy,
            analysis_score=rec.score,
            description=(f"Iteration {rec.name} duration={rec.duration_seconds}s"),
        )
        self._analyses[key] = analysis
        return {
            "key": key,
            "analysis_id": analysis.id,
            "score": analysis.analysis_score,
        }

    def generate_report(self) -> IterationReport:
        by_strat: dict[str, int] = {}
        by_stat: dict[str, int] = {}
        by_con: dict[str, int] = {}
        completed = 0
        durations: list[float] = []
        for r in self._records:
            s = r.strategy.value
            by_strat[s] = by_strat.get(s, 0) + 1
            st = r.status.value
            by_stat[st] = by_stat.get(st, 0) + 1
            c = r.constraint.value
            by_con[c] = by_con.get(c, 0) + 1
            if r.status == IterationStatus.COMPLETED:
                completed += 1
                durations.append(r.duration_seconds)
        avg_dur = round(sum(durations) / len(durations), 4) if durations else 0.0
        recs: list[str] = []
        cancelled = by_stat.get("cancelled", 0)
        total = len(self._records)
        if total > 0 and cancelled / total > 0.2:
            recs.append("High cancellation rate — review scheduling strategy")
        if not recs:
            recs.append("Iteration scheduling is healthy")
        return IterationReport(
            total_records=total,
            total_analyses=len(self._analyses),
            completed_count=completed,
            avg_duration=avg_dur,
            by_strategy=by_strat,
            by_status=by_stat,
            by_constraint=by_con,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        strat_dist: dict[str, int] = {}
        for r in self._records:
            k = r.strategy.value
            strat_dist[k] = strat_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "strategy_distribution": strat_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("iteration_scheduler_engine.cleared")
        return {"status": "cleared"}

    # --- Domain methods ---

    def schedule_next_iteration(self, service: str) -> dict[str, Any]:
        """Determine next iteration to schedule."""
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return {
                "service": service,
                "status": "no_data",
            }
        queued = [r for r in matching if r.status == IterationStatus.QUEUED]
        if not queued:
            return {
                "service": service,
                "status": "no_queued",
            }
        next_item = queued[0]
        return {
            "service": service,
            "next_iteration": next_item.name,
            "strategy": next_item.strategy.value,
            "constraint": next_item.constraint.value,
        }

    def compute_throughput(self, service: str) -> dict[str, Any]:
        """Compute iteration throughput."""
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return {
                "service": service,
                "status": "no_data",
            }
        completed = [r for r in matching if r.status == IterationStatus.COMPLETED]
        if not completed:
            return {
                "service": service,
                "throughput": 0.0,
            }
        total_dur = sum(r.duration_seconds for r in completed)
        avg_dur = total_dur / len(completed)
        throughput = round(3600.0 / avg_dur, 2) if avg_dur > 0 else 0.0
        return {
            "service": service,
            "throughput_per_hour": throughput,
            "completed_count": len(completed),
            "avg_duration_seconds": round(avg_dur, 2),
        }

    def detect_scheduling_bottlenecks(self, service: str) -> dict[str, Any]:
        """Detect scheduling bottlenecks."""
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return {
                "service": service,
                "status": "no_data",
            }
        queued = len([r for r in matching if r.status == IterationStatus.QUEUED])
        running = len([r for r in matching if r.status == IterationStatus.RUNNING])
        return {
            "service": service,
            "queued_count": queued,
            "running_count": running,
            "bottleneck": queued > running * 3,
        }
