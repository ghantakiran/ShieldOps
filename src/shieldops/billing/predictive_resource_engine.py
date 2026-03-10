"""Predictive Resource Engine

Forecasts resource demand and recommends sizing changes
to optimize cost while maintaining performance headroom.
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


class ResourceDemandTrend(StrEnum):
    GROWING = "growing"
    STABLE = "stable"
    DECLINING = "declining"
    SEASONAL = "seasonal"
    VOLATILE = "volatile"


class SizingRecommendation(StrEnum):
    DOWNSIZE = "downsize"
    MAINTAIN = "maintain"
    UPSIZE = "upsize"
    RESERVED_INSTANCE = "reserved_instance"
    SPOT_ELIGIBLE = "spot_eligible"


class PredictionConfidence(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


# --- Models ---


class ResourceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    resource_type: str = ""
    current_usage_pct: float = 0.0
    predicted_usage_pct: float = 0.0
    demand_trend: ResourceDemandTrend = ResourceDemandTrend.STABLE
    sizing_recommendation: SizingRecommendation = SizingRecommendation.MAINTAIN
    confidence: PredictionConfidence = PredictionConfidence.MODERATE
    estimated_monthly_cost: float = 0.0
    potential_savings: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ResourceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ResourceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_usage_pct: float = 0.0
    total_potential_savings: float = 0.0
    by_trend: dict[str, int] = Field(default_factory=dict)
    by_recommendation: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PredictiveResourceEngine:
    """Predictive Resource Engine

    Forecasts resource demand and recommends sizing
    to optimize cost and performance headroom.
    """

    def __init__(
        self,
        max_records: int = 200000,
        usage_threshold: float = 0.8,
    ) -> None:
        self._max_records = max_records
        self._usage_threshold = usage_threshold
        self._records: list[ResourceRecord] = []
        self._analyses: list[ResourceAnalysis] = []
        logger.info(
            "predictive_resource_engine.initialized",
            max_records=max_records,
            usage_threshold=usage_threshold,
        )

    def add_record(
        self,
        service: str,
        resource_type: str = "",
        current_usage_pct: float = 0.0,
        predicted_usage_pct: float = 0.0,
        demand_trend: ResourceDemandTrend = (ResourceDemandTrend.STABLE),
        sizing_recommendation: SizingRecommendation = (SizingRecommendation.MAINTAIN),
        confidence: PredictionConfidence = (PredictionConfidence.MODERATE),
        estimated_monthly_cost: float = 0.0,
        potential_savings: float = 0.0,
    ) -> ResourceRecord:
        record = ResourceRecord(
            service=service,
            resource_type=resource_type,
            current_usage_pct=current_usage_pct,
            predicted_usage_pct=predicted_usage_pct,
            demand_trend=demand_trend,
            sizing_recommendation=(sizing_recommendation),
            confidence=confidence,
            estimated_monthly_cost=(estimated_monthly_cost),
            potential_savings=potential_savings,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "predictive_resource_engine.record_added",
            record_id=record.id,
            service=service,
            resource_type=resource_type,
        )
        return record

    def predict_demand(self, service: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return {
                "service": service,
                "status": "no_data",
            }
        latest = sorted(
            matching,
            key=lambda r: r.created_at,
            reverse=True,
        )[:10]
        avg_predicted = round(
            sum(r.predicted_usage_pct for r in latest) / len(latest),
            4,
        )
        avg_current = round(
            sum(r.current_usage_pct for r in latest) / len(latest),
            4,
        )
        trend_counts: dict[str, int] = {}
        for r in latest:
            tv = r.demand_trend.value
            trend_counts[tv] = trend_counts.get(tv, 0) + 1
        dominant = max(
            trend_counts,
            key=trend_counts.get,  # type: ignore[arg-type]
        )
        return {
            "service": service,
            "avg_current_pct": avg_current,
            "avg_predicted_pct": avg_predicted,
            "dominant_trend": dominant,
            "sample_count": len(latest),
        }

    def recommend_sizing(self, service: str) -> list[dict[str, Any]]:
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return []
        by_type: dict[str, list[ResourceRecord]] = {}
        for r in matching:
            if r.resource_type not in by_type:
                by_type[r.resource_type] = []
            by_type[r.resource_type].append(r)
        results = []
        for rtype, recs in by_type.items():
            latest = max(recs, key=lambda r: r.created_at)
            results.append(
                {
                    "resource_type": rtype,
                    "recommendation": (latest.sizing_recommendation.value),
                    "predicted_usage": (latest.predicted_usage_pct),
                    "savings": latest.potential_savings,
                }
            )
        return results

    def compute_savings_potential(self, service: str = "") -> dict[str, Any]:
        matching = list(self._records)
        if service:
            matching = [r for r in matching if r.service == service]
        if not matching:
            return {
                "service": service or "all",
                "status": "no_data",
            }
        total_savings = round(
            sum(r.potential_savings for r in matching),
            2,
        )
        total_cost = round(
            sum(r.estimated_monthly_cost for r in matching),
            2,
        )
        savings_pct = round(total_savings / total_cost, 4) if total_cost > 0 else 0.0
        return {
            "service": service or "all",
            "total_monthly_cost": total_cost,
            "total_potential_savings": total_savings,
            "savings_pct": savings_pct,
        }

    def process(self, service: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return {
                "service": service,
                "status": "no_data",
            }
        usages = [r.current_usage_pct for r in matching]
        avg_usage = round(sum(usages) / len(usages), 4)
        over = sum(1 for u in usages if u > self._usage_threshold)
        savings = round(
            sum(r.potential_savings for r in matching),
            2,
        )
        return {
            "service": service,
            "resource_count": len(matching),
            "avg_usage_pct": avg_usage,
            "over_threshold": over,
            "total_savings": savings,
        }

    def generate_report(self) -> ResourceReport:
        by_trend: dict[str, int] = {}
        by_rec: dict[str, int] = {}
        by_conf: dict[str, int] = {}
        for r in self._records:
            tv = r.demand_trend.value
            by_trend[tv] = by_trend.get(tv, 0) + 1
            rv = r.sizing_recommendation.value
            by_rec[rv] = by_rec.get(rv, 0) + 1
            cv = r.confidence.value
            by_conf[cv] = by_conf.get(cv, 0) + 1
        usages = [r.current_usage_pct for r in self._records]
        avg_usage = round(sum(usages) / len(usages), 4) if usages else 0.0
        total_savings = round(
            sum(r.potential_savings for r in self._records),
            2,
        )
        recs: list[str] = []
        downsize = by_rec.get("downsize", 0)
        total = len(self._records)
        if downsize > 0:
            recs.append(f"{downsize} resource(s) can be downsized")
        if total_savings > 0:
            recs.append(f"${total_savings:,.0f}/mo potential savings identified")
        growing = by_trend.get("growing", 0)
        if total > 0 and growing / total > 0.4:
            recs.append("Over 40% resources growing — plan capacity ahead")
        if not recs:
            recs.append("Resource utilization is nominal")
        return ResourceReport(
            total_records=total,
            total_analyses=len(self._analyses),
            avg_usage_pct=avg_usage,
            total_potential_savings=total_savings,
            by_trend=by_trend,
            by_recommendation=by_rec,
            by_confidence=by_conf,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        trend_dist: dict[str, int] = {}
        for r in self._records:
            k = r.demand_trend.value
            trend_dist[k] = trend_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "usage_threshold": (self._usage_threshold),
            "trend_distribution": trend_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_resource_types": len({r.resource_type for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("predictive_resource_engine.cleared")
        return {"status": "cleared"}
