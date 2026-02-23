"""Dependency health tracking with cascade failure detection.

Tracks health status of upstream/downstream dependencies and detects
cascade failures when multiple related services go down simultaneously.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class DependencyStatus(enum.StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class DependencyType(enum.StrEnum):
    DATABASE = "database"
    API = "api"
    QUEUE = "queue"
    CACHE = "cache"
    INTERNAL_SERVICE = "internal_service"
    EXTERNAL_SERVICE = "external_service"


# -- Models --------------------------------------------------------------------


class DependencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    dependency_type: DependencyType
    upstream_of: list[str] = Field(default_factory=list)
    downstream_of: list[str] = Field(default_factory=list)
    status: DependencyStatus = DependencyStatus.UNKNOWN
    endpoint: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class HealthCheck(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    dependency_id: str
    status: DependencyStatus
    latency_ms: float = 0.0
    error_message: str = ""
    checked_at: float = Field(default_factory=time.time)


class CascadeAlert(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    root_dependency_id: str
    affected_dependencies: list[str] = Field(default_factory=list)
    severity: str = "warning"
    message: str = ""
    detected_at: float = Field(default_factory=time.time)


# -- Tracker -------------------------------------------------------------------


class DependencyHealthTracker:
    """Track dependency health and detect cascade failures.

    Parameters
    ----------
    max_checks:
        Maximum health check records to retain.
    cascade_threshold:
        Minimum affected dependencies to trigger a cascade alert.
    """

    def __init__(
        self,
        max_checks: int = 10000,
        cascade_threshold: int = 3,
    ) -> None:
        self._dependencies: dict[str, DependencyRecord] = {}
        self._checks: list[HealthCheck] = []
        self._cascades: list[CascadeAlert] = []
        self._max_checks = max_checks
        self._cascade_threshold = cascade_threshold

    def register_dependency(
        self,
        name: str,
        dependency_type: DependencyType,
        upstream_of: list[str] | None = None,
        downstream_of: list[str] | None = None,
        endpoint: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> DependencyRecord:
        dep = DependencyRecord(
            name=name,
            dependency_type=dependency_type,
            upstream_of=upstream_of or [],
            downstream_of=downstream_of or [],
            endpoint=endpoint,
            metadata=metadata or {},
        )
        self._dependencies[dep.id] = dep
        logger.info("dependency_registered", dependency_id=dep.id, name=name)
        return dep

    def record_health_check(
        self,
        dependency_id: str,
        status: DependencyStatus,
        latency_ms: float = 0.0,
        error_message: str = "",
    ) -> HealthCheck:
        if dependency_id not in self._dependencies:
            raise ValueError(f"Dependency not found: {dependency_id}")
        check = HealthCheck(
            dependency_id=dependency_id,
            status=status,
            latency_ms=latency_ms,
            error_message=error_message,
        )
        self._checks.append(check)
        if len(self._checks) > self._max_checks:
            self._checks = self._checks[-self._max_checks :]
        self._dependencies[dependency_id].status = status
        logger.info(
            "health_check_recorded",
            dependency_id=dependency_id,
            status=status,
        )
        return check

    def get_dependency_status(self, dependency_id: str) -> DependencyStatus:
        for check in reversed(self._checks):
            if check.dependency_id == dependency_id:
                return check.status
        return DependencyStatus.UNKNOWN

    def detect_cascades(self) -> list[CascadeAlert]:
        new_cascades: list[CascadeAlert] = []
        for dep in self._dependencies.values():
            if dep.status != DependencyStatus.DOWN:
                continue
            affected = [
                d_id
                for d_id, d in self._dependencies.items()
                if dep.id in d.downstream_of and d_id != dep.id
            ]
            if len(affected) >= self._cascade_threshold:
                cascade = CascadeAlert(
                    root_dependency_id=dep.id,
                    affected_dependencies=affected,
                    severity=(
                        "critical" if len(affected) >= self._cascade_threshold * 2 else "warning"
                    ),
                    message=(
                        f"Cascade detected: {dep.name} is down, "
                        f"affecting {len(affected)} dependencies"
                    ),
                )
                new_cascades.append(cascade)
                self._cascades.append(cascade)
                logger.warning(
                    "cascade_detected",
                    root_dependency_id=dep.id,
                    affected_count=len(affected),
                )
        return new_cascades

    def list_dependencies(
        self,
        status: DependencyStatus | None = None,
        dep_type: DependencyType | None = None,
    ) -> list[DependencyRecord]:
        deps = list(self._dependencies.values())
        if status:
            deps = [d for d in deps if d.status == status]
        if dep_type:
            deps = [d for d in deps if d.dependency_type == dep_type]
        return deps

    def get_dependency(self, dependency_id: str) -> DependencyRecord | None:
        return self._dependencies.get(dependency_id)

    def remove_dependency(self, dependency_id: str) -> bool:
        return self._dependencies.pop(dependency_id, None) is not None

    def get_stats(self) -> dict[str, Any]:
        healthy = sum(
            1 for d in self._dependencies.values() if d.status == DependencyStatus.HEALTHY
        )
        degraded = sum(
            1 for d in self._dependencies.values() if d.status == DependencyStatus.DEGRADED
        )
        down = sum(1 for d in self._dependencies.values() if d.status == DependencyStatus.DOWN)
        return {
            "total_dependencies": len(self._dependencies),
            "total_checks": len(self._checks),
            "healthy_count": healthy,
            "degraded_count": degraded,
            "down_count": down,
            "total_cascades": len(self._cascades),
        }
