"""Advantage Estimation Engine —
computes advantage estimates from group-level statistics,
analyzes stability, and visualizes the advantage landscape."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EstimationMethod(StrEnum):
    GROUP_RELATIVE = "group_relative"
    GLOBAL_RELATIVE = "global_relative"
    GAE = "gae"
    TEMPORAL_DIFFERENCE = "temporal_difference"


class AdvantageSign(StrEnum):
    POSITIVE = "positive"
    NEAR_ZERO = "near_zero"
    NEGATIVE = "negative"
    HIGHLY_POSITIVE = "highly_positive"


class BaselineType(StrEnum):
    GROUP_MEAN = "group_mean"
    RUNNING_AVERAGE = "running_average"
    EXPONENTIAL_MOVING = "exponential_moving"
    MEDIAN = "median"


# --- Models ---


class AdvantageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    group_id: str = ""
    estimation_method: EstimationMethod = EstimationMethod.GROUP_RELATIVE
    advantage_sign: AdvantageSign = AdvantageSign.NEAR_ZERO
    baseline_type: BaselineType = BaselineType.GROUP_MEAN
    reward: float = 0.0
    baseline_value: float = 0.0
    advantage_value: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AdvantageAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    group_id: str = ""
    estimation_method: EstimationMethod = EstimationMethod.GROUP_RELATIVE
    computed_advantage: float = 0.0
    advantage_sign: AdvantageSign = AdvantageSign.NEAR_ZERO
    variance: float = 0.0
    is_stable: bool = True
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AdvantageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_advantage: float = 0.0
    by_estimation_method: dict[str, int] = Field(default_factory=dict)
    by_advantage_sign: dict[str, int] = Field(default_factory=dict)
    by_baseline_type: dict[str, int] = Field(default_factory=dict)
    unstable_groups: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AdvantageEstimationEngine:
    """Computes advantage estimates from group-level statistics."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AdvantageRecord] = []
        self._analyses: dict[str, AdvantageAnalysis] = {}
        logger.info(
            "advantage_estimation_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        task_id: str = "",
        group_id: str = "",
        estimation_method: EstimationMethod = EstimationMethod.GROUP_RELATIVE,
        advantage_sign: AdvantageSign = AdvantageSign.NEAR_ZERO,
        baseline_type: BaselineType = BaselineType.GROUP_MEAN,
        reward: float = 0.0,
        baseline_value: float = 0.0,
        advantage_value: float = 0.0,
        description: str = "",
    ) -> AdvantageRecord:
        record = AdvantageRecord(
            task_id=task_id,
            group_id=group_id,
            estimation_method=estimation_method,
            advantage_sign=advantage_sign,
            baseline_type=baseline_type,
            reward=reward,
            baseline_value=baseline_value,
            advantage_value=advantage_value,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "advantage_estimation.record_added",
            record_id=record.id,
            task_id=task_id,
        )
        return record

    def process(self, key: str) -> AdvantageAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        group_recs = [r for r in self._records if r.group_id == rec.group_id]
        adv_values = [r.advantage_value for r in group_recs]
        mean_adv = sum(adv_values) / len(adv_values) if adv_values else 0.0
        variance = (
            sum((v - mean_adv) ** 2 for v in adv_values) / len(adv_values) if adv_values else 0.0
        )
        computed = round(rec.reward - rec.baseline_value, 4)
        if computed > 1.0:
            sign = AdvantageSign.HIGHLY_POSITIVE
        elif computed > 0.0:
            sign = AdvantageSign.POSITIVE
        elif computed < 0.0:
            sign = AdvantageSign.NEGATIVE
        else:
            sign = AdvantageSign.NEAR_ZERO
        analysis = AdvantageAnalysis(
            task_id=rec.task_id,
            group_id=rec.group_id,
            estimation_method=rec.estimation_method,
            computed_advantage=computed,
            advantage_sign=sign,
            variance=round(variance, 6),
            is_stable=variance < 1.0,
            description=(f"Task {rec.task_id} advantage {computed:.4f}, variance {variance:.6f}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> AdvantageReport:
        by_em: dict[str, int] = {}
        by_as: dict[str, int] = {}
        by_bt: dict[str, int] = {}
        advantages: list[float] = []
        for r in self._records:
            k = r.estimation_method.value
            by_em[k] = by_em.get(k, 0) + 1
            k2 = r.advantage_sign.value
            by_as[k2] = by_as.get(k2, 0) + 1
            k3 = r.baseline_type.value
            by_bt[k3] = by_bt.get(k3, 0) + 1
            advantages.append(r.advantage_value)
        avg_adv = round(sum(advantages) / len(advantages), 4) if advantages else 0.0
        unstable: list[str] = []
        for a in self._analyses.values():
            if not a.is_stable and a.group_id not in unstable:
                unstable.append(a.group_id)
        recs_list: list[str] = []
        if unstable:
            recs_list.append(f"{len(unstable)} groups show high advantage variance")
        if not recs_list:
            recs_list.append("Advantage estimates are stable across groups")
        return AdvantageReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_advantage=avg_adv,
            by_estimation_method=by_em,
            by_advantage_sign=by_as,
            by_baseline_type=by_bt,
            unstable_groups=unstable[:10],
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        method_dist: dict[str, int] = {}
        for r in self._records:
            k = r.estimation_method.value
            method_dist[k] = method_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "method_distribution": method_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("advantage_estimation_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_group_advantages(self) -> list[dict[str, Any]]:
        """Compute mean advantage per group using stored baseline values."""
        group_data: dict[str, list[float]] = {}
        for r in self._records:
            adv = r.reward - r.baseline_value
            group_data.setdefault(r.group_id, []).append(adv)
        results: list[dict[str, Any]] = []
        for gid, advs in group_data.items():
            mean_adv = sum(advs) / len(advs)
            results.append(
                {
                    "group_id": gid,
                    "mean_advantage": round(mean_adv, 4),
                    "sample_count": len(advs),
                    "positive_frac": round(sum(1 for a in advs if a > 0) / len(advs), 4),
                }
            )
        results.sort(key=lambda x: x["mean_advantage"], reverse=True)
        return results

    def analyze_advantage_stability(self) -> list[dict[str, Any]]:
        """Analyze variance of advantage values per group."""
        group_data: dict[str, list[float]] = {}
        for r in self._records:
            adv = r.reward - r.baseline_value
            group_data.setdefault(r.group_id, []).append(adv)
        results: list[dict[str, Any]] = []
        for gid, advs in group_data.items():
            mean_adv = sum(advs) / len(advs)
            variance = sum((a - mean_adv) ** 2 for a in advs) / len(advs)
            results.append(
                {
                    "group_id": gid,
                    "variance": round(variance, 6),
                    "is_stable": variance < 1.0,
                    "sample_count": len(advs),
                }
            )
        results.sort(key=lambda x: x["variance"], reverse=True)
        return results

    def visualize_advantage_landscape(self) -> dict[str, Any]:
        """Summarize the advantage landscape across estimation methods."""
        method_advantages: dict[str, list[float]] = {}
        for r in self._records:
            adv = r.reward - r.baseline_value
            method_advantages.setdefault(r.estimation_method.value, []).append(adv)
        landscape: dict[str, dict[str, float]] = {}
        for method, advs in method_advantages.items():
            if not advs:
                continue
            mean_v = sum(advs) / len(advs)
            landscape[method] = {
                "mean": round(mean_v, 4),
                "min": round(min(advs), 4),
                "max": round(max(advs), 4),
                "count": float(len(advs)),
            }
        return {"landscape": landscape, "total_methods": len(landscape)}
