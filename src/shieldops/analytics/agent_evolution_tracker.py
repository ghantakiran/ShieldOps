"""Agent Evolution Tracker

Track generational progress of agent optimization
with evolution velocity and dead-end detection.
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


class EvolutionStage(StrEnum):
    INITIAL = "initial"
    LEARNING = "learning"
    OPTIMIZING = "optimizing"
    MATURE = "mature"


class MutationType(StrEnum):
    PARAMETER = "parameter"
    ARCHITECTURE = "architecture"
    STRATEGY = "strategy"
    PROMPT = "prompt"


class SelectionPressure(StrEnum):
    PERFORMANCE = "performance"
    COST = "cost"
    RELIABILITY = "reliability"
    SPEED = "speed"


# --- Models ---


class EvolutionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    stage: EvolutionStage = EvolutionStage.INITIAL
    mutation: MutationType = MutationType.PARAMETER
    pressure: SelectionPressure = SelectionPressure.PERFORMANCE
    fitness_score: float = 0.0
    generation: int = 0
    service: str = ""
    created_at: float = Field(default_factory=time.time)


class EvolutionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    stage: EvolutionStage = EvolutionStage.INITIAL
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EvolutionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    mature_count: int = 0
    avg_fitness: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_mutation: dict[str, int] = Field(default_factory=dict)
    by_pressure: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentEvolutionTracker:
    """Track generational progress with evolution
    velocity and dead-end detection.
    """

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[EvolutionRecord] = []
        self._analyses: dict[str, EvolutionAnalysis] = {}
        logger.info(
            "agent_evolution_tracker.initialized",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        stage: EvolutionStage = EvolutionStage.INITIAL,
        mutation: MutationType = MutationType.PARAMETER,
        pressure: SelectionPressure = (SelectionPressure.PERFORMANCE),
        fitness_score: float = 0.0,
        generation: int = 0,
        service: str = "",
    ) -> EvolutionRecord:
        record = EvolutionRecord(
            agent_id=agent_id,
            stage=stage,
            mutation=mutation,
            pressure=pressure,
            fitness_score=fitness_score,
            generation=generation,
            service=service,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "agent_evolution_tracker.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.id == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        rec = matching[0]
        analysis = EvolutionAnalysis(
            agent_id=rec.agent_id,
            stage=rec.stage,
            analysis_score=rec.fitness_score,
            description=(f"Evolution {rec.agent_id} gen={rec.generation}"),
        )
        self._analyses[key] = analysis
        return {
            "key": key,
            "analysis_id": analysis.id,
            "score": analysis.analysis_score,
        }

    def generate_report(self) -> EvolutionReport:
        by_stage: dict[str, int] = {}
        by_mut: dict[str, int] = {}
        by_pres: dict[str, int] = {}
        mature = 0
        scores: list[float] = []
        for r in self._records:
            s = r.stage.value
            by_stage[s] = by_stage.get(s, 0) + 1
            m = r.mutation.value
            by_mut[m] = by_mut.get(m, 0) + 1
            p = r.pressure.value
            by_pres[p] = by_pres.get(p, 0) + 1
            if r.stage == EvolutionStage.MATURE:
                mature += 1
            scores.append(r.fitness_score)
        avg = round(sum(scores) / len(scores), 4) if scores else 0.0
        recs: list[str] = []
        initial = by_stage.get("initial", 0)
        total = len(self._records)
        if total > 0 and initial / total > 0.5:
            recs.append("Many agents stuck at initial — accelerate training")
        if not recs:
            recs.append("Evolution tracking is healthy")
        return EvolutionReport(
            total_records=total,
            total_analyses=len(self._analyses),
            mature_count=mature,
            avg_fitness=avg,
            by_stage=by_stage,
            by_mutation=by_mut,
            by_pressure=by_pres,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            k = r.stage.value
            stage_dist[k] = stage_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "stage_distribution": stage_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("agent_evolution_tracker.cleared")
        return {"status": "cleared"}

    # --- Domain methods ---

    def track_generational_progress(self, agent_id: str) -> list[dict[str, Any]]:
        """Track progress across generations."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return []
        sorted_recs = sorted(matching, key=lambda r: r.generation)
        return [
            {
                "generation": r.generation,
                "fitness_score": r.fitness_score,
                "stage": r.stage.value,
                "mutation": r.mutation.value,
            }
            for r in sorted_recs
        ]

    def compute_evolution_velocity(self, agent_id: str) -> dict[str, Any]:
        """Compute evolution velocity."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return {
                "agent_id": agent_id,
                "status": "no_data",
            }
        sorted_recs = sorted(matching, key=lambda r: r.generation)
        if len(sorted_recs) < 2:
            return {
                "agent_id": agent_id,
                "status": "insufficient_data",
            }
        deltas = [
            sorted_recs[i].fitness_score - sorted_recs[i - 1].fitness_score
            for i in range(1, len(sorted_recs))
        ]
        avg_vel = round(sum(deltas) / len(deltas), 4)
        return {
            "agent_id": agent_id,
            "velocity": avg_vel,
            "generations": len(sorted_recs),
        }

    def identify_evolutionary_dead_ends(self, agent_id: str) -> list[dict[str, Any]]:
        """Identify evolutionary dead ends."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return []
        by_mut: dict[str, list[float]] = {}
        for r in matching:
            m = r.mutation.value
            if m not in by_mut:
                by_mut[m] = []
            by_mut[m].append(r.fitness_score)
        dead_ends = []
        for mut, scores in by_mut.items():
            if len(scores) >= 2:
                avg_delta = (scores[-1] - scores[0]) / len(scores)
                if avg_delta <= 0:
                    dead_ends.append(
                        {
                            "mutation_type": mut,
                            "avg_delta": round(avg_delta, 4),
                            "attempts": len(scores),
                        }
                    )
        return dead_ends
