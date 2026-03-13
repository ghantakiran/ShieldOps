"""Agent Fitness Scorer

Compute composite fitness scores for agents across
multiple dimensions with plateau detection.
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


class FitnessDimension(StrEnum):
    ACCURACY = "accuracy"
    SPEED = "speed"
    COST = "cost"
    RELIABILITY = "reliability"


class ScoringMethod(StrEnum):
    WEIGHTED_SUM = "weighted_sum"
    PARETO = "pareto"
    TOURNAMENT = "tournament"
    ELO = "elo"


class FitnessTrend(StrEnum):
    IMPROVING = "improving"
    PLATEAUED = "plateaued"
    DECLINING = "declining"
    VOLATILE = "volatile"


# --- Models ---


class FitnessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    dimension: FitnessDimension = FitnessDimension.ACCURACY
    method: ScoringMethod = ScoringMethod.WEIGHTED_SUM
    trend: FitnessTrend = FitnessTrend.IMPROVING
    score: float = 0.0
    generation: int = 0
    service: str = ""
    created_at: float = Field(default_factory=time.time)


class FitnessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    dimension: FitnessDimension = FitnessDimension.ACCURACY
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FitnessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_fitness: float = 0.0
    plateaued_count: int = 0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentFitnessScorer:
    """Compute composite fitness scores for agents
    with plateau detection and improvement focus.
    """

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[FitnessRecord] = []
        self._analyses: dict[str, FitnessAnalysis] = {}
        logger.info(
            "agent_fitness_scorer.initialized",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        dimension: FitnessDimension = (FitnessDimension.ACCURACY),
        method: ScoringMethod = (ScoringMethod.WEIGHTED_SUM),
        trend: FitnessTrend = FitnessTrend.IMPROVING,
        score: float = 0.0,
        generation: int = 0,
        service: str = "",
    ) -> FitnessRecord:
        record = FitnessRecord(
            agent_id=agent_id,
            dimension=dimension,
            method=method,
            trend=trend,
            score=score,
            generation=generation,
            service=service,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "agent_fitness_scorer.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.id == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        rec = matching[0]
        analysis = FitnessAnalysis(
            agent_id=rec.agent_id,
            dimension=rec.dimension,
            analysis_score=rec.score,
            description=(f"Fitness {rec.agent_id} score={rec.score}"),
        )
        self._analyses[key] = analysis
        return {
            "key": key,
            "analysis_id": analysis.id,
            "score": analysis.analysis_score,
        }

    def generate_report(self) -> FitnessReport:
        by_dim: dict[str, int] = {}
        by_met: dict[str, int] = {}
        by_trend: dict[str, int] = {}
        plateaued = 0
        scores: list[float] = []
        for r in self._records:
            d = r.dimension.value
            by_dim[d] = by_dim.get(d, 0) + 1
            m = r.method.value
            by_met[m] = by_met.get(m, 0) + 1
            t = r.trend.value
            by_trend[t] = by_trend.get(t, 0) + 1
            if r.trend == FitnessTrend.PLATEAUED:
                plateaued += 1
            scores.append(r.score)
        avg = round(sum(scores) / len(scores), 4) if scores else 0.0
        recs: list[str] = []
        total = len(self._records)
        if total > 0 and plateaued / total > 0.3:
            recs.append("Many agents plateaued — try new optimization strategies")
        if not recs:
            recs.append("Fitness scoring is healthy")
        return FitnessReport(
            total_records=total,
            total_analyses=len(self._analyses),
            avg_fitness=avg,
            plateaued_count=plateaued,
            by_dimension=by_dim,
            by_method=by_met,
            by_trend=by_trend,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dim_dist: dict[str, int] = {}
        for r in self._records:
            k = r.dimension.value
            dim_dist[k] = dim_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "dimension_distribution": dim_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("agent_fitness_scorer.cleared")
        return {"status": "cleared"}

    # --- Domain methods ---

    def compute_composite_fitness(self, agent_id: str) -> dict[str, Any]:
        """Compute composite fitness across dimensions."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return {
                "agent_id": agent_id,
                "status": "no_data",
            }
        by_dim: dict[str, list[float]] = {}
        for r in matching:
            d = r.dimension.value
            if d not in by_dim:
                by_dim[d] = []
            by_dim[d].append(r.score)
        composite = {d: round(sum(s) / len(s), 4) for d, s in by_dim.items()}
        overall = round(
            sum(composite.values()) / len(composite),
            4,
        )
        return {
            "agent_id": agent_id,
            "by_dimension": composite,
            "overall_fitness": overall,
        }

    def detect_fitness_plateau(self, agent_id: str) -> dict[str, Any]:
        """Detect if an agent has plateaued."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return {
                "agent_id": agent_id,
                "status": "no_data",
            }
        plateaued = [r for r in matching if r.trend == FitnessTrend.PLATEAUED]
        rate = len(plateaued) / len(matching)
        return {
            "agent_id": agent_id,
            "plateau_rate": round(rate, 4),
            "plateaued_dimensions": list({r.dimension.value for r in plateaued}),
        }

    def recommend_improvement_focus(self, agent_id: str) -> dict[str, Any]:
        """Recommend which dimension to improve."""
        matching = [r for r in self._records if r.agent_id == agent_id]
        if not matching:
            return {
                "agent_id": agent_id,
                "status": "no_data",
            }
        by_dim: dict[str, list[float]] = {}
        for r in matching:
            d = r.dimension.value
            if d not in by_dim:
                by_dim[d] = []
            by_dim[d].append(r.score)
        avgs = {d: sum(s) / len(s) for d, s in by_dim.items()}
        weakest = min(avgs, key=lambda k: avgs[k])
        return {
            "agent_id": agent_id,
            "weakest_dimension": weakest,
            "weakest_score": round(avgs[weakest], 4),
            "dimension_scores": {d: round(v, 4) for d, v in avgs.items()},
        }
