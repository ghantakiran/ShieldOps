"""Proposer Solver Coevolution Engine —
manages the co-evolution feedback loop between proposer and solver."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CoevolutionState(StrEnum):
    INITIALIZING = "initializing"
    EVOLVING = "evolving"
    CONVERGING = "converging"
    CONVERGED = "converged"


class FeedbackDirection(StrEnum):
    PROPOSER_TO_SOLVER = "proposer_to_solver"
    SOLVER_TO_PROPOSER = "solver_to_proposer"
    BIDIRECTIONAL = "bidirectional"
    STALLED = "stalled"


class IterationOutcome(StrEnum):
    SOLVER_IMPROVED = "solver_improved"
    PROPOSER_ADAPTED = "proposer_adapted"
    BOTH_IMPROVED = "both_improved"
    NO_CHANGE = "no_change"


# --- Models ---


class CoevolutionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    coevolution_id: str = ""
    iteration: int = 0
    state: CoevolutionState = CoevolutionState.INITIALIZING
    feedback_direction: FeedbackDirection = FeedbackDirection.BIDIRECTIONAL
    outcome: IterationOutcome = IterationOutcome.NO_CHANGE
    solver_delta: float = 0.0
    proposer_delta: float = 0.0
    efficiency_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CoevolutionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    coevolution_id: str = ""
    avg_solver_delta: float = 0.0
    avg_proposer_delta: float = 0.0
    current_state: CoevolutionState = CoevolutionState.INITIALIZING
    iteration_count: int = 0
    efficiency_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CoevolutionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_efficiency: float = 0.0
    by_state: dict[str, int] = Field(default_factory=dict)
    by_feedback: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    top_coevolutions: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ProposerSolverCoevolutionEngine:
    """Manages the co-evolution feedback loop between proposer and solver."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CoevolutionRecord] = []
        self._analyses: dict[str, CoevolutionAnalysis] = {}
        logger.info(
            "proposer_solver_coevolution_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        coevolution_id: str = "",
        iteration: int = 0,
        state: CoevolutionState = CoevolutionState.INITIALIZING,
        feedback_direction: FeedbackDirection = FeedbackDirection.BIDIRECTIONAL,
        outcome: IterationOutcome = IterationOutcome.NO_CHANGE,
        solver_delta: float = 0.0,
        proposer_delta: float = 0.0,
        efficiency_score: float = 0.0,
        description: str = "",
    ) -> CoevolutionRecord:
        record = CoevolutionRecord(
            coevolution_id=coevolution_id,
            iteration=iteration,
            state=state,
            feedback_direction=feedback_direction,
            outcome=outcome,
            solver_delta=solver_delta,
            proposer_delta=proposer_delta,
            efficiency_score=efficiency_score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "proposer_solver_coevolution.record_added",
            record_id=record.id,
            coevolution_id=coevolution_id,
        )
        return record

    def process(self, key: str) -> CoevolutionAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        coevo_recs = [r for r in self._records if r.coevolution_id == rec.coevolution_id]
        s_deltas = [r.solver_delta for r in coevo_recs]
        p_deltas = [r.proposer_delta for r in coevo_recs]
        eff_vals = [r.efficiency_score for r in coevo_recs]
        avg_s = round(sum(s_deltas) / len(s_deltas), 4) if s_deltas else 0.0
        avg_p = round(sum(p_deltas) / len(p_deltas), 4) if p_deltas else 0.0
        avg_eff = round(sum(eff_vals) / len(eff_vals), 4) if eff_vals else 0.0
        analysis = CoevolutionAnalysis(
            coevolution_id=rec.coevolution_id,
            avg_solver_delta=avg_s,
            avg_proposer_delta=avg_p,
            current_state=rec.state,
            iteration_count=len(coevo_recs),
            efficiency_score=avg_eff,
            description=f"Coevolution {rec.coevolution_id} eff {avg_eff}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CoevolutionReport:
        by_st: dict[str, int] = {}
        by_fb: dict[str, int] = {}
        by_out: dict[str, int] = {}
        eff_vals: list[float] = []
        for r in self._records:
            k1 = r.state.value
            by_st[k1] = by_st.get(k1, 0) + 1
            k2 = r.feedback_direction.value
            by_fb[k2] = by_fb.get(k2, 0) + 1
            k3 = r.outcome.value
            by_out[k3] = by_out.get(k3, 0) + 1
            eff_vals.append(r.efficiency_score)
        avg_eff = round(sum(eff_vals) / len(eff_vals), 4) if eff_vals else 0.0
        coevo_effs: dict[str, float] = {}
        for r in self._records:
            if r.efficiency_score > coevo_effs.get(r.coevolution_id, -1.0):
                coevo_effs[r.coevolution_id] = r.efficiency_score
        top_coevos = sorted(
            coevo_effs,
            key=lambda x: coevo_effs[x],
            reverse=True,
        )[:10]
        recs_list: list[str] = []
        stalled = by_fb.get("stalled", 0)
        no_change = by_out.get("no_change", 0)
        if stalled > 0:
            recs_list.append(f"{stalled} stalled feedback loops — intervene")
        if no_change > len(self._records) * 0.3:
            recs_list.append("High no-change rate — review co-evolution parameters")
        if not recs_list:
            recs_list.append("Co-evolution feedback loop is healthy")
        return CoevolutionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_efficiency=avg_eff,
            by_state=by_st,
            by_feedback=by_fb,
            by_outcome=by_out,
            top_coevolutions=top_coevos,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        state_dist: dict[str, int] = {}
        for r in self._records:
            k = r.state.value
            state_dist[k] = state_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "state_distribution": state_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("proposer_solver_coevolution_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def execute_coevolution_step(
        self,
        coevolution_id: str,
        solver_success_rate: float,
        current_difficulty: float,
    ) -> dict[str, Any]:
        """Execute one co-evolution step and compute next actions."""
        coevo_recs = [r for r in self._records if r.coevolution_id == coevolution_id]
        if not coevo_recs:
            return {
                "coevolution_id": coevolution_id,
                "step": 0,
                "action": "initialize",
                "next_difficulty": current_difficulty,
            }
        latest = max(coevo_recs, key=lambda x: x.iteration)
        if solver_success_rate > 0.75:
            next_diff = min(1.0, current_difficulty + 0.05)
            outcome = IterationOutcome.SOLVER_IMPROVED
            direction = FeedbackDirection.SOLVER_TO_PROPOSER
        elif solver_success_rate < 0.35:
            next_diff = max(0.0, current_difficulty - 0.05)
            outcome = IterationOutcome.PROPOSER_ADAPTED
            direction = FeedbackDirection.PROPOSER_TO_SOLVER
        else:
            next_diff = current_difficulty
            outcome = IterationOutcome.BOTH_IMPROVED
            direction = FeedbackDirection.BIDIRECTIONAL
        return {
            "coevolution_id": coevolution_id,
            "step": latest.iteration + 1,
            "solver_success_rate": solver_success_rate,
            "current_difficulty": current_difficulty,
            "next_difficulty": round(next_diff, 3),
            "outcome": outcome.value,
            "feedback_direction": direction.value,
        }

    def detect_coevolution_divergence(self) -> list[dict[str, Any]]:
        """Detect co-evolution pairs that are diverging (arms race)."""
        coevo_iters: dict[str, list[CoevolutionRecord]] = {}
        for r in self._records:
            coevo_iters.setdefault(r.coevolution_id, []).append(r)
        results: list[dict[str, Any]] = []
        for cid, iters in coevo_iters.items():
            if len(iters) < 4:
                continue
            iters_sorted = sorted(iters, key=lambda x: x.iteration)
            recent = iters_sorted[-4:]
            no_change_count = sum(1 for i in recent if i.outcome == IterationOutcome.NO_CHANGE)
            stalled_count = sum(
                1 for i in recent if i.feedback_direction == FeedbackDirection.STALLED
            )
            if no_change_count >= 3 or stalled_count >= 2:
                results.append(
                    {
                        "coevolution_id": cid,
                        "divergence_detected": True,
                        "no_change_count": no_change_count,
                        "stalled_count": stalled_count,
                        "iterations_checked": len(recent),
                    }
                )
        return results

    def compute_coevolution_efficiency(self) -> dict[str, Any]:
        """Compute efficiency metrics across all co-evolution runs."""
        coevo_effs: dict[str, list[float]] = {}
        for r in self._records:
            coevo_effs.setdefault(r.coevolution_id, []).append(r.efficiency_score)
        per_coevo: list[dict[str, Any]] = []
        for cid, effs in coevo_effs.items():
            avg_eff = round(sum(effs) / len(effs), 4) if effs else 0.0
            per_coevo.append(
                {
                    "coevolution_id": cid,
                    "avg_efficiency": avg_eff,
                    "iterations": len(effs),
                }
            )
        per_coevo.sort(key=lambda x: x["avg_efficiency"], reverse=True)
        all_effs = [r.efficiency_score for r in self._records]
        global_avg = round(sum(all_effs) / len(all_effs), 4) if all_effs else 0.0
        return {
            "global_avg_efficiency": global_avg,
            "coevolution_count": len(coevo_effs),
            "per_coevolution": per_coevo,
        }
