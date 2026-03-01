"""Tests for shieldops.sla.maintenance_impact — MaintenanceImpactAnalyzer."""

from __future__ import annotations

from shieldops.sla.maintenance_impact import (
    DowntimeAttribution,
    ImpactLevel,
    MaintenanceImpactAnalyzer,
    MaintenanceImpactRecord,
    MaintenanceImpactReport,
    MaintenanceOutcome,
    MaintenanceType,
)


def _engine(**kw) -> MaintenanceImpactAnalyzer:
    return MaintenanceImpactAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_maintenance_type_planned(self):
        assert MaintenanceType.PLANNED == "planned"

    def test_maintenance_type_emergency(self):
        assert MaintenanceType.EMERGENCY == "emergency"

    def test_maintenance_type_rolling(self):
        assert MaintenanceType.ROLLING == "rolling"

    def test_maintenance_type_blue_green(self):
        assert MaintenanceType.BLUE_GREEN == "blue_green"

    def test_maintenance_type_canary(self):
        assert MaintenanceType.CANARY == "canary"

    def test_impact_level_full_outage(self):
        assert ImpactLevel.FULL_OUTAGE == "full_outage"

    def test_impact_level_partial_degradation(self):
        assert ImpactLevel.PARTIAL_DEGRADATION == "partial_degradation"

    def test_impact_level_minor_impact(self):
        assert ImpactLevel.MINOR_IMPACT == "minor_impact"

    def test_impact_level_no_impact(self):
        assert ImpactLevel.NO_IMPACT == "no_impact"

    def test_impact_level_improved(self):
        assert ImpactLevel.IMPROVED == "improved"

    def test_outcome_successful(self):
        assert MaintenanceOutcome.SUCCESSFUL == "successful"

    def test_outcome_partial_success(self):
        assert MaintenanceOutcome.PARTIAL_SUCCESS == "partial_success"

    def test_outcome_failed(self):
        assert MaintenanceOutcome.FAILED == "failed"

    def test_outcome_extended(self):
        assert MaintenanceOutcome.EXTENDED == "extended"

    def test_outcome_cancelled(self):
        assert MaintenanceOutcome.CANCELLED == "cancelled"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_maintenance_impact_record_defaults(self):
        r = MaintenanceImpactRecord()
        assert r.id
        assert r.window_id == ""
        assert r.maintenance_type == MaintenanceType.PLANNED
        assert r.impact_level == ImpactLevel.NO_IMPACT
        assert r.maintenance_outcome == MaintenanceOutcome.SUCCESSFUL
        assert r.impact_minutes == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_downtime_attribution_defaults(self):
        a = DowntimeAttribution()
        assert a.id
        assert a.window_id == ""
        assert a.maintenance_type == MaintenanceType.PLANNED
        assert a.downtime_minutes == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_maintenance_impact_report_defaults(self):
        r = MaintenanceImpactReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_attributions == 0
        assert r.high_impact_count == 0
        assert r.avg_impact_minutes == 0.0
        assert r.by_maintenance_type == {}
        assert r.by_impact_level == {}
        assert r.by_outcome == {}
        assert r.top_impacted == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_maintenance
# ---------------------------------------------------------------------------


class TestRecordMaintenance:
    def test_basic(self):
        eng = _engine()
        r = eng.record_maintenance(
            window_id="WIN-001",
            maintenance_type=MaintenanceType.ROLLING,
            impact_level=ImpactLevel.MINOR_IMPACT,
            maintenance_outcome=MaintenanceOutcome.SUCCESSFUL,
            impact_minutes=15.0,
            service="api-gateway",
            team="sre",
        )
        assert r.window_id == "WIN-001"
        assert r.maintenance_type == MaintenanceType.ROLLING
        assert r.impact_level == ImpactLevel.MINOR_IMPACT
        assert r.maintenance_outcome == MaintenanceOutcome.SUCCESSFUL
        assert r.impact_minutes == 15.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_maintenance(window_id=f"WIN-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_maintenance
# ---------------------------------------------------------------------------


class TestGetMaintenance:
    def test_found(self):
        eng = _engine()
        r = eng.record_maintenance(
            window_id="WIN-001",
            impact_level=ImpactLevel.FULL_OUTAGE,
        )
        result = eng.get_maintenance(r.id)
        assert result is not None
        assert result.impact_level == ImpactLevel.FULL_OUTAGE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_maintenance("nonexistent") is None


# ---------------------------------------------------------------------------
# list_maintenances
# ---------------------------------------------------------------------------


class TestListMaintenances:
    def test_list_all(self):
        eng = _engine()
        eng.record_maintenance(window_id="WIN-001")
        eng.record_maintenance(window_id="WIN-002")
        assert len(eng.list_maintenances()) == 2

    def test_filter_by_maintenance_type(self):
        eng = _engine()
        eng.record_maintenance(
            window_id="WIN-001",
            maintenance_type=MaintenanceType.ROLLING,
        )
        eng.record_maintenance(
            window_id="WIN-002",
            maintenance_type=MaintenanceType.PLANNED,
        )
        results = eng.list_maintenances(maintenance_type=MaintenanceType.ROLLING)
        assert len(results) == 1

    def test_filter_by_impact_level(self):
        eng = _engine()
        eng.record_maintenance(
            window_id="WIN-001",
            impact_level=ImpactLevel.FULL_OUTAGE,
        )
        eng.record_maintenance(
            window_id="WIN-002",
            impact_level=ImpactLevel.NO_IMPACT,
        )
        results = eng.list_maintenances(impact_level=ImpactLevel.FULL_OUTAGE)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_maintenance(window_id="WIN-001", service="api")
        eng.record_maintenance(window_id="WIN-002", service="web")
        results = eng.list_maintenances(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_maintenance(window_id="WIN-001", team="sre")
        eng.record_maintenance(window_id="WIN-002", team="platform")
        results = eng.list_maintenances(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_maintenance(window_id=f"WIN-{i}")
        assert len(eng.list_maintenances(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_attribution
# ---------------------------------------------------------------------------


class TestAddAttribution:
    def test_basic(self):
        eng = _engine()
        a = eng.add_attribution(
            window_id="WIN-001",
            maintenance_type=MaintenanceType.EMERGENCY,
            downtime_minutes=45.0,
            threshold=60.0,
            breached=False,
            description="Downtime within limits",
        )
        assert a.window_id == "WIN-001"
        assert a.maintenance_type == MaintenanceType.EMERGENCY
        assert a.downtime_minutes == 45.0
        assert a.threshold == 60.0
        assert a.breached is False
        assert a.description == "Downtime within limits"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_attribution(window_id=f"WIN-{i}")
        assert len(eng._attributions) == 2


# ---------------------------------------------------------------------------
# analyze_maintenance_impact
# ---------------------------------------------------------------------------


class TestAnalyzeMaintenanceImpact:
    def test_with_data(self):
        eng = _engine()
        eng.record_maintenance(
            window_id="WIN-001",
            maintenance_type=MaintenanceType.PLANNED,
            impact_minutes=30.0,
        )
        eng.record_maintenance(
            window_id="WIN-002",
            maintenance_type=MaintenanceType.PLANNED,
            impact_minutes=50.0,
        )
        result = eng.analyze_maintenance_impact()
        assert "planned" in result
        assert result["planned"]["count"] == 2
        assert result["planned"]["avg_impact_minutes"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_maintenance_impact() == {}


# ---------------------------------------------------------------------------
# identify_high_impact_windows
# ---------------------------------------------------------------------------


class TestIdentifyHighImpactWindows:
    def test_detects_high_impact(self):
        eng = _engine()
        eng.record_maintenance(
            window_id="WIN-001",
            impact_level=ImpactLevel.FULL_OUTAGE,
        )
        eng.record_maintenance(
            window_id="WIN-002",
            impact_level=ImpactLevel.NO_IMPACT,
        )
        results = eng.identify_high_impact_windows()
        assert len(results) == 1
        assert results[0]["window_id"] == "WIN-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_impact_windows() == []


# ---------------------------------------------------------------------------
# rank_by_impact_minutes
# ---------------------------------------------------------------------------


class TestRankByImpactMinutes:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_maintenance(window_id="WIN-001", service="api", impact_minutes=90.0)
        eng.record_maintenance(window_id="WIN-002", service="api", impact_minutes=80.0)
        eng.record_maintenance(window_id="WIN-003", service="web", impact_minutes=50.0)
        results = eng.rank_by_impact_minutes()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_impact_minutes"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact_minutes() == []


# ---------------------------------------------------------------------------
# detect_impact_trends
# ---------------------------------------------------------------------------


class TestDetectImpactTrends:
    def test_stable(self):
        eng = _engine()
        for val in [10.0, 10.0, 10.0, 10.0]:
            eng.add_attribution(window_id="WIN-001", downtime_minutes=val)
        result = eng.detect_impact_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_attribution(window_id="WIN-001", downtime_minutes=val)
        result = eng.detect_impact_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_impact_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_maintenance(
            window_id="WIN-001",
            maintenance_type=MaintenanceType.EMERGENCY,
            impact_level=ImpactLevel.FULL_OUTAGE,
            impact_minutes=120.0,
            service="api",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, MaintenanceImpactReport)
        assert report.total_records == 1
        assert report.high_impact_count == 1
        assert report.avg_impact_minutes == 120.0
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
        eng.record_maintenance(window_id="WIN-001")
        eng.add_attribution(window_id="WIN-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._attributions) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_attributions"] == 0
        assert stats["maintenance_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_maintenance(
            window_id="WIN-001",
            maintenance_type=MaintenanceType.ROLLING,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_windows"] == 1
        assert "rolling" in stats["maintenance_type_distribution"]
