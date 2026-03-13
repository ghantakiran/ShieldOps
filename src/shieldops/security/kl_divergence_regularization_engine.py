"""KL Divergence Regularization Engine —
manages KL divergence penalty for policy stability,
computes divergence, adjusts penalty, detects policy drift."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RegularizationStrength(StrEnum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    ADAPTIVE = "adaptive"


class DivergenceLevel(StrEnum):
    MINIMAL = "minimal"
    ACCEPTABLE = "acceptable"
    HIGH = "high"
    EXCESSIVE = "excessive"


class ReferencePolicy(StrEnum):
    INITIAL = "initial"
    BEST_SO_FAR = "best_so_far"
    MOVING_AVERAGE = "moving_average"
    ENSEMBLE = "ensemble"


# --- Models ---


class KLDivergenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    regularization_strength: RegularizationStrength = RegularizationStrength.MODERATE
    divergence_level: DivergenceLevel = DivergenceLevel.MINIMAL
    reference_policy: ReferencePolicy = ReferencePolicy.INITIAL
    kl_value: float = 0.0
    penalty_coefficient: float = 0.0
    policy_step: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KLDivergenceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    regularization_strength: RegularizationStrength = RegularizationStrength.MODERATE
    divergence_level: DivergenceLevel = DivergenceLevel.MINIMAL
    adjusted_penalty: float = 0.0
    is_drifting: bool = False
    recommended_strength: RegularizationStrength = RegularizationStrength.MODERATE
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KLDivergenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_kl_value: float = 0.0
    by_regularization_strength: dict[str, int] = Field(default_factory=dict)
    by_divergence_level: dict[str, int] = Field(default_factory=dict)
    by_reference_policy: dict[str, int] = Field(default_factory=dict)
    drifting_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class KLDivergenceRegularizationEngine:
    """Manages KL divergence penalty for policy stability."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[KLDivergenceRecord] = []
        self._analyses: dict[str, KLDivergenceAnalysis] = {}
        logger.info(
            "kl_divergence_regularization_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        regularization_strength: RegularizationStrength = RegularizationStrength.MODERATE,
        divergence_level: DivergenceLevel = DivergenceLevel.MINIMAL,
        reference_policy: ReferencePolicy = ReferencePolicy.INITIAL,
        kl_value: float = 0.0,
        penalty_coefficient: float = 0.0,
        policy_step: int = 0,
        description: str = "",
    ) -> KLDivergenceRecord:
        record = KLDivergenceRecord(
            agent_id=agent_id,
            regularization_strength=regularization_strength,
            divergence_level=divergence_level,
            reference_policy=reference_policy,
            kl_value=kl_value,
            penalty_coefficient=penalty_coefficient,
            policy_step=policy_step,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "kl_divergence_regularization.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> KLDivergenceAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        strength_multipliers = {
            RegularizationStrength.WEAK: 0.5,
            RegularizationStrength.MODERATE: 1.0,
            RegularizationStrength.STRONG: 2.0,
            RegularizationStrength.ADAPTIVE: 1.5,
        }
        mult = strength_multipliers.get(rec.regularization_strength, 1.0)
        adjusted = round(rec.penalty_coefficient * mult, 4)
        is_drifting = rec.divergence_level in (DivergenceLevel.HIGH, DivergenceLevel.EXCESSIVE)
        recommended = RegularizationStrength.STRONG if is_drifting else rec.regularization_strength
        analysis = KLDivergenceAnalysis(
            agent_id=rec.agent_id,
            regularization_strength=rec.regularization_strength,
            divergence_level=rec.divergence_level,
            adjusted_penalty=adjusted,
            is_drifting=is_drifting,
            recommended_strength=recommended,
            description=(
                f"Agent {rec.agent_id} KL {rec.kl_value:.4f}, adjusted penalty {adjusted:.4f}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> KLDivergenceReport:
        by_rs: dict[str, int] = {}
        by_dl: dict[str, int] = {}
        by_rp: dict[str, int] = {}
        kl_values: list[float] = []
        for r in self._records:
            k = r.regularization_strength.value
            by_rs[k] = by_rs.get(k, 0) + 1
            k2 = r.divergence_level.value
            by_dl[k2] = by_dl.get(k2, 0) + 1
            k3 = r.reference_policy.value
            by_rp[k3] = by_rp.get(k3, 0) + 1
            kl_values.append(r.kl_value)
        avg_kl = round(sum(kl_values) / len(kl_values), 4) if kl_values else 0.0
        drifting = list(
            {
                r.agent_id
                for r in self._records
                if r.divergence_level in (DivergenceLevel.HIGH, DivergenceLevel.EXCESSIVE)
            }
        )[:10]
        recs_list: list[str] = []
        if drifting:
            recs_list.append(f"{len(drifting)} agents showing excessive KL divergence")
        if not recs_list:
            recs_list.append("KL divergence within acceptable bounds")
        return KLDivergenceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_kl_value=avg_kl,
            by_regularization_strength=by_rs,
            by_divergence_level=by_dl,
            by_reference_policy=by_rp,
            drifting_agents=drifting,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            k = r.divergence_level.value
            level_dist[k] = level_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "divergence_level_distribution": level_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("kl_divergence_regularization_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_kl_divergence(self) -> list[dict[str, Any]]:
        """Compute mean KL divergence per agent."""
        agent_data: dict[str, list[float]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r.kl_value)
        results: list[dict[str, Any]] = []
        for agent_id, kl_vals in agent_data.items():
            mean_kl = sum(kl_vals) / len(kl_vals)
            results.append(
                {
                    "agent_id": agent_id,
                    "mean_kl": round(mean_kl, 4),
                    "max_kl": round(max(kl_vals), 4),
                    "sample_count": len(kl_vals),
                }
            )
        results.sort(key=lambda x: x["mean_kl"], reverse=True)
        return results

    def adjust_kl_penalty(self) -> list[dict[str, Any]]:
        """Recommend adjusted KL penalty coefficients per agent."""
        agent_data: dict[str, list[KLDivergenceRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for agent_id, recs in agent_data.items():
            latest = max(recs, key=lambda x: x.policy_step)
            is_excessive = latest.divergence_level == DivergenceLevel.EXCESSIVE
            suggested = (
                round(latest.penalty_coefficient * 1.5, 4)
                if is_excessive
                else (
                    round(latest.penalty_coefficient * 0.8, 4)
                    if latest.divergence_level == DivergenceLevel.MINIMAL
                    else latest.penalty_coefficient
                )
            )
            results.append(
                {
                    "agent_id": agent_id,
                    "current_penalty": latest.penalty_coefficient,
                    "suggested_penalty": suggested,
                    "divergence_level": latest.divergence_level.value,
                }
            )
        results.sort(key=lambda x: x["suggested_penalty"], reverse=True)
        return results

    def detect_policy_drift(self) -> list[dict[str, Any]]:
        """Detect agents drifting beyond acceptable KL thresholds."""
        agent_data: dict[str, list[float]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r.kl_value)
        results: list[dict[str, Any]] = []
        for agent_id, kl_vals in agent_data.items():
            mean_kl = sum(kl_vals) / len(kl_vals)
            is_drifting = mean_kl > 0.5
            results.append(
                {
                    "agent_id": agent_id,
                    "mean_kl": round(mean_kl, 4),
                    "is_drifting": is_drifting,
                    "drift_severity": (
                        "high" if mean_kl > 1.0 else "moderate" if mean_kl > 0.5 else "low"
                    ),
                }
            )
        results.sort(key=lambda x: x["mean_kl"], reverse=True)
        return results
