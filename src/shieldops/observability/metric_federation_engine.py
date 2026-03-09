"""Metric Federation Engine — federate metrics across monitoring instances."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FederationSource(StrEnum):
    PROMETHEUS = "prometheus"
    THANOS = "thanos"
    MIMIR = "mimir"
    VICTORIA_METRICS = "victoria_metrics"
    CUSTOM = "custom"


class ConflictStrategy(StrEnum):
    LATEST_WINS = "latest_wins"
    SOURCE_PRIORITY = "source_priority"
    AVERAGE = "average"
    MAX = "max"
    MIN = "min"


class FederationStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"
    SYNCING = "syncing"


# --- Models ---


class FederationEndpoint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    source_type: FederationSource = FederationSource.PROMETHEUS
    url: str = ""
    status: FederationStatus = FederationStatus.HEALTHY
    priority: int = 0
    latency_ms: float = 0.0
    created_at: float = Field(default_factory=time.time)


class FederatedResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str = ""
    sources_queried: int = 0
    results_merged: int = 0
    conflicts_resolved: int = 0
    latency_ms: float = 0.0
    created_at: float = Field(default_factory=time.time)


class FederationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_endpoints: int = 0
    healthy_count: int = 0
    total_queries: int = 0
    avg_latency_ms: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MetricFederationEngine:
    """Federate metrics across multiple Prometheus/monitoring instances."""

    def __init__(
        self,
        conflict_strategy: ConflictStrategy = ConflictStrategy.LATEST_WINS,
        max_endpoints: int = 1000,
    ) -> None:
        self._conflict_strategy = conflict_strategy
        self._max_endpoints = max_endpoints
        self._endpoints: list[FederationEndpoint] = []
        self._results: list[FederatedResult] = []
        logger.info(
            "metric_federation_engine.initialized",
            conflict_strategy=conflict_strategy.value,
        )

    def add_endpoint(
        self,
        name: str,
        source_type: FederationSource = FederationSource.PROMETHEUS,
        url: str = "",
        priority: int = 0,
    ) -> FederationEndpoint:
        """Register a federation endpoint."""
        endpoint = FederationEndpoint(
            name=name, source_type=source_type, url=url, priority=priority
        )
        self._endpoints.append(endpoint)
        if len(self._endpoints) > self._max_endpoints:
            self._endpoints = self._endpoints[-self._max_endpoints :]
        logger.info(
            "metric_federation_engine.endpoint_added",
            name=name,
            source_type=source_type.value,
        )
        return endpoint

    def federate_query(self, query: str) -> FederatedResult:
        """Execute a federated query across all healthy endpoints."""
        healthy = [e for e in self._endpoints if e.status == FederationStatus.HEALTHY]
        total_latency = sum(e.latency_ms for e in healthy)
        result = FederatedResult(
            query=query,
            sources_queried=len(healthy),
            results_merged=len(healthy),
            latency_ms=round(total_latency / len(healthy), 2) if healthy else 0,
        )
        self._results.append(result)
        logger.info(
            "metric_federation_engine.query_executed",
            query=query,
            sources=len(healthy),
        )
        return result

    def merge_results(
        self,
        values: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Merge metric results from multiple sources using conflict strategy."""
        if not values:
            return {"merged": [], "conflicts": 0}
        metric_groups: dict[str, list[float]] = {}
        for v in values:
            name = v.get("metric", "unknown")
            val = v.get("value", 0.0)
            metric_groups.setdefault(name, []).append(val)
        merged: list[dict[str, Any]] = []
        conflicts = 0
        for metric, vals in metric_groups.items():
            if len(vals) > 1:
                conflicts += 1
            resolved = self._resolve_conflict(vals)
            merged.append({"metric": metric, "value": resolved})
        return {"merged": merged, "conflicts": conflicts}

    def _resolve_conflict(self, values: list[float]) -> float:
        if not values:
            return 0.0
        if self._conflict_strategy == ConflictStrategy.AVERAGE:
            return round(sum(values) / len(values), 4)
        if self._conflict_strategy == ConflictStrategy.MAX:
            return max(values)
        if self._conflict_strategy == ConflictStrategy.MIN:
            return min(values)
        return values[-1]  # LATEST_WINS or SOURCE_PRIORITY

    def resolve_conflicts(
        self,
        values: list[float],
    ) -> dict[str, Any]:
        """Resolve conflicting metric values."""
        resolved = self._resolve_conflict(values)
        return {
            "strategy": self._conflict_strategy.value,
            "input_count": len(values),
            "resolved_value": resolved,
        }

    def optimize_federation(self) -> list[dict[str, Any]]:
        """Suggest federation topology optimizations."""
        suggestions: list[dict[str, Any]] = []
        unreachable = [e for e in self._endpoints if e.status == FederationStatus.UNREACHABLE]
        if unreachable:
            suggestions.append(
                {
                    "type": "connectivity",
                    "message": f"{len(unreachable)} endpoint(s) unreachable",
                    "endpoints": [e.name for e in unreachable],
                }
            )
        slow = [e for e in self._endpoints if e.latency_ms > 500]
        if slow:
            suggestions.append(
                {
                    "type": "latency",
                    "message": f"{len(slow)} endpoint(s) with high latency (>500ms)",
                    "endpoints": [e.name for e in slow],
                }
            )
        if not suggestions:
            suggestions.append(
                {
                    "type": "none",
                    "message": "Federation topology is optimal",
                }
            )
        return suggestions

    def get_federation_topology(self) -> dict[str, Any]:
        """Return the current federation topology."""
        return {
            "endpoints": [
                {
                    "name": e.name,
                    "source_type": e.source_type.value,
                    "status": e.status.value,
                    "priority": e.priority,
                    "latency_ms": e.latency_ms,
                }
                for e in self._endpoints
            ],
            "total_endpoints": len(self._endpoints),
            "healthy": sum(1 for e in self._endpoints if e.status == FederationStatus.HEALTHY),
        }

    def generate_report(self) -> FederationReport:
        """Generate federation report."""
        by_src: dict[str, int] = {}
        by_st: dict[str, int] = {}
        for e in self._endpoints:
            by_src[e.source_type.value] = by_src.get(e.source_type.value, 0) + 1
            by_st[e.status.value] = by_st.get(e.status.value, 0) + 1
        healthy = sum(1 for e in self._endpoints if e.status == FederationStatus.HEALTHY)
        lats = [r.latency_ms for r in self._results]
        avg_lat = round(sum(lats) / len(lats), 2) if lats else 0.0
        recs: list[str] = []
        degraded = sum(1 for e in self._endpoints if e.status != FederationStatus.HEALTHY)
        if degraded > 0:
            recs.append(f"{degraded} endpoint(s) not healthy")
        if not recs:
            recs.append("Federation is healthy")
        return FederationReport(
            total_endpoints=len(self._endpoints),
            healthy_count=healthy,
            total_queries=len(self._results),
            avg_latency_ms=avg_lat,
            by_source=by_src,
            by_status=by_st,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all endpoints and results."""
        self._endpoints.clear()
        self._results.clear()
        logger.info("metric_federation_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        """Return engine statistics."""
        return {
            "total_endpoints": len(self._endpoints),
            "total_queries": len(self._results),
            "conflict_strategy": self._conflict_strategy.value,
        }
