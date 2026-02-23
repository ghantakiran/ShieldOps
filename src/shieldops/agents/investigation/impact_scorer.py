"""Incident impact scorer.

Multi-dimensional impact scoring that evaluates availability, performance,
data integrity, security, and financial dimensions of incidents.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class ImpactLevel(enum.StrEnum):
    NEGLIGIBLE = "negligible"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ImpactCategory(enum.StrEnum):
    AVAILABILITY = "availability"
    PERFORMANCE = "performance"
    DATA_INTEGRITY = "data_integrity"
    SECURITY = "security"
    FINANCIAL = "financial"


# ── Models ───────────────────────────────────────────────────────────


class ImpactDimension(BaseModel):
    category: ImpactCategory
    score: float = 0.0
    level: ImpactLevel = ImpactLevel.NEGLIGIBLE
    description: str = ""
    affected_users: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImpactScore(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    incident_id: str
    overall_score: float = 0.0
    overall_level: ImpactLevel = ImpactLevel.NEGLIGIBLE
    dimensions: list[ImpactDimension] = Field(default_factory=list)
    affected_services: list[str] = Field(default_factory=list)
    estimated_users_affected: int = 0
    estimated_revenue_impact: float = 0.0
    blast_radius: float = 0.0
    scored_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Scorer ───────────────────────────────────────────────────────────

LEVEL_THRESHOLDS = {
    ImpactLevel.CRITICAL: 0.8,
    ImpactLevel.HIGH: 0.6,
    ImpactLevel.MODERATE: 0.4,
    ImpactLevel.LOW: 0.2,
    ImpactLevel.NEGLIGIBLE: 0.0,
}

LEVEL_WEIGHTS = {
    ImpactCategory.AVAILABILITY: 1.0,
    ImpactCategory.PERFORMANCE: 0.7,
    ImpactCategory.DATA_INTEGRITY: 0.9,
    ImpactCategory.SECURITY: 1.0,
    ImpactCategory.FINANCIAL: 0.8,
}


def _score_to_level(score: float) -> ImpactLevel:
    for level, threshold in LEVEL_THRESHOLDS.items():
        if score >= threshold:
            return level
    return ImpactLevel.NEGLIGIBLE


class IncidentImpactScorer:
    """Score the multi-dimensional impact of incidents.

    Parameters
    ----------
    max_records:
        Maximum impact score records to store.
    """

    def __init__(self, max_records: int = 10000) -> None:
        self._scores: dict[str, ImpactScore] = {}
        self._max_records = max_records

    def score_incident(
        self,
        incident_id: str,
        dimensions: list[dict[str, Any]] | None = None,
        affected_services: list[str] | None = None,
        estimated_users_affected: int = 0,
        estimated_revenue_impact: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> ImpactScore:
        if len(self._scores) >= self._max_records:
            raise ValueError(f"Maximum records limit reached: {self._max_records}")

        dims: list[ImpactDimension] = []
        for d in dimensions or []:
            cat = ImpactCategory(d.get("category", "availability"))
            score = float(d.get("score", 0.0))
            dim = ImpactDimension(
                category=cat,
                score=min(max(score, 0.0), 1.0),
                level=_score_to_level(score),
                description=d.get("description", ""),
                affected_users=d.get("affected_users", 0),
                metadata=d.get("metadata", {}),
            )
            dims.append(dim)

        # Compute overall weighted score
        total_weight = 0.0
        weighted_sum = 0.0
        for dim in dims:
            w = LEVEL_WEIGHTS.get(dim.category, 0.5)
            weighted_sum += dim.score * w
            total_weight += w
        overall = weighted_sum / total_weight if total_weight > 0 else 0.0

        services = affected_services or []
        blast = len(services) / 10.0 if services else 0.0
        blast = min(blast, 1.0)

        impact = ImpactScore(
            incident_id=incident_id,
            overall_score=round(overall, 4),
            overall_level=_score_to_level(overall),
            dimensions=dims,
            affected_services=services,
            estimated_users_affected=estimated_users_affected,
            estimated_revenue_impact=estimated_revenue_impact,
            blast_radius=round(blast, 4),
            metadata=metadata or {},
        )
        self._scores[incident_id] = impact
        logger.info(
            "incident_impact_scored",
            incident_id=incident_id,
            overall_score=impact.overall_score,
            level=impact.overall_level,
        )
        return impact

    def score_from_topology(
        self,
        incident_id: str,
        affected_services: list[str],
        total_services: int = 0,
        users_per_service: int = 100,
        revenue_per_service_hour: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> ImpactScore:
        n = len(affected_services)
        total = max(total_services, n)
        availability_score = min(n / max(total, 1), 1.0)
        users = n * users_per_service
        revenue = n * revenue_per_service_hour

        dims = [
            {
                "category": "availability",
                "score": availability_score,
                "description": f"{n}/{total} services affected",
                "affected_users": users,
            },
            {
                "category": "financial",
                "score": min(revenue / 10000, 1.0) if revenue > 0 else 0.0,
                "description": f"Est. ${revenue:.0f}/hour impact",
            },
        ]
        return self.score_incident(
            incident_id=incident_id,
            dimensions=dims,
            affected_services=affected_services,
            estimated_users_affected=users,
            estimated_revenue_impact=revenue,
            metadata=metadata,
        )

    def get_score(self, incident_id: str) -> ImpactScore | None:
        return self._scores.get(incident_id)

    def list_by_severity(
        self,
        min_level: ImpactLevel = ImpactLevel.NEGLIGIBLE,
        limit: int = 50,
    ) -> list[ImpactScore]:
        level_order = list(ImpactLevel)
        min_idx = level_order.index(min_level)
        scores = [s for s in self._scores.values() if level_order.index(s.overall_level) >= min_idx]
        scores.sort(key=lambda s: s.overall_score, reverse=True)
        return scores[:limit]

    def get_stats(self) -> dict[str, Any]:
        by_level: dict[str, int] = {}
        for s in self._scores.values():
            by_level[s.overall_level.value] = by_level.get(s.overall_level.value, 0) + 1
        return {
            "total_scores": len(self._scores),
            "by_level": by_level,
        }
