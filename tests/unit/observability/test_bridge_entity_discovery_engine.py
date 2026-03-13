"""Tests for BridgeEntityDiscoveryEngine."""

from __future__ import annotations

from shieldops.observability.bridge_entity_discovery_engine import (
    BridgeEntityAnalysis,
    BridgeEntityDiscoveryEngine,
    BridgeEntityRecord,
    BridgeEntityReport,
    BridgeStrength,
    DiscoveryMethod,
    EntityType,
)


def test_add_record() -> None:
    engine = BridgeEntityDiscoveryEngine()
    rec = engine.add_record(
        entity_id="svc-auth",
        entity_type=EntityType.SERVICE,
        bridge_strength=BridgeStrength.STRONG,
        discovery_method=DiscoveryMethod.TOPOLOGY,
        significance_score=0.92,
        connected_alerts=5,
        source_signal="alert-001",
    )
    assert isinstance(rec, BridgeEntityRecord)
    assert rec.entity_id == "svc-auth"
    assert rec.connected_alerts == 5


def test_process() -> None:
    engine = BridgeEntityDiscoveryEngine()
    rec = engine.add_record(
        entity_id="host-db",
        entity_type=EntityType.HOST,
        bridge_strength=BridgeStrength.STRONG,
        significance_score=0.85,
    )
    result = engine.process(rec.id)
    assert isinstance(result, BridgeEntityAnalysis)
    assert result.entity_id == "host-db"
    assert result.is_significant is True


def test_process_not_found() -> None:
    engine = BridgeEntityDiscoveryEngine()
    result = engine.process("ghost-entity")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = BridgeEntityDiscoveryEngine()
    for eid, et, bs, dm, sig in [
        ("e1", EntityType.SERVICE, BridgeStrength.STRONG, DiscoveryMethod.CORRELATION, 0.9),
        ("e2", EntityType.HOST, BridgeStrength.MODERATE, DiscoveryMethod.TOPOLOGY, 0.7),
        ("e3", EntityType.DEPLOYMENT, BridgeStrength.WEAK, DiscoveryMethod.TEMPORAL, 0.4),
        ("e4", EntityType.CONFIGURATION, BridgeStrength.SPECULATIVE, DiscoveryMethod.SEMANTIC, 0.2),
    ]:
        engine.add_record(
            entity_id=eid,
            entity_type=et,
            bridge_strength=bs,
            discovery_method=dm,
            significance_score=sig,
        )
    report = engine.generate_report()
    assert isinstance(report, BridgeEntityReport)
    assert report.total_records == 4
    assert "service" in report.by_entity_type


def test_get_stats() -> None:
    engine = BridgeEntityDiscoveryEngine()
    engine.add_record(entity_type=EntityType.SERVICE, significance_score=0.8)
    engine.add_record(entity_type=EntityType.HOST, significance_score=0.6)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "entity_type_distribution" in stats


def test_clear_data() -> None:
    engine = BridgeEntityDiscoveryEngine()
    engine.add_record(entity_id="e-x")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_discover_bridge_entities() -> None:
    engine = BridgeEntityDiscoveryEngine()
    engine.add_record(entity_id="svc-a", significance_score=0.9, connected_alerts=3)
    engine.add_record(entity_id="svc-a", significance_score=0.85, connected_alerts=2)
    engine.add_record(entity_id="svc-b", significance_score=0.5, connected_alerts=1)
    results = engine.discover_bridge_entities()
    assert isinstance(results, list)
    assert results[0]["entity_id"] == "svc-a"
    assert results[0]["avg_significance"] >= results[-1]["avg_significance"]


def test_score_bridge_significance() -> None:
    engine = BridgeEntityDiscoveryEngine()
    engine.add_record(
        entity_id="svc-a",
        bridge_strength=BridgeStrength.STRONG,
        significance_score=0.9,
        connected_alerts=10,
    )
    engine.add_record(
        entity_id="svc-b",
        bridge_strength=BridgeStrength.WEAK,
        significance_score=0.3,
        connected_alerts=1,
    )
    results = engine.score_bridge_significance()
    assert isinstance(results, list)
    assert results[0]["rank"] == 1
    assert results[0]["weighted_score"] >= results[-1]["weighted_score"]


def test_reconstruct_entity_graph() -> None:
    engine = BridgeEntityDiscoveryEngine()
    engine.add_record(entity_id="svc-a", source_signal="svc-b")
    engine.add_record(entity_id="svc-a", source_signal="svc-c")
    engine.add_record(entity_id="svc-d", source_signal="svc-b")
    graph = engine.reconstruct_entity_graph()
    assert isinstance(graph, dict)
    assert graph["node_count"] >= 2
    assert graph["edge_count"] >= 1
    assert "nodes" in graph
    assert "edges" in graph
