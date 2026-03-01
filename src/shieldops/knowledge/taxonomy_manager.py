"""Taxonomy Manager — manage knowledge taxonomy hierarchies and auto-categorization."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TaxonomyLevel(StrEnum):
    DOMAIN = "domain"
    CATEGORY = "category"
    SUBCATEGORY = "subcategory"
    TOPIC = "topic"
    TAG = "tag"


class TaxonomyStatus(StrEnum):
    ACTIVE = "active"
    DRAFT = "draft"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
    PENDING_REVIEW = "pending_review"


class TaxonomyQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    NEEDS_IMPROVEMENT = "needs_improvement"
    POOR = "poor"


# --- Models ---


class TaxonomyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    taxonomy_id: str = ""
    taxonomy_level: TaxonomyLevel = TaxonomyLevel.DOMAIN
    taxonomy_status: TaxonomyStatus = TaxonomyStatus.DRAFT
    taxonomy_quality: TaxonomyQuality = TaxonomyQuality.ADEQUATE
    completeness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TaxonomyMapping(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    taxonomy_id: str = ""
    taxonomy_level: TaxonomyLevel = TaxonomyLevel.DOMAIN
    mapping_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TaxonomyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_mappings: int = 0
    poor_taxonomies: int = 0
    avg_completeness_score: float = 0.0
    by_level: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_quality: dict[str, int] = Field(default_factory=dict)
    top_incomplete: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TaxonomyManager:
    """Manage knowledge taxonomy hierarchies, auto-categorization, tag normalization."""

    def __init__(
        self,
        max_records: int = 200000,
        min_completeness_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_completeness_score = min_completeness_score
        self._records: list[TaxonomyRecord] = []
        self._mappings: list[TaxonomyMapping] = []
        logger.info(
            "taxonomy_manager.initialized",
            max_records=max_records,
            min_completeness_score=min_completeness_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_taxonomy(
        self,
        taxonomy_id: str,
        taxonomy_level: TaxonomyLevel = TaxonomyLevel.DOMAIN,
        taxonomy_status: TaxonomyStatus = TaxonomyStatus.DRAFT,
        taxonomy_quality: TaxonomyQuality = TaxonomyQuality.ADEQUATE,
        completeness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TaxonomyRecord:
        record = TaxonomyRecord(
            taxonomy_id=taxonomy_id,
            taxonomy_level=taxonomy_level,
            taxonomy_status=taxonomy_status,
            taxonomy_quality=taxonomy_quality,
            completeness_score=completeness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "taxonomy_manager.taxonomy_recorded",
            record_id=record.id,
            taxonomy_id=taxonomy_id,
            taxonomy_level=taxonomy_level.value,
            taxonomy_status=taxonomy_status.value,
        )
        return record

    def get_taxonomy(self, record_id: str) -> TaxonomyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_taxonomies(
        self,
        level: TaxonomyLevel | None = None,
        status: TaxonomyStatus | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[TaxonomyRecord]:
        results = list(self._records)
        if level is not None:
            results = [r for r in results if r.taxonomy_level == level]
        if status is not None:
            results = [r for r in results if r.taxonomy_status == status]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_mapping(
        self,
        taxonomy_id: str,
        taxonomy_level: TaxonomyLevel = TaxonomyLevel.DOMAIN,
        mapping_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> TaxonomyMapping:
        mapping = TaxonomyMapping(
            taxonomy_id=taxonomy_id,
            taxonomy_level=taxonomy_level,
            mapping_score=mapping_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._mappings.append(mapping)
        if len(self._mappings) > self._max_records:
            self._mappings = self._mappings[-self._max_records :]
        logger.info(
            "taxonomy_manager.mapping_added",
            taxonomy_id=taxonomy_id,
            taxonomy_level=taxonomy_level.value,
            mapping_score=mapping_score,
        )
        return mapping

    # -- domain operations --------------------------------------------------

    def analyze_taxonomy_coverage(self) -> dict[str, Any]:
        """Group by taxonomy level; return count and avg completeness."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.taxonomy_level.value
            level_data.setdefault(key, []).append(r.completeness_score)
        result: dict[str, Any] = {}
        for level, scores in level_data.items():
            result[level] = {
                "count": len(scores),
                "avg_completeness": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_poor_taxonomies(self) -> list[dict[str, Any]]:
        """Return records where quality is POOR."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.taxonomy_quality == TaxonomyQuality.POOR:
                results.append(
                    {
                        "record_id": r.id,
                        "taxonomy_id": r.taxonomy_id,
                        "taxonomy_level": r.taxonomy_level.value,
                        "taxonomy_status": r.taxonomy_status.value,
                        "completeness_score": r.completeness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_completeness(self) -> list[dict[str, Any]]:
        """Group by service, avg completeness, sort ascending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.completeness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_completeness": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_completeness"])
        return results

    def detect_taxonomy_trends(self) -> dict[str, Any]:
        """Split-half comparison on mapping_score; delta threshold 5.0."""
        if len(self._mappings) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [m.mapping_score for m in self._mappings]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> TaxonomyReport:
        by_level: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_quality: dict[str, int] = {}
        for r in self._records:
            by_level[r.taxonomy_level.value] = by_level.get(r.taxonomy_level.value, 0) + 1
            by_status[r.taxonomy_status.value] = by_status.get(r.taxonomy_status.value, 0) + 1
            by_quality[r.taxonomy_quality.value] = by_quality.get(r.taxonomy_quality.value, 0) + 1
        poor_taxonomies = sum(
            1 for r in self._records if r.taxonomy_quality == TaxonomyQuality.POOR
        )
        avg_completeness_score = (
            round(
                sum(r.completeness_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        ranked = self.rank_by_completeness()
        top_incomplete = [r["service"] for r in ranked[:5]]
        recs: list[str] = []
        if poor_taxonomies > 0:
            recs.append(f"{poor_taxonomies} poor taxonomy(ies) — review and improve categorization")
        low_comp = sum(
            1 for r in self._records if r.completeness_score < self._min_completeness_score
        )
        if low_comp > 0:
            recs.append(
                f"{low_comp} taxonomy(ies) below completeness threshold"
                f" ({self._min_completeness_score})"
            )
        if not recs:
            recs.append("Taxonomy completeness levels are healthy")
        return TaxonomyReport(
            total_records=len(self._records),
            total_mappings=len(self._mappings),
            poor_taxonomies=poor_taxonomies,
            avg_completeness_score=avg_completeness_score,
            by_level=by_level,
            by_status=by_status,
            by_quality=by_quality,
            top_incomplete=top_incomplete,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._mappings.clear()
        logger.info("taxonomy_manager.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.taxonomy_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_mappings": len(self._mappings),
            "min_completeness_score": self._min_completeness_score,
            "level_distribution": level_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
