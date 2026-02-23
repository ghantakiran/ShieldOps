"""Tests for shieldops.analytics.deployment_velocity — DeploymentVelocityTracker.

Covers:
- DeploymentStage, VelocityTrend, BottleneckType enums
- DeploymentEvent, VelocityReport model defaults
- record_deployment (basic, unique IDs, extra fields, trims at max)
- get_velocity (basic, filter by service, filter by team)
- get_trend (basic)
- identify_bottlenecks (basic, empty)
- list_events (all, filter by service, filter by stage)
- compare_teams (basic, empty)
- get_leaderboard (basic)
- clear_events (basic)
- get_stats (empty, populated)
"""

from __future__ import annotations

import pytest

from shieldops.analytics.deployment_velocity import (
    BottleneckType,
    DeploymentEvent,
    DeploymentStage,
    DeploymentVelocityTracker,
    VelocityReport,
    VelocityTrend,
)


def _tracker(**kw) -> DeploymentVelocityTracker:
    return DeploymentVelocityTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # DeploymentStage (5 values)

    def test_stage_commit(self):
        assert DeploymentStage.COMMIT == "commit"

    def test_stage_build(self):
        assert DeploymentStage.BUILD == "build"

    def test_stage_test(self):
        assert DeploymentStage.TEST == "test"

    def test_stage_staging(self):
        assert DeploymentStage.STAGING == "staging"

    def test_stage_production(self):
        assert DeploymentStage.PRODUCTION == "production"

    # VelocityTrend (4 values)

    def test_trend_accelerating(self):
        assert VelocityTrend.ACCELERATING == "accelerating"

    def test_trend_stable(self):
        assert VelocityTrend.STABLE == "stable"

    def test_trend_decelerating(self):
        assert VelocityTrend.DECELERATING == "decelerating"

    def test_trend_stalled(self):
        assert VelocityTrend.STALLED == "stalled"

    # BottleneckType (5 values)

    def test_bottleneck_build(self):
        assert BottleneckType.BUILD == "build"

    def test_bottleneck_test(self):
        assert BottleneckType.TEST == "test"

    def test_bottleneck_approval(self):
        assert BottleneckType.APPROVAL == "approval"

    def test_bottleneck_deployment(self):
        assert BottleneckType.DEPLOYMENT == "deployment"

    def test_bottleneck_rollback(self):
        assert BottleneckType.ROLLBACK == "rollback"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_deployment_event_defaults(self):
        event = DeploymentEvent(service="api")
        assert event.id
        assert event.service == "api"
        assert event.team == ""
        assert event.stage == DeploymentStage.PRODUCTION
        assert event.duration_seconds == 0.0
        assert event.success is True
        assert event.commit_sha == ""
        assert event.tags == []
        assert event.deployed_at > 0

    def test_velocity_report_defaults(self):
        report = VelocityReport(service="api")
        assert report.service == "api"
        assert report.team == ""
        assert report.total_deployments == 0
        assert report.successful_deployments == 0
        assert report.avg_duration == 0.0
        assert report.deployments_per_day == 0.0
        assert report.trend == VelocityTrend.STABLE
        assert report.period_days == 30


# ---------------------------------------------------------------------------
# record_deployment
# ---------------------------------------------------------------------------


class TestRecordDeployment:
    def test_basic(self):
        t = _tracker()
        event = t.record_deployment("api-server", team="backend", duration_seconds=120.0)
        assert event.service == "api-server"
        assert event.team == "backend"
        assert event.duration_seconds == 120.0
        assert event.success is True

    def test_unique_ids(self):
        t = _tracker()
        e1 = t.record_deployment("api")
        e2 = t.record_deployment("api")
        assert e1.id != e2.id

    def test_extra_fields(self):
        t = _tracker()
        event = t.record_deployment(
            "api",
            team="platform",
            stage=DeploymentStage.STAGING,
            success=False,
            commit_sha="abc123",
        )
        assert event.stage == DeploymentStage.STAGING
        assert event.success is False
        assert event.commit_sha == "abc123"

    def test_trims_at_max(self):
        t = _tracker(max_events=2)
        t.record_deployment("svc-a")
        t.record_deployment("svc-b")
        t.record_deployment("svc-c")
        events = t.list_events()
        assert len(events) == 2


# ---------------------------------------------------------------------------
# get_velocity
# ---------------------------------------------------------------------------


class TestGetVelocity:
    def test_basic(self):
        t = _tracker()
        t.record_deployment("api", duration_seconds=100.0, success=True)
        t.record_deployment("api", duration_seconds=200.0, success=False)
        report = t.get_velocity()
        assert report.total_deployments == 2
        assert report.successful_deployments == 1
        assert report.avg_duration == pytest.approx(150.0, abs=0.01)

    def test_filter_by_service(self):
        t = _tracker()
        t.record_deployment("api", duration_seconds=100.0)
        t.record_deployment("web", duration_seconds=200.0)
        report = t.get_velocity(service="api")
        assert report.total_deployments == 1
        assert report.service == "api"

    def test_filter_by_team(self):
        t = _tracker()
        t.record_deployment("api", team="backend")
        t.record_deployment("api", team="platform")
        t.record_deployment("web", team="backend")
        report = t.get_velocity(team="backend")
        assert report.total_deployments == 2
        assert report.team == "backend"


# ---------------------------------------------------------------------------
# get_trend
# ---------------------------------------------------------------------------


class TestGetTrend:
    def test_basic(self):
        t = _tracker()
        t.record_deployment("api")
        trend = t.get_trend("api")
        assert trend["service"] == "api"
        assert "trend" in trend
        assert "deployments_per_day" in trend
        assert "total_deployments" in trend


# ---------------------------------------------------------------------------
# identify_bottlenecks
# ---------------------------------------------------------------------------


class TestIdentifyBottlenecks:
    def test_basic(self):
        t = _tracker()
        t.record_deployment("api", stage=DeploymentStage.BUILD, duration_seconds=300.0)
        t.record_deployment("api", stage=DeploymentStage.TEST, duration_seconds=600.0)
        t.record_deployment("api", stage=DeploymentStage.BUILD, duration_seconds=100.0)
        bottlenecks = t.identify_bottlenecks()
        assert len(bottlenecks) == 2
        # Sorted by avg_duration descending; TEST (600) > BUILD (200 avg)
        assert bottlenecks[0]["stage"] == DeploymentStage.TEST
        assert bottlenecks[0]["avg_duration"] == pytest.approx(600.0, abs=0.01)
        assert bottlenecks[1]["avg_duration"] == pytest.approx(200.0, abs=0.01)

    def test_empty(self):
        t = _tracker()
        assert t.identify_bottlenecks() == []


# ---------------------------------------------------------------------------
# list_events
# ---------------------------------------------------------------------------


class TestListEvents:
    def test_list_all(self):
        t = _tracker()
        t.record_deployment("api")
        t.record_deployment("web")
        events = t.list_events()
        assert len(events) == 2

    def test_filter_by_service(self):
        t = _tracker()
        t.record_deployment("api")
        t.record_deployment("web")
        t.record_deployment("api")
        events = t.list_events(service="api")
        assert len(events) == 2
        assert all(e.service == "api" for e in events)

    def test_filter_by_stage(self):
        t = _tracker()
        t.record_deployment("api", stage=DeploymentStage.BUILD)
        t.record_deployment("api", stage=DeploymentStage.TEST)
        t.record_deployment("api", stage=DeploymentStage.BUILD)
        events = t.list_events(stage=DeploymentStage.BUILD)
        assert len(events) == 2
        assert all(e.stage == DeploymentStage.BUILD for e in events)


# ---------------------------------------------------------------------------
# compare_teams
# ---------------------------------------------------------------------------


class TestCompareTeams:
    def test_basic(self):
        t = _tracker()
        t.record_deployment("api", team="backend", duration_seconds=100.0)
        t.record_deployment("web", team="frontend", duration_seconds=200.0)
        t.record_deployment("api", team="backend", duration_seconds=150.0)
        comparisons = t.compare_teams()
        assert len(comparisons) == 2
        teams = {c["team"] for c in comparisons}
        assert teams == {"backend", "frontend"}

    def test_empty(self):
        t = _tracker()
        assert t.compare_teams() == []


# ---------------------------------------------------------------------------
# get_leaderboard
# ---------------------------------------------------------------------------


class TestGetLeaderboard:
    def test_basic(self):
        t = _tracker()
        t.record_deployment("api")
        t.record_deployment("api")
        t.record_deployment("api")
        t.record_deployment("web")
        t.record_deployment("web")
        t.record_deployment("db")
        board = t.get_leaderboard(limit=2)
        assert len(board) == 2
        assert board[0]["service"] == "api"
        assert board[0]["deployment_count"] == 3
        assert board[1]["service"] == "web"
        assert board[1]["deployment_count"] == 2


# ---------------------------------------------------------------------------
# clear_events
# ---------------------------------------------------------------------------


class TestClearEvents:
    def test_basic(self):
        t = _tracker()
        t.record_deployment("api")
        t.record_deployment("web")
        cleared = t.clear_events()
        assert cleared == 2
        assert t.list_events() == []


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        t = _tracker()
        stats = t.get_stats()
        assert stats["total_events"] == 0
        assert stats["successful_events"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["stage_distribution"] == {}

    def test_populated(self):
        t = _tracker()
        t.record_deployment("api", stage=DeploymentStage.PRODUCTION, success=True)
        t.record_deployment("api", stage=DeploymentStage.PRODUCTION, success=False)
        t.record_deployment("api", stage=DeploymentStage.BUILD, success=True)
        stats = t.get_stats()
        assert stats["total_events"] == 3
        assert stats["successful_events"] == 2
        assert stats["success_rate"] == pytest.approx(0.6667, abs=0.001)
        assert DeploymentStage.PRODUCTION in stats["stage_distribution"]
        assert stats["stage_distribution"][DeploymentStage.PRODUCTION] == 2
