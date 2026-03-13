"""Incident Scenario Proposer Engine —
generates synthetic SRE incident scenarios of varying complexity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ScenarioComplexity(StrEnum):
    SINGLE_HOP = "single_hop"
    TWO_HOP = "two_hop"
    THREE_HOP = "three_hop"
    FOUR_HOP = "four_hop"


class ScenarioCategory(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    SECURITY = "security"
    CASCADING = "cascading"


class ProposerStrategy(StrEnum):
    RANDOM = "random"
    ADAPTIVE = "adaptive"
    ADVERSARIAL = "adversarial"
    CURRICULUM = "curriculum"


# --- Models ---


class IncidentScenarioRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_id: str = ""
    complexity: ScenarioComplexity = ScenarioComplexity.SINGLE_HOP
    category: ScenarioCategory = ScenarioCategory.INFRASTRUCTURE
    strategy: ProposerStrategy = ProposerStrategy.RANDOM
    novelty_score: float = 0.0
    difficulty_rating: float = 0.0
    solver_success_rate: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentScenarioAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_id: str = ""
    avg_difficulty: float = 0.0
    complexity: ScenarioComplexity = ScenarioComplexity.SINGLE_HOP
    novelty_rank: float = 0.0
    batch_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentScenarioReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_difficulty: float = 0.0
    by_complexity: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    top_novel_scenarios: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentScenarioProposerEngine:
    """Generates synthetic SRE incident scenarios of varying complexity."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[IncidentScenarioRecord] = []
        self._analyses: dict[str, IncidentScenarioAnalysis] = {}
        logger.info(
            "incident_scenario_proposer_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        scenario_id: str = "",
        complexity: ScenarioComplexity = ScenarioComplexity.SINGLE_HOP,
        category: ScenarioCategory = ScenarioCategory.INFRASTRUCTURE,
        strategy: ProposerStrategy = ProposerStrategy.RANDOM,
        novelty_score: float = 0.0,
        difficulty_rating: float = 0.0,
        solver_success_rate: float = 0.0,
        description: str = "",
    ) -> IncidentScenarioRecord:
        record = IncidentScenarioRecord(
            scenario_id=scenario_id,
            complexity=complexity,
            category=category,
            strategy=strategy,
            novelty_score=novelty_score,
            difficulty_rating=difficulty_rating,
            solver_success_rate=solver_success_rate,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_scenario_proposer.record_added",
            record_id=record.id,
            scenario_id=scenario_id,
        )
        return record

    def process(self, key: str) -> IncidentScenarioAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        batch_recs = [r for r in self._records if r.scenario_id == rec.scenario_id]
        diffs = [r.difficulty_rating for r in batch_recs]
        avg_diff = round(sum(diffs) / len(diffs), 2) if diffs else 0.0
        novelty_vals = [r.novelty_score for r in batch_recs]
        avg_novelty = round(sum(novelty_vals) / len(novelty_vals), 2) if novelty_vals else 0.0
        analysis = IncidentScenarioAnalysis(
            scenario_id=rec.scenario_id,
            avg_difficulty=avg_diff,
            complexity=rec.complexity,
            novelty_rank=avg_novelty,
            batch_count=len(batch_recs),
            description=f"Scenario {rec.scenario_id} avg difficulty {avg_diff}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> IncidentScenarioReport:
        by_c: dict[str, int] = {}
        by_cat: dict[str, int] = {}
        by_s: dict[str, int] = {}
        diffs: list[float] = []
        for r in self._records:
            k1 = r.complexity.value
            by_c[k1] = by_c.get(k1, 0) + 1
            k2 = r.category.value
            by_cat[k2] = by_cat.get(k2, 0) + 1
            k3 = r.strategy.value
            by_s[k3] = by_s.get(k3, 0) + 1
            diffs.append(r.difficulty_rating)
        avg_diff = round(sum(diffs) / len(diffs), 2) if diffs else 0.0
        novelty_map: dict[str, float] = {}
        for r in self._records:
            if r.novelty_score > novelty_map.get(r.scenario_id, -1.0):
                novelty_map[r.scenario_id] = r.novelty_score
        top_novel = sorted(
            novelty_map,
            key=lambda x: novelty_map[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        casc = by_cat.get("cascading", 0)
        if casc > 0:
            recs.append(f"{casc} cascading scenarios detected — review blast radius")
        if not recs:
            recs.append("Scenario diversity is healthy")
        return IncidentScenarioReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_difficulty=avg_diff,
            by_complexity=by_c,
            by_category=by_cat,
            by_strategy=by_s,
            top_novel_scenarios=top_novel,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            k = r.category.value
            cat_dist[k] = cat_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "category_distribution": cat_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("incident_scenario_proposer_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def generate_scenario_batch(
        self,
        batch_size: int = 10,
        strategy: ProposerStrategy = ProposerStrategy.RANDOM,
    ) -> list[dict[str, Any]]:
        """Generate a batch of synthetic incident scenarios."""
        complexities = list(ScenarioComplexity)
        categories = list(ScenarioCategory)
        batch: list[dict[str, Any]] = []
        for i in range(batch_size):
            if strategy == ProposerStrategy.CURRICULUM:
                idx = min(i % len(complexities), len(complexities) - 1)
                complexity = complexities[idx]
            elif strategy == ProposerStrategy.ADVERSARIAL:
                complexity = ScenarioComplexity.FOUR_HOP
            else:
                complexity = complexities[i % len(complexities)]
            hop_count = complexities.index(complexity) + 1
            difficulty = round(hop_count * 0.25, 2)
            novelty = round(0.1 + (i % 9) * 0.1, 3)
            batch.append(
                {
                    "scenario_id": str(uuid.uuid4()),
                    "complexity": complexity.value,
                    "category": categories[i % len(categories)].value,
                    "strategy": strategy.value,
                    "difficulty_rating": difficulty,
                    "novelty_score": novelty,
                }
            )
        batch.sort(key=lambda x: x["difficulty_rating"], reverse=True)
        return batch

    def calibrate_difficulty_to_solver(
        self,
        solver_success_rate: float,
    ) -> dict[str, Any]:
        """Calibrate scenario difficulty based on solver success rate."""
        if solver_success_rate > 0.85:
            target = ScenarioComplexity.FOUR_HOP
            adjustment = "increase"
        elif solver_success_rate > 0.6:
            target = ScenarioComplexity.THREE_HOP
            adjustment = "maintain"
        elif solver_success_rate > 0.35:
            target = ScenarioComplexity.TWO_HOP
            adjustment = "maintain"
        else:
            target = ScenarioComplexity.SINGLE_HOP
            adjustment = "decrease"
        return {
            "solver_success_rate": solver_success_rate,
            "recommended_complexity": target.value,
            "difficulty_adjustment": adjustment,
            "target_difficulty_rating": round(
                (list(ScenarioComplexity).index(target) + 1) * 0.25, 2
            ),
        }

    def rank_scenarios_by_novelty(self) -> list[dict[str, Any]]:
        """Rank all scenarios by their novelty score."""
        novelty_map: dict[str, float] = {}
        category_map: dict[str, str] = {}
        for r in self._records:
            if r.novelty_score > novelty_map.get(r.scenario_id, -1.0):
                novelty_map[r.scenario_id] = r.novelty_score
                category_map[r.scenario_id] = r.category.value
        ranked = sorted(
            novelty_map,
            key=lambda x: novelty_map[x],
            reverse=True,
        )
        results: list[dict[str, Any]] = []
        for i, sid in enumerate(ranked, 1):
            results.append(
                {
                    "rank": i,
                    "scenario_id": sid,
                    "novelty_score": novelty_map[sid],
                    "category": category_map[sid],
                }
            )
        return results
