"""Group Baseline Estimator Engine —
computes group-level baselines for advantage estimation,
evaluates staleness, compares baseline methods."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BaselineMethod(StrEnum):
    GROUP_MEAN = "group_mean"
    GROUP_MEDIAN = "group_median"
    EXPONENTIAL_DECAY = "exponential_decay"
    WINDOWED = "windowed"


class GroupSize(StrEnum):
    SMALL_GROUP = "small_group"
    MEDIUM_GROUP = "medium_group"
    LARGE_GROUP = "large_group"
    FULL_BATCH = "full_batch"


class UpdateFrequency(StrEnum):
    PER_BATCH = "per_batch"
    PER_EPOCH = "per_epoch"
    PER_GROUP_FILL = "per_group_fill"
    CONTINUOUS = "continuous"


# --- Models ---


class BaselineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_id: str = ""
    task_id: str = ""
    baseline_method: BaselineMethod = BaselineMethod.GROUP_MEAN
    group_size: GroupSize = GroupSize.MEDIUM_GROUP
    update_frequency: UpdateFrequency = UpdateFrequency.PER_BATCH
    reward: float = 0.0
    baseline_value: float = 0.0
    staleness_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BaselineAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_id: str = ""
    task_id: str = ""
    baseline_method: BaselineMethod = BaselineMethod.GROUP_MEAN
    computed_baseline: float = 0.0
    advantage: float = 0.0
    is_stale: bool = False
    staleness_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BaselineReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_baseline_value: float = 0.0
    avg_staleness_score: float = 0.0
    by_baseline_method: dict[str, int] = Field(default_factory=dict)
    by_group_size: dict[str, int] = Field(default_factory=dict)
    by_update_frequency: dict[str, int] = Field(default_factory=dict)
    stale_groups: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class GroupBaselineEstimatorEngine:
    """Computes group-level baselines for advantage estimation."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[BaselineRecord] = []
        self._analyses: dict[str, BaselineAnalysis] = {}
        logger.info(
            "group_baseline_estimator_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        group_id: str = "",
        task_id: str = "",
        baseline_method: BaselineMethod = BaselineMethod.GROUP_MEAN,
        group_size: GroupSize = GroupSize.MEDIUM_GROUP,
        update_frequency: UpdateFrequency = UpdateFrequency.PER_BATCH,
        reward: float = 0.0,
        baseline_value: float = 0.0,
        staleness_score: float = 0.0,
        description: str = "",
    ) -> BaselineRecord:
        record = BaselineRecord(
            group_id=group_id,
            task_id=task_id,
            baseline_method=baseline_method,
            group_size=group_size,
            update_frequency=update_frequency,
            reward=reward,
            baseline_value=baseline_value,
            staleness_score=staleness_score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "group_baseline_estimator.record_added",
            record_id=record.id,
            group_id=group_id,
        )
        return record

    def process(self, key: str) -> BaselineAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        group_recs = [r for r in self._records if r.group_id == rec.group_id]
        rewards = [r.reward for r in group_recs]
        if rec.baseline_method == BaselineMethod.GROUP_MEDIAN:
            sorted_rewards = sorted(rewards)
            n = len(sorted_rewards)
            computed = (
                (sorted_rewards[n // 2 - 1] + sorted_rewards[n // 2]) / 2
                if n % 2 == 0
                else sorted_rewards[n // 2]
            )
        else:
            computed = sum(rewards) / len(rewards) if rewards else 0.0
        advantage = round(rec.reward - computed, 4)
        analysis = BaselineAnalysis(
            group_id=rec.group_id,
            task_id=rec.task_id,
            baseline_method=rec.baseline_method,
            computed_baseline=round(computed, 4),
            advantage=advantage,
            is_stale=rec.staleness_score > 0.5,
            staleness_score=rec.staleness_score,
            description=(
                f"Group {rec.group_id} baseline {computed:.4f}, advantage {advantage:.4f}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> BaselineReport:
        by_bm: dict[str, int] = {}
        by_gs: dict[str, int] = {}
        by_uf: dict[str, int] = {}
        baselines: list[float] = []
        staleness: list[float] = []
        for r in self._records:
            k = r.baseline_method.value
            by_bm[k] = by_bm.get(k, 0) + 1
            k2 = r.group_size.value
            by_gs[k2] = by_gs.get(k2, 0) + 1
            k3 = r.update_frequency.value
            by_uf[k3] = by_uf.get(k3, 0) + 1
            baselines.append(r.baseline_value)
            staleness.append(r.staleness_score)
        avg_baseline = round(sum(baselines) / len(baselines), 4) if baselines else 0.0
        avg_staleness = round(sum(staleness) / len(staleness), 4) if staleness else 0.0
        stale_groups = list({r.group_id for r in self._records if r.staleness_score > 0.5})[:10]
        recs_list: list[str] = []
        if stale_groups:
            recs_list.append(f"{len(stale_groups)} groups with stale baselines")
        if not recs_list:
            recs_list.append("Group baselines are up-to-date")
        return BaselineReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_baseline_value=avg_baseline,
            avg_staleness_score=avg_staleness,
            by_baseline_method=by_bm,
            by_group_size=by_gs,
            by_update_frequency=by_uf,
            stale_groups=stale_groups,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        method_dist: dict[str, int] = {}
        for r in self._records:
            k = r.baseline_method.value
            method_dist[k] = method_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "baseline_method_distribution": method_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("group_baseline_estimator_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_group_baselines(self) -> list[dict[str, Any]]:
        """Compute mean reward baseline per group."""
        group_data: dict[str, list[float]] = {}
        for r in self._records:
            group_data.setdefault(r.group_id, []).append(r.reward)
        results: list[dict[str, Any]] = []
        for gid, rewards in group_data.items():
            mean_r = sum(rewards) / len(rewards)
            results.append(
                {
                    "group_id": gid,
                    "mean_baseline": round(mean_r, 4),
                    "sample_count": len(rewards),
                    "min_reward": round(min(rewards), 4),
                    "max_reward": round(max(rewards), 4),
                }
            )
        results.sort(key=lambda x: x["mean_baseline"], reverse=True)
        return results

    def evaluate_baseline_staleness(self) -> list[dict[str, Any]]:
        """Evaluate baseline staleness per group."""
        group_data: dict[str, list[float]] = {}
        for r in self._records:
            group_data.setdefault(r.group_id, []).append(r.staleness_score)
        results: list[dict[str, Any]] = []
        for gid, staleness_vals in group_data.items():
            mean_s = sum(staleness_vals) / len(staleness_vals)
            results.append(
                {
                    "group_id": gid,
                    "mean_staleness": round(mean_s, 4),
                    "is_stale": mean_s > 0.5,
                    "sample_count": len(staleness_vals),
                }
            )
        results.sort(key=lambda x: x["mean_staleness"], reverse=True)
        return results

    def compare_baseline_methods(self) -> list[dict[str, Any]]:
        """Compare baseline values produced by each method."""
        method_data: dict[str, list[float]] = {}
        for r in self._records:
            method_data.setdefault(r.baseline_method.value, []).append(r.baseline_value)
        results: list[dict[str, Any]] = []
        for method, vals in method_data.items():
            mean_v = sum(vals) / len(vals)
            results.append(
                {
                    "method": method,
                    "mean_baseline": round(mean_v, 4),
                    "min_baseline": round(min(vals), 4),
                    "max_baseline": round(max(vals), 4),
                    "sample_count": len(vals),
                }
            )
        results.sort(key=lambda x: x["mean_baseline"], reverse=True)
        return results
