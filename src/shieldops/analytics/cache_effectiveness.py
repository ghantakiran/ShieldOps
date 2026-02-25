"""Cache Effectiveness Analyzer — measure cache hit/miss rates and optimize."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CacheLayer(StrEnum):
    APPLICATION = "application"
    CDN = "cdn"
    DATABASE = "database"
    API_GATEWAY = "api_gateway"
    DISTRIBUTED = "distributed"


class CacheHealth(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class OptimizationAction(StrEnum):
    INCREASE_SIZE = "increase_size"
    DECREASE_TTL = "decrease_ttl"
    INCREASE_TTL = "increase_ttl"
    ADD_CACHE_LAYER = "add_cache_layer"
    NO_ACTION = "no_action"


# --- Models ---


class CacheMetricRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cache_name: str = ""
    layer: CacheLayer = CacheLayer.APPLICATION
    hit_rate_pct: float = 0.0
    miss_rate_pct: float = 0.0
    eviction_rate: float = 0.0
    avg_latency_ms: float = 0.0
    size_mb: float = 0.0
    health: CacheHealth = CacheHealth.GOOD
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CacheRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cache_name: str = ""
    action: OptimizationAction = OptimizationAction.NO_ACTION
    expected_improvement_pct: float = 0.0
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class CacheEffectivenessReport(BaseModel):
    total_caches: int = 0
    total_recommendations: int = 0
    avg_hit_rate_pct: float = 0.0
    by_layer: dict[str, float] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    underperforming_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CacheEffectivenessAnalyzer:
    """Measure cache hit/miss rates and recommend optimizations."""

    def __init__(
        self,
        max_records: int = 200000,
        min_hit_rate_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_hit_rate_pct = min_hit_rate_pct
        self._records: list[CacheMetricRecord] = []
        self._recommendations: list[CacheRecommendation] = []
        logger.info(
            "cache_effectiveness.initialized",
            max_records=max_records,
            min_hit_rate_pct=min_hit_rate_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _hit_rate_to_health(self, hit_rate: float) -> CacheHealth:
        if hit_rate >= 95:
            return CacheHealth.EXCELLENT
        if hit_rate >= 85:
            return CacheHealth.GOOD
        if hit_rate >= 70:
            return CacheHealth.FAIR
        if hit_rate >= 50:
            return CacheHealth.POOR
        return CacheHealth.CRITICAL

    # -- record / get / list ---------------------------------------------

    def record_metrics(
        self,
        cache_name: str,
        layer: CacheLayer = CacheLayer.APPLICATION,
        hit_rate_pct: float = 0.0,
        miss_rate_pct: float = 0.0,
        eviction_rate: float = 0.0,
        avg_latency_ms: float = 0.0,
        size_mb: float = 0.0,
        health: CacheHealth | None = None,
        details: str = "",
    ) -> CacheMetricRecord:
        if health is None:
            health = self._hit_rate_to_health(hit_rate_pct)
        record = CacheMetricRecord(
            cache_name=cache_name,
            layer=layer,
            hit_rate_pct=hit_rate_pct,
            miss_rate_pct=miss_rate_pct,
            eviction_rate=eviction_rate,
            avg_latency_ms=avg_latency_ms,
            size_mb=size_mb,
            health=health,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cache_effectiveness.metrics_recorded",
            record_id=record.id,
            cache_name=cache_name,
            hit_rate_pct=hit_rate_pct,
            health=health.value,
        )
        return record

    def get_metrics(self, record_id: str) -> CacheMetricRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_metrics(
        self,
        cache_name: str | None = None,
        layer: CacheLayer | None = None,
        limit: int = 50,
    ) -> list[CacheMetricRecord]:
        results = list(self._records)
        if cache_name is not None:
            results = [r for r in results if r.cache_name == cache_name]
        if layer is not None:
            results = [r for r in results if r.layer == layer]
        return results[-limit:]

    def add_recommendation(
        self,
        cache_name: str,
        action: OptimizationAction = OptimizationAction.NO_ACTION,
        expected_improvement_pct: float = 0.0,
        reason: str = "",
    ) -> CacheRecommendation:
        rec = CacheRecommendation(
            cache_name=cache_name,
            action=action,
            expected_improvement_pct=expected_improvement_pct,
            reason=reason,
        )
        self._recommendations.append(rec)
        if len(self._recommendations) > self._max_records:
            self._recommendations = self._recommendations[-self._max_records :]
        logger.info(
            "cache_effectiveness.recommendation_added",
            cache_name=cache_name,
            action=action.value,
        )
        return rec

    # -- domain operations -----------------------------------------------

    def analyze_cache_effectiveness(self, cache_name: str) -> dict[str, Any]:
        """Analyze effectiveness for a specific cache."""
        records = [r for r in self._records if r.cache_name == cache_name]
        if not records:
            return {"cache_name": cache_name, "status": "no_data"}
        latest = records[-1]
        return {
            "cache_name": cache_name,
            "hit_rate_pct": latest.hit_rate_pct,
            "miss_rate_pct": latest.miss_rate_pct,
            "eviction_rate": latest.eviction_rate,
            "health": latest.health.value,
            "layer": latest.layer.value,
        }

    def identify_underperforming_caches(self) -> list[dict[str, Any]]:
        """Find caches below minimum hit rate."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.hit_rate_pct < self._min_hit_rate_pct:
                results.append(
                    {
                        "cache_name": r.cache_name,
                        "hit_rate_pct": r.hit_rate_pct,
                        "health": r.health.value,
                        "layer": r.layer.value,
                        "gap_pct": round(self._min_hit_rate_pct - r.hit_rate_pct, 2),
                    }
                )
        results.sort(key=lambda x: x["hit_rate_pct"])
        return results

    def rank_caches_by_hit_rate(self) -> list[dict[str, Any]]:
        """Rank caches by hit rate."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "cache_name": r.cache_name,
                    "hit_rate_pct": r.hit_rate_pct,
                    "health": r.health.value,
                    "layer": r.layer.value,
                }
            )
        results.sort(key=lambda x: x["hit_rate_pct"], reverse=True)
        return results

    def estimate_latency_impact(self) -> list[dict[str, Any]]:
        """Estimate latency impact of cache improvements."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.hit_rate_pct < self._min_hit_rate_pct:
                gap = self._min_hit_rate_pct - r.hit_rate_pct
                estimated_saving_ms = round(r.avg_latency_ms * (gap / 100), 2)
                results.append(
                    {
                        "cache_name": r.cache_name,
                        "current_hit_rate": r.hit_rate_pct,
                        "target_hit_rate": self._min_hit_rate_pct,
                        "avg_latency_ms": r.avg_latency_ms,
                        "estimated_saving_ms": estimated_saving_ms,
                    }
                )
        results.sort(key=lambda x: x["estimated_saving_ms"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> CacheEffectivenessReport:
        by_health: dict[str, int] = {}
        layer_hits: dict[str, list[float]] = {}
        for r in self._records:
            by_health[r.health.value] = by_health.get(r.health.value, 0) + 1
            layer_hits.setdefault(r.layer.value, []).append(r.hit_rate_pct)
        by_layer: dict[str, float] = {}
        for layer, hits in layer_hits.items():
            by_layer[layer] = round(sum(hits) / len(hits), 2)
        avg_hit = (
            round(
                sum(r.hit_rate_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        underperforming = sum(1 for r in self._records if r.hit_rate_pct < self._min_hit_rate_pct)
        recs: list[str] = []
        if underperforming > 0:
            recs.append(
                f"{underperforming} cache(s) below {self._min_hit_rate_pct}% hit rate threshold"
            )
        critical = sum(1 for r in self._records if r.health == CacheHealth.CRITICAL)
        if critical > 0:
            recs.append(f"{critical} cache(s) in critical health")
        if not recs:
            recs.append("Cache effectiveness meets targets")
        return CacheEffectivenessReport(
            total_caches=len(self._records),
            total_recommendations=len(self._recommendations),
            avg_hit_rate_pct=avg_hit,
            by_layer=by_layer,
            by_health=by_health,
            underperforming_count=underperforming,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._recommendations.clear()
        logger.info("cache_effectiveness.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        layer_dist: dict[str, int] = {}
        for r in self._records:
            key = r.layer.value
            layer_dist[key] = layer_dist.get(key, 0) + 1
        return {
            "total_caches": len(self._records),
            "total_recommendations": len(self._recommendations),
            "min_hit_rate_pct": self._min_hit_rate_pct,
            "layer_distribution": layer_dist,
            "unique_caches": len({r.cache_name for r in self._records}),
        }
