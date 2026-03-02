"""SLO Threshold Optimizer — optimize SLO thresholds based on historical data and cost analysis."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThresholdDirection(StrEnum):
    TIGHTEN = "tighten"
    RELAX = "relax"
    MAINTAIN = "maintain"
    SPLIT_TIER = "split_tier"
    CONSOLIDATE = "consolidate"


class OptimizationBasis(StrEnum):
    HISTORICAL_P99 = "historical_p99"
    COST_EFFICIENCY = "cost_efficiency"
    CUSTOMER_IMPACT = "customer_impact"
    ENGINEERING_EFFORT = "engineering_effort"
    COMPETITIVE_BENCHMARK = "competitive_benchmark"


class ThresholdConfidence(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class ThresholdRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slo_name: str = ""
    threshold_direction: ThresholdDirection = ThresholdDirection.TIGHTEN
    optimization_basis: OptimizationBasis = OptimizationBasis.HISTORICAL_P99
    threshold_confidence: ThresholdConfidence = ThresholdConfidence.VERY_HIGH
    adjustment_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ThresholdAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slo_name: str = ""
    threshold_direction: ThresholdDirection = ThresholdDirection.TIGHTEN
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SloThresholdReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_confidence_count: int = 0
    avg_adjustment_score: float = 0.0
    by_direction: dict[str, int] = Field(default_factory=dict)
    by_basis: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    top_adjustments: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SloThresholdOptimizer:
    """Optimize SLO thresholds based on historical data and cost analysis."""

    def __init__(
        self,
        max_records: int = 200000,
        adjustment_sensitivity: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._adjustment_sensitivity = adjustment_sensitivity
        self._records: list[ThresholdRecord] = []
        self._analyses: list[ThresholdAnalysis] = []
        logger.info(
            "slo_threshold_optimizer.initialized",
            max_records=max_records,
            adjustment_sensitivity=adjustment_sensitivity,
        )

    # -- record / get / list ------------------------------------------------

    def record_threshold(
        self,
        slo_name: str,
        threshold_direction: ThresholdDirection = ThresholdDirection.TIGHTEN,
        optimization_basis: OptimizationBasis = OptimizationBasis.HISTORICAL_P99,
        threshold_confidence: ThresholdConfidence = ThresholdConfidence.VERY_HIGH,
        adjustment_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ThresholdRecord:
        record = ThresholdRecord(
            slo_name=slo_name,
            threshold_direction=threshold_direction,
            optimization_basis=optimization_basis,
            threshold_confidence=threshold_confidence,
            adjustment_score=adjustment_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "slo_threshold_optimizer.threshold_recorded",
            record_id=record.id,
            slo_name=slo_name,
            threshold_direction=threshold_direction.value,
            optimization_basis=optimization_basis.value,
        )
        return record

    def get_threshold(self, record_id: str) -> ThresholdRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_thresholds(
        self,
        threshold_direction: ThresholdDirection | None = None,
        optimization_basis: OptimizationBasis | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ThresholdRecord]:
        results = list(self._records)
        if threshold_direction is not None:
            results = [r for r in results if r.threshold_direction == threshold_direction]
        if optimization_basis is not None:
            results = [r for r in results if r.optimization_basis == optimization_basis]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        slo_name: str,
        threshold_direction: ThresholdDirection = ThresholdDirection.TIGHTEN,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ThresholdAnalysis:
        analysis = ThresholdAnalysis(
            slo_name=slo_name,
            threshold_direction=threshold_direction,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "slo_threshold_optimizer.analysis_added",
            slo_name=slo_name,
            threshold_direction=threshold_direction.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_threshold_distribution(self) -> dict[str, Any]:
        """Group by threshold_direction; return count and avg adjustment_score."""
        dir_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.threshold_direction.value
            dir_data.setdefault(key, []).append(r.adjustment_score)
        result: dict[str, Any] = {}
        for direction, scores in dir_data.items():
            result[direction] = {
                "count": len(scores),
                "avg_adjustment_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_confidence_thresholds(self) -> list[dict[str, Any]]:
        """Return records where adjustment_score < adjustment_sensitivity."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.adjustment_score < self._adjustment_sensitivity:
                results.append(
                    {
                        "record_id": r.id,
                        "slo_name": r.slo_name,
                        "threshold_direction": r.threshold_direction.value,
                        "adjustment_score": r.adjustment_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["adjustment_score"])

    def rank_by_adjustment(self) -> list[dict[str, Any]]:
        """Group by service, avg adjustment_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.adjustment_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_adjustment_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_adjustment_score"])
        return results

    def detect_threshold_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> SloThresholdReport:
        by_direction: dict[str, int] = {}
        by_basis: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for r in self._records:
            by_direction[r.threshold_direction.value] = (
                by_direction.get(r.threshold_direction.value, 0) + 1
            )
            by_basis[r.optimization_basis.value] = by_basis.get(r.optimization_basis.value, 0) + 1
            by_confidence[r.threshold_confidence.value] = (
                by_confidence.get(r.threshold_confidence.value, 0) + 1
            )
        low_confidence_count = sum(
            1 for r in self._records if r.adjustment_score < self._adjustment_sensitivity
        )
        scores = [r.adjustment_score for r in self._records]
        avg_adjustment_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_confidence_thresholds()
        top_adjustments = [o["slo_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_confidence_count > 0:
            recs.append(
                f"{low_confidence_count} threshold(s) below adjustment sensitivity "
                f"({self._adjustment_sensitivity})"
            )
        if self._records and avg_adjustment_score < self._adjustment_sensitivity:
            recs.append(
                f"Avg adjustment score {avg_adjustment_score} below sensitivity "
                f"({self._adjustment_sensitivity})"
            )
        if not recs:
            recs.append("SLO threshold optimization levels are healthy")
        return SloThresholdReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_confidence_count=low_confidence_count,
            avg_adjustment_score=avg_adjustment_score,
            by_direction=by_direction,
            by_basis=by_basis,
            by_confidence=by_confidence,
            top_adjustments=top_adjustments,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("slo_threshold_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        direction_dist: dict[str, int] = {}
        for r in self._records:
            key = r.threshold_direction.value
            direction_dist[key] = direction_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "adjustment_sensitivity": self._adjustment_sensitivity,
            "direction_distribution": direction_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
