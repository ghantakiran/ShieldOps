"""Tests for shieldops.security.identity_analytics_engine — IdentityAnalyticsEngine."""

from __future__ import annotations

from shieldops.security.identity_analytics_engine import (
    AccessPattern,
    IdentityAnalyticsEngine,
    IdentityRiskLevel,
    IdentityType,
)


def _engine(**kw) -> IdentityAnalyticsEngine:
    return IdentityAnalyticsEngine(**kw)


class TestEnums:
    def test_risk_level(self):
        assert IdentityRiskLevel.CRITICAL == "critical"

    def test_access_pattern(self):
        assert AccessPattern.NORMAL == "normal"

    def test_identity_type(self):
        assert IdentityType.HUMAN == "human"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        rec = eng.add_record(identity_name="admin@corp.com", identity_type=IdentityType.HUMAN)
        assert rec.identity_name == "admin@corp.com"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(identity_name=f"user-{i}")
        assert len(eng._records) == 3


class TestPrivilegeAnomalies:
    def test_basic(self):
        eng = _engine()
        eng.add_record(identity_name="admin", privilege_count=50, risk_score=0.9)
        result = eng.detect_privilege_anomalies()
        assert isinstance(result, list)


class TestAccessPatterns:
    def test_basic(self):
        eng = _engine()
        eng.add_record(identity_name="user-1", access_pattern=AccessPattern.NORMAL)
        result = eng.profile_access_patterns()
        assert isinstance(result, dict)


class TestHighRisk:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            identity_name="admin", risk_score=0.95, risk_level=IdentityRiskLevel.CRITICAL
        )
        result = eng.identify_high_risk()
        assert isinstance(result, list)


class TestProcess:
    def test_found(self):
        eng = _engine()
        eng.add_record(identity_name="admin", service="iam")
        result = eng.process("iam")
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(identity_name="admin")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.add_record(identity_name="admin")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_record(identity_name="admin")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
