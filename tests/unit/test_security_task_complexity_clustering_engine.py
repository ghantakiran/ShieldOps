"""Tests for SecurityTaskComplexityClusteringEngine."""

from __future__ import annotations

import pytest

from shieldops.security.security_task_complexity_clustering_engine import (
    ClusteringFeature,
    ClusterQuality,
    ComplexityTier,
    SecurityTaskComplexityClusteringEngine,
)


@pytest.fixture()
def engine() -> SecurityTaskComplexityClusteringEngine:
    return SecurityTaskComplexityClusteringEngine(max_records=100)


def test_add_record(engine: SecurityTaskComplexityClusteringEngine) -> None:
    rec = engine.add_record(
        task_id="task-1",
        cluster_id="c1",
        complexity_tier=ComplexityTier.TIER_3_COMPLEX,
        clustering_feature=ClusteringFeature.DECISION_DEPTH,
        cluster_quality=ClusterQuality.TIGHT,
        feature_value=0.7,
        similarity_score=0.9,
    )
    assert rec.task_id == "task-1"
    assert rec.similarity_score == 0.9
    assert len(engine._records) == 1


def test_process(engine: SecurityTaskComplexityClusteringEngine) -> None:
    engine.add_record(cluster_id="c1", similarity_score=0.8)
    engine.add_record(cluster_id="c1", similarity_score=0.9)
    rec = engine.add_record(cluster_id="c1", similarity_score=0.85)
    result = engine.process(rec.id)
    assert hasattr(result, "cluster_size")
    assert result.cluster_size == 3  # type: ignore[union-attr]


def test_process_not_found(engine: SecurityTaskComplexityClusteringEngine) -> None:
    result = engine.process("bad-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report(engine: SecurityTaskComplexityClusteringEngine) -> None:
    engine.add_record(
        complexity_tier=ComplexityTier.TIER_4_ADVANCED,
        cluster_quality=ClusterQuality.FRAGMENTED,
        cluster_id="cx",
        similarity_score=0.3,
    )
    engine.add_record(
        complexity_tier=ComplexityTier.TIER_1_SIMPLE,
        cluster_quality=ClusterQuality.TIGHT,
        similarity_score=0.95,
    )
    report = engine.generate_report()
    assert report.total_records == 2
    assert "fragmented" in report.by_cluster_quality


def test_get_stats(engine: SecurityTaskComplexityClusteringEngine) -> None:
    engine.add_record(complexity_tier=ComplexityTier.TIER_2_MODERATE)
    stats = engine.get_stats()
    assert "tier_distribution" in stats
    assert stats["total_records"] == 1


def test_clear_data(engine: SecurityTaskComplexityClusteringEngine) -> None:
    engine.add_record(task_id="t1")
    engine.clear_data()
    assert len(engine._records) == 0
    assert len(engine._analyses) == 0


def test_cluster_by_structural_similarity(
    engine: SecurityTaskComplexityClusteringEngine,
) -> None:
    engine.add_record(cluster_id="c1", similarity_score=0.9)
    engine.add_record(cluster_id="c1", similarity_score=0.8)
    engine.add_record(cluster_id="c2", similarity_score=0.5)
    result = engine.cluster_by_structural_similarity()
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["mean_similarity"] >= result[-1]["mean_similarity"]


def test_evaluate_cluster_homogeneity(
    engine: SecurityTaskComplexityClusteringEngine,
) -> None:
    engine.add_record(cluster_id="c1", feature_value=0.5)
    engine.add_record(cluster_id="c1", feature_value=0.5)
    engine.add_record(cluster_id="c2", feature_value=0.1)
    result = engine.evaluate_cluster_homogeneity()
    assert isinstance(result, list)
    assert result[0]["homogeneity_score"] >= result[-1]["homogeneity_score"]


def test_rebalance_clusters(engine: SecurityTaskComplexityClusteringEngine) -> None:
    for _ in range(8):
        engine.add_record(cluster_id="big_cluster")
    engine.add_record(cluster_id="small_cluster")
    result = engine.rebalance_clusters()
    assert "needs_rebalance" in result
    assert "target_size" in result
    assert result["total_clusters"] == 2


def test_max_records_eviction(engine: SecurityTaskComplexityClusteringEngine) -> None:
    for i in range(110):
        engine.add_record(task_id=f"t-{i}")
    assert len(engine._records) == 100
