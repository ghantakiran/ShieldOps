"""Cognitive Runbook Engine

Self-evolving runbook system that learns from execution
outcomes and suggests step modifications over time.
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


class RunbookOutcome(StrEnum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


class LearningSignal(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    AMBIGUOUS = "ambiguous"


class EvolutionAction(StrEnum):
    ADD_STEP = "add_step"
    REMOVE_STEP = "remove_step"
    MODIFY_STEP = "modify_step"
    REORDER = "reorder"
    SPLIT = "split"


# --- Models ---


class RunbookRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    step_name: str = ""
    outcome: RunbookOutcome = RunbookOutcome.SUCCESS
    execution_time_sec: float = 0.0
    learning_signal: LearningSignal = LearningSignal.NEUTRAL
    service: str = ""
    operator: str = ""
    created_at: float = Field(default_factory=time.time)


class RunbookAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    effectiveness_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RunbookReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_effectiveness: float = 0.0
    avg_execution_time_sec: float = 0.0
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_signal: dict[str, int] = Field(default_factory=dict)
    stale_runbooks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CognitiveRunbookEngine:
    """Cognitive Runbook Engine

    Self-evolving runbook system that learns from
    execution outcomes and suggests modifications.
    """

    def __init__(
        self,
        max_records: int = 200000,
        effectiveness_threshold: float = 0.7,
    ) -> None:
        self._max_records = max_records
        self._effectiveness_threshold = effectiveness_threshold
        self._records: list[RunbookRecord] = []
        self._analyses: list[RunbookAnalysis] = []
        logger.info(
            "cognitive_runbook_engine.initialized",
            max_records=max_records,
            effectiveness_threshold=effectiveness_threshold,
        )

    def add_record(
        self,
        runbook_id: str,
        step_name: str,
        outcome: RunbookOutcome = RunbookOutcome.SUCCESS,
        execution_time_sec: float = 0.0,
        learning_signal: LearningSignal = (LearningSignal.NEUTRAL),
        service: str = "",
        operator: str = "",
    ) -> RunbookRecord:
        record = RunbookRecord(
            runbook_id=runbook_id,
            step_name=step_name,
            outcome=outcome,
            execution_time_sec=execution_time_sec,
            learning_signal=learning_signal,
            service=service,
            operator=operator,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cognitive_runbook_engine.record_added",
            record_id=record.id,
            runbook_id=runbook_id,
            step_name=step_name,
        )
        return record

    def suggest_modifications(self, runbook_id: str) -> list[dict[str, Any]]:
        matching = [r for r in self._records if r.runbook_id == runbook_id]
        if not matching:
            return []
        suggestions: list[dict[str, Any]] = []
        step_outcomes: dict[str, list[str]] = {}
        for r in matching:
            if r.step_name not in step_outcomes:
                step_outcomes[r.step_name] = []
            step_outcomes[r.step_name].append(r.outcome.value)
        for step, outcomes in step_outcomes.items():
            fail_rate = outcomes.count("failure") / len(outcomes)
            if fail_rate > 0.3:
                suggestions.append(
                    {
                        "step": step,
                        "action": "modify_step",
                        "reason": f"Failure rate {fail_rate:.0%}",
                    }
                )
            skip_rate = outcomes.count("skipped") / len(outcomes)
            if skip_rate > 0.5:
                suggestions.append(
                    {
                        "step": step,
                        "action": "remove_step",
                        "reason": f"Skip rate {skip_rate:.0%}",
                    }
                )
        return suggestions

    def compute_effectiveness(self, runbook_id: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.runbook_id == runbook_id]
        if not matching:
            return {
                "runbook_id": runbook_id,
                "status": "no_data",
            }
        success = sum(1 for r in matching if r.outcome == RunbookOutcome.SUCCESS)
        score = round(success / len(matching), 4)
        times = [r.execution_time_sec for r in matching if r.execution_time_sec > 0]
        avg_time = round(sum(times) / len(times), 2) if times else 0.0
        return {
            "runbook_id": runbook_id,
            "effectiveness_score": score,
            "avg_execution_time_sec": avg_time,
            "total_executions": len(matching),
        }

    def identify_stale_runbooks(self, stale_days: int = 30) -> list[dict[str, Any]]:
        cutoff = time.time() - (stale_days * 86400)
        rb_latest: dict[str, float] = {}
        for r in self._records:
            if r.runbook_id not in rb_latest or r.created_at > rb_latest[r.runbook_id]:
                rb_latest[r.runbook_id] = r.created_at
        stale = []
        for rb_id, latest in rb_latest.items():
            if latest < cutoff:
                days_ago = int((time.time() - latest) / 86400)
                stale.append(
                    {
                        "runbook_id": rb_id,
                        "last_used_days_ago": days_ago,
                    }
                )
        return sorted(
            stale,
            key=lambda x: x["last_used_days_ago"],
            reverse=True,
        )

    def process(self, runbook_id: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.runbook_id == runbook_id]
        if not matching:
            return {
                "runbook_id": runbook_id,
                "status": "no_data",
            }
        success = sum(1 for r in matching if r.outcome == RunbookOutcome.SUCCESS)
        score = round(success / len(matching), 4)
        neg = sum(1 for r in matching if r.learning_signal == LearningSignal.NEGATIVE)
        health = "effective"
        if score < self._effectiveness_threshold:
            health = "needs_improvement"
        if neg > len(matching) * 0.5:
            health = "degraded"
        return {
            "runbook_id": runbook_id,
            "execution_count": len(matching),
            "effectiveness_score": score,
            "negative_signals": neg,
            "health": health,
        }

    def generate_report(self) -> RunbookReport:
        by_outcome: dict[str, int] = {}
        by_signal: dict[str, int] = {}
        for r in self._records:
            ov = r.outcome.value
            by_outcome[ov] = by_outcome.get(ov, 0) + 1
            sv = r.learning_signal.value
            by_signal[sv] = by_signal.get(sv, 0) + 1
        total = len(self._records)
        success = by_outcome.get("success", 0)
        avg_eff = round(success / total, 4) if total else 0.0
        times = [r.execution_time_sec for r in self._records if r.execution_time_sec > 0]
        avg_time = round(sum(times) / len(times), 2) if times else 0.0
        stale = self.identify_stale_runbooks()
        stale_ids = [s["runbook_id"] for s in stale[:10]]
        recs: list[str] = []
        fail_rate = by_outcome.get("failure", 0)
        if total > 0 and fail_rate / total > 0.2:
            recs.append("Over 20% failure rate — review failing steps")
        if stale_ids:
            recs.append(f"{len(stale_ids)} stale runbook(s) — review or retire")
        if not recs:
            recs.append("Runbook effectiveness is nominal")
        return RunbookReport(
            total_records=total,
            total_analyses=len(self._analyses),
            avg_effectiveness=avg_eff,
            avg_execution_time_sec=avg_time,
            by_outcome=by_outcome,
            by_signal=by_signal,
            stale_runbooks=stale_ids,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        outcome_dist: dict[str, int] = {}
        for r in self._records:
            k = r.outcome.value
            outcome_dist[k] = outcome_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "effectiveness_threshold": (self._effectiveness_threshold),
            "outcome_distribution": outcome_dist,
            "unique_runbooks": len({r.runbook_id for r in self._records}),
            "unique_operators": len({r.operator for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("cognitive_runbook_engine.cleared")
        return {"status": "cleared"}
