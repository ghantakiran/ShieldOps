"""Service Latency Analyzer — analyze latency chains and identify bottlenecks."""

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
    ACCEPTABLE = "acceptable"
    SLOW = "slow"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class LatencySource(StrEnum):
    APPLICATION = "application"
    DATABASE = "database"
    NETWORK = "network"
    EXTERNAL_API = "external_api"
    QUEUE = "queue"


class LatencyImpact(StrEnum):
    SEVERE = "severe"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NONE = "none"


# --- Models ---


class LatencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    latency_ms: float = 0.0
    latency_tier: LatencyTier = LatencyTier.ACCEPTABLE
    latency_source: LatencySource = LatencySource.APPLICATION
    impact: LatencyImpact = LatencyImpact.LOW
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class LatencyBaseline(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_pattern: str = ""
    latency_tier: LatencyTier = LatencyTier.ACCEPTABLE
    latency_source: LatencySource = LatencySource.APPLICATION
    baseline_ms: float = 0.0
    threshold_ms: float = 0.0
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class ServiceLatencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_baselines: int = 0
    slow_count: int = 0
    avg_latency_ms: float = 0.0
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    bottleneck_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceLatencyAnalyzer:
    """Analyze end-to-end service latency chains and identify bottlenecks."""

    def __init__(
        self,
        max_records: int = 200000,
        max_latency_threshold_ms: float = 500.0,
    ) -> None:
        self._max_records = max_records
        self._max_latency_threshold_ms = max_latency_threshold_ms
        self._records: list[LatencyRecord] = []
        self._baselines: list[LatencyBaseline] = []
        logger.info(
            "service_latency.initialized",
            max_records=max_records,
            max_latency_threshold_ms=max_latency_threshold_ms,
        )

    # -- record / get / list ------------------------------------------------

    def record_latency(
        self,
        service: str,
        latency_ms: float = 0.0,
        latency_tier: LatencyTier = LatencyTier.ACCEPTABLE,
        latency_source: LatencySource = (LatencySource.APPLICATION),
        impact: LatencyImpact = LatencyImpact.LOW,
        team: str = "",
        details: str = "",
    ) -> LatencyRecord:
        record = LatencyRecord(
            service=service,
            latency_ms=latency_ms,
            latency_tier=latency_tier,
            latency_source=latency_source,
            impact=impact,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "service_latency.latency_recorded",
            record_id=record.id,
            service=service,
            latency_tier=latency_tier.value,
            latency_source=latency_source.value,
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
        team: str | None = None,
        limit: int = 50,
    ) -> list[LatencyRecord]:
        results = list(self._records)
        if tier is not None:
            results = [r for r in results if r.latency_tier == tier]
        if source is not None:
            results = [r for r in results if r.latency_source == source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_baseline(
        self,
        service_pattern: str,
        latency_tier: LatencyTier = LatencyTier.ACCEPTABLE,
        latency_source: LatencySource = (LatencySource.APPLICATION),
        baseline_ms: float = 0.0,
        threshold_ms: float = 0.0,
        reason: str = "",
    ) -> LatencyBaseline:
        baseline = LatencyBaseline(
            service_pattern=service_pattern,
            latency_tier=latency_tier,
            latency_source=latency_source,
            baseline_ms=baseline_ms,
            threshold_ms=threshold_ms,
            reason=reason,
        )
        self._baselines.append(baseline)
        if len(self._baselines) > self._max_records:
            self._baselines = self._baselines[-self._max_records :]
        logger.info(
            "service_latency.baseline_added",
            service_pattern=service_pattern,
            latency_tier=latency_tier.value,
            baseline_ms=baseline_ms,
        )
        return baseline

    # -- domain operations --------------------------------------------------

    def analyze_latency_distribution(
        self,
    ) -> dict[str, Any]:
        """Group by tier; return count and avg latency per tier."""
        tier_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.latency_tier.value
            tier_data.setdefault(key, []).append(r.latency_ms)
        result: dict[str, Any] = {}
        for tier, vals in tier_data.items():
            result[tier] = {
                "count": len(vals),
                "avg_latency": round(sum(vals) / len(vals), 2),
            }
        return result

    def identify_slow_services(
        self,
    ) -> list[dict[str, Any]]:
        """Return records where tier is SLOW, DEGRADED, or CRITICAL."""
        slow_tiers = {
            LatencyTier.SLOW,
            LatencyTier.DEGRADED,
            LatencyTier.CRITICAL,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.latency_tier in slow_tiers:
                results.append(
                    {
                        "record_id": r.id,
                        "service": r.service,
                        "latency_tier": r.latency_tier.value,
                        "latency_source": (r.latency_source.value),
                        "latency_ms": r.latency_ms,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["latency_ms"], reverse=True)
        return results

    def rank_by_latency(self) -> list[dict[str, Any]]:
        """Group by service, avg latency, sort desc."""
        svc_latencies: dict[str, list[float]] = {}
        for r in self._records:
            svc_latencies.setdefault(r.service, []).append(r.latency_ms)
        results: list[dict[str, Any]] = []
        for svc, vals in svc_latencies.items():
            results.append(
                {
                    "service": svc,
                    "avg_latency": round(sum(vals) / len(vals), 2),
                    "record_count": len(vals),
                }
            )
        results.sort(key=lambda x: x["avg_latency"], reverse=True)
        return results

    def detect_latency_trends(self) -> dict[str, Any]:
        """Split-half comparison on latency_ms; delta threshold 5.0."""
        if len(self._records) < 2:
            return {
                "trend": "insufficient_data",
                "delta": 0.0,
            }
        scores = [r.latency_ms for r in self._records]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ServiceLatencyReport:
        by_tier: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        for r in self._records:
            by_tier[r.latency_tier.value] = by_tier.get(r.latency_tier.value, 0) + 1
            by_source[r.latency_source.value] = by_source.get(r.latency_source.value, 0) + 1
            by_impact[r.impact.value] = by_impact.get(r.impact.value, 0) + 1
        slow_count = sum(
            1
            for r in self._records
            if r.latency_tier
            in {
                LatencyTier.SLOW,
                LatencyTier.DEGRADED,
                LatencyTier.CRITICAL,
            }
        )
        avg_latency = (
            round(
                sum(r.latency_ms for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        slow = self.identify_slow_services()
        bottleneck_services = [s["service"] for s in slow]
        recs: list[str] = []
        if slow:
            recs.append(f"{len(slow)} slow service(s) detected — investigate bottlenecks")
        high_latency = sum(
            1 for r in self._records if r.latency_ms > self._max_latency_threshold_ms
        )
        if high_latency > 0:
            recs.append(
                f"{high_latency} record(s) above latency "
                f"threshold "
                f"({self._max_latency_threshold_ms}ms)"
            )
        if not recs:
            recs.append("Service latency levels are acceptable")
        return ServiceLatencyReport(
            total_records=len(self._records),
            total_baselines=len(self._baselines),
            slow_count=slow_count,
            avg_latency_ms=avg_latency,
            by_tier=by_tier,
            by_source=by_source,
            by_impact=by_impact,
            bottleneck_services=bottleneck_services,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._baselines.clear()
        logger.info("service_latency.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        tier_dist: dict[str, int] = {}
        for r in self._records:
            key = r.latency_tier.value
            tier_dist[key] = tier_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_baselines": len(self._baselines),
            "max_latency_threshold_ms": (self._max_latency_threshold_ms),
            "tier_distribution": tier_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
