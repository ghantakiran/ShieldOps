"""Tests for SecurityKnowledgeGraphEngine."""

from __future__ import annotations

from shieldops.security.security_knowledge_graph_engine import (
    EntityType,
    GraphDepth,
    RelationType,
    SecurityKnowledgeGraphEngine,
)


def _engine(**kw) -> SecurityKnowledgeGraphEngine:
    return SecurityKnowledgeGraphEngine(**kw)


class TestEnums:
    def test_entity_asset(self):
        assert EntityType.ASSET == "asset"

    def test_entity_vuln(self):
        assert EntityType.VULNERABILITY == "vulnerability"

    def test_entity_actor(self):
        assert EntityType.THREAT_ACTOR == "threat_actor"

    def test_entity_indicator(self):
        assert EntityType.INDICATOR == "indicator"

    def test_rel_exploits(self):
        assert RelationType.EXPLOITS == "exploits"

    def test_rel_targets(self):
        assert RelationType.TARGETS == "targets"

    def test_rel_indicates(self):
        assert RelationType.INDICATES == "indicates"

    def test_rel_mitigates(self):
        assert RelationType.MITIGATES == "mitigates"

    def test_depth_shallow(self):
        assert GraphDepth.SHALLOW == "shallow"

    def test_depth_moderate(self):
        assert GraphDepth.MODERATE == "moderate"

    def test_depth_deep(self):
        assert GraphDepth.DEEP == "deep"

    def test_depth_exhaustive(self):
        assert GraphDepth.EXHAUSTIVE == "exhaustive"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            entity_id="e1",
            entity_type=EntityType.ASSET,
            centrality_score=0.9,
        )
        assert r.entity_id == "e1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(entity_id=f"e-{i}")
        assert len(eng._records) == 3


class TestProcess:
    def test_returns_analysis(self):
        eng = _engine()
        r = eng.add_record(
            entity_id="e1",
            centrality_score=0.8,
            connection_count=5,
        )
        a = eng.process(r.id)
        assert a is not None
        assert a.entity_id == "e1"

    def test_missing_key(self):
        assert _engine().process("x") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(entity_id="e1")
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(entity_id="e1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(entity_id="e1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestBuildThreatSubgraph:
    def test_basic(self):
        eng = _engine()
        eng.add_record(entity_id="e1", entity_type=EntityType.ASSET)
        result = eng.build_threat_subgraph()
        assert len(result) == 1
        assert result[0]["entity_type"] == "asset"

    def test_empty(self):
        assert _engine().build_threat_subgraph() == []


class TestDetectHiddenRelationships:
    def test_basic(self):
        eng = _engine(centrality_threshold=0.7)
        eng.add_record(
            entity_id="e1",
            centrality_score=0.3,
            connection_count=5,
        )
        result = eng.detect_hidden_relationships()
        assert len(result) == 1
        assert result[0]["hidden_influence_score"] > 0

    def test_empty(self):
        assert _engine().detect_hidden_relationships() == []


class TestComputeEntityCentrality:
    def test_basic(self):
        eng = _engine()
        eng.add_record(entity_id="e1", centrality_score=0.9)
        result = eng.compute_entity_centrality()
        assert result["avg_centrality"] == 0.9

    def test_empty(self):
        result = _engine().compute_entity_centrality()
        assert result["avg_centrality"] == 0.0
