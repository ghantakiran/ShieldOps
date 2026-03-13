"""Recovery Runbook Effectiveness Engine — compute runbook success rate,
detect runbook gaps, rank runbooks by recovery impact."""

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
    PARTIAL = "partial"
    FAILURE = "failure"
    SKIPPED = "skipped"


class RunbookType(StrEnum):
    AUTOMATED = "automated"
    SEMI_AUTOMATED = "semi_automated"
    MANUAL = "manual"
    HYBRID = "hybrid"


class EffectivenessLevel(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


# --- Models ---


class RunbookEffectivenessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    runbook_id: str = ""
    runbook_outcome: RunbookOutcome = RunbookOutcome.SUCCESS
    runbook_type: RunbookType = RunbookType.AUTOMATED
    effectiveness_level: EffectivenessLevel = EffectivenessLevel.GOOD
    recovery_time_seconds: float = 0.0
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RunbookEffectivenessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    runbook_id: str = ""
    success_rate: float = 0.0
    has_gaps: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RunbookEffectivenessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_effectiveness: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RecoveryRunbookEffectivenessEngine:
    """Compute runbook success rate, detect runbook gaps,
    rank runbooks by recovery impact."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RunbookEffectivenessRecord] = []
        self._analyses: dict[str, RunbookEffectivenessAnalysis] = {}
        logger.info(
            "recovery_runbook_effectiveness_engine.init",
            max_records=max_records,
        )

    def record_item(
        self,
        name: str = "",
        runbook_id: str = "",
        runbook_outcome: RunbookOutcome = RunbookOutcome.SUCCESS,
        runbook_type: RunbookType = RunbookType.AUTOMATED,
        effectiveness_level: EffectivenessLevel = EffectivenessLevel.GOOD,
        recovery_time_seconds: float = 0.0,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RunbookEffectivenessRecord:
        record = RunbookEffectivenessRecord(
            name=name,
            runbook_id=runbook_id,
            runbook_outcome=runbook_outcome,
            runbook_type=runbook_type,
            effectiveness_level=effectiveness_level,
            recovery_time_seconds=recovery_time_seconds,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "recovery_runbook_effectiveness.record_added",
            record_id=record.id,
            runbook_id=runbook_id,
        )
        return record

    def process(self, key: str) -> RunbookEffectivenessAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        related = [r for r in self._records if r.runbook_id == rec.runbook_id]
        successes = sum(1 for r in related if r.runbook_outcome == RunbookOutcome.SUCCESS)
        rate = round(successes / len(related), 2) if related else 0.0
        has_gaps = rate < 0.8
        analysis = RunbookEffectivenessAnalysis(
            name=rec.name,
            runbook_id=rec.runbook_id,
            success_rate=rate,
            has_gaps=has_gaps,
            description=f"Runbook {rec.runbook_id} success rate {rate}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> RunbookEffectivenessReport:
        by_out: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_eff: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            by_out[r.runbook_outcome.value] = by_out.get(r.runbook_outcome.value, 0) + 1
            by_type[r.runbook_type.value] = by_type.get(r.runbook_type.value, 0) + 1
            by_eff[r.effectiveness_level.value] = by_eff.get(r.effectiveness_level.value, 0) + 1
            scores.append(r.score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        gaps: list[str] = []
        failures = by_out.get("failure", 0)
        if failures > 0:
            gaps.append(f"{failures} runbook failures detected")
        recs: list[str] = []
        if gaps:
            recs.extend(gaps)
        if not recs:
            recs.append("All runbooks performing within acceptable parameters")
        return RunbookEffectivenessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg,
            by_outcome=by_out,
            by_type=by_type,
            by_effectiveness=by_eff,
            top_gaps=gaps,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        outcome_dist: dict[str, int] = {}
        for r in self._records:
            k = r.runbook_outcome.value
            outcome_dist[k] = outcome_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "outcome_distribution": outcome_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("recovery_runbook_effectiveness_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_runbook_success_rate(self) -> list[dict[str, Any]]:
        """Compute success rate per runbook."""
        runbook_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            k = r.runbook_id
            if k not in runbook_data:
                runbook_data[k] = {"success": 0, "total": 0}
            runbook_data[k]["total"] += 1
            if r.runbook_outcome == RunbookOutcome.SUCCESS:
                runbook_data[k]["success"] += 1
        results: list[dict[str, Any]] = []
        for rid, data in runbook_data.items():
            rate = round(data["success"] / data["total"], 2) if data["total"] > 0 else 0.0
            results.append(
                {
                    "runbook_id": rid,
                    "success_rate": rate,
                    "success_count": data["success"],
                    "total_executions": data["total"],
                }
            )
        results.sort(key=lambda x: x["success_rate"], reverse=True)
        return results

    def detect_runbook_gaps(self) -> list[dict[str, Any]]:
        """Detect runbooks with high failure rates."""
        runbook_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            k = r.runbook_id
            if k not in runbook_data:
                runbook_data[k] = {"failures": 0, "total": 0}
            runbook_data[k]["total"] += 1
            if r.runbook_outcome in (RunbookOutcome.FAILURE, RunbookOutcome.PARTIAL):
                runbook_data[k]["failures"] += 1
        results: list[dict[str, Any]] = []
        for rid, data in runbook_data.items():
            failure_rate = round(data["failures"] / data["total"], 2) if data["total"] > 0 else 0.0
            if failure_rate > 0.2:
                results.append(
                    {
                        "runbook_id": rid,
                        "failure_rate": failure_rate,
                        "failure_count": data["failures"],
                        "total_executions": data["total"],
                    }
                )
        results.sort(key=lambda x: x["failure_rate"], reverse=True)
        return results

    def rank_runbooks_by_recovery_impact(self) -> list[dict[str, Any]]:
        """Rank runbooks by recovery impact (success * speed)."""
        runbook_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            k = r.runbook_id
            if k not in runbook_data:
                runbook_data[k] = {"scores": [], "times": [], "successes": 0, "total": 0}
            runbook_data[k]["scores"].append(r.score)
            runbook_data[k]["times"].append(r.recovery_time_seconds)
            runbook_data[k]["total"] += 1
            if r.runbook_outcome == RunbookOutcome.SUCCESS:
                runbook_data[k]["successes"] += 1
        results: list[dict[str, Any]] = []
        for rid, data in runbook_data.items():
            avg_score = round(sum(data["scores"]) / len(data["scores"]), 2)
            avg_time = round(sum(data["times"]) / len(data["times"]), 2)
            rate = round(data["successes"] / data["total"], 2) if data["total"] > 0 else 0.0
            impact = round(avg_score * rate, 2)
            results.append(
                {
                    "runbook_id": rid,
                    "impact_score": impact,
                    "success_rate": rate,
                    "avg_recovery_time": avg_time,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["impact_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
