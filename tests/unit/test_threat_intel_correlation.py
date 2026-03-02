"""Tests for shieldops.security.threat_intel_correlation — ThreatIntelCorrelation."""

from __future__ import annotations

from shieldops.security.threat_intel_correlation import (
    CorrelationAnalysis,
    CorrelationRecord,
    CorrelationType,
    IntelFeed,
    ThreatCategory,
    ThreatIntelCorrelation,
    ThreatIntelReport,
)


def _engine(**kw) -> ThreatIntelCorrelation:
    return ThreatIntelCorrelation(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_feed_open_source(self):
        assert IntelFeed.OPEN_SOURCE == "open_source"

    def test_feed_commercial(self):
        assert IntelFeed.COMMERCIAL == "commercial"

    def test_feed_government(self):
        assert IntelFeed.GOVERNMENT == "government"

    def test_feed_isac(self):
        assert IntelFeed.ISAC == "isac"

    def test_feed_internal(self):
        assert IntelFeed.INTERNAL == "internal"

    def test_type_ioc_match(self):
        assert CorrelationType.IOC_MATCH == "ioc_match"

    def test_type_ttp_overlap(self):
        assert CorrelationType.TTP_OVERLAP == "ttp_overlap"

    def test_type_campaign_link(self):
        assert CorrelationType.CAMPAIGN_LINK == "campaign_link"

    def test_type_infrastructure_overlap(self):
        assert CorrelationType.INFRASTRUCTURE_OVERLAP == "infrastructure_overlap"

    def test_type_behavioral_match(self):
        assert CorrelationType.BEHAVIORAL_MATCH == "behavioral_match"

    def test_category_nation_state(self):
        assert ThreatCategory.NATION_STATE == "nation_state"

    def test_category_cybercrime(self):
        assert ThreatCategory.CYBERCRIME == "cybercrime"

    def test_category_hacktivism(self):
        assert ThreatCategory.HACKTIVISM == "hacktivism"

    def test_category_insider(self):
        assert ThreatCategory.INSIDER == "insider"

    def test_category_unknown(self):
        assert ThreatCategory.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_correlation_record_defaults(self):
        r = CorrelationRecord()
        assert r.id
        assert r.correlation_name == ""
        assert r.intel_feed == IntelFeed.OPEN_SOURCE
        assert r.correlation_type == CorrelationType.IOC_MATCH
        assert r.threat_category == ThreatCategory.NATION_STATE
        assert r.correlation_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_correlation_analysis_defaults(self):
        c = CorrelationAnalysis()
        assert c.id
        assert c.correlation_name == ""
        assert c.intel_feed == IntelFeed.OPEN_SOURCE
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_threat_intel_report_defaults(self):
        r = ThreatIntelReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_confidence_count == 0
        assert r.avg_correlation_score == 0.0
        assert r.by_feed == {}
        assert r.by_type == {}
        assert r.by_category == {}
        assert r.top_low_confidence == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_correlation
# ---------------------------------------------------------------------------


class TestRecordCorrelation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_correlation(
            correlation_name="apt-match-001",
            intel_feed=IntelFeed.COMMERCIAL,
            correlation_type=CorrelationType.TTP_OVERLAP,
            threat_category=ThreatCategory.CYBERCRIME,
            correlation_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.correlation_name == "apt-match-001"
        assert r.intel_feed == IntelFeed.COMMERCIAL
        assert r.correlation_type == CorrelationType.TTP_OVERLAP
        assert r.threat_category == ThreatCategory.CYBERCRIME
        assert r.correlation_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_correlation(correlation_name=f"C-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_correlation
# ---------------------------------------------------------------------------


class TestGetCorrelation:
    def test_found(self):
        eng = _engine()
        r = eng.record_correlation(
            correlation_name="apt-match-001",
            threat_category=ThreatCategory.NATION_STATE,
        )
        result = eng.get_correlation(r.id)
        assert result is not None
        assert result.threat_category == ThreatCategory.NATION_STATE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_correlation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_correlations
# ---------------------------------------------------------------------------


class TestListCorrelations:
    def test_list_all(self):
        eng = _engine()
        eng.record_correlation(correlation_name="C-001")
        eng.record_correlation(correlation_name="C-002")
        assert len(eng.list_correlations()) == 2

    def test_filter_by_intel_feed(self):
        eng = _engine()
        eng.record_correlation(
            correlation_name="C-001",
            intel_feed=IntelFeed.OPEN_SOURCE,
        )
        eng.record_correlation(
            correlation_name="C-002",
            intel_feed=IntelFeed.COMMERCIAL,
        )
        results = eng.list_correlations(intel_feed=IntelFeed.OPEN_SOURCE)
        assert len(results) == 1

    def test_filter_by_correlation_type(self):
        eng = _engine()
        eng.record_correlation(
            correlation_name="C-001",
            correlation_type=CorrelationType.IOC_MATCH,
        )
        eng.record_correlation(
            correlation_name="C-002",
            correlation_type=CorrelationType.TTP_OVERLAP,
        )
        results = eng.list_correlations(
            correlation_type=CorrelationType.IOC_MATCH,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_correlation(correlation_name="C-001", team="security")
        eng.record_correlation(correlation_name="C-002", team="platform")
        results = eng.list_correlations(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_correlation(correlation_name=f"C-{i}")
        assert len(eng.list_correlations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            correlation_name="apt-match-001",
            intel_feed=IntelFeed.COMMERCIAL,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="low confidence correlation",
        )
        assert a.correlation_name == "apt-match-001"
        assert a.intel_feed == IntelFeed.COMMERCIAL
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(correlation_name=f"C-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_feed_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_correlation(
            correlation_name="C-001",
            intel_feed=IntelFeed.OPEN_SOURCE,
            correlation_score=90.0,
        )
        eng.record_correlation(
            correlation_name="C-002",
            intel_feed=IntelFeed.OPEN_SOURCE,
            correlation_score=70.0,
        )
        result = eng.analyze_feed_distribution()
        assert "open_source" in result
        assert result["open_source"]["count"] == 2
        assert result["open_source"]["avg_correlation_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_feed_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_confidence_correlations
# ---------------------------------------------------------------------------


class TestIdentifyLowConfidenceCorrelations:
    def test_detects_below_threshold(self):
        eng = _engine(correlation_confidence_threshold=80.0)
        eng.record_correlation(correlation_name="C-001", correlation_score=60.0)
        eng.record_correlation(correlation_name="C-002", correlation_score=90.0)
        results = eng.identify_low_confidence_correlations()
        assert len(results) == 1
        assert results[0]["correlation_name"] == "C-001"

    def test_sorted_ascending(self):
        eng = _engine(correlation_confidence_threshold=80.0)
        eng.record_correlation(correlation_name="C-001", correlation_score=50.0)
        eng.record_correlation(correlation_name="C-002", correlation_score=30.0)
        results = eng.identify_low_confidence_correlations()
        assert len(results) == 2
        assert results[0]["correlation_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_confidence_correlations() == []


# ---------------------------------------------------------------------------
# rank_by_correlation_score
# ---------------------------------------------------------------------------


class TestRankByCorrelationScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_correlation(correlation_name="C-001", service="auth-svc", correlation_score=90.0)
        eng.record_correlation(correlation_name="C-002", service="api-gw", correlation_score=50.0)
        results = eng.rank_by_correlation_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_correlation_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_correlation_score() == []


# ---------------------------------------------------------------------------
# detect_correlation_trends
# ---------------------------------------------------------------------------


class TestDetectCorrelationTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(correlation_name="C-001", analysis_score=50.0)
        result = eng.detect_correlation_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(correlation_name="C-001", analysis_score=20.0)
        eng.add_analysis(correlation_name="C-002", analysis_score=20.0)
        eng.add_analysis(correlation_name="C-003", analysis_score=80.0)
        eng.add_analysis(correlation_name="C-004", analysis_score=80.0)
        result = eng.detect_correlation_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_correlation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(correlation_confidence_threshold=80.0)
        eng.record_correlation(
            correlation_name="apt-match-001",
            intel_feed=IntelFeed.COMMERCIAL,
            correlation_type=CorrelationType.TTP_OVERLAP,
            threat_category=ThreatCategory.CYBERCRIME,
            correlation_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ThreatIntelReport)
        assert report.total_records == 1
        assert report.low_confidence_count == 1
        assert len(report.top_low_confidence) == 1
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
        eng.record_correlation(correlation_name="C-001")
        eng.add_analysis(correlation_name="C-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["feed_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_correlation(
            correlation_name="C-001",
            intel_feed=IntelFeed.OPEN_SOURCE,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "open_source" in stats["feed_distribution"]
