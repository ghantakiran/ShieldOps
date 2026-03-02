"""Tests for shieldops.security.security_signal_correlator — SecuritySignalCorrelator."""

from __future__ import annotations

from shieldops.security.security_signal_correlator import (
    CorrelationPattern,
    SecuritySignalCorrelator,
    SecuritySignalReport,
    SignalCorrelation,
    SignalRecord,
    SignalSource,
    ThreatSeverity,
)


def _engine(**kw) -> SecuritySignalCorrelator:
    return SecuritySignalCorrelator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_source_waf(self):
        assert SignalSource.WAF == "waf"

    def test_source_ids_ips(self):
        assert SignalSource.IDS_IPS == "ids_ips"

    def test_source_siem(self):
        assert SignalSource.SIEM == "siem"

    def test_source_cloud_audit(self):
        assert SignalSource.CLOUD_AUDIT == "cloud_audit"

    def test_source_endpoint_agent(self):
        assert SignalSource.ENDPOINT_AGENT == "endpoint_agent"

    def test_pattern_lateral_movement(self):
        assert CorrelationPattern.LATERAL_MOVEMENT == "lateral_movement"

    def test_pattern_privilege_escalation(self):
        assert CorrelationPattern.PRIVILEGE_ESCALATION == "privilege_escalation"

    def test_pattern_data_exfiltration(self):
        assert CorrelationPattern.DATA_EXFILTRATION == "data_exfiltration"

    def test_pattern_reconnaissance(self):
        assert CorrelationPattern.RECONNAISSANCE == "reconnaissance"

    def test_pattern_persistence(self):
        assert CorrelationPattern.PERSISTENCE == "persistence"

    def test_severity_critical(self):
        assert ThreatSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert ThreatSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert ThreatSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert ThreatSeverity.LOW == "low"

    def test_severity_informational(self):
        assert ThreatSeverity.INFORMATIONAL == "informational"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_signal_record_defaults(self):
        r = SignalRecord()
        assert r.id
        assert r.signal_name == ""
        assert r.signal_source == SignalSource.WAF
        assert r.correlation_pattern == CorrelationPattern.LATERAL_MOVEMENT
        assert r.threat_severity == ThreatSeverity.CRITICAL
        assert r.confidence_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_signal_correlation_defaults(self):
        c = SignalCorrelation()
        assert c.id
        assert c.signal_name == ""
        assert c.signal_source == SignalSource.WAF
        assert c.correlation_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_security_signal_report_defaults(self):
        r = SecuritySignalReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_correlations == 0
        assert r.low_confidence_count == 0
        assert r.avg_confidence_score == 0.0
        assert r.by_source == {}
        assert r.by_pattern == {}
        assert r.by_severity == {}
        assert r.top_low_confidence == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_signal
# ---------------------------------------------------------------------------


class TestRecordSignal:
    def test_basic(self):
        eng = _engine()
        r = eng.record_signal(
            signal_name="suspicious-login",
            signal_source=SignalSource.SIEM,
            correlation_pattern=CorrelationPattern.PRIVILEGE_ESCALATION,
            threat_severity=ThreatSeverity.HIGH,
            confidence_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.signal_name == "suspicious-login"
        assert r.signal_source == SignalSource.SIEM
        assert r.correlation_pattern == CorrelationPattern.PRIVILEGE_ESCALATION
        assert r.threat_severity == ThreatSeverity.HIGH
        assert r.confidence_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_signal(signal_name=f"SIG-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_signal
# ---------------------------------------------------------------------------


class TestGetSignal:
    def test_found(self):
        eng = _engine()
        r = eng.record_signal(
            signal_name="suspicious-login",
            threat_severity=ThreatSeverity.CRITICAL,
        )
        result = eng.get_signal(r.id)
        assert result is not None
        assert result.threat_severity == ThreatSeverity.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_signal("nonexistent") is None


# ---------------------------------------------------------------------------
# list_signals
# ---------------------------------------------------------------------------


class TestListSignals:
    def test_list_all(self):
        eng = _engine()
        eng.record_signal(signal_name="SIG-001")
        eng.record_signal(signal_name="SIG-002")
        assert len(eng.list_signals()) == 2

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_signal(
            signal_name="SIG-001",
            signal_source=SignalSource.WAF,
        )
        eng.record_signal(
            signal_name="SIG-002",
            signal_source=SignalSource.SIEM,
        )
        results = eng.list_signals(signal_source=SignalSource.WAF)
        assert len(results) == 1

    def test_filter_by_pattern(self):
        eng = _engine()
        eng.record_signal(
            signal_name="SIG-001",
            correlation_pattern=CorrelationPattern.LATERAL_MOVEMENT,
        )
        eng.record_signal(
            signal_name="SIG-002",
            correlation_pattern=CorrelationPattern.RECONNAISSANCE,
        )
        results = eng.list_signals(
            correlation_pattern=CorrelationPattern.LATERAL_MOVEMENT,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_signal(signal_name="SIG-001", team="security")
        eng.record_signal(signal_name="SIG-002", team="platform")
        results = eng.list_signals(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_signal(signal_name=f"SIG-{i}")
        assert len(eng.list_signals(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_correlation
# ---------------------------------------------------------------------------


class TestAddCorrelation:
    def test_basic(self):
        eng = _engine()
        c = eng.add_correlation(
            signal_name="suspicious-login",
            signal_source=SignalSource.IDS_IPS,
            correlation_score=88.5,
            threshold=80.0,
            breached=True,
            description="correlated with lateral movement",
        )
        assert c.signal_name == "suspicious-login"
        assert c.signal_source == SignalSource.IDS_IPS
        assert c.correlation_score == 88.5
        assert c.threshold == 80.0
        assert c.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_correlation(signal_name=f"SIG-{i}")
        assert len(eng._correlations) == 2


# ---------------------------------------------------------------------------
# analyze_signal_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeSignalDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_signal(
            signal_name="SIG-001",
            signal_source=SignalSource.WAF,
            confidence_score=90.0,
        )
        eng.record_signal(
            signal_name="SIG-002",
            signal_source=SignalSource.WAF,
            confidence_score=70.0,
        )
        result = eng.analyze_signal_distribution()
        assert "waf" in result
        assert result["waf"]["count"] == 2
        assert result["waf"]["avg_confidence_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_signal_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_confidence_signals
# ---------------------------------------------------------------------------


class TestIdentifyLowConfidenceSignals:
    def test_detects_below_threshold(self):
        eng = _engine(correlation_confidence_threshold=80.0)
        eng.record_signal(signal_name="SIG-001", confidence_score=60.0)
        eng.record_signal(signal_name="SIG-002", confidence_score=90.0)
        results = eng.identify_low_confidence_signals()
        assert len(results) == 1
        assert results[0]["signal_name"] == "SIG-001"

    def test_sorted_ascending(self):
        eng = _engine(correlation_confidence_threshold=80.0)
        eng.record_signal(signal_name="SIG-001", confidence_score=50.0)
        eng.record_signal(signal_name="SIG-002", confidence_score=30.0)
        results = eng.identify_low_confidence_signals()
        assert len(results) == 2
        assert results[0]["confidence_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_confidence_signals() == []


# ---------------------------------------------------------------------------
# rank_by_confidence
# ---------------------------------------------------------------------------


class TestRankByConfidence:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_signal(signal_name="SIG-001", service="auth-svc", confidence_score=90.0)
        eng.record_signal(signal_name="SIG-002", service="api-gw", confidence_score=50.0)
        results = eng.rank_by_confidence()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_confidence_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_confidence() == []


# ---------------------------------------------------------------------------
# detect_signal_trends
# ---------------------------------------------------------------------------


class TestDetectSignalTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_correlation(signal_name="SIG-001", correlation_score=50.0)
        result = eng.detect_signal_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_correlation(signal_name="SIG-001", correlation_score=20.0)
        eng.add_correlation(signal_name="SIG-002", correlation_score=20.0)
        eng.add_correlation(signal_name="SIG-003", correlation_score=80.0)
        eng.add_correlation(signal_name="SIG-004", correlation_score=80.0)
        result = eng.detect_signal_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_signal_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(correlation_confidence_threshold=80.0)
        eng.record_signal(
            signal_name="suspicious-login",
            signal_source=SignalSource.SIEM,
            correlation_pattern=CorrelationPattern.PRIVILEGE_ESCALATION,
            threat_severity=ThreatSeverity.HIGH,
            confidence_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, SecuritySignalReport)
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
        eng.record_signal(signal_name="SIG-001")
        eng.add_correlation(signal_name="SIG-001")
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
        assert stats["source_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_signal(
            signal_name="SIG-001",
            signal_source=SignalSource.WAF,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "waf" in stats["source_distribution"]
