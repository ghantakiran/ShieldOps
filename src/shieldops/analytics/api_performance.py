"""API Performance Profiler — profile and analyze API endpoint performance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PerformanceTier(StrEnum):
    FAST = "fast"
    ACCEPTABLE = "acceptable"
    SLOW = "slow"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class LatencyPercentile(StrEnum):
    P50 = "p50"
    P75 = "p75"
    P90 = "p90"
    P95 = "p95"
    P99 = "p99"


class PerformanceTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class PerformanceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    endpoint_name: str = ""
    tier: PerformanceTier = PerformanceTier.ACCEPTABLE
    percentile: LatencyPercentile = LatencyPercentile.P50
    latency_ms: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class EndpointProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    profile_name: str = ""
    tier: PerformanceTier = PerformanceTier.ACCEPTABLE
    percentile: LatencyPercentile = LatencyPercentile.P50
    avg_latency_ms: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class APIPerformanceReport(BaseModel):
    total_records: int = 0
    total_profiles: int = 0
    avg_latency_ms: float = 0.0
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_percentile: dict[str, int] = Field(default_factory=dict)
    slow_endpoint_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class APIPerformanceProfiler:
    """Profile and analyze API endpoint performance."""

    def __init__(
        self,
        max_records: int = 200000,
        slow_threshold_ms: float = 500.0,
    ) -> None:
        self._max_records = max_records
        self._slow_threshold_ms = slow_threshold_ms
        self._records: list[PerformanceRecord] = []
        self._profiles: list[EndpointProfile] = []
        logger.info(
            "api_performance.initialized",
            max_records=max_records,
            slow_threshold_ms=slow_threshold_ms,
        )

    # -- record / get / list ---------------------------------------------

    def record_performance(
        self,
        endpoint_name: str,
        tier: PerformanceTier = PerformanceTier.ACCEPTABLE,
        percentile: LatencyPercentile = LatencyPercentile.P50,
        latency_ms: float = 0.0,
        details: str = "",
    ) -> PerformanceRecord:
        record = PerformanceRecord(
            endpoint_name=endpoint_name,
            tier=tier,
            percentile=percentile,
            latency_ms=latency_ms,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "api_performance.recorded",
            record_id=record.id,
            endpoint_name=endpoint_name,
            tier=tier.value,
        )
        return record

    def get_performance(self, record_id: str) -> PerformanceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_performances(
        self,
        endpoint_name: str | None = None,
        tier: PerformanceTier | None = None,
        limit: int = 50,
    ) -> list[PerformanceRecord]:
        results = list(self._records)
        if endpoint_name is not None:
            results = [r for r in results if r.endpoint_name == endpoint_name]
        if tier is not None:
            results = [r for r in results if r.tier == tier]
        return results[-limit:]

    def add_endpoint_profile(
        self,
        profile_name: str,
        tier: PerformanceTier = PerformanceTier.ACCEPTABLE,
        percentile: LatencyPercentile = LatencyPercentile.P50,
        avg_latency_ms: float = 0.0,
        description: str = "",
    ) -> EndpointProfile:
        profile = EndpointProfile(
            profile_name=profile_name,
            tier=tier,
            percentile=percentile,
            avg_latency_ms=avg_latency_ms,
            description=description,
        )
        self._profiles.append(profile)
        if len(self._profiles) > self._max_records:
            self._profiles = self._profiles[-self._max_records :]
        logger.info(
            "api_performance.profile_added",
            profile_name=profile_name,
            avg_latency_ms=avg_latency_ms,
        )
        return profile

    # -- domain operations -----------------------------------------------

    def analyze_endpoint_performance(self, endpoint_name: str) -> dict[str, Any]:
        """Analyze performance for a specific endpoint."""
        records = [r for r in self._records if r.endpoint_name == endpoint_name]
        if not records:
            return {"endpoint_name": endpoint_name, "status": "no_data"}
        avg_latency = round(sum(r.latency_ms for r in records) / len(records), 2)
        return {
            "endpoint_name": endpoint_name,
            "total": len(records),
            "avg_latency": avg_latency,
            "meets_threshold": avg_latency <= self._slow_threshold_ms,
        }

    def identify_slow_endpoints(self) -> list[dict[str, Any]]:
        """Find endpoints with slow, degraded, or critical tier records."""
        slow_tiers = {PerformanceTier.SLOW, PerformanceTier.DEGRADED, PerformanceTier.CRITICAL}
        endpoint_counts: dict[str, int] = {}
        for r in self._records:
            if r.tier in slow_tiers:
                endpoint_counts[r.endpoint_name] = endpoint_counts.get(r.endpoint_name, 0) + 1
        results: list[dict[str, Any]] = []
        for name, count in endpoint_counts.items():
            if count > 1:
                results.append({"endpoint_name": name, "slow_count": count})
        results.sort(key=lambda x: x["slow_count"], reverse=True)
        return results

    def rank_by_latency(self) -> list[dict[str, Any]]:
        """Rank endpoints by average latency descending."""
        endpoint_latencies: dict[str, list[float]] = {}
        for r in self._records:
            endpoint_latencies.setdefault(r.endpoint_name, []).append(r.latency_ms)
        results: list[dict[str, Any]] = []
        for name, latencies in endpoint_latencies.items():
            avg = round(sum(latencies) / len(latencies), 2)
            results.append({"endpoint_name": name, "avg_latency_ms": avg})
        results.sort(key=lambda x: x["avg_latency_ms"], reverse=True)
        return results

    def detect_performance_degradation(self) -> list[dict[str, Any]]:
        """Detect performance degradation for endpoints with sufficient data."""
        endpoint_records: dict[str, list[PerformanceRecord]] = {}
        for r in self._records:
            endpoint_records.setdefault(r.endpoint_name, []).append(r)
        results: list[dict[str, Any]] = []
        for name, records in endpoint_records.items():
            if len(records) > 3:
                latencies = [r.latency_ms for r in records]
                degradation = "degrading" if latencies[-1] > latencies[0] else "improving"
                results.append(
                    {
                        "endpoint_name": name,
                        "record_count": len(records),
                        "degradation": degradation,
                    }
                )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> APIPerformanceReport:
        by_tier: dict[str, int] = {}
        by_percentile: dict[str, int] = {}
        for r in self._records:
            by_tier[r.tier.value] = by_tier.get(r.tier.value, 0) + 1
            by_percentile[r.percentile.value] = by_percentile.get(r.percentile.value, 0) + 1
        avg_latency = (
            round(
                sum(r.latency_ms for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        slow_tiers = {PerformanceTier.SLOW, PerformanceTier.DEGRADED, PerformanceTier.CRITICAL}
        slow_count = sum(1 for r in self._records if r.tier in slow_tiers)
        recs: list[str] = []
        if slow_count > 0:
            recs.append(f"{slow_count} record(s) with slow/degraded/critical tier")
        high_latency = sum(1 for r in self._records if r.latency_ms > self._slow_threshold_ms)
        if high_latency > 0:
            recs.append(f"{high_latency} record(s) exceeding slow threshold")
        if not recs:
            recs.append("API performance within acceptable limits")
        return APIPerformanceReport(
            total_records=len(self._records),
            total_profiles=len(self._profiles),
            avg_latency_ms=avg_latency,
            by_tier=by_tier,
            by_percentile=by_percentile,
            slow_endpoint_count=slow_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._profiles.clear()
        logger.info("api_performance.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        tier_dist: dict[str, int] = {}
        for r in self._records:
            key = r.tier.value
            tier_dist[key] = tier_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_profiles": len(self._profiles),
            "slow_threshold_ms": self._slow_threshold_ms,
            "tier_distribution": tier_dist,
            "unique_endpoints": len({r.endpoint_name for r in self._records}),
        }
