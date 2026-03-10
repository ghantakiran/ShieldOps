"""Intelligent Noise Reduction Engine

Clusters and deduplicates related alerts using semantic,
temporal, and topological methods to reduce alert fatigue.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ClusterMethod(StrEnum):
    SEMANTIC = "semantic"
    TEMPORAL = "temporal"
    TOPOLOGICAL = "topological"
    OWNERSHIP = "ownership"
    COMPOSITE = "composite"


class NoiseCategory(StrEnum):
    DUPLICATE = "duplicate"
    TRANSIENT = "transient"
    CASCADING = "cascading"
    INFORMATIONAL = "informational"
    ACTIONABLE = "actionable"


class ReductionOutcome(StrEnum):
    MERGED = "merged"
    SUPPRESSED = "suppressed"
    ESCALATED = "escalated"
    RETAINED = "retained"


# --- Models ---


class NoiseReductionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    cluster_id: str = ""
    noise_category: NoiseCategory = NoiseCategory.ACTIONABLE
    cluster_method: ClusterMethod = ClusterMethod.SEMANTIC
    similarity_score: float = 0.0
    original_severity: str = ""
    adjusted_severity: str = ""
    service: str = ""
    reduction_outcome: ReductionOutcome = ReductionOutcome.RETAINED
    created_at: float = Field(default_factory=time.time)


class NoiseReductionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cluster_id: str = ""
    noise_ratio: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class NoiseReductionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    noise_ratio: float = 0.0
    reduction_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IntelligentNoiseReductionEngine:
    """Intelligent Noise Reduction Engine

    Clusters and deduplicates related alerts to reduce
    alert fatigue and surface actionable signals.
    """

    def __init__(
        self,
        max_records: int = 200000,
        similarity_threshold: float = 0.75,
    ) -> None:
        self._max_records = max_records
        self._similarity_threshold = similarity_threshold
        self._records: list[NoiseReductionRecord] = []
        self._analyses: list[NoiseReductionAnalysis] = []
        logger.info(
            "intelligent_noise_reduction_engine.initialized",
            max_records=max_records,
            similarity_threshold=similarity_threshold,
        )

    def add_record(
        self,
        alert_id: str,
        service: str,
        cluster_id: str = "",
        noise_category: NoiseCategory = (NoiseCategory.ACTIONABLE),
        cluster_method: ClusterMethod = (ClusterMethod.SEMANTIC),
        similarity_score: float = 0.0,
        original_severity: str = "",
        adjusted_severity: str = "",
        reduction_outcome: ReductionOutcome = (ReductionOutcome.RETAINED),
    ) -> NoiseReductionRecord:
        record = NoiseReductionRecord(
            alert_id=alert_id,
            cluster_id=cluster_id,
            noise_category=noise_category,
            cluster_method=cluster_method,
            similarity_score=similarity_score,
            original_severity=original_severity,
            adjusted_severity=adjusted_severity,
            service=service,
            reduction_outcome=reduction_outcome,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "intelligent_noise_reduction_engine.record_added",
            record_id=record.id,
            alert_id=alert_id,
            service=service,
        )
        return record

    def cluster_related_alerts(self, cluster_id: str) -> list[dict[str, Any]]:
        matching = [r for r in self._records if r.cluster_id == cluster_id]
        if not matching:
            return []
        return [
            {
                "alert_id": r.alert_id,
                "service": r.service,
                "similarity": r.similarity_score,
                "category": r.noise_category.value,
                "outcome": r.reduction_outcome.value,
            }
            for r in sorted(
                matching,
                key=lambda x: x.similarity_score,
                reverse=True,
            )
        ]

    def compute_noise_ratio(self, service: str = "") -> dict[str, Any]:
        matching = list(self._records)
        if service:
            matching = [r for r in matching if r.service == service]
        if not matching:
            return {
                "service": service or "all",
                "status": "no_data",
            }
        noise = sum(1 for r in matching if r.noise_category != NoiseCategory.ACTIONABLE)
        ratio = round(noise / len(matching), 4)
        return {
            "service": service or "all",
            "total_alerts": len(matching),
            "noise_count": noise,
            "noise_ratio": ratio,
        }

    def evaluate_reduction_quality(
        self,
    ) -> dict[str, Any]:
        if not self._records:
            return {"status": "no_data"}
        suppressed = sum(
            1
            for r in self._records
            if r.reduction_outcome
            in (
                ReductionOutcome.MERGED,
                ReductionOutcome.SUPPRESSED,
            )
        )
        escalated = sum(
            1 for r in self._records if r.reduction_outcome == ReductionOutcome.ESCALATED
        )
        total = len(self._records)
        reduction_pct = round(suppressed / total, 4)
        return {
            "total_alerts": total,
            "suppressed": suppressed,
            "escalated": escalated,
            "reduction_pct": reduction_pct,
        }

    def process(self, cluster_id: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.cluster_id == cluster_id]
        if not matching:
            return {
                "cluster_id": cluster_id,
                "status": "no_data",
            }
        noise = sum(1 for r in matching if r.noise_category != NoiseCategory.ACTIONABLE)
        avg_sim = round(
            sum(r.similarity_score for r in matching) / len(matching),
            4,
        )
        return {
            "cluster_id": cluster_id,
            "alert_count": len(matching),
            "noise_count": noise,
            "avg_similarity": avg_sim,
        }

    def generate_report(self) -> NoiseReductionReport:
        by_cat: dict[str, int] = {}
        by_method: dict[str, int] = {}
        by_out: dict[str, int] = {}
        for r in self._records:
            cv = r.noise_category.value
            by_cat[cv] = by_cat.get(cv, 0) + 1
            mv = r.cluster_method.value
            by_method[mv] = by_method.get(mv, 0) + 1
            ov = r.reduction_outcome.value
            by_out[ov] = by_out.get(ov, 0) + 1
        total = len(self._records)
        noise = sum(1 for r in self._records if r.noise_category != NoiseCategory.ACTIONABLE)
        noise_ratio = round(noise / total, 4) if total else 0.0
        suppressed = by_out.get("merged", 0) + by_out.get("suppressed", 0)
        reduction = round(suppressed / total, 4) if total else 0.0
        recs: list[str] = []
        if noise_ratio > 0.6:
            recs.append(f"Noise ratio {noise_ratio:.0%} — tighten alert rules")
        if reduction < 0.2 and noise_ratio > 0.3:
            recs.append("Low reduction despite noise — improve clustering")
        if not recs:
            recs.append("Alert noise reduction is nominal")
        return NoiseReductionReport(
            total_records=total,
            total_analyses=len(self._analyses),
            noise_ratio=noise_ratio,
            reduction_pct=reduction,
            by_category=by_cat,
            by_method=by_method,
            by_outcome=by_out,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            k = r.noise_category.value
            cat_dist[k] = cat_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "similarity_threshold": (self._similarity_threshold),
            "category_distribution": cat_dist,
            "unique_clusters": len({r.cluster_id for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("intelligent_noise_reduction_engine.cleared")
        return {"status": "cleared"}
