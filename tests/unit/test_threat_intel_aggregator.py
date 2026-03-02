"""Tests for shieldops.security.threat_intel_aggregator — ThreatIntelAggregator."""

from __future__ import annotations

from shieldops.security.threat_intel_aggregator import (
    FeedSource,
    IOCCorrelation,
    IOCRecord,
    IOCType,
    ThreatIntelAggregator,
    ThreatIntelReport,
    ThreatLevel,
)


def _engine(**kw) -> ThreatIntelAggregator:
    return ThreatIntelAggregator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_ioc_type_ip_address(self):
        assert IOCType.IP_ADDRESS == "ip_address"

    def test_ioc_type_domain(self):
        assert IOCType.DOMAIN == "domain"

    def test_ioc_type_file_hash(self):
        assert IOCType.FILE_HASH == "file_hash"

    def test_ioc_type_url(self):
        assert IOCType.URL == "url"

    def test_ioc_type_email(self):
        assert IOCType.EMAIL == "email"

    def test_feed_source_stix_taxii(self):
        assert FeedSource.STIX_TAXII == "stix_taxii"

    def test_feed_source_osint(self):
        assert FeedSource.OSINT == "osint"

    def test_feed_source_commercial(self):
        assert FeedSource.COMMERCIAL == "commercial"

    def test_feed_source_internal(self):
        assert FeedSource.INTERNAL == "internal"

    def test_feed_source_government(self):
        assert FeedSource.GOVERNMENT == "government"

    def test_threat_level_critical(self):
        assert ThreatLevel.CRITICAL == "critical"

    def test_threat_level_high(self):
        assert ThreatLevel.HIGH == "high"

    def test_threat_level_medium(self):
        assert ThreatLevel.MEDIUM == "medium"

    def test_threat_level_low(self):
        assert ThreatLevel.LOW == "low"

    def test_threat_level_informational(self):
        assert ThreatLevel.INFORMATIONAL == "informational"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_ioc_record_defaults(self):
        r = IOCRecord()
        assert r.id
        assert r.indicator_value == ""
        assert r.ioc_type == IOCType.IP_ADDRESS
        assert r.feed_source == FeedSource.STIX_TAXII
        assert r.threat_level == ThreatLevel.CRITICAL
        assert r.confidence_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_ioc_correlation_defaults(self):
        c = IOCCorrelation()
        assert c.id
        assert c.indicator_value == ""
        assert c.ioc_type == IOCType.IP_ADDRESS
        assert c.correlation_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_threat_intel_report_defaults(self):
        r = ThreatIntelReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_correlations == 0
        assert r.low_confidence_count == 0
        assert r.avg_confidence_score == 0.0
        assert r.by_type == {}
        assert r.by_source == {}
        assert r.by_threat == {}
        assert r.top_low_confidence == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_ioc
# ---------------------------------------------------------------------------


class TestRecordIoc:
    def test_basic(self):
        eng = _engine()
        r = eng.record_ioc(
            indicator_value="192.168.1.100",
            ioc_type=IOCType.DOMAIN,
            feed_source=FeedSource.OSINT,
            threat_level=ThreatLevel.HIGH,
            confidence_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.indicator_value == "192.168.1.100"
        assert r.ioc_type == IOCType.DOMAIN
        assert r.feed_source == FeedSource.OSINT
        assert r.threat_level == ThreatLevel.HIGH
        assert r.confidence_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_ioc(indicator_value=f"IOC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_ioc
# ---------------------------------------------------------------------------


class TestGetIoc:
    def test_found(self):
        eng = _engine()
        r = eng.record_ioc(
            indicator_value="192.168.1.100",
            threat_level=ThreatLevel.CRITICAL,
        )
        result = eng.get_ioc(r.id)
        assert result is not None
        assert result.threat_level == ThreatLevel.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_ioc("nonexistent") is None


# ---------------------------------------------------------------------------
# list_iocs
# ---------------------------------------------------------------------------


class TestListIocs:
    def test_list_all(self):
        eng = _engine()
        eng.record_ioc(indicator_value="IOC-001")
        eng.record_ioc(indicator_value="IOC-002")
        assert len(eng.list_iocs()) == 2

    def test_filter_by_ioc_type(self):
        eng = _engine()
        eng.record_ioc(
            indicator_value="IOC-001",
            ioc_type=IOCType.IP_ADDRESS,
        )
        eng.record_ioc(
            indicator_value="IOC-002",
            ioc_type=IOCType.DOMAIN,
        )
        results = eng.list_iocs(ioc_type=IOCType.IP_ADDRESS)
        assert len(results) == 1

    def test_filter_by_feed_source(self):
        eng = _engine()
        eng.record_ioc(
            indicator_value="IOC-001",
            feed_source=FeedSource.STIX_TAXII,
        )
        eng.record_ioc(
            indicator_value="IOC-002",
            feed_source=FeedSource.OSINT,
        )
        results = eng.list_iocs(
            feed_source=FeedSource.STIX_TAXII,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_ioc(indicator_value="IOC-001", team="security")
        eng.record_ioc(indicator_value="IOC-002", team="platform")
        results = eng.list_iocs(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_ioc(indicator_value=f"IOC-{i}")
        assert len(eng.list_iocs(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_correlation
# ---------------------------------------------------------------------------


class TestAddCorrelation:
    def test_basic(self):
        eng = _engine()
        c = eng.add_correlation(
            indicator_value="192.168.1.100",
            ioc_type=IOCType.DOMAIN,
            correlation_score=88.5,
            threshold=80.0,
            breached=True,
            description="correlated with known C2",
        )
        assert c.indicator_value == "192.168.1.100"
        assert c.ioc_type == IOCType.DOMAIN
        assert c.correlation_score == 88.5
        assert c.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_correlation(indicator_value=f"IOC-{i}")
        assert len(eng._correlations) == 2


# ---------------------------------------------------------------------------
# analyze_ioc_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeIocDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_ioc(
            indicator_value="IOC-001",
            ioc_type=IOCType.IP_ADDRESS,
            confidence_score=90.0,
        )
        eng.record_ioc(
            indicator_value="IOC-002",
            ioc_type=IOCType.IP_ADDRESS,
            confidence_score=70.0,
        )
        result = eng.analyze_ioc_distribution()
        assert "ip_address" in result
        assert result["ip_address"]["count"] == 2
        assert result["ip_address"]["avg_confidence_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_ioc_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_confidence_iocs
# ---------------------------------------------------------------------------


class TestIdentifyLowConfidenceIocs:
    def test_detects_below_threshold(self):
        eng = _engine(ioc_confidence_threshold=80.0)
        eng.record_ioc(indicator_value="IOC-001", confidence_score=60.0)
        eng.record_ioc(indicator_value="IOC-002", confidence_score=90.0)
        results = eng.identify_low_confidence_iocs()
        assert len(results) == 1
        assert results[0]["indicator_value"] == "IOC-001"

    def test_sorted_ascending(self):
        eng = _engine(ioc_confidence_threshold=80.0)
        eng.record_ioc(indicator_value="IOC-001", confidence_score=50.0)
        eng.record_ioc(indicator_value="IOC-002", confidence_score=30.0)
        results = eng.identify_low_confidence_iocs()
        assert len(results) == 2
        assert results[0]["confidence_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_confidence_iocs() == []


# ---------------------------------------------------------------------------
# rank_by_confidence
# ---------------------------------------------------------------------------


class TestRankByConfidence:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_ioc(indicator_value="IOC-001", service="auth-svc", confidence_score=90.0)
        eng.record_ioc(indicator_value="IOC-002", service="api-gw", confidence_score=50.0)
        results = eng.rank_by_confidence()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_confidence_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_confidence() == []


# ---------------------------------------------------------------------------
# detect_intel_trends
# ---------------------------------------------------------------------------


class TestDetectIntelTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_correlation(indicator_value="IOC-001", correlation_score=50.0)
        result = eng.detect_intel_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_correlation(indicator_value="IOC-001", correlation_score=20.0)
        eng.add_correlation(indicator_value="IOC-002", correlation_score=20.0)
        eng.add_correlation(indicator_value="IOC-003", correlation_score=80.0)
        eng.add_correlation(indicator_value="IOC-004", correlation_score=80.0)
        result = eng.detect_intel_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_intel_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(ioc_confidence_threshold=80.0)
        eng.record_ioc(
            indicator_value="192.168.1.100",
            ioc_type=IOCType.DOMAIN,
            feed_source=FeedSource.OSINT,
            threat_level=ThreatLevel.HIGH,
            confidence_score=50.0,
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
        eng.record_ioc(indicator_value="IOC-001")
        eng.add_correlation(indicator_value="IOC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._correlations) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_correlations"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_ioc(
            indicator_value="IOC-001",
            ioc_type=IOCType.IP_ADDRESS,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "ip_address" in stats["type_distribution"]
