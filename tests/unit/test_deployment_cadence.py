"""Tests for shieldops.analytics.deployment_cadence — DeploymentCadenceAnalyzer.

Covers DeploymentFrequency, CadenceHealth, and TimeSlot enums,
DeploymentEvent / CadenceScore / CadenceReport models, and all
DeploymentCadenceAnalyzer operations including recording, cadence
calculation, bottleneck identification, team comparison, time
distribution analysis, and report generation.
"""

from __future__ import annotations

from shieldops.analytics.deployment_cadence import (
    CadenceHealth,
    CadenceReport,
    CadenceScore,
    DeploymentCadenceAnalyzer,
    DeploymentEvent,
    DeploymentFrequency,
    TimeSlot,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(**kw) -> DeploymentCadenceAnalyzer:
    return DeploymentCadenceAnalyzer(**kw)


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    """Validate every member of all three enums."""

    # -- DeploymentFrequency (5 members) ----------------------------

    def test_frequency_multiple_daily(self):
        assert DeploymentFrequency.MULTIPLE_DAILY == "multiple_daily"

    def test_frequency_daily(self):
        assert DeploymentFrequency.DAILY == "daily"

    def test_frequency_weekly(self):
        assert DeploymentFrequency.WEEKLY == "weekly"

    def test_frequency_biweekly(self):
        assert DeploymentFrequency.BIWEEKLY == "biweekly"

    def test_frequency_monthly(self):
        assert DeploymentFrequency.MONTHLY == "monthly"

    # -- CadenceHealth (5 members) ----------------------------------

    def test_health_excellent(self):
        assert CadenceHealth.EXCELLENT == "excellent"

    def test_health_good(self):
        assert CadenceHealth.GOOD == "good"

    def test_health_fair(self):
        assert CadenceHealth.FAIR == "fair"

    def test_health_poor(self):
        assert CadenceHealth.POOR == "poor"

    def test_health_stalled(self):
        assert CadenceHealth.STALLED == "stalled"

    # -- TimeSlot (5 members) ---------------------------------------

    def test_slot_business_hours(self):
        assert TimeSlot.BUSINESS_HOURS == "business_hours"

    def test_slot_after_hours(self):
        assert TimeSlot.AFTER_HOURS == "after_hours"

    def test_slot_weekend(self):
        assert TimeSlot.WEEKEND == "weekend"

    def test_slot_holiday(self):
        assert TimeSlot.HOLIDAY == "holiday"

    def test_slot_maintenance_window(self):
        assert TimeSlot.MAINTENANCE_WINDOW == "maintenance_window"


# ===========================================================================
# Model defaults
# ===========================================================================


class TestModels:
    """Verify default field values for each Pydantic model."""

    def test_deployment_event_defaults(self):
        e = DeploymentEvent()
        assert e.id
        assert e.service_name == ""
        assert e.team == ""
        assert e.deployed_at > 0
        assert e.time_slot == TimeSlot.BUSINESS_HOURS
        assert e.frequency == DeploymentFrequency.WEEKLY
        assert e.environment == "production"
        assert e.is_success is True
        assert e.rollback is False
        assert e.created_at > 0

    def test_cadence_score_defaults(self):
        s = CadenceScore()
        assert s.service_name == ""
        assert s.team == ""
        assert s.frequency == DeploymentFrequency.WEEKLY
        assert s.health == CadenceHealth.FAIR
        assert s.deploy_count == 0
        assert s.success_rate == 0.0
        assert s.avg_interval_hours == 0.0
        assert s.score == 0.0
        assert s.created_at > 0

    def test_cadence_report_defaults(self):
        r = CadenceReport()
        assert r.total_deployments == 0
        assert r.total_services == 0
        assert r.avg_frequency_score == 0.0
        assert r.by_frequency == {}
        assert r.by_health == {}
        assert r.recommendations == []
        assert r.generated_at > 0


# ===========================================================================
# RecordDeployment
# ===========================================================================


class TestRecordDeployment:
    """Test DeploymentCadenceAnalyzer.record_deployment."""

    def test_basic_record(self):
        eng = _engine()
        e = eng.record_deployment(
            service_name="auth-svc",
            team="platform",
        )
        assert e.id
        assert e.service_name == "auth-svc"
        assert e.team == "platform"

    def test_custom_fields(self):
        eng = _engine()
        e = eng.record_deployment(
            service_name="api",
            team="backend",
            time_slot=TimeSlot.AFTER_HOURS,
            frequency=DeploymentFrequency.DAILY,
            environment="staging",
            is_success=False,
            rollback=True,
        )
        assert e.time_slot == TimeSlot.AFTER_HOURS
        assert e.frequency == DeploymentFrequency.DAILY
        assert e.environment == "staging"
        assert e.is_success is False
        assert e.rollback is True

    def test_eviction_on_overflow(self):
        eng = _engine(max_deployments=3)
        eng.record_deployment(service_name="a")
        eng.record_deployment(service_name="b")
        eng.record_deployment(service_name="c")
        e4 = eng.record_deployment(service_name="d")
        items = eng.list_deployments(limit=100)
        assert len(items) == 3
        assert items[-1].id == e4.id


# ===========================================================================
# GetDeployment
# ===========================================================================


class TestGetDeployment:
    """Test DeploymentCadenceAnalyzer.get_deployment."""

    def test_found(self):
        eng = _engine()
        e = eng.record_deployment(service_name="api")
        assert eng.get_deployment(e.id) is e

    def test_not_found(self):
        eng = _engine()
        assert eng.get_deployment("missing") is None


# ===========================================================================
# ListDeployments
# ===========================================================================


class TestListDeployments:
    """Test DeploymentCadenceAnalyzer.list_deployments."""

    def test_all(self):
        eng = _engine()
        eng.record_deployment(service_name="a")
        eng.record_deployment(service_name="b")
        assert len(eng.list_deployments()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_deployment(service_name="api")
        eng.record_deployment(service_name="web")
        eng.record_deployment(service_name="api")
        results = eng.list_deployments(service_name="api")
        assert len(results) == 2
        assert all(e.service_name == "api" for e in results)

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_deployment(
            service_name="a",
            team="alpha",
        )
        eng.record_deployment(
            service_name="b",
            team="beta",
        )
        results = eng.list_deployments(team="alpha")
        assert len(results) == 1
        assert results[0].team == "alpha"

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_deployment(service_name=f"svc-{i}")
        assert len(eng.list_deployments(limit=3)) == 3


# ===========================================================================
# CalculateCadence
# ===========================================================================


class TestCalculateCadence:
    """Test DeploymentCadenceAnalyzer.calculate_cadence."""

    def test_empty_service(self):
        eng = _engine()
        score = eng.calculate_cadence("nonexistent")
        assert score.deploy_count == 0
        assert score.service_name == "nonexistent"

    def test_single_deployment(self):
        eng = _engine()
        eng.record_deployment(
            service_name="api",
            team="backend",
        )
        score = eng.calculate_cadence("api")
        assert score.deploy_count == 1
        assert score.success_rate == 1.0
        assert score.service_name == "api"

    def test_with_failures(self):
        eng = _engine()
        eng.record_deployment(
            service_name="api",
            is_success=True,
        )
        eng.record_deployment(
            service_name="api",
            is_success=False,
        )
        score = eng.calculate_cadence("api")
        assert score.deploy_count == 2
        assert score.success_rate == 0.5


# ===========================================================================
# DetectCadenceHealth
# ===========================================================================


class TestDetectCadenceHealth:
    """Test DeploymentCadenceAnalyzer.detect_cadence_health."""

    def test_multiple_services(self):
        eng = _engine()
        eng.record_deployment(service_name="api")
        eng.record_deployment(service_name="web")
        results = eng.detect_cadence_health()
        assert len(results) == 2
        svc_names = {r.service_name for r in results}
        assert "api" in svc_names
        assert "web" in svc_names

    def test_empty(self):
        eng = _engine()
        assert eng.detect_cadence_health() == []


# ===========================================================================
# IdentifyBottlenecks
# ===========================================================================


class TestIdentifyBottlenecks:
    """Test DeploymentCadenceAnalyzer.identify_bottlenecks."""

    def test_with_failures(self):
        eng = _engine()
        eng.record_deployment(
            service_name="api",
            time_slot=TimeSlot.WEEKEND,
            is_success=False,
        )
        eng.record_deployment(
            service_name="api",
            time_slot=TimeSlot.BUSINESS_HOURS,
            is_success=True,
        )
        bns = eng.identify_bottlenecks()
        assert len(bns) >= 1
        assert any(b["time_slot"] == "weekend" for b in bns)

    def test_empty(self):
        eng = _engine()
        assert eng.identify_bottlenecks() == []


# ===========================================================================
# AnalyzeTimeDistribution
# ===========================================================================


class TestAnalyzeTimeDistribution:
    """Test DeploymentCadenceAnalyzer.analyze_time_distribution."""

    def test_distribution(self):
        eng = _engine()
        eng.record_deployment(
            service_name="a",
            time_slot=TimeSlot.BUSINESS_HOURS,
        )
        eng.record_deployment(
            service_name="b",
            time_slot=TimeSlot.BUSINESS_HOURS,
        )
        eng.record_deployment(
            service_name="c",
            time_slot=TimeSlot.WEEKEND,
        )
        dist = eng.analyze_time_distribution()
        assert dist["business_hours"] == 2
        assert dist["weekend"] == 1

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_time_distribution() == {}


# ===========================================================================
# CompareTeams
# ===========================================================================


class TestCompareTeams:
    """Test DeploymentCadenceAnalyzer.compare_teams."""

    def test_multiple_teams(self):
        eng = _engine()
        eng.record_deployment(
            service_name="a",
            team="alpha",
        )
        eng.record_deployment(
            service_name="b",
            team="beta",
        )
        eng.record_deployment(
            service_name="c",
            team="alpha",
        )
        teams = eng.compare_teams()
        assert len(teams) == 2
        alpha = next(t for t in teams if t["team"] == "alpha")
        assert alpha["total_deployments"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.compare_teams() == []


# ===========================================================================
# GenerateCadenceReport
# ===========================================================================


class TestGenerateCadenceReport:
    """Test DeploymentCadenceAnalyzer.generate_cadence_report."""

    def test_basic_report(self):
        eng = _engine()
        eng.record_deployment(
            service_name="api",
            team="backend",
            is_success=True,
        )
        eng.record_deployment(
            service_name="web",
            team="frontend",
            is_success=False,
            rollback=True,
        )
        report = eng.generate_cadence_report()
        assert isinstance(report, CadenceReport)
        assert report.total_deployments == 2
        assert report.total_services == 2
        assert report.generated_at > 0
        assert len(report.by_frequency) >= 1

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_cadence_report()
        assert report.total_deployments == 0
        assert report.total_services == 0

    def test_report_recommendations(self):
        eng = _engine()
        eng.record_deployment(
            service_name="api",
            is_success=False,
            rollback=True,
        )
        report = eng.generate_cadence_report()
        assert len(report.recommendations) >= 1


# ===========================================================================
# ClearData
# ===========================================================================


class TestClearData:
    """Test DeploymentCadenceAnalyzer.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        eng.record_deployment(service_name="api")
        eng.clear_data()
        assert len(eng.list_deployments()) == 0
        stats = eng.get_stats()
        assert stats["total_deployments"] == 0


# ===========================================================================
# GetStats
# ===========================================================================


class TestGetStats:
    """Test DeploymentCadenceAnalyzer.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_deployments"] == 0
        assert stats["unique_services"] == 0
        assert stats["unique_teams"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["environment_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_deployment(
            service_name="api",
            team="backend",
            environment="production",
            is_success=True,
        )
        eng.record_deployment(
            service_name="web",
            team="frontend",
            environment="staging",
            is_success=False,
        )
        stats = eng.get_stats()
        assert stats["total_deployments"] == 2
        assert stats["unique_services"] == 2
        assert stats["unique_teams"] == 2
        assert stats["success_rate"] == 0.5
        assert stats["environment_distribution"]["production"] == 1
        assert stats["environment_distribution"]["staging"] == 1
