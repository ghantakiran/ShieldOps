"""Reward Shaping Intelligence Engine —
shapes rewards for verifiable, non-trivial security tasks,
calibrates reward scale, detects reward hacking."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RewardShape(StrEnum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    LOGARITHMIC = "logarithmic"
    STEPPED = "stepped"


class TaskDifficulty(StrEnum):
    TRIVIAL = "trivial"
    MODERATE = "moderate"
    CHALLENGING = "challenging"
    EXTREME = "extreme"


class ShapingObjective(StrEnum):
    EXPLORATION = "exploration"
    EXPLOITATION = "exploitation"
    BALANCED = "balanced"
    CURRICULUM = "curriculum"


# --- Models ---


class RewardShapingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    agent_id: str = ""
    reward_shape: RewardShape = RewardShape.LINEAR
    task_difficulty: TaskDifficulty = TaskDifficulty.MODERATE
    shaping_objective: ShapingObjective = ShapingObjective.BALANCED
    raw_reward: float = 0.0
    shaped_reward: float = 0.0
    hacking_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RewardShapingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    agent_id: str = ""
    reward_shape: RewardShape = RewardShape.LINEAR
    task_difficulty: TaskDifficulty = TaskDifficulty.MODERATE
    shaping_multiplier: float = 1.0
    is_hacking_suspected: bool = False
    effective_reward: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RewardShapingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_raw_reward: float = 0.0
    avg_shaped_reward: float = 0.0
    by_reward_shape: dict[str, int] = Field(default_factory=dict)
    by_task_difficulty: dict[str, int] = Field(default_factory=dict)
    by_shaping_objective: dict[str, int] = Field(default_factory=dict)
    hacking_suspects: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RewardShapingIntelligenceEngine:
    """Shapes rewards for verifiable, non-trivial security tasks."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RewardShapingRecord] = []
        self._analyses: dict[str, RewardShapingAnalysis] = {}
        logger.info(
            "reward_shaping_intelligence_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        task_id: str = "",
        agent_id: str = "",
        reward_shape: RewardShape = RewardShape.LINEAR,
        task_difficulty: TaskDifficulty = TaskDifficulty.MODERATE,
        shaping_objective: ShapingObjective = ShapingObjective.BALANCED,
        raw_reward: float = 0.0,
        shaped_reward: float = 0.0,
        hacking_score: float = 0.0,
        description: str = "",
    ) -> RewardShapingRecord:
        record = RewardShapingRecord(
            task_id=task_id,
            agent_id=agent_id,
            reward_shape=reward_shape,
            task_difficulty=task_difficulty,
            shaping_objective=shaping_objective,
            raw_reward=raw_reward,
            shaped_reward=shaped_reward,
            hacking_score=hacking_score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "reward_shaping_intelligence.record_added",
            record_id=record.id,
            task_id=task_id,
        )
        return record

    def process(self, key: str) -> RewardShapingAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        difficulty_multipliers = {
            TaskDifficulty.TRIVIAL: 0.5,
            TaskDifficulty.MODERATE: 1.0,
            TaskDifficulty.CHALLENGING: 1.5,
            TaskDifficulty.EXTREME: 2.0,
        }
        multiplier = difficulty_multipliers.get(rec.task_difficulty, 1.0)
        effective = round(rec.shaped_reward * multiplier, 4)
        analysis = RewardShapingAnalysis(
            task_id=rec.task_id,
            agent_id=rec.agent_id,
            reward_shape=rec.reward_shape,
            task_difficulty=rec.task_difficulty,
            shaping_multiplier=multiplier,
            is_hacking_suspected=rec.hacking_score > 0.7,
            effective_reward=effective,
            description=(
                f"Task {rec.task_id} effective reward {effective:.4f} (multiplier {multiplier})"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> RewardShapingReport:
        by_rs: dict[str, int] = {}
        by_td: dict[str, int] = {}
        by_so: dict[str, int] = {}
        raw_rewards: list[float] = []
        shaped_rewards: list[float] = []
        for r in self._records:
            k = r.reward_shape.value
            by_rs[k] = by_rs.get(k, 0) + 1
            k2 = r.task_difficulty.value
            by_td[k2] = by_td.get(k2, 0) + 1
            k3 = r.shaping_objective.value
            by_so[k3] = by_so.get(k3, 0) + 1
            raw_rewards.append(r.raw_reward)
            shaped_rewards.append(r.shaped_reward)
        avg_raw = round(sum(raw_rewards) / len(raw_rewards), 4) if raw_rewards else 0.0
        avg_shaped = round(sum(shaped_rewards) / len(shaped_rewards), 4) if shaped_rewards else 0.0
        hackers = list({r.agent_id for r in self._records if r.hacking_score > 0.7})[:10]
        recs_list: list[str] = []
        if hackers:
            recs_list.append(f"{len(hackers)} agents suspected of reward hacking")
        if not recs_list:
            recs_list.append("Reward shaping functioning within parameters")
        return RewardShapingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_raw_reward=avg_raw,
            avg_shaped_reward=avg_shaped,
            by_reward_shape=by_rs,
            by_task_difficulty=by_td,
            by_shaping_objective=by_so,
            hacking_suspects=hackers,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        difficulty_dist: dict[str, int] = {}
        for r in self._records:
            k = r.task_difficulty.value
            difficulty_dist[k] = difficulty_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "difficulty_distribution": difficulty_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("reward_shaping_intelligence_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def shape_security_reward(self) -> list[dict[str, Any]]:
        """Apply shaping to each task's raw reward based on difficulty."""
        results: list[dict[str, Any]] = []
        difficulty_multipliers = {
            TaskDifficulty.TRIVIAL.value: 0.5,
            TaskDifficulty.MODERATE.value: 1.0,
            TaskDifficulty.CHALLENGING.value: 1.5,
            TaskDifficulty.EXTREME.value: 2.0,
        }
        for r in self._records:
            mult = difficulty_multipliers.get(r.task_difficulty.value, 1.0)
            shaped = round(r.raw_reward * mult, 4)
            results.append(
                {
                    "task_id": r.task_id,
                    "raw_reward": r.raw_reward,
                    "shaped_reward": shaped,
                    "difficulty": r.task_difficulty.value,
                    "multiplier": mult,
                }
            )
        results.sort(key=lambda x: x["shaped_reward"], reverse=True)
        return results

    def calibrate_reward_scale(self) -> dict[str, Any]:
        """Calibrate reward scale statistics per difficulty tier."""
        tier_data: dict[str, list[float]] = {}
        for r in self._records:
            tier_data.setdefault(r.task_difficulty.value, []).append(r.shaped_reward)
        calibration: dict[str, dict[str, float]] = {}
        for tier, rewards in tier_data.items():
            mean_r = sum(rewards) / len(rewards)
            calibration[tier] = {
                "mean": round(mean_r, 4),
                "min": round(min(rewards), 4),
                "max": round(max(rewards), 4),
                "count": float(len(rewards)),
            }
        return {"calibration": calibration, "total_tiers": len(calibration)}

    def detect_reward_hacking(self) -> list[dict[str, Any]]:
        """Detect agents with suspiciously high hacking scores."""
        agent_scores: dict[str, list[float]] = {}
        for r in self._records:
            agent_scores.setdefault(r.agent_id, []).append(r.hacking_score)
        results: list[dict[str, Any]] = []
        for agent_id, scores in agent_scores.items():
            mean_score = sum(scores) / len(scores)
            results.append(
                {
                    "agent_id": agent_id,
                    "mean_hacking_score": round(mean_score, 4),
                    "max_hacking_score": round(max(scores), 4),
                    "suspected": mean_score > 0.7,
                    "sample_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["mean_hacking_score"], reverse=True)
        return results
