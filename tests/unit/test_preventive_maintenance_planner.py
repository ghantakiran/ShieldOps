"""Tests for shieldops.operations.preventive_maintenance_planner — PreventiveMaintenancePlanner."""

from __future__ import annotations

from shieldops.operations.preventive_maintenance_planner import (
    MaintenanceRisk,
    MaintenanceType,
    MaintenanceWindow,
    PreventiveMaintenancePlanner,
    PreventiveMaintenancePlannerAnalysis,
    PreventiveMaintenancePlannerRecord,
    PreventiveMaintenancePlannerReport,
)


def _engine(**kw) -> PreventiveMaintenancePlanner:
    return PreventiveMaintenancePlanner(**kw)


class TestEnums:
    def test_maintenance_type_first(self):
        assert MaintenanceType.PATCHING == "patching"

    def test_maintenance_type_second(self):
        assert MaintenanceType.UPGRADE == "upgrade"

    def test_maintenance_type_third(self):
        assert MaintenanceType.REPLACEMENT == "replacement"

    def test_maintenance_type_fourth(self):
        assert MaintenanceType.OPTIMIZATION == "optimization"

    def test_maintenance_type_fifth(self):
        assert MaintenanceType.CERTIFICATION == "certification"

    def test_maintenance_window_first(self):
        assert MaintenanceWindow.IMMEDIATE == "immediate"

    def test_maintenance_window_second(self):
        assert MaintenanceWindow.NEXT_WINDOW == "next_window"

    def test_maintenance_window_third(self):
        assert MaintenanceWindow.SCHEDULED == "scheduled"

    def test_maintenance_window_fourth(self):
        assert MaintenanceWindow.DEFERRED == "deferred"

    def test_maintenance_window_fifth(self):
        assert MaintenanceWindow.ON_DEMAND == "on_demand"

    def test_maintenance_risk_first(self):
        assert MaintenanceRisk.LOW == "low"

    def test_maintenance_risk_second(self):
        assert MaintenanceRisk.MEDIUM == "medium"

    def test_maintenance_risk_third(self):
        assert MaintenanceRisk.HIGH == "high"

    def test_maintenance_risk_fourth(self):
        assert MaintenanceRisk.VERY_HIGH == "very_high"

    def test_maintenance_risk_fifth(self):
        assert MaintenanceRisk.CRITICAL == "critical"


class TestModels:
    def test_record_defaults(self):
        r = PreventiveMaintenancePlannerRecord()
        assert r.id
        assert r.name == ""
        assert r.maintenance_type == MaintenanceType.PATCHING
        assert r.maintenance_window == MaintenanceWindow.IMMEDIATE
        assert r.maintenance_risk == MaintenanceRisk.LOW
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = PreventiveMaintenancePlannerAnalysis()
        assert a.id
        assert a.name == ""
        assert a.maintenance_type == MaintenanceType.PATCHING
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = PreventiveMaintenancePlannerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_maintenance_type == {}
        assert r.by_maintenance_window == {}
        assert r.by_maintenance_risk == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            maintenance_type=MaintenanceType.PATCHING,
            maintenance_window=MaintenanceWindow.NEXT_WINDOW,
            maintenance_risk=MaintenanceRisk.HIGH,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.maintenance_type == MaintenanceType.PATCHING
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.record_item(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_maintenance_type(self):
        eng = _engine()
        eng.record_item(name="a", maintenance_type=MaintenanceType.UPGRADE)
        eng.record_item(name="b", maintenance_type=MaintenanceType.PATCHING)
        assert len(eng.list_records(maintenance_type=MaintenanceType.UPGRADE)) == 1

    def test_filter_by_maintenance_window(self):
        eng = _engine()
        eng.record_item(name="a", maintenance_window=MaintenanceWindow.IMMEDIATE)
        eng.record_item(name="b", maintenance_window=MaintenanceWindow.NEXT_WINDOW)
        assert len(eng.list_records(maintenance_window=MaintenanceWindow.IMMEDIATE)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_item(name="a", team="sec")
        eng.record_item(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_item(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="test analysis",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(name="a", maintenance_type=MaintenanceType.UPGRADE, score=90.0)
        eng.record_item(name="b", maintenance_type=MaintenanceType.UPGRADE, score=70.0)
        result = eng.analyze_distribution()
        assert "upgrade" in result
        assert result["upgrade"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=60.0)
        eng.record_item(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=50.0)
        eng.record_item(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_item(name="a", service="auth", score=90.0)
        eng.record_item(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_item(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
