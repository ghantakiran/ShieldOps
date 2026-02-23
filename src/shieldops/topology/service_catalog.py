"""Service Catalog Manager — service registry with tier classification, lifecycle, ownership."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ServiceTier(StrEnum):
    TIER_0 = "tier_0"
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"


class ServiceLifecycle(StrEnum):
    INCUBATING = "incubating"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DECOMMISSIONED = "decommissioned"


class DocumentationType(StrEnum):
    OPENAPI = "openapi"
    GRPC = "grpc"
    GRAPHQL = "graphql"
    RUNBOOK = "runbook"
    ARCHITECTURE = "architecture"


# --- Models ---


class ServiceEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    tier: ServiceTier = ServiceTier.TIER_2
    lifecycle: ServiceLifecycle = ServiceLifecycle.INCUBATING
    owner: str = ""
    team: str = ""
    description: str = ""
    repository_url: str = ""
    documentation: dict[str, str] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class ServiceSearchResult(BaseModel):
    services: list[ServiceEntry] = Field(default_factory=list)
    total: int = 0
    query: str = ""


class CatalogStats(BaseModel):
    total_services: int = 0
    tier_distribution: dict[str, int] = Field(default_factory=dict)
    lifecycle_distribution: dict[str, int] = Field(default_factory=dict)
    stale_count: int = 0


# --- Engine ---


class ServiceCatalogManager:
    """Service registry with tier classification, lifecycle state, ownership, API docs links."""

    def __init__(
        self,
        max_services: int = 5000,
        stale_days: int = 180,
    ) -> None:
        self._max_services = max_services
        self._stale_days = stale_days
        self._services: dict[str, ServiceEntry] = {}
        logger.info(
            "service_catalog.initialized",
            max_services=max_services,
            stale_days=stale_days,
        )

    def register_service(
        self,
        name: str,
        tier: ServiceTier = ServiceTier.TIER_2,
        **kw: Any,
    ) -> ServiceEntry:
        entry = ServiceEntry(name=name, tier=tier, **kw)
        self._services[entry.id] = entry
        if len(self._services) > self._max_services:
            oldest = next(iter(self._services))
            del self._services[oldest]
        logger.info("service_catalog.service_registered", service_id=entry.id, name=name)
        return entry

    def get_service(self, service_id: str) -> ServiceEntry | None:
        return self._services.get(service_id)

    def update_service(self, service_id: str, **kw: Any) -> ServiceEntry | None:
        entry = self._services.get(service_id)
        if entry is None:
            return None
        for key, value in kw.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        entry.updated_at = time.time()
        logger.info("service_catalog.service_updated", service_id=service_id)
        return entry

    def decommission_service(self, service_id: str) -> ServiceEntry | None:
        entry = self._services.get(service_id)
        if entry is None:
            return None
        entry.lifecycle = ServiceLifecycle.DECOMMISSIONED
        entry.updated_at = time.time()
        logger.info("service_catalog.service_decommissioned", service_id=service_id)
        return entry

    def search_services(
        self,
        query: str = "",
        tier: ServiceTier | None = None,
        lifecycle: ServiceLifecycle | None = None,
        team: str | None = None,
    ) -> ServiceSearchResult:
        results = list(self._services.values())
        if query:
            q = query.lower()
            results = [
                s
                for s in results
                if q in s.name.lower() or q in s.description.lower() or q in s.team.lower()
            ]
        if tier is not None:
            results = [s for s in results if s.tier == tier]
        if lifecycle is not None:
            results = [s for s in results if s.lifecycle == lifecycle]
        if team is not None:
            results = [s for s in results if s.team == team]
        return ServiceSearchResult(services=results, total=len(results), query=query)

    def list_dependencies(self, service_id: str) -> list[ServiceEntry]:
        entry = self._services.get(service_id)
        if entry is None:
            return []
        return [self._services[dep_id] for dep_id in entry.dependencies if dep_id in self._services]

    def get_dependents(self, service_id: str) -> list[ServiceEntry]:
        return [s for s in self._services.values() if service_id in s.dependencies]

    def get_stale_services(self) -> list[ServiceEntry]:
        cutoff = time.time() - (self._stale_days * 86400)
        return [s for s in self._services.values() if s.updated_at < cutoff]

    def validate_catalog_completeness(self) -> dict[str, Any]:
        issues: list[dict[str, str]] = []
        for s in self._services.values():
            if not s.owner:
                issues.append({"service_id": s.id, "name": s.name, "issue": "missing_owner"})
            if not s.description:
                issues.append({"service_id": s.id, "name": s.name, "issue": "missing_description"})
            if not s.documentation:
                issues.append(
                    {"service_id": s.id, "name": s.name, "issue": "missing_documentation"}
                )
        return {
            "total_services": len(self._services),
            "issues": issues,
            "completeness_score": round(
                (1 - len(issues) / max(len(self._services) * 3, 1)) * 100, 1
            ),
        }

    def get_stats(self) -> dict[str, Any]:
        tier_counts: dict[str, int] = {}
        lifecycle_counts: dict[str, int] = {}
        for s in self._services.values():
            tier_counts[s.tier] = tier_counts.get(s.tier, 0) + 1
            lifecycle_counts[s.lifecycle] = lifecycle_counts.get(s.lifecycle, 0) + 1
        return {
            "total_services": len(self._services),
            "tier_distribution": tier_counts,
            "lifecycle_distribution": lifecycle_counts,
            "stale_count": len(self.get_stale_services()),
        }
