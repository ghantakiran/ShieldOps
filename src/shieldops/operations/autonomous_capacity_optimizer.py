"""Autonomous Capacity Optimizer — autonomous capacity optimization and scaling."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ScalingDirection(StrEnum):
    UP = "up"
    DOWN = "down"
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class CapacitySignal(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    NETWORK = "network"
    STORAGE = "storage"


class OptimizationMode(StrEnum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


# --- Models ---


class CapacityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    scaling_direction: ScalingDirection = ScalingDirection.UP
    capacity_signal: CapacitySignal = CapacitySignal.CPU
    optimization_mode: OptimizationMode = OptimizationMode.BALANCED
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CapacityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    scaling_direction: ScalingDirection = ScalingDirection.UP
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AutonomousCapacityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_scaling_direction: dict[str, int] = Field(default_factory=dict)
    by_capacity_signal: dict[str, int] = Field(default_factory=dict)
    by_optimization_mode: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutonomousCapacityOptimizer:
    """Autonomous Capacity Optimizer
    for capacity optimization and scaling decisions.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[CapacityRecord] = []
        self._analyses: list[CapacityAnalysis] = []
        logger.info(
            "autonomous_capacity_optimizer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def record_item(
        self,
        name: str,
        scaling_direction: ScalingDirection = (ScalingDirection.UP),
        capacity_signal: CapacitySignal = (CapacitySignal.CPU),
        optimization_mode: OptimizationMode = (OptimizationMode.BALANCED),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CapacityRecord:
        record = CapacityRecord(
            name=name,
            scaling_direction=scaling_direction,
            capacity_signal=capacity_signal,
            optimization_mode=optimization_mode,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "autonomous_capacity_optimizer.item_recorded",
            record_id=record.id,
            name=name,
        )
        return record

    def get_record(self, record_id: str) -> CapacityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        scaling_direction: ScalingDirection | None = None,
        capacity_signal: CapacitySignal | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CapacityRecord]:
        results = list(self._records)
        if scaling_direction is not None:
            results = [r for r in results if r.scaling_direction == scaling_direction]
        if capacity_signal is not None:
            results = [r for r in results if r.capacity_signal == capacity_signal]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        scaling_direction: ScalingDirection = (ScalingDirection.UP),
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CapacityAnalysis:
        analysis = CapacityAnalysis(
            name=name,
            scaling_direction=scaling_direction,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "autonomous_capacity_optimizer.analysis_added",
            name=name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------

    def predict_capacity_needs(
        self,
    ) -> list[dict[str, Any]]:
        """Predict future capacity needs per service."""
        svc_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            svc_data.setdefault(r.service, []).append(
                {
                    "signal": r.capacity_signal.value,
                    "score": r.score,
                    "direction": r.scaling_direction.value,
                }
            )
        results: list[dict[str, Any]] = []
        for svc, entries in svc_data.items():
            avg_score = round(sum(e["score"] for e in entries) / len(entries), 2)
            up_count = sum(1 for e in entries if e["direction"] in ("up", "horizontal"))
            results.append(
                {
                    "service": svc,
                    "avg_utilization": avg_score,
                    "scale_up_signals": up_count,
                    "needs_scaling": avg_score > self._threshold,
                    "sample_count": len(entries),
                }
            )
        results.sort(
            key=lambda x: x["avg_utilization"],
            reverse=True,
        )
        return results

    def generate_scaling_recommendation(
        self,
    ) -> dict[str, Any]:
        """Generate scaling recommendations."""
        signal_data: dict[str, list[float]] = {}
        for r in self._records:
            signal_data.setdefault(r.capacity_signal.value, []).append(r.score)
        recs: list[dict[str, Any]] = []
        for signal, scores in signal_data.items():
            avg = round(sum(scores) / len(scores), 2)
            if avg > 80:
                action = "scale_up"
                priority = "high"
            elif avg > self._threshold:
                action = "monitor"
                priority = "medium"
            elif avg < 20:
                action = "scale_down"
                priority = "low"
            else:
                action = "maintain"
                priority = "low"
            recs.append(
                {
                    "signal": signal,
                    "avg_utilization": avg,
                    "recommended_action": action,
                    "priority": priority,
                }
            )
        return {
            "recommendations": recs,
            "total_signals": len(self._records),
        }

    def evaluate_scaling_outcome(
        self,
    ) -> dict[str, Any]:
        """Evaluate outcomes of past scaling decisions."""
        mode_data: dict[str, list[float]] = {}
        for r in self._records:
            mode_data.setdefault(r.optimization_mode.value, []).append(r.score)
        outcomes: dict[str, Any] = {}
        for mode, scores in mode_data.items():
            avg = round(sum(scores) / len(scores), 2)
            outcomes[mode] = {
                "count": len(scores),
                "avg_effectiveness": avg,
                "success_rate": round(
                    sum(1 for s in scores if s >= self._threshold) / len(scores) * 100, 2
                ),
            }
        return {
            "outcomes_by_mode": outcomes,
            "total_evaluated": len(self._records),
        }

    # -- report / stats -----------------------------------------------

    def generate_report(self) -> AutonomousCapacityReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.scaling_direction.value] = by_e1.get(r.scaling_direction.value, 0) + 1
            by_e2[r.capacity_signal.value] = by_e2.get(r.capacity_signal.value, 0) + 1
            by_e3[r.optimization_mode.value] = by_e3.get(r.optimization_mode.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gaps = [r.name for r in self._records if r.score < self._threshold][:5]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Autonomous Capacity Optimizer is healthy")
        return AutonomousCapacityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_scaling_direction=by_e1,
            by_capacity_signal=by_e2,
            by_optimization_mode=by_e3,
            top_gaps=gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("autonomous_capacity_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.scaling_direction.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "scaling_direction_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
