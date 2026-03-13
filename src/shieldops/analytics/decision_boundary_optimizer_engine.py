"""Decision Boundary Optimizer Engine —
evaluate boundary quality, detect boundary drift,
and optimize decision thresholds for agents."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BoundaryType(StrEnum):
    LINEAR = "linear"
    NONLINEAR = "nonlinear"
    ENSEMBLE = "ensemble"
    ADAPTIVE = "adaptive"


class OptimizationMethod(StrEnum):
    GRADIENT = "gradient"
    EVOLUTIONARY = "evolutionary"
    BAYESIAN = "bayesian"
    REINFORCEMENT = "reinforcement"


class BoundaryQuality(StrEnum):
    SHARP = "sharp"
    FUZZY = "fuzzy"
    NOISY = "noisy"
    OPTIMAL = "optimal"


# --- Models ---


class DecisionBoundaryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    boundary_type: BoundaryType = BoundaryType.ADAPTIVE
    optimization_method: OptimizationMethod = OptimizationMethod.BAYESIAN
    boundary_quality: BoundaryQuality = BoundaryQuality.SHARP
    accuracy_score: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DecisionBoundaryAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    avg_accuracy: float = 0.0
    dominant_boundary_type: BoundaryType = BoundaryType.ADAPTIVE
    best_method: OptimizationMethod = OptimizationMethod.BAYESIAN
    avg_fpr: float = 0.0
    record_count: int = 0
    boundary_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DecisionBoundaryReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_accuracy_score: float = 0.0
    by_boundary_type: dict[str, int] = Field(default_factory=dict)
    by_optimization_method: dict[str, int] = Field(default_factory=dict)
    by_boundary_quality: dict[str, int] = Field(default_factory=dict)
    top_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DecisionBoundaryOptimizerEngine:
    """Optimize agent decision boundaries, detect boundary drift,
    and tune decision thresholds for maximal accuracy."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[DecisionBoundaryRecord] = []
        self._analyses: dict[str, DecisionBoundaryAnalysis] = {}
        logger.info(
            "decision_boundary_optimizer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        boundary_type: BoundaryType = BoundaryType.ADAPTIVE,
        optimization_method: OptimizationMethod = OptimizationMethod.BAYESIAN,
        boundary_quality: BoundaryQuality = BoundaryQuality.SHARP,
        accuracy_score: float = 0.0,
        false_positive_rate: float = 0.0,
        false_negative_rate: float = 0.0,
        description: str = "",
    ) -> DecisionBoundaryRecord:
        record = DecisionBoundaryRecord(
            agent_id=agent_id,
            boundary_type=boundary_type,
            optimization_method=optimization_method,
            boundary_quality=boundary_quality,
            accuracy_score=accuracy_score,
            false_positive_rate=false_positive_rate,
            false_negative_rate=false_negative_rate,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "decision_boundary.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> DecisionBoundaryAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        agent_recs = [r for r in self._records if r.agent_id == rec.agent_id]
        accs = [r.accuracy_score for r in agent_recs]
        fprs = [r.false_positive_rate for r in agent_recs]
        avg_acc = round(sum(accs) / len(accs), 2) if accs else 0.0
        avg_fpr = round(sum(fprs) / len(fprs), 4) if fprs else 0.0
        type_counts: dict[str, int] = {}
        method_accs: dict[str, list[float]] = {}
        for r in agent_recs:
            type_counts[r.boundary_type.value] = type_counts.get(r.boundary_type.value, 0) + 1
            method_accs.setdefault(r.optimization_method.value, []).append(r.accuracy_score)
        dominant_type = (
            BoundaryType(max(type_counts, key=lambda x: type_counts[x]))
            if type_counts
            else BoundaryType.ADAPTIVE
        )
        best_method_val = (
            max(
                method_accs,
                key=lambda x: sum(method_accs[x]) / len(method_accs[x]),
            )
            if method_accs
            else OptimizationMethod.BAYESIAN.value
        )
        best_method = OptimizationMethod(best_method_val)
        boundary_score = round(avg_acc * (1.0 - avg_fpr), 2)
        analysis = DecisionBoundaryAnalysis(
            agent_id=rec.agent_id,
            avg_accuracy=avg_acc,
            dominant_boundary_type=dominant_type,
            best_method=best_method,
            avg_fpr=avg_fpr,
            record_count=len(agent_recs),
            boundary_score=boundary_score,
            description=f"Agent {rec.agent_id} boundary score {boundary_score}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> DecisionBoundaryReport:
        by_bt: dict[str, int] = {}
        by_om: dict[str, int] = {}
        by_bq: dict[str, int] = {}
        accs: list[float] = []
        for r in self._records:
            by_bt[r.boundary_type.value] = by_bt.get(r.boundary_type.value, 0) + 1
            by_om[r.optimization_method.value] = by_om.get(r.optimization_method.value, 0) + 1
            by_bq[r.boundary_quality.value] = by_bq.get(r.boundary_quality.value, 0) + 1
            accs.append(r.accuracy_score)
        avg = round(sum(accs) / len(accs), 2) if accs else 0.0
        agent_totals: dict[str, float] = {}
        for r in self._records:
            agent_totals[r.agent_id] = agent_totals.get(r.agent_id, 0.0) + r.accuracy_score
        ranked = sorted(
            agent_totals,
            key=lambda x: agent_totals[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        noisy = by_bq.get("noisy", 0)
        if noisy > 0:
            recs.append(f"{noisy} noisy boundaries — apply smoothing or ensemble")
        fuzzy = by_bq.get("fuzzy", 0)
        if fuzzy > 0:
            recs.append(f"{fuzzy} fuzzy boundaries — increase training data density")
        if not recs:
            recs.append("Decision boundaries are well-optimized")
        return DecisionBoundaryReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_accuracy_score=avg,
            by_boundary_type=by_bt,
            by_optimization_method=by_om,
            by_boundary_quality=by_bq,
            top_agents=ranked,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            dist[r.boundary_type.value] = dist.get(r.boundary_type.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "boundary_type_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("decision_boundary_optimizer.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def evaluate_boundary_quality(self) -> list[dict[str, Any]]:
        """Evaluate decision boundary quality per agent."""
        agent_data: dict[str, list[DecisionBoundaryRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for aid, recs in agent_data.items():
            accs = [r.accuracy_score for r in recs]
            fprs = [r.false_positive_rate for r in recs]
            fnrs = [r.false_negative_rate for r in recs]
            avg_acc = round(sum(accs) / len(accs), 2) if accs else 0.0
            avg_fpr = round(sum(fprs) / len(fprs), 4) if fprs else 0.0
            avg_fnr = round(sum(fnrs) / len(fnrs), 4) if fnrs else 0.0
            quality_counts: dict[str, int] = {}
            for r in recs:
                quality_counts[r.boundary_quality.value] = (
                    quality_counts.get(r.boundary_quality.value, 0) + 1
                )
            f1_approx = round(2 * avg_acc / (avg_acc + avg_fpr + avg_fnr + 1e-9), 2)
            results.append(
                {
                    "agent_id": aid,
                    "avg_accuracy": avg_acc,
                    "avg_fpr": avg_fpr,
                    "avg_fnr": avg_fnr,
                    "f1_approx": f1_approx,
                    "quality_distribution": quality_counts,
                    "record_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["avg_accuracy"], reverse=True)
        return results

    def detect_boundary_drift(self) -> list[dict[str, Any]]:
        """Detect agents whose decision boundaries are drifting over time."""
        agent_data: dict[str, list[DecisionBoundaryRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for aid, recs in agent_data.items():
            if len(recs) < 2:
                continue
            accs = [r.accuracy_score for r in recs]
            fprs = [r.false_positive_rate for r in recs]
            acc_trend = accs[-1] - accs[0] if len(accs) > 1 else 0.0
            fpr_trend = fprs[-1] - fprs[0] if len(fprs) > 1 else 0.0
            is_drifting = abs(acc_trend) > 0.05 or fpr_trend > 0.05
            results.append(
                {
                    "agent_id": aid,
                    "accuracy_trend": round(acc_trend, 4),
                    "fpr_trend": round(fpr_trend, 4),
                    "is_drifting": is_drifting,
                    "drift_severity": (
                        "high" if abs(acc_trend) > 0.1 else "medium" if is_drifting else "low"
                    ),
                    "record_count": len(recs),
                }
            )
        results.sort(key=lambda x: abs(x["accuracy_trend"]), reverse=True)
        return results

    def optimize_decision_thresholds(self) -> list[dict[str, Any]]:
        """Recommend optimal decision thresholds per boundary type."""
        type_data: dict[str, list[DecisionBoundaryRecord]] = {}
        for r in self._records:
            type_data.setdefault(r.boundary_type.value, []).append(r)
        results: list[dict[str, Any]] = []
        for btype, recs in type_data.items():
            accs = [r.accuracy_score for r in recs]
            fprs = [r.false_positive_rate for r in recs]
            fnrs = [r.false_negative_rate for r in recs]
            avg_acc = round(sum(accs) / len(accs), 2) if accs else 0.0
            avg_fpr = round(sum(fprs) / len(fprs), 4) if fprs else 0.0
            avg_fnr = round(sum(fnrs) / len(fnrs), 4) if fnrs else 0.0
            if avg_fpr > avg_fnr:
                recommended_threshold = round(min(0.9, 0.5 + avg_fpr), 2)
                rationale = "Raise threshold to reduce false positives"
            elif avg_fnr > avg_fpr:
                recommended_threshold = round(max(0.1, 0.5 - avg_fnr), 2)
                rationale = "Lower threshold to reduce false negatives"
            else:
                recommended_threshold = 0.5
                rationale = "Current threshold is balanced"
            results.append(
                {
                    "boundary_type": btype,
                    "avg_accuracy": avg_acc,
                    "avg_fpr": avg_fpr,
                    "avg_fnr": avg_fnr,
                    "recommended_threshold": recommended_threshold,
                    "rationale": rationale,
                    "sample_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["avg_accuracy"], reverse=True)
        return results
