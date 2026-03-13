"""Difficulty Guided Reward Engine —
implements Dr. Zero reward function for SRE agent training."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RewardZone(StrEnum):
    TRIVIAL = "trivial"
    PRODUCTIVE = "productive"
    CHALLENGING = "challenging"
    IMPOSSIBLE = "impossible"


class FormatRewardLevel(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"


class PenaltyType(StrEnum):
    TRIVIAL_PENALTY = "trivial_penalty"
    IMPOSSIBLE_PENALTY = "impossible_penalty"
    FORMAT_PENALTY = "format_penalty"
    NO_PENALTY = "no_penalty"


# --- Models ---


class DifficultyRewardRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    solver_id: str = ""
    reward_zone: RewardZone = RewardZone.PRODUCTIVE
    format_reward: FormatRewardLevel = FormatRewardLevel.FULL
    penalty_type: PenaltyType = PenaltyType.NO_PENALTY
    raw_reward: float = 0.0
    difficulty_score: float = 0.0
    correctness_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DifficultyRewardAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    solver_id: str = ""
    avg_reward: float = 0.0
    dominant_zone: RewardZone = RewardZone.PRODUCTIVE
    format_quality: FormatRewardLevel = FormatRewardLevel.FULL
    record_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DifficultyRewardReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_raw_reward: float = 0.0
    by_zone: dict[str, int] = Field(default_factory=dict)
    by_format_reward: dict[str, int] = Field(default_factory=dict)
    by_penalty: dict[str, int] = Field(default_factory=dict)
    productive_ratio: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DifficultyGuidedRewardEngine:
    """Implements Dr. Zero reward function for SRE agent training."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[DifficultyRewardRecord] = []
        self._analyses: dict[str, DifficultyRewardAnalysis] = {}
        logger.info(
            "difficulty_guided_reward_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        solver_id: str = "",
        reward_zone: RewardZone = RewardZone.PRODUCTIVE,
        format_reward: FormatRewardLevel = FormatRewardLevel.FULL,
        penalty_type: PenaltyType = PenaltyType.NO_PENALTY,
        raw_reward: float = 0.0,
        difficulty_score: float = 0.0,
        correctness_score: float = 0.0,
        description: str = "",
    ) -> DifficultyRewardRecord:
        record = DifficultyRewardRecord(
            solver_id=solver_id,
            reward_zone=reward_zone,
            format_reward=format_reward,
            penalty_type=penalty_type,
            raw_reward=raw_reward,
            difficulty_score=difficulty_score,
            correctness_score=correctness_score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "difficulty_guided_reward.record_added",
            record_id=record.id,
            solver_id=solver_id,
        )
        return record

    def process(self, key: str) -> DifficultyRewardAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        solver_recs = [r for r in self._records if r.solver_id == rec.solver_id]
        rewards = [r.raw_reward for r in solver_recs]
        avg_reward = round(sum(rewards) / len(rewards), 4) if rewards else 0.0
        zone_counts: dict[str, int] = {}
        for sr in solver_recs:
            zk = sr.reward_zone.value
            zone_counts[zk] = zone_counts.get(zk, 0) + 1
        dominant_zone_str = max(zone_counts, key=lambda x: zone_counts[x]) if zone_counts else ""
        dominant_zone = RewardZone(dominant_zone_str) if dominant_zone_str else rec.reward_zone
        analysis = DifficultyRewardAnalysis(
            solver_id=rec.solver_id,
            avg_reward=avg_reward,
            dominant_zone=dominant_zone,
            format_quality=rec.format_reward,
            record_count=len(solver_recs),
            description=f"Solver {rec.solver_id} avg reward {avg_reward}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> DifficultyRewardReport:
        by_z: dict[str, int] = {}
        by_f: dict[str, int] = {}
        by_p: dict[str, int] = {}
        rewards: list[float] = []
        for r in self._records:
            k1 = r.reward_zone.value
            by_z[k1] = by_z.get(k1, 0) + 1
            k2 = r.format_reward.value
            by_f[k2] = by_f.get(k2, 0) + 1
            k3 = r.penalty_type.value
            by_p[k3] = by_p.get(k3, 0) + 1
            rewards.append(r.raw_reward)
        avg_reward = round(sum(rewards) / len(rewards), 4) if rewards else 0.0
        total = len(self._records)
        productive = by_z.get("productive", 0)
        productive_ratio = round(productive / total, 4) if total > 0 else 0.0
        recs_list: list[str] = []
        trivial = by_z.get("trivial", 0)
        impossible = by_z.get("impossible", 0)
        if productive_ratio < 0.5:
            recs_list.append("Productive zone ratio below 50% — recalibrate difficulty")
        if trivial > impossible:
            recs_list.append("Too many trivial scenarios — increase difficulty")
        elif impossible > trivial:
            recs_list.append("Too many impossible scenarios — decrease difficulty")
        if not recs_list:
            recs_list.append("Reward distribution is well-balanced")
        return DifficultyRewardReport(
            total_records=total,
            total_analyses=len(self._analyses),
            avg_raw_reward=avg_reward,
            by_zone=by_z,
            by_format_reward=by_f,
            by_penalty=by_p,
            productive_ratio=productive_ratio,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        zone_dist: dict[str, int] = {}
        for r in self._records:
            k = r.reward_zone.value
            zone_dist[k] = zone_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "zone_distribution": zone_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("difficulty_guided_reward_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_difficulty_reward(
        self,
        difficulty_score: float,
        correctness_score: float,
    ) -> dict[str, Any]:
        """Compute the Dr. Zero difficulty-guided reward."""
        if difficulty_score < 0.25:
            zone = RewardZone.TRIVIAL
            base_reward = -0.5
            penalty = PenaltyType.TRIVIAL_PENALTY
        elif difficulty_score < 0.75:
            zone = RewardZone.PRODUCTIVE
            base_reward = correctness_score
            penalty = PenaltyType.NO_PENALTY
        elif difficulty_score < 0.9:
            zone = RewardZone.CHALLENGING
            base_reward = correctness_score * 1.2
            penalty = PenaltyType.NO_PENALTY
        else:
            zone = RewardZone.IMPOSSIBLE
            base_reward = -0.25
            penalty = PenaltyType.IMPOSSIBLE_PENALTY
        final_reward = round(base_reward, 4)
        return {
            "difficulty_score": difficulty_score,
            "correctness_score": correctness_score,
            "reward_zone": zone.value,
            "final_reward": final_reward,
            "penalty_type": penalty.value,
        }

    def analyze_reward_distribution(self) -> dict[str, Any]:
        """Analyze the distribution of rewards across zones."""
        zone_rewards: dict[str, list[float]] = {}
        for r in self._records:
            zk = r.reward_zone.value
            zone_rewards.setdefault(zk, []).append(r.raw_reward)
        result: dict[str, Any] = {}
        for zone, zone_vals in zone_rewards.items():
            avg = round(sum(zone_vals) / len(zone_vals), 4) if zone_vals else 0.0
            result[zone] = {
                "count": len(zone_vals),
                "avg_reward": avg,
                "min_reward": min(zone_vals) if zone_vals else 0.0,
                "max_reward": max(zone_vals) if zone_vals else 0.0,
            }
        return result

    def optimize_difficulty_ratio(self) -> dict[str, Any]:
        """Recommend optimal difficulty ratio for productive learning."""
        zone_counts: dict[str, int] = {}
        for r in self._records:
            k = r.reward_zone.value
            zone_counts[k] = zone_counts.get(k, 0) + 1
        total = len(self._records)
        ratios: dict[str, float] = {}
        for zone, cnt in zone_counts.items():
            ratios[zone] = round(cnt / total, 4) if total > 0 else 0.0
        productive_ratio = ratios.get("productive", 0.0)
        trivial_ratio = ratios.get("trivial", 0.0)
        impossible_ratio = ratios.get("impossible", 0.0)
        optimal = productive_ratio >= 0.5
        suggestions: list[str] = []
        if trivial_ratio > 0.3:
            suggestions.append("Reduce trivial scenarios by increasing base difficulty")
        if impossible_ratio > 0.2:
            suggestions.append("Reduce impossible scenarios by lowering ceiling difficulty")
        if not suggestions:
            suggestions.append("Difficulty ratio is near-optimal")
        return {
            "current_ratios": ratios,
            "productive_ratio": productive_ratio,
            "is_optimal": optimal,
            "target_productive_ratio": 0.5,
            "suggestions": suggestions,
        }
