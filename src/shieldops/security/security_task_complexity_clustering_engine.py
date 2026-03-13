"""Security Task Complexity Clustering Engine —
clusters security tasks by structural similarity,
evaluates cluster homogeneity, rebalances clusters."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComplexityTier(StrEnum):
    TIER_1_SIMPLE = "tier_1_simple"
    TIER_2_MODERATE = "tier_2_moderate"
    TIER_3_COMPLEX = "tier_3_complex"
    TIER_4_ADVANCED = "tier_4_advanced"


class ClusteringFeature(StrEnum):
    ATTACK_STAGE = "attack_stage"
    TOOL_COUNT = "tool_count"
    DATA_VOLUME = "data_volume"
    DECISION_DEPTH = "decision_depth"


class ClusterQuality(StrEnum):
    TIGHT = "tight"
    MODERATE = "moderate"
    LOOSE = "loose"
    FRAGMENTED = "fragmented"


# --- Models ---


class ClusteringRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    cluster_id: str = ""
    complexity_tier: ComplexityTier = ComplexityTier.TIER_1_SIMPLE
    clustering_feature: ClusteringFeature = ClusteringFeature.ATTACK_STAGE
    cluster_quality: ClusterQuality = ClusterQuality.TIGHT
    feature_value: float = 0.0
    similarity_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ClusteringAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    cluster_id: str = ""
    complexity_tier: ComplexityTier = ComplexityTier.TIER_1_SIMPLE
    cluster_size: int = 0
    homogeneity_score: float = 0.0
    cluster_quality: ClusterQuality = ClusterQuality.TIGHT
    needs_rebalance: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ClusteringReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_similarity_score: float = 0.0
    by_complexity_tier: dict[str, int] = Field(default_factory=dict)
    by_clustering_feature: dict[str, int] = Field(default_factory=dict)
    by_cluster_quality: dict[str, int] = Field(default_factory=dict)
    fragmented_clusters: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityTaskComplexityClusteringEngine:
    """Clusters security tasks by structural similarity."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ClusteringRecord] = []
        self._analyses: dict[str, ClusteringAnalysis] = {}
        logger.info(
            "security_task_complexity_clustering.init",
            max_records=max_records,
        )

    def add_record(
        self,
        task_id: str = "",
        cluster_id: str = "",
        complexity_tier: ComplexityTier = ComplexityTier.TIER_1_SIMPLE,
        clustering_feature: ClusteringFeature = ClusteringFeature.ATTACK_STAGE,
        cluster_quality: ClusterQuality = ClusterQuality.TIGHT,
        feature_value: float = 0.0,
        similarity_score: float = 0.0,
        description: str = "",
    ) -> ClusteringRecord:
        record = ClusteringRecord(
            task_id=task_id,
            cluster_id=cluster_id,
            complexity_tier=complexity_tier,
            clustering_feature=clustering_feature,
            cluster_quality=cluster_quality,
            feature_value=feature_value,
            similarity_score=similarity_score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_task_complexity_clustering.record_added",
            record_id=record.id,
            task_id=task_id,
        )
        return record

    def process(self, key: str) -> ClusteringAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        cluster_recs = [r for r in self._records if r.cluster_id == rec.cluster_id]
        scores = [r.similarity_score for r in cluster_recs]
        mean_score = sum(scores) / len(scores) if scores else 0.0
        variance = sum((s - mean_score) ** 2 for s in scores) / len(scores) if scores else 0.0
        if variance < 0.05:
            quality = ClusterQuality.TIGHT
        elif variance < 0.15:
            quality = ClusterQuality.MODERATE
        elif variance < 0.3:
            quality = ClusterQuality.LOOSE
        else:
            quality = ClusterQuality.FRAGMENTED
        analysis = ClusteringAnalysis(
            task_id=rec.task_id,
            cluster_id=rec.cluster_id,
            complexity_tier=rec.complexity_tier,
            cluster_size=len(cluster_recs),
            homogeneity_score=round(mean_score, 4),
            cluster_quality=quality,
            needs_rebalance=quality == ClusterQuality.FRAGMENTED,
            description=(
                f"Cluster {rec.cluster_id} size {len(cluster_recs)}, quality {quality.value}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ClusteringReport:
        by_ct: dict[str, int] = {}
        by_cf: dict[str, int] = {}
        by_cq: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.complexity_tier.value
            by_ct[k] = by_ct.get(k, 0) + 1
            k2 = r.clustering_feature.value
            by_cf[k2] = by_cf.get(k2, 0) + 1
            k3 = r.cluster_quality.value
            by_cq[k3] = by_cq.get(k3, 0) + 1
            scores.append(r.similarity_score)
        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        frag_clusters = list(
            {r.cluster_id for r in self._records if r.cluster_quality == ClusterQuality.FRAGMENTED}
        )[:10]
        recs_list: list[str] = []
        if frag_clusters:
            recs_list.append(f"{len(frag_clusters)} fragmented clusters require rebalancing")
        if not recs_list:
            recs_list.append("Cluster quality within acceptable thresholds")
        return ClusteringReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_similarity_score=avg_score,
            by_complexity_tier=by_ct,
            by_clustering_feature=by_cf,
            by_cluster_quality=by_cq,
            fragmented_clusters=frag_clusters,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        tier_dist: dict[str, int] = {}
        for r in self._records:
            k = r.complexity_tier.value
            tier_dist[k] = tier_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "tier_distribution": tier_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("security_task_complexity_clustering.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def cluster_by_structural_similarity(self) -> list[dict[str, Any]]:
        """Group tasks into clusters ranked by mean similarity score."""
        cluster_data: dict[str, list[float]] = {}
        for r in self._records:
            cluster_data.setdefault(r.cluster_id, []).append(r.similarity_score)
        results: list[dict[str, Any]] = []
        for cid, sims in cluster_data.items():
            mean_sim = sum(sims) / len(sims)
            results.append(
                {
                    "cluster_id": cid,
                    "mean_similarity": round(mean_sim, 4),
                    "task_count": len(sims),
                    "min_similarity": round(min(sims), 4),
                    "max_similarity": round(max(sims), 4),
                }
            )
        results.sort(key=lambda x: x["mean_similarity"], reverse=True)
        return results

    def evaluate_cluster_homogeneity(self) -> list[dict[str, Any]]:
        """Evaluate homogeneity score per cluster."""
        cluster_data: dict[str, list[float]] = {}
        for r in self._records:
            cluster_data.setdefault(r.cluster_id, []).append(r.feature_value)
        results: list[dict[str, Any]] = []
        for cid, vals in cluster_data.items():
            mean_v = sum(vals) / len(vals)
            variance = sum((v - mean_v) ** 2 for v in vals) / len(vals)
            homogeneity = round(1.0 / (1.0 + variance), 4)
            results.append(
                {
                    "cluster_id": cid,
                    "homogeneity_score": homogeneity,
                    "feature_variance": round(variance, 6),
                    "task_count": len(vals),
                }
            )
        results.sort(key=lambda x: x["homogeneity_score"], reverse=True)
        return results

    def rebalance_clusters(self) -> dict[str, Any]:
        """Identify clusters needing rebalancing and suggest target sizes."""
        cluster_counts: dict[str, int] = {}
        for r in self._records:
            cluster_counts[r.cluster_id] = cluster_counts.get(r.cluster_id, 0) + 1
        if not cluster_counts:
            return {"needs_rebalance": [], "target_size": 0}
        target = sum(cluster_counts.values()) // max(len(cluster_counts), 1)
        imbalanced: list[tuple[str, int, int]] = [
            (cid, cnt, target)
            for cid, cnt in cluster_counts.items()
            if abs(cnt - target) > max(target // 2, 1)
        ]
        imbalanced.sort(
            key=lambda x: abs(x[1] - x[2]),
            reverse=True,
        )
        needs_rebalance: list[dict[str, Any]] = [
            {
                "cluster_id": cid,
                "current_size": cnt,
                "target_size": tgt,
            }
            for cid, cnt, tgt in imbalanced
        ]
        return {
            "needs_rebalance": needs_rebalance,
            "target_size": target,
            "total_clusters": len(cluster_counts),
        }
