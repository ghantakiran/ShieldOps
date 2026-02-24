"""Resource Lifecycle Tracker — cloud resource lifecycle from provisioning to decommissioning."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LifecyclePhase(StrEnum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SCALING = "scaling"
    DEPRECATED = "deprecated"
    DECOMMISSIONING = "decommissioning"
    TERMINATED = "terminated"


class ResourceCategory(StrEnum):
    COMPUTE = "compute"
    DATABASE = "database"
    STORAGE = "storage"
    NETWORK = "network"
    CONTAINER = "container"
    SERVERLESS = "serverless"


class TransitionReason(StrEnum):
    PLANNED = "planned"
    COST_OPTIMIZATION = "cost_optimization"
    END_OF_LIFE = "end_of_life"
    SECURITY_CONCERN = "security_concern"
    MIGRATION = "migration"
    AUTO_SCALING = "auto_scaling"


# --- Models ---


class ResourceEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_name: str
    category: ResourceCategory
    phase: LifecyclePhase = LifecyclePhase.PROVISIONING
    owner: str = ""
    environment: str = "production"
    monthly_cost: float = 0.0
    created_at: float = Field(default_factory=time.time)


class PhaseTransition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str
    from_phase: LifecyclePhase
    to_phase: LifecyclePhase
    reason: TransitionReason = TransitionReason.PLANNED
    transitioned_at: float = Field(default_factory=time.time)


class LifecycleSummary(BaseModel):
    total_resources: int = 0
    phase_breakdown: dict[str, int] = Field(default_factory=dict)
    category_breakdown: dict[str, int] = Field(default_factory=dict)
    stale_count: int = 0
    decommission_candidates: int = 0
    avg_age_days: float = 0.0
    total_monthly_cost: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ResourceLifecycleTracker:
    """Track cloud resource lifecycle from provisioning through decommissioning."""

    def __init__(
        self,
        max_resources: int = 100000,
        stale_days: int = 180,
    ) -> None:
        self._max_resources = max_resources
        self._stale_days = stale_days
        self._resources: list[ResourceEntry] = []
        self._transitions: list[PhaseTransition] = []
        logger.info(
            "resource_lifecycle.initialized",
            max_resources=max_resources,
            stale_days=stale_days,
        )

    def register_resource(
        self,
        resource_name: str,
        category: ResourceCategory,
        owner: str = "",
        environment: str = "production",
        monthly_cost: float = 0.0,
    ) -> ResourceEntry:
        resource = ResourceEntry(
            resource_name=resource_name,
            category=category,
            owner=owner,
            environment=environment,
            monthly_cost=monthly_cost,
        )
        self._resources.append(resource)
        if len(self._resources) > self._max_resources:
            self._resources = self._resources[-self._max_resources :]
        logger.info(
            "resource_lifecycle.resource_registered",
            resource_id=resource.id,
            resource_name=resource_name,
            category=category,
        )
        return resource

    def get_resource(self, resource_id: str) -> ResourceEntry | None:
        for r in self._resources:
            if r.id == resource_id:
                return r
        return None

    def list_resources(
        self,
        category: ResourceCategory | None = None,
        phase: LifecyclePhase | None = None,
        limit: int = 100,
    ) -> list[ResourceEntry]:
        results = self._resources
        if category is not None:
            results = [r for r in results if r.category == category]
        if phase is not None:
            results = [r for r in results if r.phase == phase]
        return results[-limit:]

    def transition_phase(
        self,
        resource_id: str,
        to_phase: LifecyclePhase,
        reason: TransitionReason = TransitionReason.PLANNED,
    ) -> PhaseTransition | None:
        resource = self.get_resource(resource_id)
        if resource is None:
            return None
        from_phase = resource.phase
        resource.phase = to_phase
        transition = PhaseTransition(
            resource_id=resource_id,
            from_phase=from_phase,
            to_phase=to_phase,
            reason=reason,
        )
        self._transitions.append(transition)
        logger.info(
            "resource_lifecycle.phase_transitioned",
            resource_id=resource_id,
            from_phase=from_phase,
            to_phase=to_phase,
            reason=reason,
        )
        return transition

    def list_transitions(
        self,
        resource_id: str | None = None,
        limit: int = 100,
    ) -> list[PhaseTransition]:
        results = self._transitions
        if resource_id is not None:
            results = [t for t in results if t.resource_id == resource_id]
        return results[-limit:]

    def detect_stale_resources(self) -> list[ResourceEntry]:
        now = time.time()
        threshold_seconds = self._stale_days * 86400
        return [
            r
            for r in self._resources
            if r.phase == LifecyclePhase.ACTIVE and (now - r.created_at) > threshold_seconds
        ]

    def get_decommission_candidates(self) -> list[ResourceEntry]:
        return [r for r in self._resources if r.phase == LifecyclePhase.DEPRECATED]

    def compute_age_distribution(self) -> dict[str, Any]:
        now = time.time()
        buckets = {
            "0_30d": 0,
            "30_90d": 0,
            "90_180d": 0,
            "180d_plus": 0,
        }
        for r in self._resources:
            age_days = (now - r.created_at) / 86400
            if age_days <= 30:
                buckets["0_30d"] += 1
            elif age_days <= 90:
                buckets["30_90d"] += 1
            elif age_days <= 180:
                buckets["90_180d"] += 1
            else:
                buckets["180d_plus"] += 1
        return {
            "total_resources": len(self._resources),
            "distribution": buckets,
        }

    def generate_summary(self) -> LifecycleSummary:
        now = time.time()
        phase_breakdown: dict[str, int] = {}
        category_breakdown: dict[str, int] = {}
        total_cost = 0.0
        total_age = 0.0

        for r in self._resources:
            phase_breakdown[r.phase] = phase_breakdown.get(r.phase, 0) + 1
            category_breakdown[r.category] = category_breakdown.get(r.category, 0) + 1
            total_cost += r.monthly_cost
            total_age += now - r.created_at

        stale = self.detect_stale_resources()
        decommission = self.get_decommission_candidates()
        avg_age_days = (
            round(total_age / len(self._resources) / 86400, 1) if self._resources else 0.0
        )

        recommendations: list[str] = []
        if stale:
            recommendations.append(
                f"{len(stale)} resources have been ACTIVE for over "
                f"{self._stale_days} days — review for deprecation"
            )
        if decommission:
            decom_cost = sum(r.monthly_cost for r in decommission)
            recommendations.append(
                f"{len(decommission)} DEPRECATED resources costing "
                f"${decom_cost:,.2f}/month — schedule decommissioning"
            )
        terminated = phase_breakdown.get(LifecyclePhase.TERMINATED, 0)
        if terminated > 0 and len(self._resources) > 0:
            recommendations.append(
                f"{terminated} terminated resources still tracked — consider purging from inventory"
            )

        return LifecycleSummary(
            total_resources=len(self._resources),
            phase_breakdown=phase_breakdown,
            category_breakdown=category_breakdown,
            stale_count=len(stale),
            decommission_candidates=len(decommission),
            avg_age_days=avg_age_days,
            total_monthly_cost=round(total_cost, 2),
            recommendations=recommendations,
        )

    def clear_data(self) -> None:
        self._resources.clear()
        self._transitions.clear()
        logger.info("resource_lifecycle.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        phase_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}
        for r in self._resources:
            phase_counts[r.phase] = phase_counts.get(r.phase, 0) + 1
            category_counts[r.category] = category_counts.get(r.category, 0) + 1
        return {
            "total_resources": len(self._resources),
            "total_transitions": len(self._transitions),
            "phase_distribution": phase_counts,
            "category_distribution": category_counts,
            "max_resources": self._max_resources,
            "stale_days": self._stale_days,
        }
