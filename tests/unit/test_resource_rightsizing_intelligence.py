"""Tests for ResourceRightsizingIntelligence."""

from __future__ import annotations

from shieldops.operations.resource_rightsizing_intelligence import (
    ResourceRightsizingIntelligence,
    SafetyLevel,
    SizingAction,
    WorkloadProfile,
)


def _engine(**kw) -> ResourceRightsizingIntelligence:
    return ResourceRightsizingIntelligence(**kw)


class TestEnums:
    def test_workload_profile_values(self):
        for v in WorkloadProfile:
            assert isinstance(v.value, str)

    def test_sizing_action_values(self):
        for v in SizingAction:
            assert isinstance(v.value, str)

    def test_safety_level_values(self):
        for v in SafetyLevel:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(resource_id="r1")
        assert r.resource_id == "r1"

    def test_with_params(self):
        eng = _engine()
        r = eng.record_item(
            resource_id="r1",
            cpu_utilization=45.0,
            memory_utilization=60.0,
        )
        assert r.cpu_utilization == 45.0

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(resource_id=f"r-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_downsize(self):
        eng = _engine()
        r = eng.record_item(
            resource_id="r1",
            sizing_action=SizingAction.DOWNSIZE,
            monthly_cost=1000,
        )
        a = eng.process(r.id)
        assert a.estimated_savings == 300.0

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_maintain(self):
        eng = _engine()
        r = eng.record_item(sizing_action=SizingAction.MAINTAIN)
        a = eng.process(r.id)
        assert a.estimated_savings == 0.0


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(resource_id="r1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_downsize_recommendation(self):
        eng = _engine()
        eng.record_item(sizing_action=SizingAction.DOWNSIZE)
        rpt = eng.generate_report()
        assert any("downsized" in r for r in rpt.recommendations)


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(resource_id="r1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestProfileWorkloadUtilization:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            resource_id="r1",
            cpu_utilization=30,
            memory_utilization=50,
        )
        result = eng.profile_workload_utilization()
        assert len(result) == 1
        assert result[0]["avg_cpu"] == 30.0

    def test_empty(self):
        assert _engine().profile_workload_utilization() == []


class TestRecommendInstanceFamily:
    def test_low_cpu(self):
        eng = _engine()
        eng.record_item(
            resource_id="r1",
            cpu_utilization=10,
            instance_type="m5.xlarge",
        )
        result = eng.recommend_instance_family()
        assert result[0]["recommended"] == "t3.small"

    def test_empty(self):
        assert _engine().recommend_instance_family() == []


class TestValidateRightsizingSafety:
    def test_safe(self):
        eng = _engine()
        eng.record_item(
            resource_id="r1",
            safety_level=SafetyLevel.SAFE,
        )
        result = eng.validate_rightsizing_safety()
        assert result[0]["can_proceed"] is True

    def test_blocked(self):
        eng = _engine()
        eng.record_item(
            resource_id="r1",
            safety_level=SafetyLevel.BLOCKED,
        )
        result = eng.validate_rightsizing_safety()
        assert result[0]["can_proceed"] is False
