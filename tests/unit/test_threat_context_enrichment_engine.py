"""Tests for shieldops.security.threat_context_enrichment_engine — ThreatContextEnrichmentEngine."""

from __future__ import annotations

from shieldops.security.threat_context_enrichment_engine import (
    ContextType,
    EnrichmentSource,
    RelevanceScore,
    ThreatContextEnrichmentEngine,
    ThreatContextEnrichmentEngineAnalysis,
    ThreatContextEnrichmentEngineRecord,
    ThreatContextEnrichmentEngineReport,
)


def _engine(**kw) -> ThreatContextEnrichmentEngine:
    return ThreatContextEnrichmentEngine(**kw)


class TestEnums:
    def test_context_type_first(self):
        assert ContextType.GEOPOLITICAL == "geopolitical"

    def test_context_type_second(self):
        assert ContextType.INDUSTRY == "industry"

    def test_context_type_third(self):
        assert ContextType.TECHNICAL == "technical"

    def test_context_type_fourth(self):
        assert ContextType.ORGANIZATIONAL == "organizational"

    def test_context_type_fifth(self):
        assert ContextType.TEMPORAL == "temporal"

    def test_enrichment_source_first(self):
        assert EnrichmentSource.THREAT_INTEL == "threat_intel"

    def test_enrichment_source_second(self):
        assert EnrichmentSource.ASSET_INVENTORY == "asset_inventory"

    def test_enrichment_source_third(self):
        assert EnrichmentSource.VULN_SCAN == "vuln_scan"

    def test_enrichment_source_fourth(self):
        assert EnrichmentSource.NETWORK_MAP == "network_map"

    def test_enrichment_source_fifth(self):
        assert EnrichmentSource.IDENTITY == "identity"

    def test_relevance_score_first(self):
        assert RelevanceScore.HIGHLY_RELEVANT == "highly_relevant"

    def test_relevance_score_second(self):
        assert RelevanceScore.RELEVANT == "relevant"

    def test_relevance_score_third(self):
        assert RelevanceScore.SOMEWHAT_RELEVANT == "somewhat_relevant"

    def test_relevance_score_fourth(self):
        assert RelevanceScore.LOW_RELEVANCE == "low_relevance"

    def test_relevance_score_fifth(self):
        assert RelevanceScore.IRRELEVANT == "irrelevant"


class TestModels:
    def test_record_defaults(self):
        r = ThreatContextEnrichmentEngineRecord()
        assert r.id
        assert r.name == ""
        assert r.context_type == ContextType.GEOPOLITICAL
        assert r.enrichment_source == EnrichmentSource.THREAT_INTEL
        assert r.relevance_score == RelevanceScore.HIGHLY_RELEVANT
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ThreatContextEnrichmentEngineAnalysis()
        assert a.id
        assert a.name == ""
        assert a.context_type == ContextType.GEOPOLITICAL
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ThreatContextEnrichmentEngineReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_context_type == {}
        assert r.by_enrichment_source == {}
        assert r.by_relevance_score == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            context_type=ContextType.GEOPOLITICAL,
            enrichment_source=EnrichmentSource.ASSET_INVENTORY,
            relevance_score=RelevanceScore.SOMEWHAT_RELEVANT,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.context_type == ContextType.GEOPOLITICAL
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.record_item(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_context_type(self):
        eng = _engine()
        eng.record_item(name="a", context_type=ContextType.INDUSTRY)
        eng.record_item(name="b", context_type=ContextType.GEOPOLITICAL)
        assert len(eng.list_records(context_type=ContextType.INDUSTRY)) == 1

    def test_filter_by_enrichment_source(self):
        eng = _engine()
        eng.record_item(name="a", enrichment_source=EnrichmentSource.THREAT_INTEL)
        eng.record_item(name="b", enrichment_source=EnrichmentSource.ASSET_INVENTORY)
        assert len(eng.list_records(enrichment_source=EnrichmentSource.THREAT_INTEL)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_item(name="a", team="sec")
        eng.record_item(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_item(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="test analysis",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(name="a", context_type=ContextType.INDUSTRY, score=90.0)
        eng.record_item(name="b", context_type=ContextType.INDUSTRY, score=70.0)
        result = eng.analyze_distribution()
        assert "industry" in result
        assert result["industry"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=60.0)
        eng.record_item(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=50.0)
        eng.record_item(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_item(name="a", service="auth", score=90.0)
        eng.record_item(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_item(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
