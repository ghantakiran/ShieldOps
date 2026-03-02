"""Service Routing Optimizer — optimize service routing paths and detect latency issues."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RouteHealth(StrEnum):
    OPTIMAL = "optimal"
    DEGRADED = "degraded"
    CONGESTED = "congested"
    FAILING = "failing"
    UNKNOWN = "unknown"


class OptimizationAction(StrEnum):
    CONSOLIDATE = "consolidate"
    REROUTE = "reroute"
    ADD_FAILOVER = "add_failover"
    REMOVE_HOP = "remove_hop"
    CACHE_RESPONSE = "cache_response"


class RouteType(StrEnum):
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    STREAMING = "streaming"
    BATCH = "batch"
    EVENT_DRIVEN = "event_driven"


# --- Models ---


class RoutingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    route_name: str = ""
    route_health: RouteHealth = RouteHealth.OPTIMAL
    optimization_action: OptimizationAction = OptimizationAction.CONSOLIDATE
    route_type: RouteType = RouteType.SYNCHRONOUS
    latency_ms: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RoutingOptimization(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    route_name: str = ""
    route_health: RouteHealth = RouteHealth.OPTIMAL
    optimization_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ServiceRoutingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_optimizations: int = 0
    high_latency_count: int = 0
    avg_latency_ms: float = 0.0
    by_health: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    top_high_latency: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceRoutingOptimizer:
    """Optimize service routing paths, detect high-latency routes, track trends."""

    def __init__(
        self,
        max_records: int = 200000,
        latency_threshold_ms: float = 200.0,
    ) -> None:
        self._max_records = max_records
        self._latency_threshold_ms = latency_threshold_ms
        self._records: list[RoutingRecord] = []
        self._optimizations: list[RoutingOptimization] = []
        logger.info(
            "service_routing_optimizer.initialized",
            max_records=max_records,
            latency_threshold_ms=latency_threshold_ms,
        )

    # -- record / get / list ------------------------------------------------

    def record_routing(
        self,
        route_name: str,
        route_health: RouteHealth = RouteHealth.OPTIMAL,
        optimization_action: OptimizationAction = OptimizationAction.CONSOLIDATE,
        route_type: RouteType = RouteType.SYNCHRONOUS,
        latency_ms: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RoutingRecord:
        record = RoutingRecord(
            route_name=route_name,
            route_health=route_health,
            optimization_action=optimization_action,
            route_type=route_type,
            latency_ms=latency_ms,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "service_routing_optimizer.routing_recorded",
            record_id=record.id,
            route_name=route_name,
            route_health=route_health.value,
            optimization_action=optimization_action.value,
        )
        return record

    def get_routing(self, record_id: str) -> RoutingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_routings(
        self,
        route_health: RouteHealth | None = None,
        optimization_action: OptimizationAction | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RoutingRecord]:
        results = list(self._records)
        if route_health is not None:
            results = [r for r in results if r.route_health == route_health]
        if optimization_action is not None:
            results = [r for r in results if r.optimization_action == optimization_action]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_optimization(
        self,
        route_name: str,
        route_health: RouteHealth = RouteHealth.OPTIMAL,
        optimization_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RoutingOptimization:
        optimization = RoutingOptimization(
            route_name=route_name,
            route_health=route_health,
            optimization_score=optimization_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._optimizations.append(optimization)
        if len(self._optimizations) > self._max_records:
            self._optimizations = self._optimizations[-self._max_records :]
        logger.info(
            "service_routing_optimizer.optimization_added",
            route_name=route_name,
            route_health=route_health.value,
            optimization_score=optimization_score,
        )
        return optimization

    # -- domain operations --------------------------------------------------

    def analyze_routing_distribution(self) -> dict[str, Any]:
        """Group by route_health; return count and avg latency."""
        health_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.route_health.value
            health_data.setdefault(key, []).append(r.latency_ms)
        result: dict[str, Any] = {}
        for health, latencies in health_data.items():
            result[health] = {
                "count": len(latencies),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
            }
        return result

    def identify_high_latency_routes(self) -> list[dict[str, Any]]:
        """Return routes where latency_ms > latency_threshold_ms."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.latency_ms > self._latency_threshold_ms:
                results.append(
                    {
                        "record_id": r.id,
                        "route_name": r.route_name,
                        "route_health": r.route_health.value,
                        "route_type": r.route_type.value,
                        "latency_ms": r.latency_ms,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["latency_ms"], reverse=True)
        return results

    def rank_by_latency(self) -> list[dict[str, Any]]:
        """Group by service, avg latency_ms, sort desc (highest first)."""
        svc_latencies: dict[str, list[float]] = {}
        for r in self._records:
            svc_latencies.setdefault(r.service, []).append(r.latency_ms)
        results: list[dict[str, Any]] = []
        for svc, latencies in svc_latencies.items():
            results.append(
                {
                    "service": svc,
                    "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
                    "routing_count": len(latencies),
                }
            )
        results.sort(key=lambda x: x["avg_latency_ms"], reverse=True)
        return results

    def detect_routing_trends(self) -> dict[str, Any]:
        """Split-half comparison on optimization_score; delta 5.0."""
        if len(self._optimizations) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [o.optimization_score for o in self._optimizations]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> ServiceRoutingReport:
        by_health: dict[str, int] = {}
        by_action: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for r in self._records:
            by_health[r.route_health.value] = by_health.get(r.route_health.value, 0) + 1
            by_action[r.optimization_action.value] = (
                by_action.get(r.optimization_action.value, 0) + 1
            )
            by_type[r.route_type.value] = by_type.get(r.route_type.value, 0) + 1
        high_latency_count = sum(
            1 for r in self._records if r.latency_ms > self._latency_threshold_ms
        )
        avg_latency = (
            round(
                sum(r.latency_ms for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        high_lat = self.identify_high_latency_routes()
        top_high_latency = [p["route_name"] for p in high_lat]
        recs: list[str] = []
        if high_lat:
            recs.append(f"{len(high_lat)} high-latency route(s) detected — review routing policies")
        above = sum(1 for r in self._records if r.latency_ms > self._latency_threshold_ms)
        if above > 0:
            recs.append(
                f"{above} route(s) above latency threshold ({self._latency_threshold_ms}ms)"
            )
        if not recs:
            recs.append("Service routing latency levels are acceptable")
        return ServiceRoutingReport(
            total_records=len(self._records),
            total_optimizations=len(self._optimizations),
            high_latency_count=high_latency_count,
            avg_latency_ms=avg_latency,
            by_health=by_health,
            by_action=by_action,
            by_type=by_type,
            top_high_latency=top_high_latency,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._optimizations.clear()
        logger.info("service_routing_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        health_dist: dict[str, int] = {}
        for r in self._records:
            key = r.route_health.value
            health_dist[key] = health_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_optimizations": len(self._optimizations),
            "latency_threshold_ms": self._latency_threshold_ms,
            "health_distribution": health_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
