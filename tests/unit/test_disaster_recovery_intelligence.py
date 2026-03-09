"""Tests for shieldops.operations.disaster_recovery_intelligence — DisasterRecoveryIntelligence."""

from __future__ import annotations

from shieldops.operations.disaster_recovery_intelligence import (
    DisasterRecoveryIntelligence,
    DRTier,
    FailoverTestResult,
    RecoveryStrategy,
)


def _engine(**kw) -> DisasterRecoveryIntelligence:
    return DisasterRecoveryIntelligence(**kw)


class TestEnums:
    def test_dr_tier(self):
        assert DRTier.TIER_1_CRITICAL == "tier_1_critical"

    def test_recovery_strategy(self):
        assert RecoveryStrategy.ACTIVE_ACTIVE == "active_active"

    def test_test_result(self):
        assert FailoverTestResult.PASSED == "passed"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        rec = eng.record_item(name="db-failover", dr_tier=DRTier.TIER_1_CRITICAL)
        assert rec.name == "db-failover"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"dr-{i}")
        assert len(eng._records) == 3


class TestRtoRpoCompliance:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="dr-1", rto_target_minutes=15.0, rto_actual_minutes=10.0)
        result = eng.assess_rto_rpo_compliance()
        assert isinstance(result, list)


class TestStaleTests:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="dr-1", last_test_days_ago=120)
        result = eng.identify_stale_tests()
        assert isinstance(result, list)


class TestReadiness:
    def test_basic(self):
        eng = _engine()
        eng.record_item(
            name="dr-1",
            dr_tier=DRTier.TIER_1_CRITICAL,
            failover_test_result=FailoverTestResult.PASSED,
        )
        result = eng.score_readiness_by_tier()
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(name="dr-1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="dr-1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="dr-1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
