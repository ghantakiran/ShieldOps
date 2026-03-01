"""Tests for shieldops.security.threat_correlator — ThreatIntelligenceCorrelator."""

from __future__ import annotations

from shieldops.security.threat_correlator import (
    ThreatCorrelation,
    ThreatCorrelatorReport,
    ThreatIntelligenceCorrelator,
    ThreatRecord,
    ThreatRelevance,
    ThreatSeverity,
    ThreatSource,
)


def _engine(**kw) -> ThreatIntelligenceCorrelator:
    return ThreatIntelligenceCorrelator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ThreatSource (5)
    def test_source_external_feed(self):
        assert ThreatSource.EXTERNAL_FEED == "external_feed"

    def test_source_internal_detection(self):
        assert ThreatSource.INTERNAL_DETECTION == "internal_detection"

    def test_source_vendor_advisory(self):
        assert ThreatSource.VENDOR_ADVISORY == "vendor_advisory"

    def test_source_community(self):
        assert ThreatSource.COMMUNITY == "community"

    def test_source_government(self):
        assert ThreatSource.GOVERNMENT == "government"

    # ThreatSeverity (5)
    def test_severity_critical(self):
        assert ThreatSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert ThreatSeverity.HIGH == "high"

    def test_severity_moderate(self):
        assert ThreatSeverity.MODERATE == "moderate"

    def test_severity_low(self):
        assert ThreatSeverity.LOW == "low"

    def test_severity_informational(self):
        assert ThreatSeverity.INFORMATIONAL == "informational"

    # ThreatRelevance (5)
    def test_relevance_direct_match(self):
        assert ThreatRelevance.DIRECT_MATCH == "direct_match"

    def test_relevance_related(self):
        assert ThreatRelevance.RELATED == "related"

    def test_relevance_potential(self):
        assert ThreatRelevance.POTENTIAL == "potential"

    def test_relevance_unlikely(self):
        assert ThreatRelevance.UNLIKELY == "unlikely"

    def test_relevance_not_applicable(self):
        assert ThreatRelevance.NOT_APPLICABLE == "not_applicable"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_threat_record_defaults(self):
        r = ThreatRecord()
        assert r.id
        assert r.threat_id == ""
        assert r.source == ThreatSource.EXTERNAL_FEED
        assert r.severity == ThreatSeverity.LOW
        assert r.relevance == ThreatRelevance.POTENTIAL
        assert r.relevance_score == 0.0
        assert r.affected_service == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_threat_correlation_defaults(self):
        c = ThreatCorrelation()
        assert c.id
        assert c.threat_record_id == ""
        assert c.correlated_threat_id == ""
        assert c.correlation_score == 0.0
        assert c.correlation_type == ""
        assert c.created_at > 0

    def test_report_defaults(self):
        r = ThreatCorrelatorReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_correlations == 0
        assert r.critical_threats == 0
        assert r.avg_relevance_score == 0.0
        assert r.by_source == {}
        assert r.by_severity == {}
        assert r.by_relevance == {}
        assert r.high_risk_services == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_threat
# -------------------------------------------------------------------


class TestRecordThreat:
    def test_basic(self):
        eng = _engine()
        r = eng.record_threat(
            "CVE-2024-1234",
            source=ThreatSource.VENDOR_ADVISORY,
            severity=ThreatSeverity.CRITICAL,
            relevance_score=90.0,
            affected_service="auth-svc",
        )
        assert r.threat_id == "CVE-2024-1234"
        assert r.source == ThreatSource.VENDOR_ADVISORY
        assert r.severity == ThreatSeverity.CRITICAL
        assert r.relevance_score == 90.0
        assert r.affected_service == "auth-svc"

    def test_relevance_stored(self):
        eng = _engine()
        r = eng.record_threat("T-001", relevance=ThreatRelevance.DIRECT_MATCH)
        assert r.relevance == ThreatRelevance.DIRECT_MATCH

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_threat(f"T-{i:03d}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_threat
# -------------------------------------------------------------------


class TestGetThreat:
    def test_found(self):
        eng = _engine()
        r = eng.record_threat("T-001")
        assert eng.get_threat(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_threat("nonexistent") is None


# -------------------------------------------------------------------
# list_threats
# -------------------------------------------------------------------


class TestListThreats:
    def test_list_all(self):
        eng = _engine()
        eng.record_threat("T-001")
        eng.record_threat("T-002")
        assert len(eng.list_threats()) == 2

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_threat("T-001", source=ThreatSource.GOVERNMENT)
        eng.record_threat("T-002", source=ThreatSource.COMMUNITY)
        results = eng.list_threats(source=ThreatSource.GOVERNMENT)
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_threat("T-001", severity=ThreatSeverity.CRITICAL)
        eng.record_threat("T-002", severity=ThreatSeverity.LOW)
        results = eng.list_threats(severity=ThreatSeverity.CRITICAL)
        assert len(results) == 1

    def test_filter_by_relevance(self):
        eng = _engine()
        eng.record_threat("T-001", relevance=ThreatRelevance.DIRECT_MATCH)
        eng.record_threat("T-002", relevance=ThreatRelevance.UNLIKELY)
        results = eng.list_threats(relevance=ThreatRelevance.DIRECT_MATCH)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_correlation
# -------------------------------------------------------------------


class TestAddCorrelation:
    def test_basic(self):
        eng = _engine()
        c = eng.add_correlation(
            "rec-id-1",
            correlated_threat_id="T-linked",
            correlation_score=85.0,
            correlation_type="campaign",
        )
        assert c.threat_record_id == "rec-id-1"
        assert c.correlated_threat_id == "T-linked"
        assert c.correlation_score == 85.0
        assert c.correlation_type == "campaign"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_correlation(f"rec-{i}")
        assert len(eng._correlations) == 2


# -------------------------------------------------------------------
# analyze_threat_landscape
# -------------------------------------------------------------------


class TestAnalyzeThreatLandscape:
    def test_groups_by_source(self):
        eng = _engine()
        eng.record_threat("T-001", source=ThreatSource.EXTERNAL_FEED, relevance_score=70.0)
        eng.record_threat("T-002", source=ThreatSource.EXTERNAL_FEED, relevance_score=80.0)
        eng.record_threat("T-003", source=ThreatSource.COMMUNITY, relevance_score=40.0)
        results = eng.analyze_threat_landscape()
        sources = {r["source"] for r in results}
        assert "external_feed" in sources and "community" in sources

    def test_sorted_desc(self):
        eng = _engine()
        eng.record_threat("T-001", source=ThreatSource.GOVERNMENT, relevance_score=95.0)
        eng.record_threat("T-002", source=ThreatSource.COMMUNITY, relevance_score=20.0)
        results = eng.analyze_threat_landscape()
        assert results[0]["avg_relevance_score"] >= results[-1]["avg_relevance_score"]

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_threat_landscape() == []


# -------------------------------------------------------------------
# identify_critical_threats
# -------------------------------------------------------------------


class TestIdentifyCriticalThreats:
    def test_finds_critical_and_high(self):
        eng = _engine()
        eng.record_threat("T-001", severity=ThreatSeverity.CRITICAL, relevance_score=90.0)
        eng.record_threat("T-002", severity=ThreatSeverity.HIGH, relevance_score=75.0)
        eng.record_threat("T-003", severity=ThreatSeverity.LOW, relevance_score=20.0)
        results = eng.identify_critical_threats()
        assert len(results) == 2
        threat_ids = {r["threat_id"] for r in results}
        assert "T-001" in threat_ids and "T-002" in threat_ids

    def test_sorted_by_relevance_desc(self):
        eng = _engine()
        eng.record_threat("T-low-rel", severity=ThreatSeverity.CRITICAL, relevance_score=30.0)
        eng.record_threat("T-high-rel", severity=ThreatSeverity.HIGH, relevance_score=90.0)
        results = eng.identify_critical_threats()
        assert results[0]["threat_id"] == "T-high-rel"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_threats() == []


# -------------------------------------------------------------------
# rank_by_relevance
# -------------------------------------------------------------------


class TestRankByRelevance:
    def test_sorted_desc(self):
        eng = _engine()
        eng.record_threat("T-001", affected_service="auth-svc", relevance_score=90.0)
        eng.record_threat("T-002", affected_service="log-svc", relevance_score=20.0)
        results = eng.rank_by_relevance()
        assert results[0]["affected_service"] == "auth-svc"

    def test_averages_correctly(self):
        eng = _engine()
        eng.record_threat("T-001", affected_service="api-gw", relevance_score=60.0)
        eng.record_threat("T-002", affected_service="api-gw", relevance_score=80.0)
        results = eng.rank_by_relevance()
        assert results[0]["avg_relevance_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_relevance() == []


# -------------------------------------------------------------------
# detect_threat_trends
# -------------------------------------------------------------------


class TestDetectThreatTrends:
    def test_detects_escalating(self):
        eng = _engine()
        for _ in range(3):
            eng.record_threat("T-x", source=ThreatSource.EXTERNAL_FEED, relevance_score=20.0)
        for _ in range(3):
            eng.record_threat("T-x", source=ThreatSource.EXTERNAL_FEED, relevance_score=80.0)
        results = eng.detect_threat_trends()
        assert len(results) == 1
        assert results[0]["trend"] == "escalating"

    def test_no_trend_below_delta(self):
        eng = _engine()
        for _ in range(4):
            eng.record_threat("T-x", source=ThreatSource.COMMUNITY, relevance_score=50.0)
        results = eng.detect_threat_trends()
        assert results == []

    def test_too_few_records(self):
        eng = _engine()
        eng.record_threat("T-001")
        assert eng.detect_threat_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_relevance_score=60.0)
        eng.record_threat(
            "T-001",
            severity=ThreatSeverity.CRITICAL,
            relevance_score=90.0,
            affected_service="payments",
        )
        eng.record_threat("T-002", severity=ThreatSeverity.LOW, relevance_score=20.0)
        eng.add_correlation("rec-id-1")
        report = eng.generate_report()
        assert isinstance(report, ThreatCorrelatorReport)
        assert report.total_records == 2
        assert report.total_correlations == 1
        assert report.critical_threats == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "nominal" in report.recommendations[0]

    def test_high_risk_services_populated(self):
        eng = _engine(min_relevance_score=60.0)
        eng.record_threat("T-001", affected_service="db-svc", relevance_score=85.0)
        report = eng.generate_report()
        assert "db-svc" in report.high_risk_services


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_threat("T-001")
        eng.add_correlation("rec-id-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._correlations) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_threats"] == 0
        assert stats["total_correlations"] == 0
        assert stats["severity_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_threat("T-001", severity=ThreatSeverity.CRITICAL, affected_service="svc-a")
        eng.record_threat("T-002", severity=ThreatSeverity.LOW, affected_service="svc-b")
        eng.add_correlation("rec-id-1")
        stats = eng.get_stats()
        assert stats["total_threats"] == 2
        assert stats["total_correlations"] == 1
        assert stats["unique_services"] == 2
