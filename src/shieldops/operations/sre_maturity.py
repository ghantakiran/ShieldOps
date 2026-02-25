"""SRE Maturity Assessor — assess SRE practices maturity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MaturityDimension(StrEnum):
    ONCALL = "oncall"
    INCIDENT_MANAGEMENT = "incident_management"
    SLO_ADOPTION = "slo_adoption"
    AUTOMATION = "automation"
    OBSERVABILITY = "observability"


class MaturityTier(StrEnum):
    INITIAL = "initial"
    DEVELOPING = "developing"
    DEFINED = "defined"
    MANAGED = "managed"
    OPTIMIZING = "optimizing"


class AssessmentScope(StrEnum):
    TEAM = "team"
    ORGANIZATION = "organization"
    SERVICE = "service"
    PLATFORM = "platform"
    ENTERPRISE = "enterprise"


# --- Models ---


class MaturityAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity: str = ""
    scope: AssessmentScope = AssessmentScope.TEAM
    dimension: MaturityDimension = MaturityDimension.ONCALL
    tier: MaturityTier = MaturityTier.INITIAL
    score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class MaturityRoadmapItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity: str = ""
    dimension: MaturityDimension = MaturityDimension.ONCALL
    current_tier: MaturityTier = MaturityTier.INITIAL
    target_tier: MaturityTier = MaturityTier.DEFINED
    recommendation: str = ""
    effort: str = "medium"
    created_at: float = Field(default_factory=time.time)


class SREMaturityReport(BaseModel):
    total_assessments: int = 0
    total_roadmap_items: int = 0
    avg_score: float = 0.0
    by_dimension: dict[str, float] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    gaps_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SREMaturityAssessor:
    """Assess SRE practices maturity across dimensions."""

    def __init__(
        self,
        max_records: int = 200000,
        target_maturity_score: float = 3.0,
    ) -> None:
        self._max_records = max_records
        self._target_maturity_score = target_maturity_score
        self._records: list[MaturityAssessment] = []
        self._roadmap: list[MaturityRoadmapItem] = []
        logger.info(
            "sre_maturity.initialized",
            max_records=max_records,
            target_maturity_score=target_maturity_score,
        )

    # -- internal helpers ------------------------------------------------

    def _tier_to_score(self, tier: MaturityTier) -> float:
        return {
            MaturityTier.INITIAL: 1.0,
            MaturityTier.DEVELOPING: 2.0,
            MaturityTier.DEFINED: 3.0,
            MaturityTier.MANAGED: 4.0,
            MaturityTier.OPTIMIZING: 5.0,
        }.get(tier, 1.0)

    def _score_to_tier(self, score: float) -> MaturityTier:
        if score >= 4.5:
            return MaturityTier.OPTIMIZING
        if score >= 3.5:
            return MaturityTier.MANAGED
        if score >= 2.5:
            return MaturityTier.DEFINED
        if score >= 1.5:
            return MaturityTier.DEVELOPING
        return MaturityTier.INITIAL

    # -- record / get / list ---------------------------------------------

    def record_assessment(
        self,
        entity: str,
        dimension: MaturityDimension = MaturityDimension.ONCALL,
        scope: AssessmentScope = AssessmentScope.TEAM,
        tier: MaturityTier = MaturityTier.INITIAL,
        score: float | None = None,
        details: str = "",
    ) -> MaturityAssessment:
        if score is None:
            score = self._tier_to_score(tier)
        record = MaturityAssessment(
            entity=entity,
            scope=scope,
            dimension=dimension,
            tier=tier,
            score=score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "sre_maturity.assessment_recorded",
            record_id=record.id,
            entity=entity,
            dimension=dimension.value,
            tier=tier.value,
        )
        return record

    def get_assessment(self, record_id: str) -> MaturityAssessment | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_assessments(
        self,
        entity: str | None = None,
        dimension: MaturityDimension | None = None,
        limit: int = 50,
    ) -> list[MaturityAssessment]:
        results = list(self._records)
        if entity is not None:
            results = [r for r in results if r.entity == entity]
        if dimension is not None:
            results = [r for r in results if r.dimension == dimension]
        return results[-limit:]

    def add_roadmap_item(
        self,
        entity: str,
        dimension: MaturityDimension = MaturityDimension.ONCALL,
        current_tier: MaturityTier = MaturityTier.INITIAL,
        target_tier: MaturityTier = MaturityTier.DEFINED,
        recommendation: str = "",
        effort: str = "medium",
    ) -> MaturityRoadmapItem:
        item = MaturityRoadmapItem(
            entity=entity,
            dimension=dimension,
            current_tier=current_tier,
            target_tier=target_tier,
            recommendation=recommendation,
            effort=effort,
        )
        self._roadmap.append(item)
        if len(self._roadmap) > self._max_records:
            self._roadmap = self._roadmap[-self._max_records :]
        logger.info(
            "sre_maturity.roadmap_item_added",
            entity=entity,
            dimension=dimension.value,
        )
        return item

    # -- domain operations -----------------------------------------------

    def calculate_overall_maturity(self, entity: str) -> dict[str, Any]:
        """Calculate overall maturity score for an entity."""
        entity_records = [r for r in self._records if r.entity == entity]
        if not entity_records:
            return {"entity": entity, "score": 0.0, "tier": "initial"}
        avg = round(sum(r.score for r in entity_records) / len(entity_records), 2)
        tier = self._score_to_tier(avg)
        dim_scores: dict[str, float] = {}
        for r in entity_records:
            dim_scores[r.dimension.value] = r.score
        return {
            "entity": entity,
            "score": avg,
            "tier": tier.value,
            "dimension_scores": dim_scores,
            "dimensions_assessed": len(entity_records),
        }

    def identify_maturity_gaps(self) -> list[dict[str, Any]]:
        """Find dimensions below target maturity."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._target_maturity_score:
                results.append(
                    {
                        "entity": r.entity,
                        "dimension": r.dimension.value,
                        "current_score": r.score,
                        "target_score": self._target_maturity_score,
                        "gap": round(self._target_maturity_score - r.score, 2),
                    }
                )
        results.sort(key=lambda x: x["gap"], reverse=True)
        return results

    def generate_roadmap(self, entity: str) -> list[dict[str, Any]]:
        """Generate improvement roadmap for an entity."""
        items = [i for i in self._roadmap if i.entity == entity]
        return [
            {
                "dimension": i.dimension.value,
                "current_tier": i.current_tier.value,
                "target_tier": i.target_tier.value,
                "recommendation": i.recommendation,
                "effort": i.effort,
            }
            for i in items
        ]

    def rank_teams_by_maturity(self) -> list[dict[str, Any]]:
        """Rank entities by overall maturity score."""
        entity_scores: dict[str, list[float]] = {}
        for r in self._records:
            entity_scores.setdefault(r.entity, []).append(r.score)
        results: list[dict[str, Any]] = []
        for entity, scores in entity_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "entity": entity,
                    "avg_score": avg,
                    "tier": self._score_to_tier(avg).value,
                    "dimensions_assessed": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_score"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> SREMaturityReport:
        by_tier: dict[str, int] = {}
        dim_totals: dict[str, float] = {}
        dim_counts: dict[str, int] = {}
        for r in self._records:
            by_tier[r.tier.value] = by_tier.get(r.tier.value, 0) + 1
            dim_totals[r.dimension.value] = dim_totals.get(r.dimension.value, 0) + r.score
            dim_counts[r.dimension.value] = dim_counts.get(r.dimension.value, 0) + 1
        by_dim: dict[str, float] = {}
        for dim, total in dim_totals.items():
            by_dim[dim] = round(total / dim_counts[dim], 2)
        avg_score = (
            round(sum(r.score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        gaps = self.identify_maturity_gaps()
        recs: list[str] = []
        if gaps:
            recs.append(
                f"{len(gaps)} maturity gap(s) below target score of {self._target_maturity_score}"
            )
        low_dims = [d for d, s in by_dim.items() if s < self._target_maturity_score]
        if low_dims:
            recs.append(f"Dimensions needing attention: {', '.join(low_dims)}")
        if not recs:
            recs.append("SRE maturity meets target levels")
        return SREMaturityReport(
            total_assessments=len(self._records),
            total_roadmap_items=len(self._roadmap),
            avg_score=avg_score,
            by_dimension=by_dim,
            by_tier=by_tier,
            gaps_count=len(gaps),
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._roadmap.clear()
        logger.info("sre_maturity.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        tier_dist: dict[str, int] = {}
        for r in self._records:
            key = r.tier.value
            tier_dist[key] = tier_dist.get(key, 0) + 1
        return {
            "total_assessments": len(self._records),
            "total_roadmap_items": len(self._roadmap),
            "target_maturity_score": self._target_maturity_score,
            "tier_distribution": tier_dist,
            "unique_entities": len({r.entity for r in self._records}),
        }
