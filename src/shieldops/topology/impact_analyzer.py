"""Service Dependency Impact Analyzer — what-if cascade failure simulation across service graph."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ImpactLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DependencyDirection(StrEnum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"
    BOTH = "both"


class SimulationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# --- Models ---


class ServiceDependency(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_service: str
    target_service: str
    dependency_type: str = "runtime"
    criticality: int = 3
    created_at: float = Field(default_factory=time.time)


class ImpactPath(BaseModel):
    path: list[str] = Field(default_factory=list)
    impact_level: ImpactLevel = ImpactLevel.NONE
    depth: int = 0


class ImpactSimulation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    failed_service: str
    direction: DependencyDirection = DependencyDirection.DOWNSTREAM
    status: SimulationStatus = SimulationStatus.PENDING
    affected_services: list[str] = Field(default_factory=list)
    impact_paths: list[ImpactPath] = Field(default_factory=list)
    overall_impact: ImpactLevel = ImpactLevel.NONE
    created_at: float = Field(default_factory=time.time)
    completed_at: float | None = None


# --- Analyzer ---


class ServiceDependencyImpactAnalyzer:
    """Simulates cascade failure impact across service dependency graph."""

    def __init__(
        self,
        max_dependencies: int = 5000,
        max_simulations: int = 10000,
    ) -> None:
        self._max_dependencies = max_dependencies
        self._max_simulations = max_simulations
        self._dependencies: dict[str, ServiceDependency] = {}
        self._simulations: dict[str, ImpactSimulation] = {}
        logger.info(
            "impact_analyzer.initialized",
            max_dependencies=max_dependencies,
            max_simulations=max_simulations,
        )

    def add_dependency(
        self,
        source_service: str,
        target_service: str,
        dependency_type: str = "runtime",
        criticality: int = 3,
    ) -> ServiceDependency:
        """Add a service dependency."""
        dep = ServiceDependency(
            source_service=source_service,
            target_service=target_service,
            dependency_type=dependency_type,
            criticality=criticality,
        )
        self._dependencies[dep.id] = dep
        if len(self._dependencies) > self._max_dependencies:
            oldest = next(iter(self._dependencies))
            del self._dependencies[oldest]
        logger.info(
            "impact_analyzer.dependency_added",
            dep_id=dep.id,
            source=source_service,
            target=target_service,
        )
        return dep

    def remove_dependency(self, dependency_id: str) -> bool:
        """Remove a dependency."""
        if dependency_id in self._dependencies:
            del self._dependencies[dependency_id]
            return True
        return False

    def simulate_failure(
        self,
        failed_service: str,
        direction: DependencyDirection = DependencyDirection.DOWNSTREAM,
    ) -> ImpactSimulation:
        """Simulate a service failure and compute cascade impact."""
        sim = ImpactSimulation(
            failed_service=failed_service,
            direction=direction,
            status=SimulationStatus.RUNNING,
        )
        affected: set[str] = set()
        paths: list[ImpactPath] = []
        if direction in (DependencyDirection.DOWNSTREAM, DependencyDirection.BOTH):
            self._trace_downstream(failed_service, [failed_service], affected, paths, set())
        if direction in (DependencyDirection.UPSTREAM, DependencyDirection.BOTH):
            self._trace_upstream(failed_service, [failed_service], affected, paths, set())
        affected.discard(failed_service)
        sim.affected_services = sorted(affected)
        sim.impact_paths = paths
        count = len(affected)
        if count == 0:
            sim.overall_impact = ImpactLevel.NONE
        elif count <= 2:
            sim.overall_impact = ImpactLevel.LOW
        elif count <= 5:
            sim.overall_impact = ImpactLevel.MEDIUM
        elif count <= 10:
            sim.overall_impact = ImpactLevel.HIGH
        else:
            sim.overall_impact = ImpactLevel.CRITICAL
        sim.status = SimulationStatus.COMPLETED
        sim.completed_at = time.time()
        self._simulations[sim.id] = sim
        if len(self._simulations) > self._max_simulations:
            oldest = next(iter(self._simulations))
            del self._simulations[oldest]
        logger.info(
            "impact_analyzer.simulation_completed",
            sim_id=sim.id,
            failed_service=failed_service,
            affected_count=count,
            overall_impact=sim.overall_impact,
        )
        return sim

    def _trace_downstream(
        self,
        service: str,
        path: list[str],
        affected: set[str],
        paths: list[ImpactPath],
        visited: set[str],
    ) -> None:
        """Trace downstream dependencies recursively."""
        if service in visited:
            return
        visited.add(service)
        for dep in self._dependencies.values():
            if dep.source_service == service:
                target = dep.target_service
                new_path = [*path, target]
                affected.add(target)
                depth = len(new_path) - 1
                if depth <= 1:
                    level = ImpactLevel.HIGH
                elif depth <= 3:
                    level = ImpactLevel.MEDIUM
                else:
                    level = ImpactLevel.LOW
                paths.append(ImpactPath(path=new_path, impact_level=level, depth=depth))
                self._trace_downstream(target, new_path, affected, paths, visited)

    def _trace_upstream(
        self,
        service: str,
        path: list[str],
        affected: set[str],
        paths: list[ImpactPath],
        visited: set[str],
    ) -> None:
        """Trace upstream dependencies recursively."""
        if service in visited:
            return
        visited.add(service)
        for dep in self._dependencies.values():
            if dep.target_service == service:
                source = dep.source_service
                new_path = [*path, source]
                affected.add(source)
                depth = len(new_path) - 1
                if depth <= 1:
                    level = ImpactLevel.HIGH
                elif depth <= 3:
                    level = ImpactLevel.MEDIUM
                else:
                    level = ImpactLevel.LOW
                paths.append(ImpactPath(path=new_path, impact_level=level, depth=depth))
                self._trace_upstream(source, new_path, affected, paths, visited)

    def get_impact_paths(
        self,
        simulation_id: str,
    ) -> list[ImpactPath]:
        """Get impact paths for a simulation."""
        sim = self._simulations.get(simulation_id)
        if sim is None:
            return []
        return sim.impact_paths

    def get_simulation(self, simulation_id: str) -> ImpactSimulation | None:
        """Retrieve a simulation by ID."""
        return self._simulations.get(simulation_id)

    def list_simulations(
        self,
        status: SimulationStatus | None = None,
    ) -> list[ImpactSimulation]:
        """List simulations with optional filter."""
        results = list(self._simulations.values())
        if status is not None:
            results = [s for s in results if s.status == status]
        return results

    def list_dependencies(
        self,
        service: str | None = None,
    ) -> list[ServiceDependency]:
        """List dependencies with optional service filter."""
        results = list(self._dependencies.values())
        if service is not None:
            results = [
                d for d in results if d.source_service == service or d.target_service == service
            ]
        return results

    def get_critical_services(self, min_dependents: int = 3) -> list[dict[str, Any]]:
        """Get services with the most dependents (single points of failure)."""
        dependent_count: dict[str, int] = {}
        for dep in self._dependencies.values():
            dependent_count[dep.target_service] = dependent_count.get(dep.target_service, 0) + 1
        critical: list[dict[str, Any]] = sorted(
            [
                {"service": svc, "dependent_count": count}
                for svc, count in dependent_count.items()
                if count >= min_dependents
            ],
            key=lambda x: x.get("dependent_count", 0),  # type: ignore[return-value]
            reverse=True,
        )
        return critical

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        status_counts: dict[str, int] = {}
        impact_counts: dict[str, int] = {}
        for s in self._simulations.values():
            status_counts[s.status] = status_counts.get(s.status, 0) + 1
            impact_counts[s.overall_impact] = impact_counts.get(s.overall_impact, 0) + 1
        return {
            "total_dependencies": len(self._dependencies),
            "total_simulations": len(self._simulations),
            "simulation_status_distribution": status_counts,
            "impact_distribution": impact_counts,
        }
