"""Tests for shieldops.security.alert_enrichment_engine — AlertEnrichmentEngine."""

from __future__ import annotations

from shieldops.security.alert_enrichment_engine import (
    AlertEnrichmentEngine,
    EnrichmentAnalysis,
    EnrichmentQuality,
    EnrichmentRecord,
    EnrichmentReport,
    EnrichmentSource,
    EnrichmentType,
)


def _engine(**kw) -> AlertEnrichmentEngine:
    return AlertEnrichmentEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_source_asset_db(self):
        assert EnrichmentSource.ASSET_DB == "asset_db"

    def test_source_geo_ip(self):
        assert EnrichmentSource.GEO_IP == "geo_ip"

    def test_source_reputation(self):
        assert EnrichmentSource.REPUTATION == "reputation"

    def test_source_threat_intel(self):
        assert EnrichmentSource.THREAT_INTEL == "threat_intel"

    def test_source_whois(self):
        assert EnrichmentSource.WHOIS == "whois"

    def test_type_ip_context(self):
        assert EnrichmentType.IP_CONTEXT == "ip_context"

    def test_type_domain_context(self):
        assert EnrichmentType.DOMAIN_CONTEXT == "domain_context"

    def test_type_user_context(self):
        assert EnrichmentType.USER_CONTEXT == "user_context"

    def test_type_file_context(self):
        assert EnrichmentType.FILE_CONTEXT == "file_context"

    def test_type_network_context(self):
        assert EnrichmentType.NETWORK_CONTEXT == "network_context"

    def test_quality_excellent(self):
        assert EnrichmentQuality.EXCELLENT == "excellent"

    def test_quality_good(self):
        assert EnrichmentQuality.GOOD == "good"

    def test_quality_moderate(self):
        assert EnrichmentQuality.MODERATE == "moderate"

    def test_quality_poor(self):
        assert EnrichmentQuality.POOR == "poor"

    def test_quality_missing(self):
        assert EnrichmentQuality.MISSING == "missing"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_enrichment_record_defaults(self):
        r = EnrichmentRecord()
        assert r.id
        assert r.alert_id == ""
        assert r.enrichment_source == EnrichmentSource.ASSET_DB
        assert r.enrichment_type == EnrichmentType.IP_CONTEXT
        assert r.enrichment_quality == EnrichmentQuality.EXCELLENT
        assert r.enrichment_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_enrichment_analysis_defaults(self):
        c = EnrichmentAnalysis()
        assert c.id
        assert c.alert_id == ""
        assert c.enrichment_source == EnrichmentSource.ASSET_DB
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_enrichment_report_defaults(self):
        r = EnrichmentReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_quality_count == 0
        assert r.avg_enrichment_score == 0.0
        assert r.by_source == {}
        assert r.by_type == {}
        assert r.by_quality == {}
        assert r.top_low_quality == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_enrichment
# ---------------------------------------------------------------------------


class TestRecordEnrichment:
    def test_basic(self):
        eng = _engine()
        r = eng.record_enrichment(
            alert_id="ALERT-001",
            enrichment_source=EnrichmentSource.GEO_IP,
            enrichment_type=EnrichmentType.DOMAIN_CONTEXT,
            enrichment_quality=EnrichmentQuality.GOOD,
            enrichment_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.alert_id == "ALERT-001"
        assert r.enrichment_source == EnrichmentSource.GEO_IP
        assert r.enrichment_type == EnrichmentType.DOMAIN_CONTEXT
        assert r.enrichment_quality == EnrichmentQuality.GOOD
        assert r.enrichment_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_enrichment(alert_id=f"ALERT-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_enrichment
# ---------------------------------------------------------------------------


class TestGetEnrichment:
    def test_found(self):
        eng = _engine()
        r = eng.record_enrichment(
            alert_id="ALERT-001",
            enrichment_quality=EnrichmentQuality.POOR,
        )
        result = eng.get_enrichment(r.id)
        assert result is not None
        assert result.enrichment_quality == EnrichmentQuality.POOR

    def test_not_found(self):
        eng = _engine()
        assert eng.get_enrichment("nonexistent") is None


# ---------------------------------------------------------------------------
# list_enrichments
# ---------------------------------------------------------------------------


class TestListEnrichments:
    def test_list_all(self):
        eng = _engine()
        eng.record_enrichment(alert_id="ALERT-001")
        eng.record_enrichment(alert_id="ALERT-002")
        assert len(eng.list_enrichments()) == 2

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_enrichment(
            alert_id="ALERT-001",
            enrichment_source=EnrichmentSource.THREAT_INTEL,
        )
        eng.record_enrichment(
            alert_id="ALERT-002",
            enrichment_source=EnrichmentSource.GEO_IP,
        )
        results = eng.list_enrichments(enrichment_source=EnrichmentSource.THREAT_INTEL)
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_enrichment(
            alert_id="ALERT-001",
            enrichment_type=EnrichmentType.IP_CONTEXT,
        )
        eng.record_enrichment(
            alert_id="ALERT-002",
            enrichment_type=EnrichmentType.FILE_CONTEXT,
        )
        results = eng.list_enrichments(
            enrichment_type=EnrichmentType.IP_CONTEXT,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_enrichment(alert_id="ALERT-001", team="security")
        eng.record_enrichment(alert_id="ALERT-002", team="platform")
        results = eng.list_enrichments(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_enrichment(alert_id=f"ALERT-{i}")
        assert len(eng.list_enrichments(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        c = eng.add_analysis(
            alert_id="ALERT-001",
            enrichment_source=EnrichmentSource.WHOIS,
            analysis_score=88.5,
        )
        assert c.alert_id == "ALERT-001"
        assert c.enrichment_source == EnrichmentSource.WHOIS
        assert c.analysis_score == 88.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(alert_id=f"ALERT-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_enrichment_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_enrichment(
            alert_id="ALERT-001",
            enrichment_source=EnrichmentSource.THREAT_INTEL,
            enrichment_score=90.0,
        )
        eng.record_enrichment(
            alert_id="ALERT-002",
            enrichment_source=EnrichmentSource.THREAT_INTEL,
            enrichment_score=70.0,
        )
        result = eng.analyze_enrichment_distribution()
        assert "threat_intel" in result
        assert result["threat_intel"]["count"] == 2
        assert result["threat_intel"]["avg_enrichment_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_enrichment_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_quality_enrichments
# ---------------------------------------------------------------------------


class TestIdentifyLowQualityEnrichments:
    def test_detects_below_threshold(self):
        eng = _engine(enrichment_quality_threshold=80.0)
        eng.record_enrichment(alert_id="ALERT-001", enrichment_score=60.0)
        eng.record_enrichment(alert_id="ALERT-002", enrichment_score=90.0)
        results = eng.identify_low_quality_enrichments()
        assert len(results) == 1
        assert results[0]["alert_id"] == "ALERT-001"

    def test_sorted_ascending(self):
        eng = _engine(enrichment_quality_threshold=80.0)
        eng.record_enrichment(alert_id="ALERT-001", enrichment_score=50.0)
        eng.record_enrichment(alert_id="ALERT-002", enrichment_score=30.0)
        results = eng.identify_low_quality_enrichments()
        assert len(results) == 2
        assert results[0]["enrichment_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_quality_enrichments() == []


# ---------------------------------------------------------------------------
# rank_by_enrichment
# ---------------------------------------------------------------------------


class TestRankByEnrichment:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_enrichment(alert_id="ALERT-001", service="auth-svc", enrichment_score=90.0)
        eng.record_enrichment(alert_id="ALERT-002", service="api-gw", enrichment_score=50.0)
        results = eng.rank_by_enrichment()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_enrichment_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_enrichment() == []


# ---------------------------------------------------------------------------
# detect_enrichment_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(alert_id="ALERT-001", analysis_score=50.0)
        result = eng.detect_enrichment_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(alert_id="ALERT-001", analysis_score=20.0)
        eng.add_analysis(alert_id="ALERT-002", analysis_score=20.0)
        eng.add_analysis(alert_id="ALERT-003", analysis_score=80.0)
        eng.add_analysis(alert_id="ALERT-004", analysis_score=80.0)
        result = eng.detect_enrichment_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_enrichment_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(enrichment_quality_threshold=80.0)
        eng.record_enrichment(
            alert_id="ALERT-001",
            enrichment_source=EnrichmentSource.GEO_IP,
            enrichment_type=EnrichmentType.IP_CONTEXT,
            enrichment_quality=EnrichmentQuality.POOR,
            enrichment_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, EnrichmentReport)
        assert report.total_records == 1
        assert report.low_quality_count == 1
        assert len(report.top_low_quality) == 1
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
        eng.record_enrichment(alert_id="ALERT-001")
        eng.add_analysis(alert_id="ALERT-001")
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
        eng.record_enrichment(
            alert_id="ALERT-001",
            enrichment_source=EnrichmentSource.THREAT_INTEL,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "threat_intel" in stats["source_distribution"]
