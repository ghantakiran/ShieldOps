"""Outcome-Based Reward Scorer Engine —
evaluates correctness of agent outputs via outcome verification,
scores outcomes, aggregates statistics, correlates with difficulty."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class OutcomeType(StrEnum):
    CORRECT_DETECTION = "correct_detection"
    FALSE_POSITIVE = "false_positive"
    MISSED_THREAT = "missed_threat"
    PARTIAL_DETECTION = "partial_detection"


class VerificationMethod(StrEnum):
    GROUND_TRUTH = "ground_truth"
    PEER_REVIEW = "peer_review"
    AUTOMATED_CHECK = "automated_check"
    REPLAY_VALIDATION = "replay_validation"


class RewardGranularity(StrEnum):
    BINARY = "binary"
    GRADED = "graded"
    CONTINUOUS = "continuous"
    MULTI_OBJECTIVE = "multi_objective"


# --- Models ---


class OutcomeRewardRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    agent_id: str = ""
    outcome_type: OutcomeType = OutcomeType.CORRECT_DETECTION
    verification_method: VerificationMethod = VerificationMethod.GROUND_TRUTH
    reward_granularity: RewardGranularity = RewardGranularity.BINARY
    outcome_score: float = 0.0
    difficulty_score: float = 0.0
    reward_value: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class OutcomeRewardAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    agent_id: str = ""
    outcome_type: OutcomeType = OutcomeType.CORRECT_DETECTION
    verification_method: VerificationMethod = VerificationMethod.GROUND_TRUTH
    computed_reward: float = 0.0
    is_correct: bool = True
    difficulty_weight: float = 1.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class OutcomeRewardReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_outcome_score: float = 0.0
    avg_reward_value: float = 0.0
    by_outcome_type: dict[str, int] = Field(default_factory=dict)
    by_verification_method: dict[str, int] = Field(default_factory=dict)
    by_reward_granularity: dict[str, int] = Field(default_factory=dict)
    low_performing_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class OutcomeBasedRewardScorerEngine:
    """Evaluates correctness of agent outputs via outcome verification."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[OutcomeRewardRecord] = []
        self._analyses: dict[str, OutcomeRewardAnalysis] = {}
        logger.info(
            "outcome_based_reward_scorer_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        task_id: str = "",
        agent_id: str = "",
        outcome_type: OutcomeType = OutcomeType.CORRECT_DETECTION,
        verification_method: VerificationMethod = VerificationMethod.GROUND_TRUTH,
        reward_granularity: RewardGranularity = RewardGranularity.BINARY,
        outcome_score: float = 0.0,
        difficulty_score: float = 0.0,
        reward_value: float = 0.0,
        description: str = "",
    ) -> OutcomeRewardRecord:
        record = OutcomeRewardRecord(
            task_id=task_id,
            agent_id=agent_id,
            outcome_type=outcome_type,
            verification_method=verification_method,
            reward_granularity=reward_granularity,
            outcome_score=outcome_score,
            difficulty_score=difficulty_score,
            reward_value=reward_value,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "outcome_based_reward_scorer.record_added",
            record_id=record.id,
            task_id=task_id,
        )
        return record

    def process(self, key: str) -> OutcomeRewardAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        outcome_weights = {
            OutcomeType.CORRECT_DETECTION: 1.0,
            OutcomeType.PARTIAL_DETECTION: 0.5,
            OutcomeType.FALSE_POSITIVE: -0.2,
            OutcomeType.MISSED_THREAT: -1.0,
        }
        weight = outcome_weights.get(rec.outcome_type, 0.0)
        diff_weight = max(0.5, rec.difficulty_score)
        computed = round(rec.reward_value * weight * diff_weight, 4)
        analysis = OutcomeRewardAnalysis(
            task_id=rec.task_id,
            agent_id=rec.agent_id,
            outcome_type=rec.outcome_type,
            verification_method=rec.verification_method,
            computed_reward=computed,
            is_correct=rec.outcome_type == OutcomeType.CORRECT_DETECTION,
            difficulty_weight=diff_weight,
            description=(
                f"Task {rec.task_id} computed reward {computed:.4f} "
                f"(outcome {rec.outcome_type.value})"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> OutcomeRewardReport:
        by_ot: dict[str, int] = {}
        by_vm: dict[str, int] = {}
        by_rg: dict[str, int] = {}
        outcome_scores: list[float] = []
        reward_values: list[float] = []
        for r in self._records:
            k = r.outcome_type.value
            by_ot[k] = by_ot.get(k, 0) + 1
            k2 = r.verification_method.value
            by_vm[k2] = by_vm.get(k2, 0) + 1
            k3 = r.reward_granularity.value
            by_rg[k3] = by_rg.get(k3, 0) + 1
            outcome_scores.append(r.outcome_score)
            reward_values.append(r.reward_value)
        avg_score = round(sum(outcome_scores) / len(outcome_scores), 4) if outcome_scores else 0.0
        avg_reward = round(sum(reward_values) / len(reward_values), 4) if reward_values else 0.0
        agent_scores: dict[str, list[float]] = {}
        for r in self._records:
            agent_scores.setdefault(r.agent_id, []).append(r.outcome_score)
        low_performers = [a for a, sc in agent_scores.items() if sum(sc) / len(sc) < 0.3][:10]
        recs_list: list[str] = []
        if low_performers:
            recs_list.append(f"{len(low_performers)} agents with low outcome scores")
        if not recs_list:
            recs_list.append("Outcome scores within expected parameters")
        return OutcomeRewardReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_outcome_score=avg_score,
            avg_reward_value=avg_reward,
            by_outcome_type=by_ot,
            by_verification_method=by_vm,
            by_reward_granularity=by_rg,
            low_performing_agents=low_performers,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        outcome_dist: dict[str, int] = {}
        for r in self._records:
            k = r.outcome_type.value
            outcome_dist[k] = outcome_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "outcome_type_distribution": outcome_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("outcome_based_reward_scorer_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def score_outcome(self) -> list[dict[str, Any]]:
        """Score each record's outcome with weighted reward."""
        outcome_weights = {
            OutcomeType.CORRECT_DETECTION.value: 1.0,
            OutcomeType.PARTIAL_DETECTION.value: 0.5,
            OutcomeType.FALSE_POSITIVE.value: -0.2,
            OutcomeType.MISSED_THREAT.value: -1.0,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            weight = outcome_weights.get(r.outcome_type.value, 0.0)
            scored = round(r.reward_value * weight, 4)
            results.append(
                {
                    "record_id": r.id,
                    "task_id": r.task_id,
                    "outcome_type": r.outcome_type.value,
                    "raw_reward": r.reward_value,
                    "scored_reward": scored,
                }
            )
        results.sort(key=lambda x: x["scored_reward"], reverse=True)
        return results

    def aggregate_outcome_statistics(self) -> dict[str, Any]:
        """Aggregate outcome counts and mean rewards per outcome type."""
        outcome_data: dict[str, list[float]] = {}
        for r in self._records:
            outcome_data.setdefault(r.outcome_type.value, []).append(r.reward_value)
        stats: dict[str, dict[str, float]] = {}
        for otype, rewards in outcome_data.items():
            mean_r = sum(rewards) / len(rewards)
            stats[otype] = {
                "count": float(len(rewards)),
                "mean_reward": round(mean_r, 4),
                "total_reward": round(sum(rewards), 4),
            }
        return {"outcome_stats": stats, "total_records": len(self._records)}

    def correlate_outcome_with_difficulty(self) -> list[dict[str, Any]]:
        """Correlate outcome correctness rate with difficulty score bins."""
        bins: dict[str, list[bool]] = {}
        for r in self._records:
            bin_key = f"{int(r.difficulty_score * 10) / 10:.1f}"
            is_correct = r.outcome_type == OutcomeType.CORRECT_DETECTION
            bins.setdefault(bin_key, []).append(is_correct)
        results: list[dict[str, Any]] = []
        for bin_key, correctness_list in bins.items():
            correct_rate = sum(1 for c in correctness_list if c) / len(correctness_list)
            results.append(
                {
                    "difficulty_bin": float(bin_key),
                    "correct_rate": round(correct_rate, 4),
                    "sample_count": len(correctness_list),
                }
            )
        results.sort(key=lambda x: x["difficulty_bin"])
        return results
