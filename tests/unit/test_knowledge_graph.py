"""Tests for shieldops.knowledge.knowledge_graph — KnowledgeGraphManager."""

from __future__ import annotations

from shieldops.knowledge.knowledge_graph import (
    GraphEdge,
    GraphHealth,
    GraphRecord,
    KnowledgeGraphManager,
    KnowledgeGraphReport,
    NodeType,
    RelationshipType,
)


def _engine(**kw) -> KnowledgeGraphManager:
    return KnowledgeGraphManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_node_type_service(self):
        assert NodeType.SERVICE == "service"

    def test_node_type_runbook(self):
        assert NodeType.RUNBOOK == "runbook"

    def test_node_type_alert(self):
        assert NodeType.ALERT == "alert"

    def test_node_type_team(self):
        assert NodeType.TEAM == "team"

    def test_node_type_incident(self):
        assert NodeType.INCIDENT == "incident"

    def test_relationship_depends_on(self):
        assert RelationshipType.DEPENDS_ON == "depends_on"

    def test_relationship_owned_by(self):
        assert RelationshipType.OWNED_BY == "owned_by"

    def test_relationship_triggers(self):
        assert RelationshipType.TRIGGERS == "triggers"

    def test_relationship_resolves(self):
        assert RelationshipType.RESOLVES == "resolves"

    def test_relationship_documents(self):
        assert RelationshipType.DOCUMENTS == "documents"

    def test_health_connected(self):
        assert GraphHealth.CONNECTED == "connected"

    def test_health_sparse(self):
        assert GraphHealth.SPARSE == "sparse"

    def test_health_fragmented(self):
        assert GraphHealth.FRAGMENTED == "fragmented"

    def test_health_orphaned(self):
        assert GraphHealth.ORPHANED == "orphaned"

    def test_health_empty(self):
        assert GraphHealth.EMPTY == "empty"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_graph_record_defaults(self):
        r = GraphRecord()
        assert r.id
        assert r.node_id == ""
        assert r.node_type == NodeType.SERVICE
        assert r.relationship_type == RelationshipType.DEPENDS_ON
        assert r.graph_health == GraphHealth.EMPTY
        assert r.connectivity_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_graph_edge_defaults(self):
        e = GraphEdge()
        assert e.id
        assert e.node_id == ""
        assert e.node_type == NodeType.SERVICE
        assert e.edge_weight == 0.0
        assert e.threshold == 0.0
        assert e.breached is False
        assert e.description == ""
        assert e.created_at > 0

    def test_knowledge_graph_report_defaults(self):
        r = KnowledgeGraphReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_edges == 0
        assert r.orphan_nodes == 0
        assert r.avg_connectivity_score == 0.0
        assert r.by_node_type == {}
        assert r.by_relationship == {}
        assert r.by_health == {}
        assert r.top_orphans == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_node
# ---------------------------------------------------------------------------


class TestRecordNode:
    def test_basic(self):
        eng = _engine()
        r = eng.record_node(
            node_id="NODE-001",
            node_type=NodeType.SERVICE,
            relationship_type=RelationshipType.DEPENDS_ON,
            graph_health=GraphHealth.CONNECTED,
            connectivity_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.node_id == "NODE-001"
        assert r.node_type == NodeType.SERVICE
        assert r.relationship_type == RelationshipType.DEPENDS_ON
        assert r.graph_health == GraphHealth.CONNECTED
        assert r.connectivity_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_node(node_id=f"NODE-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_node
# ---------------------------------------------------------------------------


class TestGetNode:
    def test_found(self):
        eng = _engine()
        r = eng.record_node(
            node_id="NODE-001",
            node_type=NodeType.RUNBOOK,
        )
        result = eng.get_node(r.id)
        assert result is not None
        assert result.node_type == NodeType.RUNBOOK

    def test_not_found(self):
        eng = _engine()
        assert eng.get_node("nonexistent") is None


# ---------------------------------------------------------------------------
# list_nodes
# ---------------------------------------------------------------------------


class TestListNodes:
    def test_list_all(self):
        eng = _engine()
        eng.record_node(node_id="NODE-001")
        eng.record_node(node_id="NODE-002")
        assert len(eng.list_nodes()) == 2

    def test_filter_by_node_type(self):
        eng = _engine()
        eng.record_node(node_id="NODE-001", node_type=NodeType.SERVICE)
        eng.record_node(node_id="NODE-002", node_type=NodeType.ALERT)
        results = eng.list_nodes(node_type=NodeType.SERVICE)
        assert len(results) == 1

    def test_filter_by_relationship(self):
        eng = _engine()
        eng.record_node(
            node_id="NODE-001",
            relationship_type=RelationshipType.DEPENDS_ON,
        )
        eng.record_node(
            node_id="NODE-002",
            relationship_type=RelationshipType.OWNED_BY,
        )
        results = eng.list_nodes(relationship=RelationshipType.DEPENDS_ON)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_node(node_id="NODE-001", service="api-gateway")
        eng.record_node(node_id="NODE-002", service="auth-svc")
        results = eng.list_nodes(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_node(node_id="NODE-001", team="sre")
        eng.record_node(node_id="NODE-002", team="platform")
        results = eng.list_nodes(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_node(node_id=f"NODE-{i}")
        assert len(eng.list_nodes(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_edge
# ---------------------------------------------------------------------------


class TestAddEdge:
    def test_basic(self):
        eng = _engine()
        e = eng.add_edge(
            node_id="NODE-001",
            node_type=NodeType.RUNBOOK,
            edge_weight=85.0,
            threshold=90.0,
            breached=True,
            description="Weak link detected",
        )
        assert e.node_id == "NODE-001"
        assert e.node_type == NodeType.RUNBOOK
        assert e.edge_weight == 85.0
        assert e.threshold == 90.0
        assert e.breached is True
        assert e.description == "Weak link detected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_edge(node_id=f"NODE-{i}")
        assert len(eng._edges) == 2


# ---------------------------------------------------------------------------
# analyze_graph_connectivity
# ---------------------------------------------------------------------------


class TestAnalyzeGraphConnectivity:
    def test_with_data(self):
        eng = _engine()
        eng.record_node(
            node_id="NODE-001",
            node_type=NodeType.SERVICE,
            connectivity_score=10.0,
        )
        eng.record_node(
            node_id="NODE-002",
            node_type=NodeType.SERVICE,
            connectivity_score=20.0,
        )
        result = eng.analyze_graph_connectivity()
        assert "service" in result
        assert result["service"]["count"] == 2
        assert result["service"]["avg_connectivity"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_graph_connectivity() == {}


# ---------------------------------------------------------------------------
# identify_orphan_nodes
# ---------------------------------------------------------------------------


class TestIdentifyOrphanNodes:
    def test_detects(self):
        eng = _engine()
        eng.record_node(
            node_id="NODE-001",
            graph_health=GraphHealth.ORPHANED,
        )
        eng.record_node(
            node_id="NODE-002",
            graph_health=GraphHealth.CONNECTED,
        )
        results = eng.identify_orphan_nodes()
        assert len(results) == 1
        assert results[0]["node_id"] == "NODE-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_orphan_nodes() == []


# ---------------------------------------------------------------------------
# rank_by_connectivity
# ---------------------------------------------------------------------------


class TestRankByConnectivity:
    def test_ranked(self):
        eng = _engine()
        eng.record_node(
            node_id="NODE-001",
            service="api-gateway",
            connectivity_score=120.0,
        )
        eng.record_node(
            node_id="NODE-002",
            service="auth-svc",
            connectivity_score=30.0,
        )
        eng.record_node(
            node_id="NODE-001",
            service="api-gateway",
            connectivity_score=80.0,
        )
        results = eng.rank_by_connectivity()
        assert len(results) == 2
        # ascending: NODE-002 (30.0) first, NODE-001 (100.0) second
        assert results[0]["node_id"] == "NODE-002"
        assert results[0]["avg_connectivity"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_connectivity() == []


# ---------------------------------------------------------------------------
# detect_graph_trends
# ---------------------------------------------------------------------------


class TestDetectGraphTrends:
    def test_stable(self):
        eng = _engine()
        for val in [60.0, 60.0, 60.0, 60.0]:
            eng.add_edge(node_id="NODE-1", edge_weight=val)
        result = eng.detect_graph_trends()
        assert result["trend"] == "stable"

    def test_growing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_edge(node_id="NODE-1", edge_weight=val)
        result = eng.detect_graph_trends()
        assert result["trend"] == "growing"
        assert result["delta"] > 0

    def test_shrinking(self):
        eng = _engine()
        for val in [20.0, 20.0, 5.0, 5.0]:
            eng.add_edge(node_id="NODE-1", edge_weight=val)
        result = eng.detect_graph_trends()
        assert result["trend"] == "shrinking"
        assert result["delta"] < 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_graph_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_node(
            node_id="NODE-001",
            node_type=NodeType.SERVICE,
            relationship_type=RelationshipType.DEPENDS_ON,
            graph_health=GraphHealth.ORPHANED,
            connectivity_score=5.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, KnowledgeGraphReport)
        assert report.total_records == 1
        assert report.orphan_nodes == 1
        assert len(report.top_orphans) >= 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_node(node_id="NODE-001")
        eng.add_edge(node_id="NODE-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._edges) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_edges"] == 0
        assert stats["node_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_node(
            node_id="NODE-001",
            node_type=NodeType.SERVICE,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "service" in stats["node_type_distribution"]
