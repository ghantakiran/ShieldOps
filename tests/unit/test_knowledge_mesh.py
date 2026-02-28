"""Tests for shieldops.agents.knowledge_mesh — AgentKnowledgeMesh."""

from __future__ import annotations

from shieldops.agents.knowledge_mesh import (
    AgentKnowledgeMesh,
    FreshnessLevel,
    KnowledgeEntry,
    KnowledgeMeshReport,
    KnowledgeType,
    PropagationEvent,
    PropagationScope,
)


def _engine(**kw) -> AgentKnowledgeMesh:
    return AgentKnowledgeMesh(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # KnowledgeType (5)
    def test_type_reasoning_chain(self):
        assert KnowledgeType.REASONING_CHAIN == "reasoning_chain"

    def test_type_observation(self):
        assert KnowledgeType.OBSERVATION == "observation"

    def test_type_hypothesis(self):
        assert KnowledgeType.HYPOTHESIS == "hypothesis"

    def test_type_evidence(self):
        assert KnowledgeType.EVIDENCE == "evidence"

    def test_type_conclusion(self):
        assert KnowledgeType.CONCLUSION == "conclusion"

    # PropagationScope (5)
    def test_scope_local(self):
        assert PropagationScope.LOCAL == "local"

    def test_scope_team(self):
        assert PropagationScope.TEAM == "team"

    def test_scope_swarm(self):
        assert PropagationScope.SWARM == "swarm"

    def test_scope_global(self):
        assert PropagationScope.GLOBAL == "global"

    def test_scope_selective(self):
        assert PropagationScope.SELECTIVE == "selective"

    # FreshnessLevel (5)
    def test_freshness_real_time(self):
        assert FreshnessLevel.REAL_TIME == "real_time"

    def test_freshness_recent(self):
        assert FreshnessLevel.RECENT == "recent"

    def test_freshness_stale(self):
        assert FreshnessLevel.STALE == "stale"

    def test_freshness_expired(self):
        assert FreshnessLevel.EXPIRED == "expired"

    def test_freshness_archived(self):
        assert FreshnessLevel.ARCHIVED == "archived"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_knowledge_entry_defaults(self):
        r = KnowledgeEntry()
        assert r.id
        assert r.source_agent == ""
        assert r.knowledge_type == KnowledgeType.OBSERVATION
        assert r.propagation_scope == PropagationScope.LOCAL
        assert r.freshness_level == FreshnessLevel.REAL_TIME
        assert r.relevance_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_propagation_event_defaults(self):
        r = PropagationEvent()
        assert r.id
        assert r.event_label == ""
        assert r.knowledge_type == KnowledgeType.OBSERVATION
        assert r.propagation_scope == PropagationScope.TEAM
        assert r.hop_count == 0
        assert r.created_at > 0

    def test_knowledge_mesh_report_defaults(self):
        r = KnowledgeMeshReport()
        assert r.total_entries == 0
        assert r.total_propagations == 0
        assert r.freshness_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_scope == {}
        assert r.stale_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_entry
# -------------------------------------------------------------------


class TestRecordEntry:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            "agent-alpha",
            knowledge_type=KnowledgeType.OBSERVATION,
            propagation_scope=PropagationScope.LOCAL,
        )
        assert r.source_agent == "agent-alpha"
        assert r.knowledge_type == KnowledgeType.OBSERVATION

    def test_max_records_trim(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(f"agent-{i}")
        assert len(eng._records) == 3

    def test_get_by_id(self):
        eng = _engine()
        r = eng.record_entry("agent-alpha")
        assert eng.get_entry(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_entry("nonexistent") is None

    def test_list_filter(self):
        eng = _engine()
        eng.record_entry("agent-alpha")
        eng.record_entry("agent-beta")
        results = eng.list_entries(source_agent="agent-alpha")
        assert len(results) == 1

    def test_list_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(f"agent-{i}")
        results = eng.list_entries(limit=3)
        assert len(results) == 3


# -------------------------------------------------------------------
# add_propagation
# -------------------------------------------------------------------


class TestAddPropagation:
    def test_basic(self):
        eng = _engine()
        p = eng.add_propagation(
            "event-1",
            knowledge_type=KnowledgeType.OBSERVATION,
            propagation_scope=PropagationScope.TEAM,
            hop_count=3,
        )
        assert p.event_label == "event-1"
        assert p.hop_count == 3

    def test_trim(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_propagation(f"event-{i}")
        assert len(eng._propagations) == 2


# -------------------------------------------------------------------
# analyze_knowledge_freshness
# -------------------------------------------------------------------


class TestAnalyze:
    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_knowledge_freshness("ghost")
        assert result["status"] == "no_data"

    def test_with_data(self):
        eng = _engine()
        eng.record_entry("agent-alpha", freshness_level=FreshnessLevel.REAL_TIME)
        eng.record_entry("agent-alpha", freshness_level=FreshnessLevel.STALE)
        result = eng.analyze_knowledge_freshness("agent-alpha")
        assert result["source_agent"] == "agent-alpha"
        assert result["total_entries"] == 2
        assert result["freshness_rate_pct"] == 50.0

    def test_meets_threshold(self):
        eng = _engine()
        eng.record_entry("agent-alpha", freshness_level=FreshnessLevel.REAL_TIME)
        result = eng.analyze_knowledge_freshness("agent-alpha")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_stale_knowledge
# -------------------------------------------------------------------


class TestIdentify:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_stale_knowledge() == []

    def test_with_matches(self):
        eng = _engine()
        eng.record_entry("agent-alpha", freshness_level=FreshnessLevel.STALE)
        eng.record_entry("agent-alpha", freshness_level=FreshnessLevel.EXPIRED)
        eng.record_entry("agent-beta", freshness_level=FreshnessLevel.REAL_TIME)
        results = eng.identify_stale_knowledge()
        assert len(results) == 1
        assert results[0]["source_agent"] == "agent-alpha"


# -------------------------------------------------------------------
# rank_by_propagation_reach
# -------------------------------------------------------------------


class TestRank:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_propagation_reach() == []

    def test_ordering(self):
        eng = _engine()
        eng.record_entry("agent-alpha")
        eng.record_entry("agent-alpha")
        eng.record_entry("agent-beta")
        results = eng.rank_by_propagation_reach()
        assert results[0]["source_agent"] == "agent-alpha"
        assert results[0]["entry_count"] == 2


# -------------------------------------------------------------------
# detect_knowledge_gaps
# -------------------------------------------------------------------


class TestDetect:
    def test_empty(self):
        eng = _engine()
        assert eng.detect_knowledge_gaps() == []

    def test_detection(self):
        eng = _engine()
        for _ in range(5):
            eng.record_entry("agent-alpha", freshness_level=FreshnessLevel.STALE)
        eng.record_entry("agent-beta", freshness_level=FreshnessLevel.REAL_TIME)
        results = eng.detect_knowledge_gaps()
        assert len(results) == 1
        assert results[0]["source_agent"] == "agent-alpha"
        assert results[0]["gap_detected"] is True


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_entries == 0
        assert "below" in report.recommendations[0]

    def test_with_data(self):
        eng = _engine()
        eng.record_entry("agent-alpha", freshness_level=FreshnessLevel.REAL_TIME)
        eng.record_entry("agent-beta", freshness_level=FreshnessLevel.STALE)
        eng.record_entry("agent-beta", freshness_level=FreshnessLevel.STALE)
        eng.add_propagation("event-1")
        report = eng.generate_report()
        assert report.total_entries == 3
        assert report.total_propagations == 1
        assert report.by_type != {}
        assert report.recommendations != []

    def test_recommendations(self):
        eng = _engine()
        eng.record_entry("agent-alpha", freshness_level=FreshnessLevel.REAL_TIME)
        report = eng.generate_report()
        assert len(report.recommendations) >= 1


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clear(self):
        eng = _engine()
        eng.record_entry("agent-alpha")
        eng.add_propagation("event-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._propagations) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_entries"] == 0
        assert stats["total_propagations"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_entry("agent-alpha", knowledge_type=KnowledgeType.OBSERVATION)
        eng.record_entry("agent-beta", knowledge_type=KnowledgeType.HYPOTHESIS)
        eng.add_propagation("event-1")
        stats = eng.get_stats()
        assert stats["total_entries"] == 2
        assert stats["total_propagations"] == 1
        assert stats["unique_agents"] == 2
