"""Tests for shieldops.incidents.knowledge_linker — IncidentKnowledgeLinker."""

from __future__ import annotations

from shieldops.incidents.knowledge_linker import (
    IncidentKnowledgeLinker,
    KnowledgeLinkerReport,
    KnowledgeLinkRecord,
    KnowledgeSource,
    LinkRelevance,
    LinkSuggestion,
    LinkType,
)


def _engine(**kw) -> IncidentKnowledgeLinker:
    return IncidentKnowledgeLinker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # LinkType (5)
    def test_link_type_runbook(self):
        assert LinkType.RUNBOOK == "runbook"

    def test_link_type_postmortem(self):
        assert LinkType.POSTMORTEM == "postmortem"

    def test_link_type_documentation(self):
        assert LinkType.DOCUMENTATION == "documentation"

    def test_link_type_training(self):
        assert LinkType.TRAINING == "training"

    def test_link_type_similar_incident(self):
        assert LinkType.SIMILAR_INCIDENT == "similar_incident"

    # LinkRelevance (5)
    def test_relevance_exact_match(self):
        assert LinkRelevance.EXACT_MATCH == "exact_match"

    def test_relevance_highly_relevant(self):
        assert LinkRelevance.HIGHLY_RELEVANT == "highly_relevant"

    def test_relevance_somewhat_relevant(self):
        assert LinkRelevance.SOMEWHAT_RELEVANT == "somewhat_relevant"

    def test_relevance_loosely_related(self):
        assert LinkRelevance.LOOSELY_RELATED == "loosely_related"

    def test_relevance_not_relevant(self):
        assert LinkRelevance.NOT_RELEVANT == "not_relevant"

    # KnowledgeSource (5)
    def test_source_internal_wiki(self):
        assert KnowledgeSource.INTERNAL_WIKI == "internal_wiki"

    def test_source_runbook_library(self):
        assert KnowledgeSource.RUNBOOK_LIBRARY == "runbook_library"

    def test_source_incident_history(self):
        assert KnowledgeSource.INCIDENT_HISTORY == "incident_history"

    def test_source_external_docs(self):
        assert KnowledgeSource.EXTERNAL_DOCS == "external_docs"

    def test_source_ai_generated(self):
        assert KnowledgeSource.AI_GENERATED == "ai_generated"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_knowledge_link_record_defaults(self):
        r = KnowledgeLinkRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.knowledge_resource_id == ""
        assert r.link_type == LinkType.DOCUMENTATION
        assert r.relevance == LinkRelevance.SOMEWHAT_RELEVANT
        assert r.knowledge_source == KnowledgeSource.INTERNAL_WIKI
        assert r.relevance_score_pct == 0.0
        assert r.notes == ""
        assert r.created_at > 0

    def test_link_suggestion_defaults(self):
        s = LinkSuggestion()
        assert s.id
        assert s.incident_pattern == ""
        assert s.suggested_resource_id == ""
        assert s.link_type == LinkType.RUNBOOK
        assert s.knowledge_source == KnowledgeSource.RUNBOOK_LIBRARY
        assert s.confidence_pct == 0.0
        assert s.auto_link is False
        assert s.created_at > 0

    def test_knowledge_linker_report_defaults(self):
        r = KnowledgeLinkerReport()
        assert r.id
        assert r.total_links == 0
        assert r.total_suggestions == 0
        assert r.avg_relevance_score_pct == 0.0
        assert r.by_link_type == {}
        assert r.by_knowledge_source == {}
        assert r.unlinked_incident_count == 0
        assert r.high_relevance_count == 0
        assert r.recommendations == []
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_link
# -------------------------------------------------------------------


class TestRecordLink:
    def test_basic(self):
        eng = _engine()
        r = eng.record_link("INC-001", link_type=LinkType.RUNBOOK)
        assert r.incident_id == "INC-001"
        assert r.link_type == LinkType.RUNBOOK

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_link(
            "INC-002",
            knowledge_resource_id="RB-42",
            link_type=LinkType.POSTMORTEM,
            relevance=LinkRelevance.EXACT_MATCH,
            knowledge_source=KnowledgeSource.INCIDENT_HISTORY,
            relevance_score_pct=98.0,
            notes="Exact match from 2024 outage",
        )
        assert r.link_type == LinkType.POSTMORTEM
        assert r.relevance == LinkRelevance.EXACT_MATCH
        assert r.relevance_score_pct == 98.0
        assert r.notes == "Exact match from 2024 outage"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_link(f"INC-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_link
# -------------------------------------------------------------------


class TestGetLink:
    def test_found(self):
        eng = _engine()
        r = eng.record_link("INC-001")
        assert eng.get_link(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_link("nonexistent") is None


# -------------------------------------------------------------------
# list_links
# -------------------------------------------------------------------


class TestListLinks:
    def test_list_all(self):
        eng = _engine()
        eng.record_link("INC-001")
        eng.record_link("INC-002")
        assert len(eng.list_links()) == 2

    def test_filter_by_incident_id(self):
        eng = _engine()
        eng.record_link("INC-001")
        eng.record_link("INC-002")
        results = eng.list_links(incident_id="INC-001")
        assert len(results) == 1
        assert results[0].incident_id == "INC-001"

    def test_filter_by_link_type(self):
        eng = _engine()
        eng.record_link("INC-001", link_type=LinkType.RUNBOOK)
        eng.record_link("INC-002", link_type=LinkType.TRAINING)
        results = eng.list_links(link_type=LinkType.TRAINING)
        assert len(results) == 1
        assert results[0].incident_id == "INC-002"


# -------------------------------------------------------------------
# add_suggestion
# -------------------------------------------------------------------


class TestAddSuggestion:
    def test_basic(self):
        eng = _engine()
        s = eng.add_suggestion(
            "db-connection-timeout",
            suggested_resource_id="RB-DB-01",
            link_type=LinkType.RUNBOOK,
            knowledge_source=KnowledgeSource.RUNBOOK_LIBRARY,
            confidence_pct=90.0,
            auto_link=True,
        )
        assert s.incident_pattern == "db-connection-timeout"
        assert s.confidence_pct == 90.0
        assert s.auto_link is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_suggestion(f"pattern-{i}")
        assert len(eng._suggestions) == 2


# -------------------------------------------------------------------
# analyze_link_effectiveness
# -------------------------------------------------------------------


class TestAnalyzeLinkEffectiveness:
    def test_with_data(self):
        eng = _engine(min_relevance_pct=60.0)
        eng.record_link(
            "INC-001", relevance_score_pct=80.0, relevance=LinkRelevance.HIGHLY_RELEVANT
        )
        eng.record_link("INC-001", relevance_score_pct=70.0, relevance=LinkRelevance.EXACT_MATCH)
        result = eng.analyze_link_effectiveness("INC-001")
        assert result["link_count"] == 2
        assert result["avg_relevance_score_pct"] == 75.0
        assert result["high_relevance_count"] == 2
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_link_effectiveness("INC-UNKNOWN")
        assert result["status"] == "no_data"

    def test_below_threshold(self):
        eng = _engine(min_relevance_pct=60.0)
        eng.record_link("INC-001", relevance_score_pct=40.0)
        result = eng.analyze_link_effectiveness("INC-001")
        assert result["meets_threshold"] is False


# -------------------------------------------------------------------
# identify_unlinked_incidents
# -------------------------------------------------------------------


class TestIdentifyUnlinkedIncidents:
    def test_with_unlinked(self):
        eng = _engine(min_relevance_pct=60.0)
        eng.record_link("INC-001", relevance_score_pct=20.0)
        eng.record_link("INC-002", relevance_score_pct=90.0)
        eng.record_link("INC-002", relevance_score_pct=85.0)
        results = eng.identify_unlinked_incidents()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_unlinked_incidents() == []

    def test_high_score_single_link_not_returned(self):
        eng = _engine(min_relevance_pct=60.0)
        eng.record_link("INC-001", relevance_score_pct=80.0)
        assert eng.identify_unlinked_incidents() == []


# -------------------------------------------------------------------
# rank_by_relevance_score
# -------------------------------------------------------------------


class TestRankByRelevanceScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_link("INC-001", relevance_score_pct=30.0)
        eng.record_link("INC-002", relevance_score_pct=95.0)
        results = eng.rank_by_relevance_score()
        assert results[0]["incident_id"] == "INC-002"
        assert results[0]["relevance_score_pct"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_relevance_score() == []


# -------------------------------------------------------------------
# detect_knowledge_gaps
# -------------------------------------------------------------------


class TestDetectKnowledgeGaps:
    def test_with_gaps(self):
        eng = _engine(min_relevance_pct=60.0)
        eng.add_suggestion("db-timeout", confidence_pct=90.0)
        eng.add_suggestion("network-flap", confidence_pct=30.0)
        results = eng.detect_knowledge_gaps()
        assert len(results) == 1
        assert results[0]["incident_pattern"] == "network-flap"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_knowledge_gaps() == []

    def test_all_high_confidence_no_gaps(self):
        eng = _engine(min_relevance_pct=60.0)
        eng.add_suggestion("db-timeout", confidence_pct=80.0)
        assert eng.detect_knowledge_gaps() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_link(
            "INC-001",
            link_type=LinkType.RUNBOOK,
            relevance=LinkRelevance.EXACT_MATCH,
            relevance_score_pct=90.0,
        )
        eng.record_link("INC-002", link_type=LinkType.TRAINING, relevance_score_pct=50.0)
        eng.add_suggestion("pattern-a")
        report = eng.generate_report()
        assert report.total_links == 2
        assert report.total_suggestions == 1
        assert report.high_relevance_count == 1
        assert report.by_link_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_links == 0
        assert report.avg_relevance_score_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_link("INC-001")
        eng.add_suggestion("pattern-a")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._suggestions) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_links"] == 0
        assert stats["total_suggestions"] == 0
        assert stats["link_type_distribution"] == {}

    def test_populated(self):
        eng = _engine(min_relevance_pct=55.0)
        eng.record_link("INC-001", link_type=LinkType.RUNBOOK)
        eng.record_link("INC-002", link_type=LinkType.POSTMORTEM)
        eng.add_suggestion("pattern-a")
        stats = eng.get_stats()
        assert stats["total_links"] == 2
        assert stats["total_suggestions"] == 1
        assert stats["unique_incidents"] == 2
        assert stats["min_relevance_pct"] == 55.0
