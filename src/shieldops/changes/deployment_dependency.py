"""Deployment Dependency Tracker — inter-service deploy deps."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DependencyType(StrEnum):
    API_CONTRACT = "api_contract"
    SCHEMA_MIGRATION = "schema_migration"
    CONFIG_CHANGE = "config_change"
    SHARED_LIBRARY = "shared_library"
    INFRASTRUCTURE = "infrastructure"


class DependencyDirection(StrEnum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"
    BIDIRECTIONAL = "bidirectional"
    TRANSITIVE = "transitive"
    OPTIONAL = "optional"


class DependencyRisk(StrEnum):
    BREAKING = "breaking"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    SAFE = "safe"


# --- Models ---


class DeployDependencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    dep_type: DependencyType = DependencyType.API_CONTRACT
    direction: DependencyDirection = DependencyDirection.UPSTREAM
    risk: DependencyRisk = DependencyRisk.LOW
    depth: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencyConstraint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    constraint_name: str = ""
    dep_type: DependencyType = DependencyType.API_CONTRACT
    direction: DependencyDirection = DependencyDirection.UPSTREAM
    priority: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DeployDependencyReport(BaseModel):
    total_records: int = 0
    total_constraints: int = 0
    avg_depth: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_direction: dict[str, int] = Field(default_factory=dict)
    breaking_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentDependencyTracker:
    """Track inter-service deployment dependencies and ordering constraints."""

    def __init__(
        self,
        max_records: int = 200000,
        max_depth: int = 5,
    ) -> None:
        self._max_records = max_records
        self._max_depth = max_depth
        self._records: list[DeployDependencyRecord] = []
        self._constraints: list[DependencyConstraint] = []
        logger.info(
            "deployment_dependency.initialized",
            max_records=max_records,
            max_depth=max_depth,
        )

    # -- record / get / list ---------------------------------------------

    def record_dependency(
        self,
        service_name: str,
        dep_type: DependencyType = DependencyType.API_CONTRACT,
        direction: DependencyDirection = DependencyDirection.UPSTREAM,
        risk: DependencyRisk = DependencyRisk.LOW,
        depth: int = 0,
        details: str = "",
    ) -> DeployDependencyRecord:
        record = DeployDependencyRecord(
            service_name=service_name,
            dep_type=dep_type,
            direction=direction,
            risk=risk,
            depth=depth,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "deployment_dependency.dependency_recorded",
            record_id=record.id,
            service_name=service_name,
            dep_type=dep_type.value,
        )
        return record

    def get_dependency(self, record_id: str) -> DeployDependencyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_dependencies(
        self,
        service_name: str | None = None,
        dep_type: DependencyType | None = None,
        limit: int = 50,
    ) -> list[DeployDependencyRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if dep_type is not None:
            results = [r for r in results if r.dep_type == dep_type]
        return results[-limit:]

    def add_constraint(
        self,
        constraint_name: str,
        dep_type: DependencyType = DependencyType.API_CONTRACT,
        direction: DependencyDirection = DependencyDirection.UPSTREAM,
        priority: int = 0,
        description: str = "",
    ) -> DependencyConstraint:
        constraint = DependencyConstraint(
            constraint_name=constraint_name,
            dep_type=dep_type,
            direction=direction,
            priority=priority,
            description=description,
        )
        self._constraints.append(constraint)
        if len(self._constraints) > self._max_records:
            self._constraints = self._constraints[-self._max_records :]
        logger.info(
            "deployment_dependency.constraint_added",
            constraint_name=constraint_name,
            dep_type=dep_type.value,
        )
        return constraint

    # -- domain operations -----------------------------------------------

    def analyze_service_dependencies(self, service_name: str) -> dict[str, Any]:
        """Analyze average depth for a service and check threshold."""
        svc_records = [r for r in self._records if r.service_name == service_name]
        if not svc_records:
            return {"service_name": service_name, "status": "no_data"}
        avg_depth = round(
            sum(r.depth for r in svc_records) / len(svc_records),
            2,
        )
        meets_threshold = avg_depth <= self._max_depth
        return {
            "service_name": service_name,
            "avg_depth": avg_depth,
            "record_count": len(svc_records),
            "meets_threshold": meets_threshold,
            "max_depth": self._max_depth,
        }

    def identify_breaking_dependencies(self) -> list[dict[str, Any]]:
        """Find services with more than one BREAKING or HIGH risk dependency."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.risk in (DependencyRisk.BREAKING, DependencyRisk.HIGH):
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 1:
                results.append({"service_name": svc, "breaking_high_count": count})
        results.sort(key=lambda x: x["breaking_high_count"], reverse=True)
        return results

    def rank_by_dependency_depth(self) -> list[dict[str, Any]]:
        """Rank services by average dependency depth descending."""
        svc_depths: dict[str, list[int]] = {}
        for r in self._records:
            svc_depths.setdefault(r.service_name, []).append(r.depth)
        results: list[dict[str, Any]] = []
        for svc, depths in svc_depths.items():
            avg = round(sum(depths) / len(depths), 2)
            results.append(
                {
                    "service_name": svc,
                    "avg_depth": avg,
                    "record_count": len(depths),
                }
            )
        results.sort(key=lambda x: x["avg_depth"], reverse=True)
        return results

    def detect_dependency_cycles(self) -> list[dict[str, Any]]:
        """Detect services with more than 3 dependency records."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append({"service_name": svc, "record_count": count})
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> DeployDependencyReport:
        by_type: dict[str, int] = {}
        by_direction: dict[str, int] = {}
        for r in self._records:
            by_type[r.dep_type.value] = by_type.get(r.dep_type.value, 0) + 1
            by_direction[r.direction.value] = by_direction.get(r.direction.value, 0) + 1
        avg_depth = (
            round(
                sum(r.depth for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        breaking_count = sum(1 for r in self._records if r.risk == DependencyRisk.BREAKING)
        recs: list[str] = []
        if breaking_count > 0:
            recs.append(f"{breaking_count} breaking dependency(ies) detected")
        high_count = sum(1 for r in self._records if r.risk == DependencyRisk.HIGH)
        if high_count > 0:
            recs.append(f"{high_count} high-risk dependency(ies) detected")
        if not recs:
            recs.append("Deployment dependency health is good")
        return DeployDependencyReport(
            total_records=len(self._records),
            total_constraints=len(self._constraints),
            avg_depth=avg_depth,
            by_type=by_type,
            by_direction=by_direction,
            breaking_count=breaking_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._constraints.clear()
        logger.info("deployment_dependency.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dep_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_constraints": len(self._constraints),
            "max_depth": self._max_depth,
            "type_distribution": type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
