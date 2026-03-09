"""Alert Impact Scorer — score business impact of alerts using dependency graphs."""

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
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ServiceTier(StrEnum):
    TIER_0 = "tier_0"
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"


class AlertCategory(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    SATURATION = "saturation"
    SECURITY = "security"


# --- Models ---


class ServiceNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    tier: ServiceTier = ServiceTier.TIER_2
    dependencies: list[str] = Field(default_factory=list)
    revenue_impact_per_min: float = 0.0
    user_facing: bool = False
    created_at: float = Field(default_factory=time.time)


class AlertImpactRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    service: str = ""
    category: AlertCategory = AlertCategory.AVAILABILITY
    impact_level: ImpactLevel = ImpactLevel.NONE
    impact_score: float = 0.0
    blast_radius: int = 0
    estimated_revenue_impact: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ImpactReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_alerts: int = 0
    total_services: int = 0
    avg_impact_score: float = 0.0
    critical_count: int = 0
    by_impact_level: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    top_impacted: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertImpactScorer:
    """Score business impact of alerts using dependency graphs."""

    def __init__(self, max_records: int = 100000) -> None:
        self._max_records = max_records
        self._services: list[ServiceNode] = []
        self._impacts: list[AlertImpactRecord] = []
        logger.info("alert_impact_scorer.initialized", max_records=max_records)

    def add_service(
        self,
        name: str,
        tier: ServiceTier = ServiceTier.TIER_2,
        dependencies: list[str] | None = None,
        revenue_impact_per_min: float = 0.0,
        user_facing: bool = False,
    ) -> ServiceNode:
        """Register a service in the dependency graph."""
        node = ServiceNode(
            name=name,
            tier=tier,
            dependencies=dependencies or [],
            revenue_impact_per_min=revenue_impact_per_min,
            user_facing=user_facing,
        )
        self._services.append(node)
        logger.info("alert_impact_scorer.service_added", name=name, tier=tier.value)
        return node

    def score_impact(
        self,
        alert_name: str,
        service: str,
        category: AlertCategory = AlertCategory.AVAILABILITY,
    ) -> AlertImpactRecord:
        """Score the business impact of an alert."""
        svc_node = self._find_service(service)
        blast = self.calculate_blast_radius(service)["affected_count"]
        tier_weights = {
            ServiceTier.TIER_0: 1.0,
            ServiceTier.TIER_1: 0.75,
            ServiceTier.TIER_2: 0.5,
            ServiceTier.TIER_3: 0.25,
        }
        tier = svc_node.tier if svc_node else ServiceTier.TIER_2
        base = tier_weights.get(tier, 0.5)
        score = round(base * 100 + blast * 5, 2)
        if score >= 80:
            level = ImpactLevel.CRITICAL
        elif score >= 60:
            level = ImpactLevel.HIGH
        elif score >= 40:
            level = ImpactLevel.MEDIUM
        else:
            level = ImpactLevel.LOW
        revenue = svc_node.revenue_impact_per_min * 5 if svc_node else 0
        record = AlertImpactRecord(
            alert_name=alert_name,
            service=service,
            category=category,
            impact_level=level,
            impact_score=score,
            blast_radius=blast,
            estimated_revenue_impact=round(revenue, 2),
        )
        self._impacts.append(record)
        if len(self._impacts) > self._max_records:
            self._impacts = self._impacts[-self._max_records :]
        logger.info(
            "alert_impact_scorer.scored",
            alert=alert_name,
            score=score,
            level=level.value,
        )
        return record

    def _find_service(self, name: str) -> ServiceNode | None:
        for s in self._services:
            if s.name == name:
                return s
        return None

    def map_dependencies(self, service: str) -> dict[str, Any]:
        """Map all transitive dependencies for a service."""
        visited: set[str] = set()
        queue = [service]
        deps: list[str] = []
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            node = self._find_service(current)
            if node:
                for dep in node.dependencies:
                    if dep not in visited:
                        deps.append(dep)
                        queue.append(dep)
        return {
            "service": service,
            "direct_deps": (node.dependencies if (node := self._find_service(service)) else []),
            "transitive_deps": deps,
            "total_depth": len(visited) - 1,
        }

    def calculate_blast_radius(self, service: str) -> dict[str, Any]:
        """Calculate the blast radius if a service fails."""
        dependents: list[str] = []
        for s in self._services:
            if service in s.dependencies:
                dependents.append(s.name)
        return {
            "service": service,
            "affected_services": dependents,
            "affected_count": len(dependents),
            "user_facing_affected": sum(
                1
                for d in dependents
                if (found := self._find_service(d)) is not None and found.user_facing
            ),
        }

    def prioritize_alerts(self) -> list[AlertImpactRecord]:
        """Return alerts sorted by impact score descending."""
        return sorted(self._impacts, key=lambda x: x.impact_score, reverse=True)

    def get_impact_report(self) -> ImpactReport:
        """Generate impact analysis report."""
        by_level: dict[str, int] = {}
        by_cat: dict[str, int] = {}
        for i in self._impacts:
            by_level[i.impact_level.value] = by_level.get(i.impact_level.value, 0) + 1
            by_cat[i.category.value] = by_cat.get(i.category.value, 0) + 1
        scores = [i.impact_score for i in self._impacts]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        critical = sum(1 for i in self._impacts if i.impact_level == ImpactLevel.CRITICAL)
        top = [
            i.service for i in sorted(self._impacts, key=lambda x: x.impact_score, reverse=True)[:5]
        ]
        recs: list[str] = []
        if critical > 0:
            recs.append(f"{critical} critical-impact alert(s) — immediate review")
        if not recs:
            recs.append("Alert impact is within normal parameters")
        return ImpactReport(
            total_alerts=len(self._impacts),
            total_services=len(self._services),
            avg_impact_score=avg,
            critical_count=critical,
            by_impact_level=by_level,
            by_category=by_cat,
            top_impacted=top,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all services and impacts."""
        self._services.clear()
        self._impacts.clear()
        logger.info("alert_impact_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        """Return engine statistics."""
        return {
            "total_services": len(self._services),
            "total_impacts": len(self._impacts),
            "unique_alerts": len({i.alert_name for i in self._impacts}),
        }
