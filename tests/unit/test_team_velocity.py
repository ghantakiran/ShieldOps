"""Tests for shieldops.analytics.team_velocity — TeamVelocityTracker."""

from __future__ import annotations

from shieldops.analytics.team_velocity import (
    SprintHealth,
    TeamVelocityReport,
    TeamVelocityTracker,
    VelocityDataPoint,
    VelocityMetric,
    VelocityRecord,
    VelocityTrend,
)


def _engine(**kw) -> TeamVelocityTracker:
    return TeamVelocityTracker(**kw)


class TestEnums:
    def test_metric_story_points(self):
        assert VelocityMetric.STORY_POINTS == "story_points"

    def test_metric_tasks_completed(self):
        assert VelocityMetric.TASKS_COMPLETED == "tasks_completed"

    def test_metric_deployments(self):
        assert VelocityMetric.DEPLOYMENTS == "deployments"

    def test_metric_incidents_resolved(self):
        assert VelocityMetric.INCIDENTS_RESOLVED == "incidents_resolved"

    def test_metric_pull_requests(self):
        assert VelocityMetric.PULL_REQUESTS == "pull_requests"

    def test_trend_accelerating(self):
        assert VelocityTrend.ACCELERATING == "accelerating"

    def test_trend_stable(self):
        assert VelocityTrend.STABLE == "stable"

    def test_trend_decelerating(self):
        assert VelocityTrend.DECELERATING == "decelerating"

    def test_trend_volatile(self):
        assert VelocityTrend.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert VelocityTrend.INSUFFICIENT_DATA == "insufficient_data"

    def test_health_excellent(self):
        assert SprintHealth.EXCELLENT == "excellent"

    def test_health_good(self):
        assert SprintHealth.GOOD == "good"

    def test_health_adequate(self):
        assert SprintHealth.ADEQUATE == "adequate"

    def test_health_struggling(self):
        assert SprintHealth.STRUGGLING == "struggling"

    def test_health_critical(self):
        assert SprintHealth.CRITICAL == "critical"


class TestModels:
    def test_velocity_record_defaults(self):
        r = VelocityRecord()
        assert r.id
        assert r.team_name == ""
        assert r.metric == VelocityMetric.STORY_POINTS
        assert r.trend == VelocityTrend.STABLE
        assert r.sprint_health == SprintHealth.ADEQUATE
        assert r.velocity_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_velocity_data_point_defaults(self):
        r = VelocityDataPoint()
        assert r.id
        assert r.team_name == ""
        assert r.metric == VelocityMetric.STORY_POINTS
        assert r.sprint_health == SprintHealth.ADEQUATE
        assert r.value == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = TeamVelocityReport()
        assert r.total_records == 0
        assert r.total_data_points == 0
        assert r.avg_velocity_score == 0.0
        assert r.by_metric == {}
        assert r.by_trend == {}
        assert r.underperforming_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordVelocity:
    def test_basic(self):
        eng = _engine()
        r = eng.record_velocity("team-a", velocity_score=80.0)
        assert r.team_name == "team-a"
        assert r.velocity_score == 80.0

    def test_with_sprint_health(self):
        eng = _engine()
        r = eng.record_velocity("team-b", sprint_health=SprintHealth.EXCELLENT)
        assert r.sprint_health == SprintHealth.EXCELLENT

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_velocity(f"team-{i}")
        assert len(eng._records) == 3


class TestGetVelocity:
    def test_found(self):
        eng = _engine()
        r = eng.record_velocity("team-a")
        assert eng.get_velocity(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_velocity("nonexistent") is None


class TestListVelocities:
    def test_list_all(self):
        eng = _engine()
        eng.record_velocity("team-a")
        eng.record_velocity("team-b")
        assert len(eng.list_velocities()) == 2

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_velocity("team-a")
        eng.record_velocity("team-b")
        results = eng.list_velocities(team_name="team-a")
        assert len(results) == 1

    def test_filter_by_metric(self):
        eng = _engine()
        eng.record_velocity("team-a", metric=VelocityMetric.DEPLOYMENTS)
        eng.record_velocity("team-b", metric=VelocityMetric.STORY_POINTS)
        results = eng.list_velocities(metric=VelocityMetric.DEPLOYMENTS)
        assert len(results) == 1


class TestAddDataPoint:
    def test_basic(self):
        eng = _engine()
        dp = eng.add_data_point("team-a", value=42.0)
        assert dp.team_name == "team-a"
        assert dp.value == 42.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_data_point(f"team-{i}")
        assert len(eng._data_points) == 2


class TestAnalyzeVelocityByTeam:
    def test_with_data(self):
        eng = _engine()
        eng.record_velocity("team-a", velocity_score=80.0)
        eng.record_velocity("team-a", velocity_score=70.0)
        result = eng.analyze_velocity_by_team("team-a")
        assert result["team_name"] == "team-a"
        assert result["total"] == 2
        assert result["avg_velocity_score"] == 75.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_velocity_by_team("ghost")
        assert result["status"] == "no_data"


class TestIdentifyUnderperformingTeams:
    def test_with_underperformers(self):
        eng = _engine(min_velocity_score=60.0)
        eng.record_velocity("team-a", velocity_score=40.0)
        eng.record_velocity("team-b", velocity_score=80.0)
        results = eng.identify_underperforming_teams()
        assert len(results) == 1
        assert results[0]["team_name"] == "team-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_underperforming_teams() == []


class TestRankByVelocityScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_velocity("team-a", velocity_score=60.0)
        eng.record_velocity("team-b", velocity_score=90.0)
        results = eng.rank_by_velocity_score()
        assert results[0]["team_name"] == "team-b"
        assert results[0]["avg_velocity_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_velocity_score() == []


class TestDetectVelocityTrends:
    def test_with_trends(self):
        eng = _engine()
        for i in range(5):
            eng.record_velocity("team-a", velocity_score=float(50 + i * 10))
        results = eng.detect_velocity_trends()
        assert len(results) == 1
        assert results[0]["team_name"] == "team-a"
        assert results[0]["trend"] == "accelerating"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_velocity_trends() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_velocity("team-a", velocity_score=40.0, sprint_health=SprintHealth.CRITICAL)
        eng.record_velocity("team-b", velocity_score=80.0, sprint_health=SprintHealth.GOOD)
        eng.add_data_point("team-a")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_data_points == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_velocity("team-a")
        eng.add_data_point("team-a")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._data_points) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_data_points"] == 0
        assert stats["metric_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_velocity("team-a", metric=VelocityMetric.DEPLOYMENTS)
        eng.record_velocity("team-b", metric=VelocityMetric.STORY_POINTS)
        eng.add_data_point("team-a")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_data_points"] == 1
        assert stats["unique_teams"] == 2
