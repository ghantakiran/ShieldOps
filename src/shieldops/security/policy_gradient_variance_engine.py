"""Policy Gradient Variance Engine —
reduces policy gradient variance through hop-grouping,
measures, decomposes, and applies variance reduction techniques."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VarianceSource(StrEnum):
    REWARD_NOISE = "reward_noise"
    GROUP_HETEROGENEITY = "group_heterogeneity"
    SAMPLE_BIAS = "sample_bias"
    TEMPORAL_SHIFT = "temporal_shift"


class ReductionTechnique(StrEnum):
    HOP_GROUPING = "hop_grouping"
    BASELINE_SUBTRACTION = "baseline_subtraction"
    REWARD_NORMALIZATION = "reward_normalization"
    CLIPPING = "clipping"


class VarianceLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# --- Models ---


class GradientVarianceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    group_id: str = ""
    variance_source: VarianceSource = VarianceSource.REWARD_NOISE
    reduction_technique: ReductionTechnique = ReductionTechnique.HOP_GROUPING
    variance_level: VarianceLevel = VarianceLevel.LOW
    raw_variance: float = 0.0
    reduced_variance: float = 0.0
    reward: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class GradientVarianceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    group_id: str = ""
    variance_source: VarianceSource = VarianceSource.REWARD_NOISE
    reduction_technique: ReductionTechnique = ReductionTechnique.HOP_GROUPING
    variance_reduction_pct: float = 0.0
    variance_level: VarianceLevel = VarianceLevel.LOW
    is_effective: bool = True
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class GradientVarianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_raw_variance: float = 0.0
    avg_reduced_variance: float = 0.0
    by_variance_source: dict[str, int] = Field(default_factory=dict)
    by_reduction_technique: dict[str, int] = Field(default_factory=dict)
    by_variance_level: dict[str, int] = Field(default_factory=dict)
    high_variance_groups: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PolicyGradientVarianceEngine:
    """Reduces policy gradient variance through hop-grouping."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[GradientVarianceRecord] = []
        self._analyses: dict[str, GradientVarianceAnalysis] = {}
        logger.info(
            "policy_gradient_variance_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        task_id: str = "",
        group_id: str = "",
        variance_source: VarianceSource = VarianceSource.REWARD_NOISE,
        reduction_technique: ReductionTechnique = ReductionTechnique.HOP_GROUPING,
        variance_level: VarianceLevel = VarianceLevel.LOW,
        raw_variance: float = 0.0,
        reduced_variance: float = 0.0,
        reward: float = 0.0,
        description: str = "",
    ) -> GradientVarianceRecord:
        record = GradientVarianceRecord(
            task_id=task_id,
            group_id=group_id,
            variance_source=variance_source,
            reduction_technique=reduction_technique,
            variance_level=variance_level,
            raw_variance=raw_variance,
            reduced_variance=reduced_variance,
            reward=reward,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "policy_gradient_variance.record_added",
            record_id=record.id,
            task_id=task_id,
        )
        return record

    def process(self, key: str) -> GradientVarianceAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        reduction_pct = (
            round((rec.raw_variance - rec.reduced_variance) / rec.raw_variance * 100, 2)
            if rec.raw_variance > 0.0
            else 0.0
        )
        analysis = GradientVarianceAnalysis(
            task_id=rec.task_id,
            group_id=rec.group_id,
            variance_source=rec.variance_source,
            reduction_technique=rec.reduction_technique,
            variance_reduction_pct=reduction_pct,
            variance_level=rec.variance_level,
            is_effective=reduction_pct > 10.0,
            description=(f"Task {rec.task_id} variance reduced by {reduction_pct:.2f}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> GradientVarianceReport:
        by_vs: dict[str, int] = {}
        by_rt: dict[str, int] = {}
        by_vl: dict[str, int] = {}
        raw_vars: list[float] = []
        red_vars: list[float] = []
        for r in self._records:
            k = r.variance_source.value
            by_vs[k] = by_vs.get(k, 0) + 1
            k2 = r.reduction_technique.value
            by_rt[k2] = by_rt.get(k2, 0) + 1
            k3 = r.variance_level.value
            by_vl[k3] = by_vl.get(k3, 0) + 1
            raw_vars.append(r.raw_variance)
            red_vars.append(r.reduced_variance)
        avg_raw = round(sum(raw_vars) / len(raw_vars), 4) if raw_vars else 0.0
        avg_red = round(sum(red_vars) / len(red_vars), 4) if red_vars else 0.0
        high_var_groups = list(
            {
                r.group_id
                for r in self._records
                if r.variance_level in (VarianceLevel.HIGH, VarianceLevel.CRITICAL)
            }
        )[:10]
        recs_list: list[str] = []
        if high_var_groups:
            recs_list.append(f"{len(high_var_groups)} groups with high/critical gradient variance")
        if not recs_list:
            recs_list.append("Gradient variance within acceptable limits")
        return GradientVarianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_raw_variance=avg_raw,
            avg_reduced_variance=avg_red,
            by_variance_source=by_vs,
            by_reduction_technique=by_rt,
            by_variance_level=by_vl,
            high_variance_groups=high_var_groups,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        source_dist: dict[str, int] = {}
        for r in self._records:
            k = r.variance_source.value
            source_dist[k] = source_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "variance_source_distribution": source_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("policy_gradient_variance_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def measure_gradient_variance(self) -> list[dict[str, Any]]:
        """Measure gradient variance per group."""
        group_data: dict[str, list[float]] = {}
        for r in self._records:
            group_data.setdefault(r.group_id, []).append(r.raw_variance)
        results: list[dict[str, Any]] = []
        for gid, variances in group_data.items():
            mean_v = sum(variances) / len(variances)
            results.append(
                {
                    "group_id": gid,
                    "mean_variance": round(mean_v, 6),
                    "max_variance": round(max(variances), 6),
                    "sample_count": len(variances),
                }
            )
        results.sort(key=lambda x: x["mean_variance"], reverse=True)
        return results

    def decompose_variance_sources(self) -> dict[str, float]:
        """Decompose total variance by source type."""
        source_totals: dict[str, float] = {}
        for r in self._records:
            key = r.variance_source.value
            source_totals[key] = source_totals.get(key, 0.0) + r.raw_variance
        total = sum(source_totals.values())
        if total == 0.0:
            return source_totals
        return {src: round(v / total * 100, 2) for src, v in source_totals.items()}

    def apply_variance_reduction(self) -> list[dict[str, Any]]:
        """Summarize effectiveness of each reduction technique."""
        tech_data: dict[str, list[tuple[float, float]]] = {}
        for r in self._records:
            tech_data.setdefault(r.reduction_technique.value, []).append(
                (r.raw_variance, r.reduced_variance)
            )
        results: list[dict[str, Any]] = []
        for tech, pairs in tech_data.items():
            avg_raw = sum(p[0] for p in pairs) / len(pairs)
            avg_red = sum(p[1] for p in pairs) / len(pairs)
            pct = round((avg_raw - avg_red) / avg_raw * 100, 2) if avg_raw > 0 else 0.0
            results.append(
                {
                    "technique": tech,
                    "avg_raw_variance": round(avg_raw, 6),
                    "avg_reduced_variance": round(avg_red, 6),
                    "reduction_pct": pct,
                    "sample_count": len(pairs),
                }
            )
        results.sort(key=lambda x: x["reduction_pct"], reverse=True)
        return results
