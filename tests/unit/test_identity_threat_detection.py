"""Tests for shieldops.security.identity_threat_detection — IdentityThreatDetection."""

from __future__ import annotations

from shieldops.security.identity_threat_detection import (
    AuthProtocol,
    IdentityAnalysis,
    IdentityRecord,
    IdentityThreat,
    IdentityThreatDetection,
    IdentityThreatReport,
    RiskScore,
)


def _engine(**kw) -> IdentityThreatDetection:
    return IdentityThreatDetection(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_threat_credential_stuffing(self):
        assert IdentityThreat.CREDENTIAL_STUFFING == "credential_stuffing"

    def test_threat_account_takeover(self):
        assert IdentityThreat.ACCOUNT_TAKEOVER == "account_takeover"

    def test_threat_mfa_bypass(self):
        assert IdentityThreat.MFA_BYPASS == "mfa_bypass"

    def test_threat_session_hijack(self):
        assert IdentityThreat.SESSION_HIJACK == "session_hijack"

    def test_threat_brute_force(self):
        assert IdentityThreat.BRUTE_FORCE == "brute_force"

    def test_protocol_oauth2(self):
        assert AuthProtocol.OAUTH2 == "oauth2"

    def test_protocol_saml(self):
        assert AuthProtocol.SAML == "saml"

    def test_protocol_ldap(self):
        assert AuthProtocol.LDAP == "ldap"

    def test_protocol_kerberos(self):
        assert AuthProtocol.KERBEROS == "kerberos"

    def test_protocol_custom(self):
        assert AuthProtocol.CUSTOM == "custom"

    def test_risk_critical(self):
        assert RiskScore.CRITICAL == "critical"

    def test_risk_high(self):
        assert RiskScore.HIGH == "high"

    def test_risk_medium(self):
        assert RiskScore.MEDIUM == "medium"

    def test_risk_low(self):
        assert RiskScore.LOW == "low"

    def test_risk_none(self):
        assert RiskScore.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_identity_record_defaults(self):
        r = IdentityRecord()
        assert r.id
        assert r.threat_name == ""
        assert r.identity_threat == IdentityThreat.CREDENTIAL_STUFFING
        assert r.auth_protocol == AuthProtocol.OAUTH2
        assert r.risk_score_level == RiskScore.CRITICAL
        assert r.detection_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_identity_analysis_defaults(self):
        c = IdentityAnalysis()
        assert c.id
        assert c.threat_name == ""
        assert c.identity_threat == IdentityThreat.CREDENTIAL_STUFFING
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_identity_threat_report_defaults(self):
        r = IdentityThreatReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_threat_count == 0
        assert r.avg_detection_score == 0.0
        assert r.by_threat == {}
        assert r.by_protocol == {}
        assert r.by_risk == {}
        assert r.top_high_threat == []
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
            threat_name="cred-stuff-001",
            identity_threat=IdentityThreat.ACCOUNT_TAKEOVER,
            auth_protocol=AuthProtocol.SAML,
            risk_score_level=RiskScore.HIGH,
            detection_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.threat_name == "cred-stuff-001"
        assert r.identity_threat == IdentityThreat.ACCOUNT_TAKEOVER
        assert r.auth_protocol == AuthProtocol.SAML
        assert r.risk_score_level == RiskScore.HIGH
        assert r.detection_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_threat(threat_name=f"T-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_threat
# ---------------------------------------------------------------------------


class TestGetThreat:
    def test_found(self):
        eng = _engine()
        r = eng.record_threat(
            threat_name="cred-stuff-001",
            risk_score_level=RiskScore.CRITICAL,
        )
        result = eng.get_threat(r.id)
        assert result is not None
        assert result.risk_score_level == RiskScore.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_threat("nonexistent") is None


# ---------------------------------------------------------------------------
# list_threats
# ---------------------------------------------------------------------------


class TestListThreats:
    def test_list_all(self):
        eng = _engine()
        eng.record_threat(threat_name="T-001")
        eng.record_threat(threat_name="T-002")
        assert len(eng.list_threats()) == 2

    def test_filter_by_identity_threat(self):
        eng = _engine()
        eng.record_threat(
            threat_name="T-001",
            identity_threat=IdentityThreat.CREDENTIAL_STUFFING,
        )
        eng.record_threat(
            threat_name="T-002",
            identity_threat=IdentityThreat.MFA_BYPASS,
        )
        results = eng.list_threats(identity_threat=IdentityThreat.CREDENTIAL_STUFFING)
        assert len(results) == 1

    def test_filter_by_auth_protocol(self):
        eng = _engine()
        eng.record_threat(
            threat_name="T-001",
            auth_protocol=AuthProtocol.OAUTH2,
        )
        eng.record_threat(
            threat_name="T-002",
            auth_protocol=AuthProtocol.LDAP,
        )
        results = eng.list_threats(
            auth_protocol=AuthProtocol.OAUTH2,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_threat(threat_name="T-001", team="security")
        eng.record_threat(threat_name="T-002", team="platform")
        results = eng.list_threats(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_threat(threat_name=f"T-{i}")
        assert len(eng.list_threats(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            threat_name="cred-stuff-001",
            identity_threat=IdentityThreat.ACCOUNT_TAKEOVER,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="identity threat detected",
        )
        assert a.threat_name == "cred-stuff-001"
        assert a.identity_threat == IdentityThreat.ACCOUNT_TAKEOVER
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(threat_name=f"T-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_threat_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_threat(
            threat_name="T-001",
            identity_threat=IdentityThreat.CREDENTIAL_STUFFING,
            detection_score=90.0,
        )
        eng.record_threat(
            threat_name="T-002",
            identity_threat=IdentityThreat.CREDENTIAL_STUFFING,
            detection_score=70.0,
        )
        result = eng.analyze_threat_distribution()
        assert "credential_stuffing" in result
        assert result["credential_stuffing"]["count"] == 2
        assert result["credential_stuffing"]["avg_detection_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_threat_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_threat_detections
# ---------------------------------------------------------------------------


class TestIdentifyHighThreatDetections:
    def test_detects_above_threshold(self):
        eng = _engine(identity_threat_threshold=65.0)
        eng.record_threat(threat_name="T-001", detection_score=90.0)
        eng.record_threat(threat_name="T-002", detection_score=40.0)
        results = eng.identify_high_threat_detections()
        assert len(results) == 1
        assert results[0]["threat_name"] == "T-001"

    def test_sorted_descending(self):
        eng = _engine(identity_threat_threshold=65.0)
        eng.record_threat(threat_name="T-001", detection_score=80.0)
        eng.record_threat(threat_name="T-002", detection_score=95.0)
        results = eng.identify_high_threat_detections()
        assert len(results) == 2
        assert results[0]["detection_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_threat_detections() == []


# ---------------------------------------------------------------------------
# rank_by_detection_score
# ---------------------------------------------------------------------------


class TestRankByDetectionScore:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_threat(threat_name="T-001", service="auth-svc", detection_score=50.0)
        eng.record_threat(threat_name="T-002", service="api-gw", detection_score=90.0)
        results = eng.rank_by_detection_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_detection_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_detection_score() == []


# ---------------------------------------------------------------------------
# detect_threat_trends
# ---------------------------------------------------------------------------


class TestDetectThreatTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(threat_name="T-001", analysis_score=50.0)
        result = eng.detect_threat_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(threat_name="T-001", analysis_score=20.0)
        eng.add_analysis(threat_name="T-002", analysis_score=20.0)
        eng.add_analysis(threat_name="T-003", analysis_score=80.0)
        eng.add_analysis(threat_name="T-004", analysis_score=80.0)
        result = eng.detect_threat_trends()
        assert result["trend"] == "improving"
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
        eng = _engine(identity_threat_threshold=50.0)
        eng.record_threat(
            threat_name="cred-stuff-001",
            identity_threat=IdentityThreat.ACCOUNT_TAKEOVER,
            auth_protocol=AuthProtocol.SAML,
            risk_score_level=RiskScore.HIGH,
            detection_score=80.0,
        )
        report = eng.generate_report()
        assert isinstance(report, IdentityThreatReport)
        assert report.total_records == 1
        assert report.high_threat_count == 1
        assert len(report.top_high_threat) == 1
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
        eng.record_threat(threat_name="T-001")
        eng.add_analysis(threat_name="T-001")
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
        assert stats["threat_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_threat(
            threat_name="T-001",
            identity_threat=IdentityThreat.CREDENTIAL_STUFFING,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "credential_stuffing" in stats["threat_distribution"]
