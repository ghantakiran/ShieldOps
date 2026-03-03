"""Tests for shieldops.security.threat_feed_normalizer — ThreatFeedNormalizer."""

from __future__ import annotations

from shieldops.security.threat_feed_normalizer import (
    FeedAnalysis,
    FeedFormat,
    FeedNormalizationReport,
    FeedRecord,
    FeedSource,
    NormalizationStatus,
    ThreatFeedNormalizer,
)


def _engine(**kw) -> ThreatFeedNormalizer:
    return ThreatFeedNormalizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_feedsource_val1(self):
        assert FeedSource.OPEN_SOURCE == "open_source"

    def test_feedsource_val2(self):
        assert FeedSource.COMMERCIAL == "commercial"

    def test_feedsource_val3(self):
        assert FeedSource.GOVERNMENT == "government"

    def test_feedsource_val4(self):
        assert FeedSource.ISAC == "isac"

    def test_feedsource_val5(self):
        assert FeedSource.INTERNAL == "internal"

    def test_feedformat_val1(self):
        assert FeedFormat.STIX == "stix"

    def test_feedformat_val2(self):
        assert FeedFormat.TAXII == "taxii"

    def test_feedformat_val3(self):
        assert FeedFormat.CSV == "csv"

    def test_feedformat_val4(self):
        assert FeedFormat.JSON == "json"

    def test_feedformat_val5(self):
        assert FeedFormat.CUSTOM == "custom"

    def test_normalizationstatus_val1(self):
        assert NormalizationStatus.RAW == "raw"

    def test_normalizationstatus_val2(self):
        assert NormalizationStatus.NORMALIZED == "normalized"

    def test_normalizationstatus_val3(self):
        assert NormalizationStatus.ENRICHED == "enriched"

    def test_normalizationstatus_val4(self):
        assert NormalizationStatus.VALIDATED == "validated"

    def test_normalizationstatus_val5(self):
        assert NormalizationStatus.EXPIRED == "expired"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = FeedRecord()
        assert r.id
        assert r.feed_name == ""
        assert r.feed_source == FeedSource.OPEN_SOURCE
        assert r.indicator_count == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = FeedAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = FeedNormalizationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_indicator_count == 0.0
        assert r.by_source == {}
        assert r.by_format == {}
        assert r.by_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_feed(
            feed_name="test",
            feed_source=FeedSource.COMMERCIAL,
            indicator_count=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.feed_name == "test"
        assert r.feed_source == FeedSource.COMMERCIAL
        assert r.indicator_count == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_feed(feed_name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_feed(feed_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# ---------------------------------------------------------------------------
# list_records
# ---------------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_feed(feed_name="a")
        eng.record_feed(feed_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_feed(feed_name="a", feed_source=FeedSource.OPEN_SOURCE)
        eng.record_feed(feed_name="b", feed_source=FeedSource.COMMERCIAL)
        results = eng.list_records(feed_source=FeedSource.OPEN_SOURCE)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_feed(feed_name="a", feed_format=FeedFormat.STIX)
        eng.record_feed(feed_name="b", feed_format=FeedFormat.TAXII)
        results = eng.list_records(feed_format=FeedFormat.STIX)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_feed(feed_name="a", team="sec")
        eng.record_feed(feed_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_feed(feed_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            feed_name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(feed_name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_feed(
            feed_name="a",
            feed_source=FeedSource.OPEN_SOURCE,
            indicator_count=90.0,
        )
        eng.record_feed(
            feed_name="b",
            feed_source=FeedSource.OPEN_SOURCE,
            indicator_count=70.0,
        )
        result = eng.analyze_source_distribution()
        assert "open_source" in result
        assert result["open_source"]["count"] == 2
        assert result["open_source"]["avg_indicator_count"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_source_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_feed(feed_name="a", indicator_count=60.0)
        eng.record_feed(feed_name="b", indicator_count=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["feed_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_feed(feed_name="a", indicator_count=50.0)
        eng.record_feed(feed_name="b", indicator_count=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["indicator_count"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_feed(feed_name="a", service="auth-svc", indicator_count=90.0)
        eng.record_feed(feed_name="b", service="api-gw", indicator_count=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_indicator_count"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(feed_name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(feed_name="t1", analysis_score=20.0)
        eng.add_analysis(feed_name="t2", analysis_score=20.0)
        eng.add_analysis(feed_name="t3", analysis_score=80.0)
        eng.add_analysis(feed_name="t4", analysis_score=80.0)
        result = eng.detect_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_feed(
            feed_name="test",
            feed_source=FeedSource.COMMERCIAL,
            indicator_count=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, FeedNormalizationReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
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
        eng.record_feed(feed_name="test")
        eng.add_analysis(feed_name="test")
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
        assert stats["source_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_feed(
            feed_name="test",
            feed_source=FeedSource.OPEN_SOURCE,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "open_source" in stats["source_distribution"]
