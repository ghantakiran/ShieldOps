"""Runbook Execution Tracker — track runbook execution results, phases, and trends."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ExecutionResult(StrEnum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    ABORTED = "aborted"
    TIMEOUT = "timeout"


class ExecutionMode(StrEnum):
    MANUAL = "manual"
    AUTOMATED = "automated"
    HYBRID = "hybrid"
    SCHEDULED = "scheduled"
    TRIGGERED = "triggered"


class ExecutionPhase(StrEnum):
    PREPARATION = "preparation"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    CLEANUP = "cleanup"
    ROLLBACK = "rollback"


# --- Models ---


class ExecutionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    result: ExecutionResult = ExecutionResult.SUCCESS
    mode: ExecutionMode = ExecutionMode.MANUAL
    duration_minutes: float = 0.0
    team: str = ""
    service: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ExecutionStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = ""
    phase: ExecutionPhase = ExecutionPhase.EXECUTION
    step_name: str = ""
    duration_minutes: float = 0.0
    success: bool = True
    created_at: float = Field(default_factory=time.time)


class RunbookExecutionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_steps: int = 0
    success_rate_pct: float = 0.0
    avg_duration_minutes: float = 0.0
    by_result: dict[str, int] = Field(default_factory=dict)
    by_mode: dict[str, int] = Field(default_factory=dict)
    failed_runbooks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RunbookExecutionTracker:
    """Track runbook executions, success rates, durations, and failure patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        min_success_rate_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_success_rate_pct = min_success_rate_pct
        self._records: list[ExecutionRecord] = []
        self._steps: list[ExecutionStep] = []
        logger.info(
            "runbook_exec_tracker.initialized",
            max_records=max_records,
            min_success_rate_pct=min_success_rate_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_execution(
        self,
        runbook_id: str,
        result: ExecutionResult = ExecutionResult.SUCCESS,
        mode: ExecutionMode = ExecutionMode.MANUAL,
        duration_minutes: float = 0.0,
        team: str = "",
        service: str = "",
        details: str = "",
    ) -> ExecutionRecord:
        record = ExecutionRecord(
            runbook_id=runbook_id,
            result=result,
            mode=mode,
            duration_minutes=duration_minutes,
            team=team,
            service=service,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "runbook_exec_tracker.execution_recorded",
            record_id=record.id,
            runbook_id=runbook_id,
            result=result.value,
            duration_minutes=duration_minutes,
        )
        return record

    def get_execution(self, record_id: str) -> ExecutionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_executions(
        self,
        result: ExecutionResult | None = None,
        mode: ExecutionMode | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ExecutionRecord]:
        results = list(self._records)
        if result is not None:
            results = [r for r in results if r.result == result]
        if mode is not None:
            results = [r for r in results if r.mode == mode]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_step(
        self,
        execution_id: str,
        phase: ExecutionPhase = ExecutionPhase.EXECUTION,
        step_name: str = "",
        duration_minutes: float = 0.0,
        success: bool = True,
    ) -> ExecutionStep:
        step = ExecutionStep(
            execution_id=execution_id,
            phase=phase,
            step_name=step_name,
            duration_minutes=duration_minutes,
            success=success,
        )
        self._steps.append(step)
        if len(self._steps) > self._max_records:
            self._steps = self._steps[-self._max_records :]
        logger.info(
            "runbook_exec_tracker.step_added",
            step_id=step.id,
            execution_id=execution_id,
            phase=phase.value,
            success=success,
        )
        return step

    # -- domain operations -----------------------------------------------

    def analyze_execution_success(self) -> list[dict[str, Any]]:
        """Group by runbook_id, compute success rate and avg duration."""
        rb_map: dict[str, dict[str, Any]] = {}
        for r in self._records:
            entry = rb_map.setdefault(
                r.runbook_id,
                {"runbook_id": r.runbook_id, "total": 0, "success": 0, "durations": []},
            )
            entry["total"] += 1
            if r.result == ExecutionResult.SUCCESS:
                entry["success"] += 1
            entry["durations"].append(r.duration_minutes)
        results: list[dict[str, Any]] = []
        for rb_id, data in rb_map.items():
            rate = round((data["success"] / data["total"]) * 100, 2)
            avg_dur = round(sum(data["durations"]) / len(data["durations"]), 2)
            results.append(
                {
                    "runbook_id": rb_id,
                    "total": data["total"],
                    "success_rate_pct": rate,
                    "avg_duration_minutes": avg_dur,
                }
            )
        results.sort(key=lambda x: x["success_rate_pct"], reverse=True)
        return results

    def identify_failing_runbooks(self) -> list[dict[str, Any]]:
        """Find runbooks with success rate below min_success_rate_pct."""
        analysis = self.analyze_execution_success()
        results = [
            item for item in analysis if item["success_rate_pct"] < self._min_success_rate_pct
        ]
        results.sort(key=lambda x: x["success_rate_pct"])
        return results

    def rank_by_duration(self) -> list[dict[str, Any]]:
        """Group by team, avg duration_minutes, sort descending."""
        team_durations: dict[str, list[float]] = {}
        for r in self._records:
            team_durations.setdefault(r.team, []).append(r.duration_minutes)
        results: list[dict[str, Any]] = []
        for team, durations in team_durations.items():
            avg = round(sum(durations) / len(durations), 2)
            results.append(
                {"team": team, "avg_duration_minutes": avg, "execution_count": len(durations)}
            )
        results.sort(key=lambda x: x["avg_duration_minutes"], reverse=True)
        return results

    def detect_execution_trends(self) -> list[dict[str, Any]]:
        """Split-half on duration_minutes; flag runbooks with delta > 5.0."""
        if len(self._records) < 2:
            return []
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]

        def avg_duration(recs: list[ExecutionRecord], rb_id: str) -> float:
            subset = [r.duration_minutes for r in recs if r.runbook_id == rb_id]
            return sum(subset) / len(subset) if subset else 0.0

        runbooks = {r.runbook_id for r in self._records}
        results: list[dict[str, Any]] = []
        for rb_id in runbooks:
            early = avg_duration(first_half, rb_id)
            late = avg_duration(second_half, rb_id)
            delta = round(late - early, 2)
            if abs(delta) > 5.0:
                results.append(
                    {
                        "runbook_id": rb_id,
                        "early_avg": round(early, 2),
                        "late_avg": round(late, 2),
                        "delta": delta,
                        "trend": "slower" if delta > 0 else "faster",
                    }
                )
        results.sort(key=lambda x: abs(x["delta"]), reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> RunbookExecutionReport:
        by_result: dict[str, int] = {}
        by_mode: dict[str, int] = {}
        for r in self._records:
            by_result[r.result.value] = by_result.get(r.result.value, 0) + 1
            by_mode[r.mode.value] = by_mode.get(r.mode.value, 0) + 1
        success_count = sum(1 for r in self._records if r.result == ExecutionResult.SUCCESS)
        rate = round((success_count / len(self._records)) * 100, 2) if self._records else 0.0
        avg_dur = (
            round(sum(r.duration_minutes for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        failing = [item["runbook_id"] for item in self.identify_failing_runbooks()]
        recs: list[str] = []
        if failing:
            recs.append(f"{len(failing)} runbook(s) below success rate threshold")
        if rate < self._min_success_rate_pct and self._records:
            recs.append(f"Overall success rate {rate}% below minimum {self._min_success_rate_pct}%")
        if not recs:
            recs.append("All runbook executions within acceptable success thresholds")
        return RunbookExecutionReport(
            total_records=len(self._records),
            total_steps=len(self._steps),
            success_rate_pct=rate,
            avg_duration_minutes=avg_dur,
            by_result=by_result,
            by_mode=by_mode,
            failed_runbooks=failing,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._steps.clear()
        logger.info("runbook_exec_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        result_dist: dict[str, int] = {}
        for r in self._records:
            key = r.result.value
            result_dist[key] = result_dist.get(key, 0) + 1
        return {
            "total_executions": len(self._records),
            "total_steps": len(self._steps),
            "min_success_rate_pct": self._min_success_rate_pct,
            "result_distribution": result_dist,
            "unique_runbooks": len({r.runbook_id for r in self._records}),
        }
