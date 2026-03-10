"""Adaptive Threshold Engine

Dynamically adjusts alert thresholds based on seasonality,
traffic patterns, and false positive feedback loops.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThresholdStrategy(StrEnum):
    STATIC = "static"
    SEASONAL = "seasonal"
    PERCENTILE = "percentile"
    ML_ADAPTIVE = "ml_adaptive"
    TRAFFIC_AWARE = "traffic_aware"


class AdjustmentReason(StrEnum):
    SEASONALITY = "seasonality"
    DEPLOYMENT = "deployment"
    TRAFFIC_SPIKE = "traffic_spike"
    DRIFT = "drift"
    MANUAL = "manual"


class ThresholdHealth(StrEnum):
    OPTIMAL = "optimal"
    NEEDS_TUNING = "needs_tuning"
    STALE = "stale"
    MISCONFIGURED = "misconfigured"


# --- Models ---


class ThresholdRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    service: str = ""
    current_threshold: float = 0.0
    recommended_threshold: float = 0.0
    strategy: ThresholdStrategy = ThresholdStrategy.STATIC
    adjustment_reason: AdjustmentReason = AdjustmentReason.MANUAL
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    health: ThresholdHealth = ThresholdHealth.NEEDS_TUNING
    created_at: float = Field(default_factory=time.time)


class ThresholdAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ThresholdReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_false_positive_rate: float = 0.0
    avg_false_negative_rate: float = 0.0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    by_reason: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AdaptiveThresholdEngine:
    """Adaptive Threshold Engine

    Dynamically adjusts alert thresholds based on
    seasonality, traffic, and feedback loops.
    """

    def __init__(
        self,
        max_records: int = 200000,
        fp_rate_threshold: float = 0.15,
    ) -> None:
        self._max_records = max_records
        self._fp_rate_threshold = fp_rate_threshold
        self._records: list[ThresholdRecord] = []
        self._analyses: list[ThresholdAnalysis] = []
        logger.info(
            "adaptive_threshold_engine.initialized",
            max_records=max_records,
            fp_rate_threshold=fp_rate_threshold,
        )

    def add_record(
        self,
        metric_name: str,
        service: str,
        current_threshold: float = 0.0,
        recommended_threshold: float = 0.0,
        strategy: ThresholdStrategy = (ThresholdStrategy.STATIC),
        adjustment_reason: AdjustmentReason = (AdjustmentReason.MANUAL),
        false_positive_rate: float = 0.0,
        false_negative_rate: float = 0.0,
        health: ThresholdHealth = (ThresholdHealth.NEEDS_TUNING),
    ) -> ThresholdRecord:
        record = ThresholdRecord(
            metric_name=metric_name,
            service=service,
            current_threshold=current_threshold,
            recommended_threshold=(recommended_threshold),
            strategy=strategy,
            adjustment_reason=adjustment_reason,
            false_positive_rate=false_positive_rate,
            false_negative_rate=false_negative_rate,
            health=health,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "adaptive_threshold_engine.record_added",
            record_id=record.id,
            metric_name=metric_name,
            service=service,
        )
        return record

    def compute_optimal_threshold(self, metric_name: str, service: str = "") -> dict[str, Any]:
        matching = [r for r in self._records if r.metric_name == metric_name]
        if service:
            matching = [r for r in matching if r.service == service]
        if not matching:
            return {
                "metric_name": metric_name,
                "status": "no_data",
            }
        recs = sorted(
            matching,
            key=lambda r: r.false_positive_rate + r.false_negative_rate,
        )
        best = recs[0]
        return {
            "metric_name": metric_name,
            "service": service or "all",
            "optimal_threshold": (best.recommended_threshold),
            "fp_rate": best.false_positive_rate,
            "fn_rate": best.false_negative_rate,
            "strategy": best.strategy.value,
        }

    def detect_threshold_staleness(self, stale_days: int = 14) -> list[dict[str, Any]]:
        cutoff = time.time() - (stale_days * 86400)
        metric_latest: dict[str, float] = {}
        for r in self._records:
            key = f"{r.metric_name}:{r.service}"
            if key not in metric_latest or r.created_at > metric_latest[key]:
                metric_latest[key] = r.created_at
        stale = []
        for key, latest in metric_latest.items():
            if latest < cutoff:
                days = int((time.time() - latest) / 86400)
                stale.append(
                    {
                        "metric_service": key,
                        "days_since_update": days,
                    }
                )
        return sorted(
            stale,
            key=lambda x: x["days_since_update"],
            reverse=True,
        )

    def evaluate_false_positive_rate(self, service: str = "") -> dict[str, Any]:
        matching = list(self._records)
        if service:
            matching = [r for r in matching if r.service == service]
        if not matching:
            return {
                "service": service or "all",
                "status": "no_data",
            }
        fp_rates = [r.false_positive_rate for r in matching]
        avg_fp = round(sum(fp_rates) / len(fp_rates), 4)
        above = sum(1 for fp in fp_rates if fp > self._fp_rate_threshold)
        return {
            "service": service or "all",
            "avg_fp_rate": avg_fp,
            "above_threshold": above,
            "total_metrics": len(matching),
        }

    def process(self, metric_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.metric_name == metric_name]
        if not matching:
            return {
                "metric_name": metric_name,
                "status": "no_data",
            }
        fp_rates = [r.false_positive_rate for r in matching]
        avg_fp = round(sum(fp_rates) / len(fp_rates), 4)
        health_counts: dict[str, int] = {}
        for r in matching:
            hv = r.health.value
            health_counts[hv] = health_counts.get(hv, 0) + 1
        return {
            "metric_name": metric_name,
            "record_count": len(matching),
            "avg_fp_rate": avg_fp,
            "health_distribution": health_counts,
        }

    def generate_report(self) -> ThresholdReport:
        by_strat: dict[str, int] = {}
        by_health: dict[str, int] = {}
        by_reason: dict[str, int] = {}
        for r in self._records:
            sv = r.strategy.value
            by_strat[sv] = by_strat.get(sv, 0) + 1
            hv = r.health.value
            by_health[hv] = by_health.get(hv, 0) + 1
            rv = r.adjustment_reason.value
            by_reason[rv] = by_reason.get(rv, 0) + 1
        fp_rates = [r.false_positive_rate for r in self._records]
        fn_rates = [r.false_negative_rate for r in self._records]
        avg_fp = round(sum(fp_rates) / len(fp_rates), 4) if fp_rates else 0.0
        avg_fn = round(sum(fn_rates) / len(fn_rates), 4) if fn_rates else 0.0
        recs: list[str] = []
        if avg_fp > self._fp_rate_threshold:
            recs.append(f"Avg FP rate {avg_fp:.0%} — tune thresholds")
        stale = by_health.get("stale", 0)
        misconf = by_health.get("misconfigured", 0)
        if stale + misconf > 0:
            recs.append(f"{stale + misconf} thresholds stale or misconfigured")
        if not recs:
            recs.append("Threshold health is nominal")
        return ThresholdReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_false_positive_rate=avg_fp,
            avg_false_negative_rate=avg_fn,
            by_strategy=by_strat,
            by_health=by_health,
            by_reason=by_reason,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        health_dist: dict[str, int] = {}
        for r in self._records:
            k = r.health.value
            health_dist[k] = health_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "fp_rate_threshold": (self._fp_rate_threshold),
            "health_distribution": health_dist,
            "unique_metrics": len({r.metric_name for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("adaptive_threshold_engine.cleared")
        return {"status": "cleared"}
