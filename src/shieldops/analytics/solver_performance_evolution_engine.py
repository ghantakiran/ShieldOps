"""Solver Performance Evolution Engine —
tracks SRE agent performance across co-evolution iterations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EvolutionPhase(StrEnum):
    WARMUP = "warmup"
    RAPID_GAIN = "rapid_gain"
    PLATEAU = "plateau"
    CONVERGENCE = "convergence"


class SolverSkillLevel(StrEnum):
    NOVICE = "novice"
    COMPETENT = "competent"
    PROFICIENT = "proficient"
    EXPERT = "expert"


class PerformanceTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    OSCILLATING = "oscillating"


# --- Models ---


class SolverPerformanceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    solver_id: str = ""
    iteration: int = 0
    phase: EvolutionPhase = EvolutionPhase.WARMUP
    skill_level: SolverSkillLevel = SolverSkillLevel.NOVICE
    trend: PerformanceTrend = PerformanceTrend.STABLE
    success_rate: float = 0.0
    reward_score: float = 0.0
    scenario_difficulty: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SolverPerformanceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    solver_id: str = ""
    avg_success_rate: float = 0.0
    current_phase: EvolutionPhase = EvolutionPhase.WARMUP
    skill_level: SolverSkillLevel = SolverSkillLevel.NOVICE
    trend: PerformanceTrend = PerformanceTrend.STABLE
    iteration_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SolverPerformanceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_success_rate: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_skill_level: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    top_solvers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SolverPerformanceEvolutionEngine:
    """Tracks SRE agent (solver) performance across co-evolution iterations."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[SolverPerformanceRecord] = []
        self._analyses: dict[str, SolverPerformanceAnalysis] = {}
        logger.info(
            "solver_performance_evolution_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        solver_id: str = "",
        iteration: int = 0,
        phase: EvolutionPhase = EvolutionPhase.WARMUP,
        skill_level: SolverSkillLevel = SolverSkillLevel.NOVICE,
        trend: PerformanceTrend = PerformanceTrend.STABLE,
        success_rate: float = 0.0,
        reward_score: float = 0.0,
        scenario_difficulty: float = 0.0,
        description: str = "",
    ) -> SolverPerformanceRecord:
        record = SolverPerformanceRecord(
            solver_id=solver_id,
            iteration=iteration,
            phase=phase,
            skill_level=skill_level,
            trend=trend,
            success_rate=success_rate,
            reward_score=reward_score,
            scenario_difficulty=scenario_difficulty,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "solver_performance_evolution.record_added",
            record_id=record.id,
            solver_id=solver_id,
        )
        return record

    def process(self, key: str) -> SolverPerformanceAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        solver_recs = [r for r in self._records if r.solver_id == rec.solver_id]
        rates = [r.success_rate for r in solver_recs]
        avg_rate = round(sum(rates) / len(rates), 2) if rates else 0.0
        analysis = SolverPerformanceAnalysis(
            solver_id=rec.solver_id,
            avg_success_rate=avg_rate,
            current_phase=rec.phase,
            skill_level=rec.skill_level,
            trend=rec.trend,
            iteration_count=len(solver_recs),
            description=f"Solver {rec.solver_id} avg success {avg_rate}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> SolverPerformanceReport:
        by_p: dict[str, int] = {}
        by_sk: dict[str, int] = {}
        by_tr: dict[str, int] = {}
        rates: list[float] = []
        for r in self._records:
            k1 = r.phase.value
            by_p[k1] = by_p.get(k1, 0) + 1
            k2 = r.skill_level.value
            by_sk[k2] = by_sk.get(k2, 0) + 1
            k3 = r.trend.value
            by_tr[k3] = by_tr.get(k3, 0) + 1
            rates.append(r.success_rate)
        avg_rate = round(sum(rates) / len(rates), 2) if rates else 0.0
        solver_totals: dict[str, float] = {}
        for r in self._records:
            solver_totals[r.solver_id] = solver_totals.get(r.solver_id, 0.0) + r.reward_score
        top_solvers = sorted(
            solver_totals,
            key=lambda x: solver_totals[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        declining = by_tr.get("declining", 0)
        if declining > 0:
            recs.append(f"{declining} solvers in declining trend — investigate")
        if not recs:
            recs.append("Solver performance trends are healthy")
        return SolverPerformanceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_success_rate=avg_rate,
            by_phase=by_p,
            by_skill_level=by_sk,
            by_trend=by_tr,
            top_solvers=top_solvers,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            k = r.phase.value
            phase_dist[k] = phase_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "phase_distribution": phase_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("solver_performance_evolution_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_evolution_curve(self, solver_id: str) -> list[dict[str, Any]]:
        """Compute per-iteration evolution curve for a solver."""
        recs = [r for r in self._records if r.solver_id == solver_id]
        recs_sorted = sorted(recs, key=lambda x: x.iteration)
        curve: list[dict[str, Any]] = []
        for r in recs_sorted:
            curve.append(
                {
                    "iteration": r.iteration,
                    "success_rate": r.success_rate,
                    "reward_score": r.reward_score,
                    "phase": r.phase.value,
                    "skill_level": r.skill_level.value,
                }
            )
        return curve

    def detect_skill_plateaus(self) -> list[dict[str, Any]]:
        """Detect solvers that have entered a skill plateau."""
        solver_iters: dict[str, list[SolverPerformanceRecord]] = {}
        for r in self._records:
            solver_iters.setdefault(r.solver_id, []).append(r)
        results: list[dict[str, Any]] = []
        for sid, iters in solver_iters.items():
            if len(iters) < 3:
                continue
            iters_sorted = sorted(iters, key=lambda x: x.iteration)
            recent = iters_sorted[-3:]
            rates = [r.success_rate for r in recent]
            rate_range = max(rates) - min(rates)
            if rate_range < 0.05:
                results.append(
                    {
                        "solver_id": sid,
                        "plateau_rate": round(sum(rates) / len(rates), 2),
                        "rate_variance": round(rate_range, 4),
                        "iterations_checked": len(recent),
                        "is_plateau": True,
                    }
                )
        results.sort(key=lambda x: x["plateau_rate"], reverse=True)
        return results

    def compare_iteration_deltas(self) -> list[dict[str, Any]]:
        """Compare performance deltas between consecutive iterations per solver."""
        solver_iters: dict[str, list[SolverPerformanceRecord]] = {}
        for r in self._records:
            solver_iters.setdefault(r.solver_id, []).append(r)
        results: list[dict[str, Any]] = []
        for sid, iters in solver_iters.items():
            if len(iters) < 2:
                continue
            iters_sorted = sorted(iters, key=lambda x: x.iteration)
            deltas: list[float] = []
            for i in range(1, len(iters_sorted)):
                delta = iters_sorted[i].success_rate - iters_sorted[i - 1].success_rate
                deltas.append(round(delta, 4))
            avg_delta = round(sum(deltas) / len(deltas), 4) if deltas else 0.0
            results.append(
                {
                    "solver_id": sid,
                    "avg_iteration_delta": avg_delta,
                    "max_delta": max(deltas) if deltas else 0.0,
                    "min_delta": min(deltas) if deltas else 0.0,
                    "iteration_count": len(iters_sorted),
                }
            )
        results.sort(key=lambda x: x["avg_iteration_delta"], reverse=True)
        return results
