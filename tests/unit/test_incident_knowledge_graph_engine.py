"""Tests for IncidentKnowledgeGraphEngine."""

import pytest

from shieldops.knowledge.incident_knowledge_graph_engine import (
    EdgeType,
    GraphScope,
    IncidentKnowledgeGraphEngine,
    KnowledgeGraphAnalysis,
    KnowledgeGraphRecord,
    KnowledgeGraphReport,
    NodeType,
)


@pytest.fixture
def engine():
    return IncidentKnowledgeGraphEngine(max_records=1000)


def test_engine_init(engine):
    assert engine._max_records == 1000
    assert engine._records == []
    assert engine._analyses == {}


def test_add_record_defaults(engine):
    rec = engine.add_record()
    assert isinstance(rec, KnowledgeGraphRecord)
    assert rec.node_type == NodeType.INCIDENT
    assert rec.edge_type == EdgeType.CAUSED_BY


def test_add_record_custom(engine):
    rec = engine.add_record(
        source_node="inc-1",
        target_node="svc-api",
        node_type=NodeType.SERVICE,
        edge_type=EdgeType.AFFECTED,
        graph_scope=GraphScope.ORGANIZATION,
        weight=2.5,
        service="api",
    )
    assert rec.source_node == "inc-1"
    assert rec.weight == 2.5


def test_add_record_ring_buffer():
    engine = IncidentKnowledgeGraphEngine(max_records=3)
    for i in range(5):
        engine.add_record(source_node=f"node-{i}")
    assert len(engine._records) == 3


def test_process_found(engine):
    rec = engine.add_record(source_node="inc-1", target_node="svc-api", weight=1.0)
    result = engine.process(rec.id)
    assert isinstance(result, KnowledgeGraphAnalysis)
    assert result.source_node == "inc-1"
    assert result.connection_count >= 1


def test_process_with_gaps(engine):
    rec = engine.add_record(source_node="isolated-node", target_node="other")
    result = engine.process(rec.id)
    assert result.has_gaps is True  # Only 1 connection


def test_process_not_found(engine):
    result = engine.process("nonexistent")
    assert result["status"] == "not_found"


def test_generate_report_empty(engine):
    report = engine.generate_report()
    assert isinstance(report, KnowledgeGraphReport)
    assert report.total_records == 0


def test_generate_report_with_data(engine):
    engine.add_record(node_type=NodeType.INCIDENT, edge_type=EdgeType.CAUSED_BY, weight=1.0)
    engine.add_record(node_type=NodeType.SERVICE, edge_type=EdgeType.AFFECTED, weight=2.0)
    report = engine.generate_report()
    assert report.total_records == 2
    assert report.avg_weight == 1.5


def test_get_stats(engine):
    engine.add_record(node_type=NodeType.ROOT_CAUSE)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "root_cause" in stats["node_type_distribution"]


def test_clear_data(engine):
    engine.add_record()
    result = engine.clear_data()
    assert result == {"status": "cleared"}
    assert engine._records == []


def test_compute_knowledge_connections(engine):
    engine.add_record(source_node="inc-1", target_node="svc-api", weight=1.0)
    engine.add_record(source_node="inc-2", target_node="svc-api", weight=2.0)
    result = engine.compute_knowledge_connections()
    assert len(result) >= 1
    # svc-api appears as target in both, so should have highest connections
    api_entry = next((r for r in result if r["node"] == "svc-api"), None)
    assert api_entry is not None
    assert api_entry["connection_count"] == 2


def test_compute_knowledge_connections_empty(engine):
    assert engine.compute_knowledge_connections() == []


def test_detect_knowledge_gaps(engine):
    engine.add_record(source_node="hub", target_node="spoke-1", weight=1.0)
    engine.add_record(source_node="hub", target_node="spoke-2", weight=1.0)
    engine.add_record(source_node="hub", target_node="spoke-3", weight=1.0)
    engine.add_record(source_node="spoke-1", target_node="spoke-2", weight=1.0)
    engine.add_record(source_node="spoke-2", target_node="spoke-3", weight=1.0)
    result = engine.detect_knowledge_gaps()
    # spoke-3 has fewest connections relative to avg
    assert isinstance(result, list)


def test_detect_knowledge_gaps_empty(engine):
    assert engine.detect_knowledge_gaps() == []


def test_rank_nodes_by_incident_centrality(engine):
    engine.add_record(source_node="inc-1", target_node="svc-api", weight=3.0)
    engine.add_record(source_node="inc-2", target_node="svc-db", weight=1.0)
    result = engine.rank_nodes_by_incident_centrality()
    assert len(result) == 2
    assert result[0]["rank"] == 1
    assert result[0]["centrality_score"] >= result[1]["centrality_score"]


def test_rank_nodes_by_incident_centrality_empty(engine):
    assert engine.rank_nodes_by_incident_centrality() == []


def test_enum_values():
    assert NodeType.TEAM == "team"
    assert EdgeType.PREVENTED == "prevented"
    assert GraphScope.CROSS_ORG == "cross_org"
