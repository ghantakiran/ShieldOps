"""Reward Signal Engineering Engine —
design reward functions, evaluate signal quality,
and optimize reward shaping for agent optimization."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RewardType(StrEnum):
    SHAPED = "shaped"
    SPARSE = "sparse"
    DENSE = "dense"
    INTRINSIC = "intrinsic"


class SignalQuality(StrEnum):
    CLEAN = "clean"
    NOISY = "noisy"
    DELAYED = "delayed"
    CORRUPTED = "corrupted"


class OptimizationGoal(StrEnum):
    MAXIMIZE_THROUGHPUT = "maximize_throughput"
    MINIMIZE_LATENCY = "minimize_latency"
    BALANCE_COST = "balance_cost"
    MAXIMIZE_RELIABILITY = "maximize_reliability"


# --- Models ---


class RewardSignalRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    reward_type: RewardType = RewardType.DENSE
    signal_quality: SignalQuality = SignalQuality.CLEAN
    optimization_goal: OptimizationGoal = OptimizationGoal.MAXIMIZE_RELIABILITY
    reward_value: float = 0.0
    signal_delay_ms: float = 0.0
    noise_level: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RewardSignalAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    avg_reward: float = 0.0
    dominant_type: RewardType = RewardType.DENSE
    avg_noise: float = 0.0
    signal_count: int = 0
    quality_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RewardSignalReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_reward: float = 0.0
    by_reward_type: dict[str, int] = Field(default_factory=dict)
    by_signal_quality: dict[str, int] = Field(default_factory=dict)
    by_optimization_goal: dict[str, int] = Field(default_factory=dict)
    top_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RewardSignalEngineeringEngine:
    """Design reward functions, evaluate signal quality,
    and optimize reward shaping for agent optimization."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RewardSignalRecord] = []
        self._analyses: dict[str, RewardSignalAnalysis] = {}
        logger.info(
            "reward_signal_engineering.init",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        reward_type: RewardType = RewardType.DENSE,
        signal_quality: SignalQuality = SignalQuality.CLEAN,
        optimization_goal: OptimizationGoal = OptimizationGoal.MAXIMIZE_RELIABILITY,
        reward_value: float = 0.0,
        signal_delay_ms: float = 0.0,
        noise_level: float = 0.0,
        description: str = "",
    ) -> RewardSignalRecord:
        record = RewardSignalRecord(
            agent_id=agent_id,
            reward_type=reward_type,
            signal_quality=signal_quality,
            optimization_goal=optimization_goal,
            reward_value=reward_value,
            signal_delay_ms=signal_delay_ms,
            noise_level=noise_level,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "reward_signal.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> RewardSignalAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        agent_recs = [r for r in self._records if r.agent_id == rec.agent_id]
        vals = [r.reward_value for r in agent_recs]
        avg = round(sum(vals) / len(vals), 2) if vals else 0.0
        avg_noise = (
            round(sum(r.noise_level for r in agent_recs) / len(agent_recs), 4)
            if agent_recs
            else 0.0
        )
        type_counts: dict[str, int] = {}
        for r in agent_recs:
            type_counts[r.reward_type.value] = type_counts.get(r.reward_type.value, 0) + 1
        dominant_type = (
            RewardType(max(type_counts, key=lambda x: type_counts[x]))
            if type_counts
            else RewardType.DENSE
        )
        quality_score = round(max(0.0, 100.0 - avg_noise * 100), 2)
        analysis = RewardSignalAnalysis(
            agent_id=rec.agent_id,
            avg_reward=avg,
            dominant_type=dominant_type,
            avg_noise=avg_noise,
            signal_count=len(agent_recs),
            quality_score=quality_score,
            description=f"Agent {rec.agent_id} avg reward {avg}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> RewardSignalReport:
        by_rt: dict[str, int] = {}
        by_sq: dict[str, int] = {}
        by_og: dict[str, int] = {}
        vals: list[float] = []
        for r in self._records:
            by_rt[r.reward_type.value] = by_rt.get(r.reward_type.value, 0) + 1
            by_sq[r.signal_quality.value] = by_sq.get(r.signal_quality.value, 0) + 1
            by_og[r.optimization_goal.value] = by_og.get(r.optimization_goal.value, 0) + 1
            vals.append(r.reward_value)
        avg = round(sum(vals) / len(vals), 2) if vals else 0.0
        agent_totals: dict[str, float] = {}
        for r in self._records:
            agent_totals[r.agent_id] = agent_totals.get(r.agent_id, 0.0) + r.reward_value
        ranked = sorted(
            agent_totals,
            key=lambda x: agent_totals[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        corrupted = by_sq.get("corrupted", 0)
        if corrupted > 0:
            recs.append(f"{corrupted} corrupted signal records detected")
        delayed = by_sq.get("delayed", 0)
        if delayed > 0:
            recs.append(f"{delayed} delayed signal records — review timing")
        if not recs:
            recs.append("Reward signal quality is healthy")
        return RewardSignalReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_reward=avg,
            by_reward_type=by_rt,
            by_signal_quality=by_sq,
            by_optimization_goal=by_og,
            top_agents=ranked,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            dist[r.reward_type.value] = dist.get(r.reward_type.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "reward_type_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("reward_signal_engineering.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def design_reward_functions(self) -> list[dict[str, Any]]:
        """Design reward functions per agent based on goals and signal data."""
        agent_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            entry = agent_data.setdefault(
                r.agent_id,
                {"rewards": [], "goals": [], "types": []},
            )
            entry["rewards"].append(r.reward_value)
            entry["goals"].append(r.optimization_goal.value)
            entry["types"].append(r.reward_type.value)
        results: list[dict[str, Any]] = []
        for aid, data in agent_data.items():
            rewards = data["rewards"]
            avg_r = round(sum(rewards) / len(rewards), 2) if rewards else 0.0
            dominant_goal = (
                max(
                    set(data["goals"]),
                    key=lambda x: data["goals"].count(x),
                )
                if data["goals"]
                else "unknown"
            )
            dominant_type = (
                max(
                    set(data["types"]),
                    key=lambda x: data["types"].count(x),
                )
                if data["types"]
                else "dense"
            )
            recommendation = (
                "Use dense shaping"
                if dominant_type == "sparse"
                else "Current reward type is appropriate"
            )
            results.append(
                {
                    "agent_id": aid,
                    "avg_reward": avg_r,
                    "dominant_goal": dominant_goal,
                    "recommended_type": dominant_type,
                    "recommendation": recommendation,
                    "sample_count": len(rewards),
                }
            )
        results.sort(key=lambda x: x["avg_reward"], reverse=True)
        return results

    def evaluate_signal_quality(self) -> list[dict[str, Any]]:
        """Evaluate signal quality metrics per agent."""
        agent_data: dict[str, list[RewardSignalRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for aid, recs in agent_data.items():
            noise_vals = [r.noise_level for r in recs]
            delay_vals = [r.signal_delay_ms for r in recs]
            avg_noise = round(sum(noise_vals) / len(noise_vals), 4) if noise_vals else 0.0
            avg_delay = round(sum(delay_vals) / len(delay_vals), 2) if delay_vals else 0.0
            quality_counts: dict[str, int] = {}
            for r in recs:
                quality_counts[r.signal_quality.value] = (
                    quality_counts.get(r.signal_quality.value, 0) + 1
                )
            dominant_quality = (
                max(
                    quality_counts,
                    key=lambda x: quality_counts[x],
                )
                if quality_counts
                else "clean"
            )
            overall_score = round(max(0.0, 100.0 - avg_noise * 100 - avg_delay / 10), 2)
            results.append(
                {
                    "agent_id": aid,
                    "avg_noise": avg_noise,
                    "avg_delay_ms": avg_delay,
                    "dominant_quality": dominant_quality,
                    "overall_score": overall_score,
                    "record_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["overall_score"], reverse=True)
        return results

    def optimize_reward_shaping(self) -> list[dict[str, Any]]:
        """Recommend reward shaping adjustments per optimization goal."""
        goal_data: dict[str, list[float]] = {}
        for r in self._records:
            goal_data.setdefault(r.optimization_goal.value, []).append(r.reward_value)
        results: list[dict[str, Any]] = []
        shaping_map = {
            "maximize_throughput": "increase dense reward frequency",
            "minimize_latency": "apply time-penalty shaping",
            "balance_cost": "use cost-aware intrinsic reward",
            "maximize_reliability": "apply reliability bonus shaping",
        }
        for goal, rewards in goal_data.items():
            avg_r = round(sum(rewards) / len(rewards), 2) if rewards else 0.0
            suggestion = shaping_map.get(goal, "review reward design")
            results.append(
                {
                    "optimization_goal": goal,
                    "avg_reward": avg_r,
                    "shaping_suggestion": suggestion,
                    "sample_count": len(rewards),
                    "needs_adjustment": avg_r < 0.5,
                }
            )
        results.sort(key=lambda x: x["avg_reward"])
        return results
