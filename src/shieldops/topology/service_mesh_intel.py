"""Service Mesh Intelligence — analyze service mesh traffic patterns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MeshPattern(StrEnum):
    DIRECT_CALL = "direct_call"
    LOAD_BALANCED = "load_balanced"
    CIRCUIT_BROKEN = "circuit_broken"
    RETRY_LOOP = "retry_loop"
    TIMEOUT_CASCADE = "timeout_cascade"


class MeshHealth(StrEnum):
    OPTIMAL = "optimal"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class MeshAntiPattern(StrEnum):
    UNNECESSARY_HOP = "unnecessary_hop"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    CHATTY_SERVICE = "chatty_service"
    SINGLE_POINT_FAILURE = "single_point_failure"
    TIGHT_COUPLING = "tight_coupling"


# --- Models ---


class MeshRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    pattern: MeshPattern = MeshPattern.DIRECT_CALL
    health: MeshHealth = MeshHealth.OPTIMAL
    anti_pattern: MeshAntiPattern = MeshAntiPattern.UNNECESSARY_HOP
    latency_ms: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class MeshRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    pattern: MeshPattern = MeshPattern.DIRECT_CALL
    health: MeshHealth = MeshHealth.OPTIMAL
    max_latency_ms: float = 500.0
    auto_optimize: bool = False
    created_at: float = Field(default_factory=time.time)


class ServiceMeshReport(BaseModel):
    total_observations: int = 0
    total_rules: int = 0
    healthy_rate_pct: float = 0.0
    by_pattern: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    anti_pattern_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceMeshIntelligence:
    """Analyze service mesh traffic patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        max_latency_ms: float = 500.0,
    ) -> None:
        self._max_records = max_records
        self._max_latency_ms = max_latency_ms
        self._records: list[MeshRecord] = []
        self._rules: list[MeshRule] = []
        logger.info(
            "service_mesh_intel.initialized",
            max_records=max_records,
            max_latency_ms=max_latency_ms,
        )

    # -- record / get / list -----------------------------------------

    def record_observation(
        self,
        service_name: str,
        pattern: MeshPattern = MeshPattern.DIRECT_CALL,
        health: MeshHealth = MeshHealth.OPTIMAL,
        anti_pattern: MeshAntiPattern = (MeshAntiPattern.UNNECESSARY_HOP),
        latency_ms: float = 0.0,
        details: str = "",
    ) -> MeshRecord:
        record = MeshRecord(
            service_name=service_name,
            pattern=pattern,
            health=health,
            anti_pattern=anti_pattern,
            latency_ms=latency_ms,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "service_mesh_intel.recorded",
            record_id=record.id,
            service_name=service_name,
            pattern=pattern.value,
            health=health.value,
        )
        return record

    def get_observation(self, record_id: str) -> MeshRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_observations(
        self,
        service_name: str | None = None,
        pattern: MeshPattern | None = None,
        limit: int = 50,
    ) -> list[MeshRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if pattern is not None:
            results = [r for r in results if r.pattern == pattern]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        pattern: MeshPattern = MeshPattern.DIRECT_CALL,
        health: MeshHealth = MeshHealth.OPTIMAL,
        max_latency_ms: float = 500.0,
        auto_optimize: bool = False,
    ) -> MeshRule:
        rule = MeshRule(
            rule_name=rule_name,
            pattern=pattern,
            health=health,
            max_latency_ms=max_latency_ms,
            auto_optimize=auto_optimize,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "service_mesh_intel.rule_added",
            rule_name=rule_name,
            pattern=pattern.value,
            health=health.value,
        )
        return rule

    # -- domain operations -------------------------------------------

    def analyze_mesh_health(self, service_name: str) -> dict[str, Any]:
        """Analyze mesh health for a service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {
                "service_name": service_name,
                "status": "no_data",
            }
        healthy = sum(1 for r in records if r.health in (MeshHealth.OPTIMAL, MeshHealth.HEALTHY))
        healthy_rate = round(healthy / len(records) * 100, 2)
        avg_latency = round(
            sum(r.latency_ms for r in records) / len(records),
            2,
        )
        return {
            "service_name": service_name,
            "observation_count": len(records),
            "healthy_count": healthy,
            "healthy_rate": healthy_rate,
            "avg_latency": avg_latency,
            "meets_threshold": (avg_latency <= self._max_latency_ms),
        }

    def identify_anti_patterns(
        self,
    ) -> list[dict[str, Any]]:
        """Find services with degraded/unhealthy/critical."""
        bad_counts: dict[str, int] = {}
        for r in self._records:
            if r.health in (
                MeshHealth.DEGRADED,
                MeshHealth.UNHEALTHY,
                MeshHealth.CRITICAL,
            ):
                bad_counts[r.service_name] = bad_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in bad_counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "anti_pattern_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["anti_pattern_count"],
            reverse=True,
        )
        return results

    def rank_by_latency(
        self,
    ) -> list[dict[str, Any]]:
        """Rank services by avg latency descending."""
        totals: dict[str, list[float]] = {}
        for r in self._records:
            totals.setdefault(r.service_name, []).append(r.latency_ms)
        results: list[dict[str, Any]] = []
        for svc, lats in totals.items():
            avg = round(sum(lats) / len(lats), 2)
            results.append(
                {
                    "service_name": svc,
                    "avg_latency_ms": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_latency_ms"],
            reverse=True,
        )
        return results

    def detect_mesh_issues(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with >3 non-OPTIMAL/HEALTHY."""
        svc_bad: dict[str, int] = {}
        for r in self._records:
            if r.health not in (
                MeshHealth.OPTIMAL,
                MeshHealth.HEALTHY,
            ):
                svc_bad[r.service_name] = svc_bad.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_bad.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "issue_count": count,
                        "issue_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["issue_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> ServiceMeshReport:
        by_pattern: dict[str, int] = {}
        by_health: dict[str, int] = {}
        for r in self._records:
            by_pattern[r.pattern.value] = by_pattern.get(r.pattern.value, 0) + 1
            by_health[r.health.value] = by_health.get(r.health.value, 0) + 1
        healthy_count = sum(
            1 for r in self._records if r.health in (MeshHealth.OPTIMAL, MeshHealth.HEALTHY)
        )
        healthy_rate = (
            round(
                healthy_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        ap_count = len(self.identify_anti_patterns())
        recs: list[str] = []
        if healthy_rate < 80.0:
            recs.append(f"Healthy rate {healthy_rate}% is below 80.0% threshold")
        if ap_count > 0:
            recs.append(f"{ap_count} service(s) with anti-patterns")
        issues = len(self.detect_mesh_issues())
        if issues > 0:
            recs.append(f"{issues} service(s) with mesh issues")
        if not recs:
            recs.append("Service mesh health is healthy")
        return ServiceMeshReport(
            total_observations=len(self._records),
            total_rules=len(self._rules),
            healthy_rate_pct=healthy_rate,
            by_pattern=by_pattern,
            by_health=by_health,
            anti_pattern_count=ap_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("service_mesh_intel.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        pattern_dist: dict[str, int] = {}
        for r in self._records:
            key = r.pattern.value
            pattern_dist[key] = pattern_dist.get(key, 0) + 1
        return {
            "total_observations": len(self._records),
            "total_rules": len(self._rules),
            "max_latency_ms": self._max_latency_ms,
            "pattern_distribution": pattern_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
