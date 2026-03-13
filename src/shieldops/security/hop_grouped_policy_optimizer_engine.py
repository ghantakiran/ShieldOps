"""Hop Grouped Policy Optimizer Engine —
HRPO-style grouping for security policy optimization,
group tasks by complexity, compute baselines, compare strategies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PolicyGroupType(StrEnum):
    SIMPLE_DETECTION = "simple_detection"
    MULTI_STAGE = "multi_stage"
    CROSS_DOMAIN = "cross_domain"
    ADVANCED_PERSISTENT = "advanced_persistent"


class OptimizationPhase(StrEnum):
    GROUPING = "grouping"
    BASELINE_COMPUTATION = "baseline_computation"
    ADVANTAGE_ESTIMATION = "advantage_estimation"
    POLICY_UPDATE = "policy_update"


class GroupingMethod(StrEnum):
    COMPLEXITY_BASED = "complexity_based"
    CATEGORY_BASED = "category_based"
    HYBRID = "hybrid"
    ADAPTIVE = "adaptive"


# --- Models ---


class PolicyOptimizerRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    group_type: PolicyGroupType = PolicyGroupType.SIMPLE_DETECTION
    optimization_phase: OptimizationPhase = OptimizationPhase.GROUPING
    grouping_method: GroupingMethod = GroupingMethod.COMPLEXITY_BASED
    reward: float = 0.0
    complexity_score: float = 0.0
    group_id: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyOptimizerAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    group_type: PolicyGroupType = PolicyGroupType.SIMPLE_DETECTION
    optimization_phase: OptimizationPhase = OptimizationPhase.GROUPING
    group_baseline: float = 0.0
    advantage_estimate: float = 0.0
    is_beneficial: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyOptimizerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_reward: float = 0.0
    by_group_type: dict[str, int] = Field(default_factory=dict)
    by_optimization_phase: dict[str, int] = Field(default_factory=dict)
    by_grouping_method: dict[str, int] = Field(default_factory=dict)
    top_groups: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class HopGroupedPolicyOptimizerEngine:
    """HRPO-style grouping for security policy optimization."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[PolicyOptimizerRecord] = []
        self._analyses: dict[str, PolicyOptimizerAnalysis] = {}
        logger.info(
            "hop_grouped_policy_optimizer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        task_id: str = "",
        group_type: PolicyGroupType = PolicyGroupType.SIMPLE_DETECTION,
        optimization_phase: OptimizationPhase = OptimizationPhase.GROUPING,
        grouping_method: GroupingMethod = GroupingMethod.COMPLEXITY_BASED,
        reward: float = 0.0,
        complexity_score: float = 0.0,
        group_id: str = "",
        description: str = "",
    ) -> PolicyOptimizerRecord:
        record = PolicyOptimizerRecord(
            task_id=task_id,
            group_type=group_type,
            optimization_phase=optimization_phase,
            grouping_method=grouping_method,
            reward=reward,
            complexity_score=complexity_score,
            group_id=group_id,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "hop_grouped_policy_optimizer.record_added",
            record_id=record.id,
            task_id=task_id,
        )
        return record

    def process(self, key: str) -> PolicyOptimizerAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        group_records = [r for r in self._records if r.group_id == rec.group_id]
        baseline = (
            sum(r.reward for r in group_records) / len(group_records) if group_records else 0.0
        )
        advantage = round(rec.reward - baseline, 4)
        analysis = PolicyOptimizerAnalysis(
            task_id=rec.task_id,
            group_type=rec.group_type,
            optimization_phase=rec.optimization_phase,
            group_baseline=round(baseline, 4),
            advantage_estimate=advantage,
            is_beneficial=advantage > 0,
            description=(
                f"Task {rec.task_id} advantage {advantage:.4f} vs baseline {baseline:.4f}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> PolicyOptimizerReport:
        by_gt: dict[str, int] = {}
        by_op: dict[str, int] = {}
        by_gm: dict[str, int] = {}
        rewards: list[float] = []
        for r in self._records:
            k = r.group_type.value
            by_gt[k] = by_gt.get(k, 0) + 1
            k2 = r.optimization_phase.value
            by_op[k2] = by_op.get(k2, 0) + 1
            k3 = r.grouping_method.value
            by_gm[k3] = by_gm.get(k3, 0) + 1
            rewards.append(r.reward)
        avg_reward = round(sum(rewards) / len(rewards), 4) if rewards else 0.0
        group_reward: dict[str, float] = {}
        for r in self._records:
            group_reward[r.group_id] = group_reward.get(r.group_id, 0.0) + r.reward
        sorted_groups = sorted(group_reward.keys(), key=lambda x: group_reward[x], reverse=True)
        top_groups = sorted_groups[:10]
        recs: list[str] = []
        if by_gt.get(PolicyGroupType.ADVANCED_PERSISTENT, 0) > 0:
            recs.append("Advanced persistent tasks detected — review grouping strategy")
        if not recs:
            recs.append("Policy optimization within expected parameters")
        return PolicyOptimizerReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_reward=avg_reward,
            by_group_type=by_gt,
            by_optimization_phase=by_op,
            by_grouping_method=by_gm,
            top_groups=top_groups,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            k = r.optimization_phase.value
            phase_dist[k] = phase_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "phase_distribution": phase_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("hop_grouped_policy_optimizer.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def group_tasks_by_complexity(self) -> list[dict[str, Any]]:
        """Group tasks by their structural complexity score."""
        groups: dict[PolicyGroupType, list[PolicyOptimizerRecord]] = {}
        for r in self._records:
            groups.setdefault(r.group_type, []).append(r)
        results: list[dict[str, Any]] = []
        for gtype, members in groups.items():
            avg_complexity = sum(m.complexity_score for m in members) / len(members)
            avg_reward = sum(m.reward for m in members) / len(members)
            results.append(
                {
                    "group_type": gtype.value,
                    "task_count": len(members),
                    "avg_complexity": round(avg_complexity, 4),
                    "avg_reward": round(avg_reward, 4),
                    "task_ids": [m.task_id for m in members[:5]],
                }
            )
        results.sort(key=lambda x: x["avg_complexity"], reverse=True)
        return results

    def compute_group_baselines(self) -> dict[str, float]:
        """Compute mean reward baseline per group_id."""
        group_rewards: dict[str, list[float]] = {}
        for r in self._records:
            group_rewards.setdefault(r.group_id, []).append(r.reward)
        baselines: dict[str, float] = {}
        for gid, rwds in group_rewards.items():
            baselines[gid] = round(sum(rwds) / len(rwds), 4)
        return baselines

    def compare_grouped_vs_flat(self) -> dict[str, Any]:
        """Compare grouped policy optimization vs flat (ungrouped) approach."""
        if not self._records:
            return {"grouped_avg": 0.0, "flat_avg": 0.0, "improvement_pct": 0.0}
        group_rewards: dict[str, list[float]] = {}
        for r in self._records:
            group_rewards.setdefault(r.group_id, []).append(r.reward)
        group_avgs = [sum(rwds) / len(rwds) for rwds in group_rewards.values() if rwds]
        grouped_avg = round(sum(group_avgs) / len(group_avgs), 4) if group_avgs else 0.0
        flat_avg = round(sum(r.reward for r in self._records) / len(self._records), 4)
        improvement_pct = (
            round((grouped_avg - flat_avg) / abs(flat_avg) * 100, 2) if flat_avg != 0.0 else 0.0
        )
        return {
            "grouped_avg": grouped_avg,
            "flat_avg": flat_avg,
            "improvement_pct": improvement_pct,
            "num_groups": len(group_rewards),
        }
