"""Dependency Latency Tracker — record and analyze inter-service latency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LatencyTier(StrEnum):
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class LatencySource(StrEnum):
    NETWORK = "network"
    PROCESSING = "processing"
    QUEUE = "queue"
    DATABASE = "database"
    EXTERNAL_API = "external_api"


class LatencyTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


# --- Models ---


class LatencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    dependency: str = ""
    latency_ms: float = 0.0
    latency_tier: LatencyTier = LatencyTier.NORMAL
    latency_source: LatencySource = LatencySource.NETWORK
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class LatencyBreakdown(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    record_id: str = ""
    component: str = ""
    component_latency_ms: float = 0.0
    percentage: float = 0.0
    created_at: float = Field(default_factory=time.time)


class DependencyLatencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_breakdowns: int = 0
    avg_latency_ms: float = 0.0
    slow_dependency_count: int = 0
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    slowest_dependencies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DependencyLatencyTracker:
    """Track and analyze latency between services and their dependencies."""

    def __init__(
        self,
        max_records: int = 200000,
        max_latency_ms: float = 500.0,
    ) -> None:
        self._max_records = max_records
        self._max_latency_ms = max_latency_ms
        self._records: list[LatencyRecord] = []
        self._breakdowns: list[LatencyBreakdown] = []
        logger.info(
            "dep_latency.initialized",
            max_records=max_records,
            max_latency_ms=max_latency_ms,
        )

    # -- record / get / list ------------------------------------------------

    def record_latency(
        self,
        service: str,
        dependency: str,
        latency_ms: float = 0.0,
        latency_tier: LatencyTier = LatencyTier.NORMAL,
        latency_source: LatencySource = LatencySource.NETWORK,
        details: str = "",
    ) -> LatencyRecord:
        record = LatencyRecord(
            service=service,
            dependency=dependency,
            latency_ms=latency_ms,
            latency_tier=latency_tier,
            latency_source=latency_source,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dep_latency.latency_recorded",
            record_id=record.id,
            service=service,
            dependency=dependency,
            latency_ms=latency_ms,
        )
        return record

    def get_latency(self, record_id: str) -> LatencyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_latencies(
        self,
        tier: LatencyTier | None = None,
        source: LatencySource | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[LatencyRecord]:
        results = list(self._records)
        if tier is not None:
            results = [r for r in results if r.latency_tier == tier]
        if source is not None:
            results = [r for r in results if r.latency_source == source]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def add_breakdown(
        self,
        record_id: str,
        component: str,
        component_latency_ms: float = 0.0,
        percentage: float = 0.0,
    ) -> LatencyBreakdown:
        breakdown = LatencyBreakdown(
            record_id=record_id,
            component=component,
            component_latency_ms=component_latency_ms,
            percentage=percentage,
        )
        self._breakdowns.append(breakdown)
        if len(self._breakdowns) > self._max_records:
            self._breakdowns = self._breakdowns[-self._max_records :]
        logger.info(
            "dep_latency.breakdown_added",
            record_id=record_id,
            component=component,
            component_latency_ms=component_latency_ms,
        )
        return breakdown

    # -- domain operations --------------------------------------------------

    def analyze_latency_by_dependency(self) -> dict[str, Any]:
        """Group by dependency; return avg latency_ms and count."""
        dep_data: dict[str, list[float]] = {}
        for r in self._records:
            dep_data.setdefault(r.dependency, []).append(r.latency_ms)
        result: dict[str, Any] = {}
        for dep, latencies in dep_data.items():
            result[dep] = {
                "count": len(latencies),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
            }
        return result

    def identify_slow_dependencies(self) -> list[dict[str, Any]]:
        """Return dependencies where avg latency_ms > max_latency_ms."""
        dep_data: dict[str, list[float]] = {}
        for r in self._records:
            dep_data.setdefault(r.dependency, []).append(r.latency_ms)
        results: list[dict[str, Any]] = []
        for dep, latencies in dep_data.items():
            avg = sum(latencies) / len(latencies)
            if avg > self._max_latency_ms:
                results.append(
                    {
                        "dependency": dep,
                        "avg_latency_ms": round(avg, 2),
                        "sample_count": len(latencies),
                        "threshold_ms": self._max_latency_ms,
                    }
                )
        results.sort(key=lambda x: x["avg_latency_ms"], reverse=True)
        return results

    def rank_by_latency(self) -> list[dict[str, Any]]:
        """Group by service; return avg latency, sorted descending."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.latency_ms)
        results: list[dict[str, Any]] = []
        for service, latencies in service_data.items():
            results.append(
                {
                    "service": service,
                    "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
                    "sample_count": len(latencies),
                }
            )
        results.sort(key=lambda x: x["avg_latency_ms"], reverse=True)
        return results

    def detect_latency_trends(self) -> dict[str, Any]:
        """Split-half comparison on latency_ms; delta threshold 50.0 ms."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        latencies = [r.latency_ms for r in self._records]
        mid = len(latencies) // 2
        first_half = latencies[:mid]
        second_half = latencies[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 50.0:
            trend = "stable"
        elif delta > 0:
            trend = "degrading"
        else:
            trend = "improving"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half_ms": round(avg_first, 2),
            "avg_second_half_ms": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> DependencyLatencyReport:
        by_tier: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for r in self._records:
            by_tier[r.latency_tier.value] = by_tier.get(r.latency_tier.value, 0) + 1
            by_source[r.latency_source.value] = by_source.get(r.latency_source.value, 0) + 1
        avg_latency = (
            round(
                sum(r.latency_ms for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        slow = self.identify_slow_dependencies()
        slowest = [s["dependency"] for s in slow]
        recs: list[str] = []
        if slow:
            recs.append(
                f"{len(slow)} dependency/dependencies exceed latency threshold "
                f"({self._max_latency_ms} ms)"
            )
        critical_count = sum(1 for r in self._records if r.latency_tier == LatencyTier.CRITICAL)
        if critical_count > 0:
            recs.append(f"{critical_count} critical latency observation(s) require attention")
        if not recs:
            recs.append("All dependency latencies are within acceptable thresholds")
        return DependencyLatencyReport(
            total_records=len(self._records),
            total_breakdowns=len(self._breakdowns),
            avg_latency_ms=avg_latency,
            slow_dependency_count=len(slow),
            by_tier=by_tier,
            by_source=by_source,
            slowest_dependencies=slowest,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._breakdowns.clear()
        logger.info("dep_latency.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        tier_dist: dict[str, int] = {}
        for r in self._records:
            key = r.latency_tier.value
            tier_dist[key] = tier_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_breakdowns": len(self._breakdowns),
            "max_latency_ms": self._max_latency_ms,
            "tier_distribution": tier_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_dependencies": len({r.dependency for r in self._records}),
        }
