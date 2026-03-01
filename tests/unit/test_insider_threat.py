"""Tests for shieldops.security.insider_threat — InsiderThreatDetector."""

from __future__ import annotations

from shieldops.security.insider_threat import (
    InsiderThreatDetector,
    InsiderThreatReport,
    ThreatCategory,
    ThreatIndicator,
    ThreatLevel,
    ThreatRecord,
    ThreatSignal,
)


def _engine(**kw) -> InsiderThreatDetector:
    return InsiderThreatDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_indicator_unusual_access(self):
        assert ThreatIndicator.UNUSUAL_ACCESS == "unusual_access"

    def test_indicator_data_exfiltration(self):
        assert ThreatIndicator.DATA_EXFILTRATION == "data_exfiltration"

    def test_indicator_privilege_abuse(self):
        assert ThreatIndicator.PRIVILEGE_ABUSE == "privilege_abuse"

    def test_indicator_policy_violation(self):
        assert ThreatIndicator.POLICY_VIOLATION == "policy_violation"

    def test_indicator_after_hours_activity(self):
        assert ThreatIndicator.AFTER_HOURS_ACTIVITY == "after_hours_activity"

    def test_level_critical(self):
        assert ThreatLevel.CRITICAL == "critical"

    def test_level_high(self):
        assert ThreatLevel.HIGH == "high"

    def test_level_moderate(self):
        assert ThreatLevel.MODERATE == "moderate"

    def test_level_low(self):
        assert ThreatLevel.LOW == "low"

    def test_level_baseline(self):
        assert ThreatLevel.BASELINE == "baseline"

    def test_category_malicious_insider(self):
        assert ThreatCategory.MALICIOUS_INSIDER == "malicious_insider"

    def test_category_compromised_account(self):
        assert ThreatCategory.COMPROMISED_ACCOUNT == "compromised_account"

    def test_category_negligent_user(self):
        assert ThreatCategory.NEGLIGENT_USER == "negligent_user"

    def test_category_departing_employee(self):
        assert ThreatCategory.DEPARTING_EMPLOYEE == "departing_employee"

    def test_category_third_party(self):
        assert ThreatCategory.THIRD_PARTY == "third_party"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_threat_record_defaults(self):
        r = ThreatRecord()
        assert r.id
        assert r.user_id == ""
        assert r.threat_indicator == ThreatIndicator.UNUSUAL_ACCESS
        assert r.threat_level == ThreatLevel.LOW
        assert r.threat_category == ThreatCategory.NEGLIGENT_USER
        assert r.threat_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_threat_signal_defaults(self):
        s = ThreatSignal()
        assert s.id
        assert s.user_id == ""
        assert s.threat_indicator == ThreatIndicator.UNUSUAL_ACCESS
        assert s.value == 0.0
        assert s.threshold == 0.0
        assert s.breached is False
        assert s.description == ""
        assert s.created_at > 0

    def test_insider_threat_report_defaults(self):
        r = InsiderThreatReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_signals == 0
        assert r.high_risk_users == 0
        assert r.avg_threat_score == 0.0
        assert r.by_indicator == {}
        assert r.by_level == {}
        assert r.by_category == {}
        assert r.top_risky == []
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
            user_id="USER-001",
            threat_indicator=ThreatIndicator.DATA_EXFILTRATION,
            threat_level=ThreatLevel.HIGH,
            threat_category=ThreatCategory.MALICIOUS_INSIDER,
            threat_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.user_id == "USER-001"
        assert r.threat_indicator == ThreatIndicator.DATA_EXFILTRATION
        assert r.threat_level == ThreatLevel.HIGH
        assert r.threat_category == ThreatCategory.MALICIOUS_INSIDER
        assert r.threat_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_threat(user_id=f"USER-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_threat
# ---------------------------------------------------------------------------


class TestGetThreat:
    def test_found(self):
        eng = _engine()
        r = eng.record_threat(
            user_id="USER-001",
            threat_level=ThreatLevel.CRITICAL,
        )
        result = eng.get_threat(r.id)
        assert result is not None
        assert result.threat_level == ThreatLevel.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_threat("nonexistent") is None


# ---------------------------------------------------------------------------
# list_threats
# ---------------------------------------------------------------------------


class TestListThreats:
    def test_list_all(self):
        eng = _engine()
        eng.record_threat(user_id="USER-001")
        eng.record_threat(user_id="USER-002")
        assert len(eng.list_threats()) == 2

    def test_filter_by_indicator(self):
        eng = _engine()
        eng.record_threat(
            user_id="USER-001",
            threat_indicator=ThreatIndicator.DATA_EXFILTRATION,
        )
        eng.record_threat(
            user_id="USER-002",
            threat_indicator=ThreatIndicator.UNUSUAL_ACCESS,
        )
        results = eng.list_threats(indicator=ThreatIndicator.DATA_EXFILTRATION)
        assert len(results) == 1

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_threat(
            user_id="USER-001",
            threat_level=ThreatLevel.CRITICAL,
        )
        eng.record_threat(
            user_id="USER-002",
            threat_level=ThreatLevel.LOW,
        )
        results = eng.list_threats(level=ThreatLevel.CRITICAL)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_threat(user_id="USER-001", service="api")
        eng.record_threat(user_id="USER-002", service="web")
        results = eng.list_threats(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_threat(user_id="USER-001", team="sre")
        eng.record_threat(user_id="USER-002", team="platform")
        results = eng.list_threats(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_threat(user_id=f"USER-{i}")
        assert len(eng.list_threats(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_signal
# ---------------------------------------------------------------------------


class TestAddSignal:
    def test_basic(self):
        eng = _engine()
        s = eng.add_signal(
            user_id="USER-001",
            threat_indicator=ThreatIndicator.PRIVILEGE_ABUSE,
            value=75.0,
            threshold=80.0,
            breached=False,
            description="Privilege use within limits",
        )
        assert s.user_id == "USER-001"
        assert s.threat_indicator == ThreatIndicator.PRIVILEGE_ABUSE
        assert s.value == 75.0
        assert s.threshold == 80.0
        assert s.breached is False
        assert s.description == "Privilege use within limits"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_signal(user_id=f"USER-{i}")
        assert len(eng._signals) == 2


# ---------------------------------------------------------------------------
# analyze_threat_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeThreatPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_threat(
            user_id="USER-001",
            threat_indicator=ThreatIndicator.UNUSUAL_ACCESS,
            threat_score=70.0,
        )
        eng.record_threat(
            user_id="USER-002",
            threat_indicator=ThreatIndicator.UNUSUAL_ACCESS,
            threat_score=90.0,
        )
        result = eng.analyze_threat_patterns()
        assert "unusual_access" in result
        assert result["unusual_access"]["count"] == 2
        assert result["unusual_access"]["avg_threat_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_threat_patterns() == {}


# ---------------------------------------------------------------------------
# identify_high_risk_users
# ---------------------------------------------------------------------------


class TestIdentifyHighRiskUsers:
    def test_detects_high_risk(self):
        eng = _engine()
        eng.record_threat(
            user_id="USER-001",
            threat_level=ThreatLevel.CRITICAL,
        )
        eng.record_threat(
            user_id="USER-002",
            threat_level=ThreatLevel.LOW,
        )
        results = eng.identify_high_risk_users()
        assert len(results) == 1
        assert results[0]["user_id"] == "USER-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_risk_users() == []


# ---------------------------------------------------------------------------
# rank_by_threat_score
# ---------------------------------------------------------------------------


class TestRankByThreatScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_threat(user_id="USER-001", service="api", threat_score=90.0)
        eng.record_threat(user_id="USER-002", service="api", threat_score=80.0)
        eng.record_threat(user_id="USER-003", service="web", threat_score=50.0)
        results = eng.rank_by_threat_score()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_threat_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_threat_score() == []


# ---------------------------------------------------------------------------
# detect_threat_escalation
# ---------------------------------------------------------------------------


class TestDetectThreatEscalation:
    def test_stable(self):
        eng = _engine()
        for val in [10.0, 10.0, 10.0, 10.0]:
            eng.add_signal(user_id="USER-001", value=val)
        result = eng.detect_threat_escalation()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_signal(user_id="USER-001", value=val)
        result = eng.detect_threat_escalation()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_threat_escalation()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_threat(
            user_id="USER-001",
            threat_indicator=ThreatIndicator.DATA_EXFILTRATION,
            threat_level=ThreatLevel.CRITICAL,
            threat_score=50.0,
            service="api",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, InsiderThreatReport)
        assert report.total_records == 1
        assert report.high_risk_users == 1
        assert report.avg_threat_score == 50.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_threat(user_id="USER-001")
        eng.add_signal(user_id="USER-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._signals) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_signals"] == 0
        assert stats["indicator_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_threat(
            user_id="USER-001",
            threat_indicator=ThreatIndicator.PRIVILEGE_ABUSE,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_users"] == 1
        assert "privilege_abuse" in stats["indicator_distribution"]
