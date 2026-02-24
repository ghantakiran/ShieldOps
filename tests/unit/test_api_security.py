"""Tests for shieldops.security.api_security — APISecurityMonitor."""

from __future__ import annotations

from shieldops.security.api_security import (
    APIEndpointProfile,
    APISecurityMonitor,
    MonitoringMode,
    RiskLevel,
    SecurityAlert,
    ThreatAssessment,
    ThreatType,
)


def _engine(**kw) -> APISecurityMonitor:
    return APISecurityMonitor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_threat_credential(self):
        assert ThreatType.CREDENTIAL_STUFFING == "credential_stuffing"

    def test_threat_rate(self):
        assert ThreatType.RATE_ABUSE == "rate_abuse"

    def test_threat_exfil(self):
        assert ThreatType.DATA_EXFILTRATION == "data_exfiltration"

    def test_threat_injection(self):
        assert ThreatType.INJECTION_ATTEMPT == "injection_attempt"

    def test_threat_auth(self):
        assert ThreatType.BROKEN_AUTH == "broken_auth"

    def test_threat_enum(self):
        assert ThreatType.ENUMERATION == "enumeration"

    def test_risk_safe(self):
        assert RiskLevel.SAFE == "safe"

    def test_risk_low(self):
        assert RiskLevel.LOW == "low"

    def test_risk_medium(self):
        assert RiskLevel.MEDIUM == "medium"

    def test_risk_high(self):
        assert RiskLevel.HIGH == "high"

    def test_risk_critical(self):
        assert RiskLevel.CRITICAL == "critical"

    def test_mode_passive(self):
        assert MonitoringMode.PASSIVE == "passive"

    def test_mode_active(self):
        assert MonitoringMode.ACTIVE == "active"

    def test_mode_blocking(self):
        assert MonitoringMode.BLOCKING == "blocking"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_endpoint_defaults(self):
        ep = APIEndpointProfile()
        assert ep.id
        assert ep.risk_level == RiskLevel.SAFE
        assert ep.total_requests == 0

    def test_alert_defaults(self):
        a = SecurityAlert()
        assert a.acknowledged is False

    def test_assessment_defaults(self):
        t = ThreatAssessment()
        assert t.overall_risk == RiskLevel.SAFE


# ---------------------------------------------------------------------------
# register_endpoint
# ---------------------------------------------------------------------------


class TestRegisterEndpoint:
    def test_basic_register(self):
        eng = _engine()
        ep = eng.register_endpoint("/api/users", method="GET")
        assert ep.path == "/api/users"
        assert ep.method == "GET"

    def test_unique_ids(self):
        eng = _engine()
        e1 = eng.register_endpoint("/a")
        e2 = eng.register_endpoint("/b")
        assert e1.id != e2.id

    def test_eviction_at_max(self):
        eng = _engine(max_endpoints=3)
        for i in range(5):
            eng.register_endpoint(f"/ep{i}")
        assert len(eng._endpoints) == 3

    def test_with_service(self):
        eng = _engine()
        ep = eng.register_endpoint("/api", service="gateway")
        assert ep.service == "gateway"


# ---------------------------------------------------------------------------
# get / list endpoints
# ---------------------------------------------------------------------------


class TestGetEndpoint:
    def test_found(self):
        eng = _engine()
        ep = eng.register_endpoint("/api")
        assert eng.get_endpoint(ep.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_endpoint("nonexistent") is None


class TestListEndpoints:
    def test_list_all(self):
        eng = _engine()
        eng.register_endpoint("/a")
        eng.register_endpoint("/b")
        assert len(eng.list_endpoints()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.register_endpoint("/a", service="svc-a")
        eng.register_endpoint("/b", service="svc-b")
        results = eng.list_endpoints(service="svc-a")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# report_request
# ---------------------------------------------------------------------------


class TestReportRequest:
    def test_basic_report(self):
        eng = _engine()
        ep = eng.register_endpoint("/api")
        result = eng.report_request(ep.id, source_ip="1.2.3.4")
        assert result["total_requests"] == 1

    def test_suspicious_updates_risk(self):
        eng = _engine()
        ep = eng.register_endpoint("/api")
        for _ in range(10):
            eng.report_request(ep.id, suspicious=True)
        assert ep.risk_level == RiskLevel.CRITICAL

    def test_invalid_endpoint(self):
        eng = _engine()
        result = eng.report_request("bad_id")
        assert result.get("error") == "endpoint_not_found"


# ---------------------------------------------------------------------------
# detect_threats
# ---------------------------------------------------------------------------


class TestDetectThreats:
    def test_no_threats(self):
        eng = _engine()
        ep = eng.register_endpoint("/api")
        eng.report_request(ep.id)
        alerts = eng.detect_threats()
        assert len(alerts) == 0

    def test_threat_detected(self):
        eng = _engine(alert_threshold=0.5)
        ep = eng.register_endpoint("/api")
        for _ in range(10):
            eng.report_request(ep.id, suspicious=True)
        alerts = eng.detect_threats()
        assert len(alerts) >= 1

    def test_auth_endpoint_threat(self):
        eng = _engine()
        ep = eng.register_endpoint("/auth/login")
        for _ in range(15):
            eng.report_request(ep.id, suspicious=True)
        alerts = eng.detect_threats()
        cred_alerts = [a for a in alerts if a.threat_type == ThreatType.CREDENTIAL_STUFFING]
        assert len(cred_alerts) >= 1


# ---------------------------------------------------------------------------
# alerts / acknowledge
# ---------------------------------------------------------------------------


class TestGetAlerts:
    def test_list_alerts(self):
        eng = _engine(alert_threshold=0.5)
        ep = eng.register_endpoint("/api")
        for _ in range(10):
            eng.report_request(ep.id, suspicious=True)
        eng.detect_threats()
        assert len(eng.get_alerts()) >= 1


class TestAcknowledgeAlert:
    def test_acknowledge(self):
        eng = _engine(alert_threshold=0.5)
        ep = eng.register_endpoint("/api")
        for _ in range(10):
            eng.report_request(ep.id, suspicious=True)
        alerts = eng.detect_threats()
        if alerts:
            assert eng.acknowledge_alert(alerts[0].id) is True

    def test_acknowledge_not_found(self):
        eng = _engine()
        assert eng.acknowledge_alert("nonexistent") is False


# ---------------------------------------------------------------------------
# risk score / top threats / stats
# ---------------------------------------------------------------------------


class TestRiskScore:
    def test_score(self):
        eng = _engine()
        ep = eng.register_endpoint("/api")
        eng.report_request(ep.id)
        score = eng.get_risk_score(ep.id)
        assert score is not None
        assert score["path"] == "/api"

    def test_score_not_found(self):
        eng = _engine()
        assert eng.get_risk_score("bad") is None


class TestTopThreats:
    def test_top_threats(self):
        eng = _engine(alert_threshold=0.5)
        ep = eng.register_endpoint("/api")
        for _ in range(10):
            eng.report_request(ep.id, suspicious=True)
        eng.detect_threats()
        threats = eng.get_top_threats()
        assert isinstance(threats, list)


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_endpoints"] == 0

    def test_populated_stats(self):
        eng = _engine()
        ep = eng.register_endpoint("/api")
        eng.report_request(ep.id, suspicious=True)
        stats = eng.get_stats()
        assert stats["total_endpoints"] == 1
        assert stats["total_suspicious"] == 1
