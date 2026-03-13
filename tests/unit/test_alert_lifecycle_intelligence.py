"""Tests for AlertLifecycleIntelligence."""

from __future__ import annotations

from shieldops.analytics.alert_lifecycle_intelligence import (
    AlertLifecycleIntelligence,
    AlertValue,
    LifecycleStage,
    RetirementReason,
)


def _engine(**kw) -> AlertLifecycleIntelligence:
    return AlertLifecycleIntelligence(**kw)


class TestEnums:
    def test_lifecycle_stage_values(self):
        for v in LifecycleStage:
            assert isinstance(v.value, str)

    def test_alert_value_values(self):
        for v in AlertValue:
            assert isinstance(v.value, str)

    def test_retirement_reason_values(self):
        for v in RetirementReason:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(alert_name="cpu_high")
        assert r.alert_name == "cpu_high"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(alert_name=f"a-{i}")
        assert len(eng._records) == 5

    def test_with_params(self):
        eng = _engine()
        r = eng.add_record(
            alert_name="cpu_high",
            age_days=365,
            fire_count=100,
        )
        assert r.age_days == 365


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            alert_name="cpu_high",
            action_rate=0.8,
        )
        a = eng.process(r.id)
        assert hasattr(a, "alert_name")
        assert a.alert_name == "cpu_high"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(alert_name="cpu_high")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(alert_name="cpu_high")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(alert_name="cpu_high")
        eng.clear_data()
        assert len(eng._records) == 0


class TestTrackAlertAging:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_name="cpu_high",
            age_days=400,
            fire_count=5,
        )
        result = eng.track_alert_aging()
        assert len(result) == 1
        assert "aging_status" in result[0]

    def test_empty(self):
        assert _engine().track_alert_aging() == []


class TestIdentifyStaleAlertDefinitions:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_name="old_alert",
            last_fired_days_ago=200,
            action_rate=0.05,
        )
        result = eng.identify_stale_alert_definitions()
        assert len(result) == 1
        assert result[0]["is_stale"] is True

    def test_empty(self):
        r = _engine().identify_stale_alert_definitions()
        assert r == []


class TestGenerateRetirementRecommendations:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_name="noisy_alert",
            action_rate=0.05,
            last_fired_days_ago=200,
            fire_count=10,
        )
        result = eng.generate_retirement_recommendations()
        assert len(result) == 1
        assert result[0]["recommendation"] == "retire"

    def test_empty(self):
        r = _engine().generate_retirement_recommendations()
        assert r == []
