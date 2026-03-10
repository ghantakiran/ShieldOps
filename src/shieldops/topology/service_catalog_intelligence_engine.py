"""Service catalog intelligence engine for platform engineering.

Scores catalog health, identifies orphaned services, and computes
documentation coverage across the service portfolio.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class CatalogCompleteness(StrEnum):
    """Completeness level of a service catalog entry."""

    complete = "complete"
    partial = "partial"
    minimal = "minimal"
    missing = "missing"
    unknown = "unknown"


class OwnershipStatus(StrEnum):
    """Ownership status of a service."""

    owned = "owned"
    shared = "shared"
    orphaned = "orphaned"
    disputed = "disputed"
    transitioning = "transitioning"


class ServiceTier(StrEnum):
    """Tier classification for services."""

    tier_0_critical = "tier_0_critical"
    tier_1_important = "tier_1_important"
    tier_2_standard = "tier_2_standard"
    tier_3_low = "tier_3_low"
    unclassified = "unclassified"


class ServiceCatalogRecord(BaseModel):
    """Record of a service catalog entry."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    tier: ServiceTier = ServiceTier.unclassified
    ownership_status: OwnershipStatus = OwnershipStatus.owned
    completeness: CatalogCompleteness = CatalogCompleteness.unknown
    doc_coverage_pct: float = 0.0
    slo_defined: bool = False
    runbook_count: int = 0
    alert_count: int = 0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ServiceCatalogAnalysis(BaseModel):
    """Analysis result for a catalog entry."""

    record_id: str = ""
    health_score: float = 0.0
    is_orphaned: bool = False
    doc_gap: float = 0.0
    recommendations: list[str] = Field(default_factory=list)


class ServiceCatalogReport(BaseModel):
    """Aggregated service catalog report."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_health_score: float = 0.0
    orphan_count: int = 0
    avg_doc_coverage: float = 0.0
    tier_distribution: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


class ServiceCatalogIntelligenceEngine:
    """Engine for service catalog intelligence."""

    def __init__(
        self,
        max_records: int = 200000,
        health_threshold: float = 0.7,
    ) -> None:
        self._max_records = max_records
        self._health_threshold = health_threshold
        self._records: list[ServiceCatalogRecord] = []
        self._analyses: list[ServiceCatalogAnalysis] = []
        logger.info(
            "service_catalog_intelligence_engine.init",
            max_records=max_records,
            health_threshold=health_threshold,
        )

    def record_item(self, **kwargs: Any) -> ServiceCatalogRecord:
        """Record a service catalog entry."""
        record = ServiceCatalogRecord(**kwargs)
        if len(self._records) >= self._max_records:
            self._records = self._records[len(self._records) // 10 :]
        self._records.append(record)
        logger.info(
            "service_catalog_intelligence_engine.record_item",
            record_id=record.id,
            service_name=record.service_name,
        )
        return record

    def process(self, key: str) -> ServiceCatalogAnalysis:
        """Process a record by ID."""
        record = next(
            (r for r in self._records if r.id == key),
            None,
        )
        if not record:
            return ServiceCatalogAnalysis()
        score = self._compute_health(record)
        is_orphaned = record.ownership_status == OwnershipStatus.orphaned
        doc_gap = max(0.0, 80.0 - record.doc_coverage_pct)
        recs: list[str] = []
        if score < self._health_threshold:
            recs.append(f"Improve catalog health for {record.service_name}")
        if is_orphaned:
            recs.append(f"Assign owner for {record.service_name}")
        if doc_gap > 0:
            recs.append(f"Increase doc coverage by {doc_gap:.1f}%")
        analysis = ServiceCatalogAnalysis(
            record_id=record.id,
            health_score=score,
            is_orphaned=is_orphaned,
            doc_gap=doc_gap,
            recommendations=recs,
        )
        self._analyses.append(analysis)
        return analysis

    def generate_report(self) -> ServiceCatalogReport:
        """Generate an aggregated report."""
        scores = [a.health_score for a in self._analyses]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        orphan_count = sum(1 for a in self._analyses if a.is_orphaned)
        coverages = [r.doc_coverage_pct for r in self._records]
        avg_doc = sum(coverages) / len(coverages) if coverages else 0.0
        tier_dist: dict[str, int] = {}
        for r in self._records:
            tier_dist[r.tier.value] = tier_dist.get(r.tier.value, 0) + 1
        recs: list[str] = []
        if avg_score < self._health_threshold:
            recs.append("Overall catalog health below threshold")
        if orphan_count > 0:
            recs.append(f"{orphan_count} orphaned services need owners")
        if avg_doc < 80.0:
            recs.append("Improve documentation coverage")
        return ServiceCatalogReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_health_score=round(avg_score, 3),
            orphan_count=orphan_count,
            avg_doc_coverage=round(avg_doc, 2),
            tier_distribution=tier_dist,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        """Return engine statistics."""
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "max_records": self._max_records,
            "health_threshold": self._health_threshold,
        }

    def clear_data(self) -> None:
        """Clear all records and analyses."""
        self._records.clear()
        self._analyses.clear()
        logger.info(
            "service_catalog_intelligence_engine.clear_data",
        )

    def score_catalog_health(self) -> float:
        """Compute overall catalog health score."""
        if not self._records:
            return 0.0
        scores = [self._compute_health(r) for r in self._records]
        return round(sum(scores) / len(scores), 3)

    def identify_orphans(
        self,
    ) -> list[ServiceCatalogRecord]:
        """Identify orphaned services."""
        return [r for r in self._records if r.ownership_status == OwnershipStatus.orphaned]

    def compute_documentation_coverage(
        self,
    ) -> dict[str, float]:
        """Compute doc coverage by team."""
        team_docs: dict[str, list[float]] = {}
        for r in self._records:
            team_docs.setdefault(r.team, []).append(r.doc_coverage_pct)
        return {t: round(sum(v) / len(v), 2) for t, v in team_docs.items() if v}

    def _compute_health(self, record: ServiceCatalogRecord) -> float:
        """Compute health score for a record."""
        score = 0.0
        completeness_map = {
            CatalogCompleteness.complete: 1.0,
            CatalogCompleteness.partial: 0.7,
            CatalogCompleteness.minimal: 0.4,
            CatalogCompleteness.missing: 0.1,
            CatalogCompleteness.unknown: 0.0,
        }
        score += completeness_map.get(record.completeness, 0.0) * 0.3
        score += (record.doc_coverage_pct / 100.0) * 0.25
        if record.slo_defined:
            score += 0.2
        if record.runbook_count > 0:
            score += min(record.runbook_count / 5.0, 1.0) * 0.15
        if record.alert_count > 0:
            score += 0.1
        return round(min(score, 1.0), 3)
