"""Tests for shieldops.security.threat_landscape_intelligence — ThreatLandscapeIntelligence."""

from __future__ import annotations

from shieldops.security.threat_landscape_intelligence import (
    IntelSource,
    LandscapeAnalysis,
    LandscapeArea,
    LandscapeRecord,
    ThreatLandscapeIntelligence,
    ThreatLandscapeReport,
    ThreatRelevance,
)


def _engine(**kw) -> ThreatLandscapeIntelligence:
    return ThreatLandscapeIntelligence(**kw)


class TestEnums:
    def test_landscape_area_ransomware(self):
        assert LandscapeArea.RANSOMWARE == "ransomware"

    def test_landscape_area_apt(self):
        assert LandscapeArea.APT == "apt"

    def test_landscape_area_supply_chain(self):
        assert LandscapeArea.SUPPLY_CHAIN == "supply_chain"

    def test_landscape_area_insider(self):
        assert LandscapeArea.INSIDER == "insider"

    def test_landscape_area_cloud_native(self):
        assert LandscapeArea.CLOUD_NATIVE == "cloud_native"

    def test_intel_source_threat_feeds(self):
        assert IntelSource.THREAT_FEEDS == "threat_feeds"

    def test_intel_source_osint(self):
        assert IntelSource.OSINT == "osint"

    def test_intel_source_commercial(self):
        assert IntelSource.COMMERCIAL == "commercial"

    def test_intel_source_government(self):
        assert IntelSource.GOVERNMENT == "government"

    def test_intel_source_peer_sharing(self):
        assert IntelSource.PEER_SHARING == "peer_sharing"

    def test_threat_relevance_critical(self):
        assert ThreatRelevance.CRITICAL == "critical"

    def test_threat_relevance_high(self):
        assert ThreatRelevance.HIGH == "high"

    def test_threat_relevance_moderate(self):
        assert ThreatRelevance.MODERATE == "moderate"

    def test_threat_relevance_low(self):
        assert ThreatRelevance.LOW == "low"

    def test_threat_relevance_irrelevant(self):
        assert ThreatRelevance.IRRELEVANT == "irrelevant"


class TestModels:
    def test_record_defaults(self):
        r = LandscapeRecord()
        assert r.id
        assert r.name == ""
        assert r.landscape_area == LandscapeArea.RANSOMWARE
        assert r.intel_source == IntelSource.THREAT_FEEDS
        assert r.threat_relevance == ThreatRelevance.IRRELEVANT
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = LandscapeAnalysis()
        assert a.id
        assert a.name == ""
        assert a.landscape_area == LandscapeArea.RANSOMWARE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ThreatLandscapeReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_landscape_area == {}
        assert r.by_intel_source == {}
        assert r.by_threat_relevance == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            landscape_area=LandscapeArea.RANSOMWARE,
            intel_source=IntelSource.OSINT,
            threat_relevance=ThreatRelevance.CRITICAL,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.landscape_area == LandscapeArea.RANSOMWARE
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_landscape_area(self):
        eng = _engine()
        eng.record_entry(name="a", landscape_area=LandscapeArea.RANSOMWARE)
        eng.record_entry(name="b", landscape_area=LandscapeArea.APT)
        assert len(eng.list_records(landscape_area=LandscapeArea.RANSOMWARE)) == 1

    def test_filter_by_intel_source(self):
        eng = _engine()
        eng.record_entry(name="a", intel_source=IntelSource.THREAT_FEEDS)
        eng.record_entry(name="b", intel_source=IntelSource.OSINT)
        assert len(eng.list_records(intel_source=IntelSource.THREAT_FEEDS)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
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
        eng.record_entry(name="a", landscape_area=LandscapeArea.APT, score=90.0)
        eng.record_entry(name="b", landscape_area=LandscapeArea.APT, score=70.0)
        result = eng.analyze_distribution()
        assert "apt" in result
        assert result["apt"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
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
        eng.record_entry(name="test", score=50.0)
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
        eng.record_entry(name="test")
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
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
