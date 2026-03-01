"""Tests for shieldops.security.threat_intelligence — ThreatIntelligenceTracker."""

from __future__ import annotations

from shieldops.security.threat_intelligence import (
    IndicatorType,
    ThreatCategory,
    ThreatIndicator,
    ThreatIntelligenceReport,
    ThreatIntelligenceTracker,
    ThreatRecord,
    ThreatSeverity,
)


def _engine(**kw) -> ThreatIntelligenceTracker:
    return ThreatIntelligenceTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_malware(self):
        assert ThreatCategory.MALWARE == "malware"

    def test_category_phishing(self):
        assert ThreatCategory.PHISHING == "phishing"

    def test_category_exploitation(self):
        assert ThreatCategory.EXPLOITATION == "exploitation"

    def test_category_data_exfiltration(self):
        assert ThreatCategory.DATA_EXFILTRATION == "data_exfiltration"

    def test_category_insider_threat(self):
        assert ThreatCategory.INSIDER_THREAT == "insider_threat"

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

    def test_indicator_type_ip_address(self):
        assert IndicatorType.IP_ADDRESS == "ip_address"

    def test_indicator_type_domain(self):
        assert IndicatorType.DOMAIN == "domain"

    def test_indicator_type_file_hash(self):
        assert IndicatorType.FILE_HASH == "file_hash"

    def test_indicator_type_url(self):
        assert IndicatorType.URL == "url"

    def test_indicator_type_email(self):
        assert IndicatorType.EMAIL == "email"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_threat_record_defaults(self):
        r = ThreatRecord()
        assert r.id
        assert r.indicator_id == ""
        assert r.threat_category == ThreatCategory.MALWARE
        assert r.threat_severity == ThreatSeverity.INFORMATIONAL
        assert r.indicator_type == IndicatorType.IP_ADDRESS
        assert r.confidence_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_threat_indicator_defaults(self):
        i = ThreatIndicator()
        assert i.id
        assert i.indicator_id == ""
        assert i.threat_category == ThreatCategory.MALWARE
        assert i.indicator_score == 0.0
        assert i.threshold == 0.0
        assert i.breached is False
        assert i.description == ""
        assert i.created_at > 0

    def test_threat_intelligence_report_defaults(self):
        r = ThreatIntelligenceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_indicators == 0
        assert r.critical_threats == 0
        assert r.avg_confidence_pct == 0.0
        assert r.by_category == {}
        assert r.by_severity == {}
        assert r.by_indicator_type == {}
        assert r.top_threats == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_threat
# ---------------------------------------------------------------------------


class TestRecordThreat:
    def test_basic(self):
        eng = _engine()
        r = eng.record_threat(
            indicator_id="IOC-001",
            threat_category=ThreatCategory.MALWARE,
            threat_severity=ThreatSeverity.CRITICAL,
            indicator_type=IndicatorType.IP_ADDRESS,
            confidence_pct=95.0,
            service="api-gateway",
            team="security",
        )
        assert r.indicator_id == "IOC-001"
        assert r.threat_category == ThreatCategory.MALWARE
        assert r.threat_severity == ThreatSeverity.CRITICAL
        assert r.indicator_type == IndicatorType.IP_ADDRESS
        assert r.confidence_pct == 95.0
        assert r.service == "api-gateway"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_threat(indicator_id=f"IOC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_threat
# ---------------------------------------------------------------------------


class TestGetThreat:
    def test_found(self):
        eng = _engine()
        r = eng.record_threat(
            indicator_id="IOC-001",
            threat_severity=ThreatSeverity.CRITICAL,
        )
        result = eng.get_threat(r.id)
        assert result is not None
        assert result.threat_severity == ThreatSeverity.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_threat("nonexistent") is None


# ---------------------------------------------------------------------------
# list_threats
# ---------------------------------------------------------------------------


class TestListThreats:
    def test_list_all(self):
        eng = _engine()
        eng.record_threat(indicator_id="IOC-001")
        eng.record_threat(indicator_id="IOC-002")
        assert len(eng.list_threats()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_threat(
            indicator_id="IOC-001",
            threat_category=ThreatCategory.MALWARE,
        )
        eng.record_threat(
            indicator_id="IOC-002",
            threat_category=ThreatCategory.PHISHING,
        )
        results = eng.list_threats(
            category=ThreatCategory.MALWARE,
        )
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_threat(
            indicator_id="IOC-001",
            threat_severity=ThreatSeverity.CRITICAL,
        )
        eng.record_threat(
            indicator_id="IOC-002",
            threat_severity=ThreatSeverity.LOW,
        )
        results = eng.list_threats(
            severity=ThreatSeverity.CRITICAL,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_threat(indicator_id="IOC-001", service="api-gateway")
        eng.record_threat(indicator_id="IOC-002", service="auth-svc")
        results = eng.list_threats(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_threat(indicator_id="IOC-001", team="security")
        eng.record_threat(indicator_id="IOC-002", team="platform")
        results = eng.list_threats(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_threat(indicator_id=f"IOC-{i}")
        assert len(eng.list_threats(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_indicator
# ---------------------------------------------------------------------------


class TestAddIndicator:
    def test_basic(self):
        eng = _engine()
        i = eng.add_indicator(
            indicator_id="IOC-001",
            threat_category=ThreatCategory.EXPLOITATION,
            indicator_score=88.0,
            threshold=75.0,
            breached=True,
            description="Known exploit detected",
        )
        assert i.indicator_id == "IOC-001"
        assert i.threat_category == ThreatCategory.EXPLOITATION
        assert i.indicator_score == 88.0
        assert i.threshold == 75.0
        assert i.breached is True
        assert i.description == "Known exploit detected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_indicator(indicator_id=f"IOC-{i}")
        assert len(eng._indicators) == 2


# ---------------------------------------------------------------------------
# analyze_threat_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeThreatDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_threat(
            indicator_id="IOC-001",
            threat_category=ThreatCategory.MALWARE,
            confidence_pct=80.0,
        )
        eng.record_threat(
            indicator_id="IOC-002",
            threat_category=ThreatCategory.MALWARE,
            confidence_pct=60.0,
        )
        result = eng.analyze_threat_distribution()
        assert "malware" in result
        assert result["malware"]["count"] == 2
        assert result["malware"]["avg_confidence_pct"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_threat_distribution() == {}


# ---------------------------------------------------------------------------
# identify_critical_threats
# ---------------------------------------------------------------------------


class TestIdentifyCriticalThreats:
    def test_detects_critical(self):
        eng = _engine()
        eng.record_threat(
            indicator_id="IOC-001",
            threat_severity=ThreatSeverity.CRITICAL,
        )
        eng.record_threat(
            indicator_id="IOC-002",
            threat_severity=ThreatSeverity.LOW,
        )
        results = eng.identify_critical_threats()
        assert len(results) == 1
        assert results[0]["indicator_id"] == "IOC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_threats() == []


# ---------------------------------------------------------------------------
# rank_by_confidence
# ---------------------------------------------------------------------------


class TestRankByConfidence:
    def test_ranked(self):
        eng = _engine()
        eng.record_threat(
            indicator_id="IOC-001",
            service="api-gateway",
            confidence_pct=90.0,
        )
        eng.record_threat(
            indicator_id="IOC-002",
            service="auth-svc",
            confidence_pct=50.0,
        )
        eng.record_threat(
            indicator_id="IOC-003",
            service="api-gateway",
            confidence_pct=70.0,
        )
        results = eng.rank_by_confidence()
        assert len(results) == 2
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_confidence_pct"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_confidence() == []


# ---------------------------------------------------------------------------
# detect_threat_trends
# ---------------------------------------------------------------------------


class TestDetectThreatTrends:
    def test_stable(self):
        eng = _engine()
        for val in [50.0, 50.0, 50.0, 50.0]:
            eng.add_indicator(indicator_id="IOC-1", indicator_score=val)
        result = eng.detect_threat_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [20.0, 20.0, 40.0, 40.0]:
            eng.add_indicator(indicator_id="IOC-1", indicator_score=val)
        result = eng.detect_threat_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_threat_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_threat(
            indicator_id="IOC-001",
            threat_category=ThreatCategory.MALWARE,
            threat_severity=ThreatSeverity.CRITICAL,
            indicator_type=IndicatorType.IP_ADDRESS,
            confidence_pct=95.0,
            service="api-gateway",
            team="security",
        )
        report = eng.generate_report()
        assert isinstance(report, ThreatIntelligenceReport)
        assert report.total_records == 1
        assert report.critical_threats == 1
        assert len(report.top_threats) >= 1
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
        eng.record_threat(indicator_id="IOC-001")
        eng.add_indicator(indicator_id="IOC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._indicators) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_indicators"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_threat(
            indicator_id="IOC-001",
            threat_category=ThreatCategory.MALWARE,
            service="api-gateway",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "malware" in stats["category_distribution"]
