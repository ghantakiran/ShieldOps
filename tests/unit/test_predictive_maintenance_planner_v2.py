"""Tests for PredictiveMaintenancePlannerV2."""

from __future__ import annotations

from shieldops.operations.predictive_maintenance_planner_v2 import (
    ComponentHealth,
    MaintenanceType,
    MaintenanceWindow,
    PredictiveMaintenancePlannerV2,
)


def _engine(**kw) -> PredictiveMaintenancePlannerV2:
    return PredictiveMaintenancePlannerV2(**kw)


class TestEnums:
    def test_maintenance_type_values(self):
        assert MaintenanceType.PREVENTIVE == "preventive"
        assert MaintenanceType.PREDICTIVE == "predictive"
        assert MaintenanceType.CORRECTIVE == "corrective"
        assert MaintenanceType.EMERGENCY == "emergency"

    def test_component_health_values(self):
        assert ComponentHealth.HEALTHY == "healthy"
        assert ComponentHealth.DEGRADING == "degrading"
        assert ComponentHealth.FAILING == "failing"
        assert ComponentHealth.FAILED == "failed"

    def test_maintenance_window_values(self):
        assert MaintenanceWindow.IMMEDIATE == "immediate"
        assert MaintenanceWindow.NEXT_WINDOW == "next_window"
        assert MaintenanceWindow.SCHEDULED == "scheduled"
        assert MaintenanceWindow.DEFERRED == "deferred"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="maint-001",
            maintenance_type=MaintenanceType.PREDICTIVE,
            component_health=ComponentHealth.DEGRADING,
            score=75.0,
            service="db",
            team="infra",
        )
        assert r.name == "maint-001"
        assert r.maintenance_type == MaintenanceType.PREDICTIVE
        assert r.score == 75.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="test", score=40.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        eng = _engine()
        stats = eng.get_stats()
        assert "total_records" in stats

    def test_populated(self):
        eng = _engine()
        eng.record_item(name="t", service="a", team="b")
        stats = eng.get_stats()
        assert stats["total_records"] == 1


class TestClearData:
    def test_resets_to_zero(self):
        eng = _engine()
        eng.record_item(name="test")
        eng.add_analysis(name="test")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestPredictComponentFailure:
    def test_returns_sorted(self):
        eng = _engine()
        eng.record_item(
            name="a",
            service="db",
            component_health=ComponentHealth.FAILING,
            score=30.0,
        )
        eng.record_item(
            name="b",
            service="api",
            component_health=ComponentHealth.HEALTHY,
            score=90.0,
        )
        results = eng.predict_component_failure()
        assert len(results) == 2
        assert results[0]["service"] == "db"

    def test_empty(self):
        eng = _engine()
        assert eng.predict_component_failure() == []


class TestOptimizeMaintenanceSchedule:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            name="a",
            maintenance_window=MaintenanceWindow.SCHEDULED,
            score=80.0,
        )
        result = eng.optimize_maintenance_schedule()
        assert "window_analysis" in result
        assert result["total_scheduled"] == 1

    def test_empty(self):
        eng = _engine()
        result = eng.optimize_maintenance_schedule()
        assert result["total_scheduled"] == 0


class TestComputeMaintenanceRoi:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            name="a",
            maintenance_type=MaintenanceType.PREVENTIVE,
            score=80.0,
        )
        eng.record_item(
            name="b",
            maintenance_type=MaintenanceType.EMERGENCY,
            score=60.0,
        )
        result = eng.compute_maintenance_roi()
        roi = result["roi_by_type"]
        assert "preventive" in roi
        assert "emergency" in roi
        assert roi["preventive"]["roi_score"] > roi["emergency"]["roi_score"]

    def test_empty(self):
        eng = _engine()
        result = eng.compute_maintenance_roi()
        assert result["total_activities"] == 0
