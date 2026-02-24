"""Dependency Health Scorer — dependency health scoring, risk propagation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HealthGrade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class DegradationType(StrEnum):
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    AVAILABILITY = "availability"
    THROUGHPUT = "throughput"
    TIMEOUT = "timeout"


class PropagationRisk(StrEnum):
    NONE = "none"
    CONTAINED = "contained"
    SPREADING = "spreading"
    CASCADE = "cascade"
    CATASTROPHIC = "catastrophic"


# --- Models ---


class DependencyScore(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    service: str = ""
    dependency_type: str = "external"
    grade: HealthGrade = HealthGrade.A
    availability_pct: float = 100.0
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    checks_total: int = 0
    checks_failed: int = 0
    last_checked: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class PropagationSimulation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    failed_dependency: str = ""
    propagation_risk: PropagationRisk = PropagationRisk.NONE
    affected_services: list[str] = Field(default_factory=list)
    estimated_impact_pct: float = 0.0
    simulated_at: float = Field(default_factory=time.time)


class CircuitBreakerRecommendation(BaseModel):
    dependency_id: str = ""
    dependency_name: str = ""
    recommended: bool = False
    reason: str = ""
    suggested_timeout_ms: int = 5000
    suggested_threshold: int = 5


# --- Engine ---


class DependencyHealthScorer:
    """External dependency health scoring, risk propagation simulation, circuit breaker recs."""

    def __init__(
        self,
        max_dependencies: int = 10000,
        check_interval: int = 60,
    ) -> None:
        self._max_dependencies = max_dependencies
        self._check_interval = check_interval
        self._dependencies: list[DependencyScore] = []
        self._simulations: list[PropagationSimulation] = []
        self._dep_graph: dict[str, list[str]] = {}  # dependency -> services that depend on it
        logger.info(
            "dependency_scorer.initialized",
            max_dependencies=max_dependencies,
            check_interval=check_interval,
        )

    def register_dependency(
        self,
        name: str,
        service: str = "",
        dependency_type: str = "external",
        dependents: list[str] | None = None,
    ) -> DependencyScore:
        dep = DependencyScore(
            name=name,
            service=service,
            dependency_type=dependency_type,
        )
        self._dependencies.append(dep)
        if dependents:
            self._dep_graph[name] = dependents
        if len(self._dependencies) > self._max_dependencies:
            self._dependencies = self._dependencies[-self._max_dependencies :]
        logger.info(
            "dependency_scorer.registered",
            dep_id=dep.id,
            name=name,
        )
        return dep

    def get_dependency(self, dep_id: str) -> DependencyScore | None:
        for d in self._dependencies:
            if d.id == dep_id:
                return d
        return None

    def list_dependencies(
        self,
        grade: HealthGrade | None = None,
        service: str | None = None,
        limit: int = 100,
    ) -> list[DependencyScore]:
        results = list(self._dependencies)
        if grade is not None:
            results = [d for d in results if d.grade == grade]
        if service is not None:
            results = [d for d in results if d.service == service]
        return results[-limit:]

    def record_health_check(
        self,
        dep_id: str,
        latency_ms: float = 0.0,
        success: bool = True,
        error_rate: float = 0.0,
    ) -> dict[str, Any]:
        dep = self.get_dependency(dep_id)
        if dep is None:
            return {"error": "dependency_not_found"}
        dep.checks_total += 1
        if not success:
            dep.checks_failed += 1
        # Running avg latency
        if dep.checks_total > 1:
            dep.avg_latency_ms = round(
                (dep.avg_latency_ms * (dep.checks_total - 1) + latency_ms) / dep.checks_total, 2
            )
        else:
            dep.avg_latency_ms = latency_ms
        dep.error_rate = error_rate
        dep.availability_pct = round(
            (dep.checks_total - dep.checks_failed) / dep.checks_total * 100, 2
        )
        dep.last_checked = time.time()
        # Compute grade
        dep.grade = self._compute_grade(dep)
        return {
            "dep_id": dep_id,
            "grade": dep.grade.value,
            "availability_pct": dep.availability_pct,
        }

    def _compute_grade(self, dep: DependencyScore) -> HealthGrade:
        if dep.availability_pct >= 99.9 and dep.error_rate < 0.01:
            return HealthGrade.A
        elif dep.availability_pct >= 99.5 and dep.error_rate < 0.05:
            return HealthGrade.B
        elif dep.availability_pct >= 99.0 and dep.error_rate < 0.1:
            return HealthGrade.C
        elif dep.availability_pct >= 95.0:
            return HealthGrade.D
        else:
            return HealthGrade.F

    def compute_health_score(self, dep_id: str) -> dict[str, Any] | None:
        dep = self.get_dependency(dep_id)
        if dep is None:
            return None
        return {
            "dep_id": dep.id,
            "name": dep.name,
            "grade": dep.grade.value,
            "availability_pct": dep.availability_pct,
            "avg_latency_ms": dep.avg_latency_ms,
            "error_rate": dep.error_rate,
            "checks_total": dep.checks_total,
        }

    def simulate_failure(self, dependency_name: str) -> PropagationSimulation:
        affected = self._dep_graph.get(dependency_name, [])
        # Check for cascading via affected services
        all_affected: set[str] = set(affected)
        for svc in affected:
            for _dep_name, dependents in self._dep_graph.items():
                if svc in dependents:
                    all_affected.update(dependents)
        total_deps = len(self._dependencies)
        impact_pct = round(len(all_affected) / max(total_deps, 1) * 100, 1)
        if impact_pct > 50:
            risk = PropagationRisk.CATASTROPHIC
        elif impact_pct > 30:
            risk = PropagationRisk.CASCADE
        elif impact_pct > 10:
            risk = PropagationRisk.SPREADING
        elif all_affected:
            risk = PropagationRisk.CONTAINED
        else:
            risk = PropagationRisk.NONE
        sim = PropagationSimulation(
            failed_dependency=dependency_name,
            propagation_risk=risk,
            affected_services=sorted(all_affected),
            estimated_impact_pct=impact_pct,
        )
        self._simulations.append(sim)
        return sim

    def recommend_circuit_breakers(self) -> list[CircuitBreakerRecommendation]:
        recs: list[CircuitBreakerRecommendation] = []
        for dep in self._dependencies:
            if dep.grade in (HealthGrade.D, HealthGrade.F):
                recs.append(
                    CircuitBreakerRecommendation(
                        dependency_id=dep.id,
                        dependency_name=dep.name,
                        recommended=True,
                        reason=f"Grade {dep.grade.value}: availability {dep.availability_pct}%",
                        suggested_timeout_ms=max(int(dep.avg_latency_ms * 3), 5000),
                        suggested_threshold=3 if dep.grade == HealthGrade.F else 5,
                    )
                )
            elif dep.error_rate > 0.05:
                recs.append(
                    CircuitBreakerRecommendation(
                        dependency_id=dep.id,
                        dependency_name=dep.name,
                        recommended=True,
                        reason=f"High error rate: {dep.error_rate:.1%}",
                        suggested_timeout_ms=5000,
                        suggested_threshold=5,
                    )
                )
        return recs

    def get_degraded_dependencies(self) -> list[DependencyScore]:
        degraded = (HealthGrade.C, HealthGrade.D, HealthGrade.F)
        return [d for d in self._dependencies if d.grade in degraded]

    def get_risk_ranking(self, limit: int = 20) -> list[dict[str, Any]]:
        ranked = sorted(
            self._dependencies,
            key=lambda d: (
                {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4}.get(d.grade, 5),
                -d.availability_pct,
            ),
            reverse=True,
        )
        return [
            {
                "name": d.name,
                "grade": d.grade.value,
                "availability_pct": d.availability_pct,
                "error_rate": d.error_rate,
            }
            for d in ranked[:limit]
        ]

    def get_stats(self) -> dict[str, Any]:
        grade_counts: dict[str, int] = {}
        for d in self._dependencies:
            grade_counts[d.grade] = grade_counts.get(d.grade, 0) + 1
        return {
            "total_dependencies": len(self._dependencies),
            "total_simulations": len(self._simulations),
            "grade_distribution": grade_counts,
            "degraded_count": len(self.get_degraded_dependencies()),
        }
