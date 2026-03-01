"""Tests for shieldops.changes.change_velocity — ChangeVelocityTracker."""

from __future__ import annotations

from shieldops.changes.change_velocity import (
    ChangeScope,
    ChangeVelocityReport,
    ChangeVelocityTracker,
    VelocityMetric,
    VelocityRecord,
    VelocityRisk,
    VelocityTrend,
)


def _engine(**kw) -> ChangeVelocityTracker:
    return ChangeVelocityTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_trend_accelerating(self):
        assert VelocityTrend.ACCELERATING == "accelerating"

    def test_trend_stable(self):
        assert VelocityTrend.STABLE == "stable"

    def test_trend_decelerating(self):
        assert VelocityTrend.DECELERATING == "decelerating"

    def test_trend_stalled(self):
        assert VelocityTrend.STALLED == "stalled"

    def test_trend_volatile(self):
        assert VelocityTrend.VOLATILE == "volatile"

    def test_scope_major(self):
        assert ChangeScope.MAJOR == "major"

    def test_scope_minor(self):
        assert ChangeScope.MINOR == "minor"

    def test_scope_patch(self):
        assert ChangeScope.PATCH == "patch"

    def test_scope_hotfix(self):
        assert ChangeScope.HOTFIX == "hotfix"

    def test_scope_config(self):
        assert ChangeScope.CONFIG == "config"

    def test_risk_high(self):
        assert VelocityRisk.HIGH == "high"

    def test_risk_moderate(self):
        assert VelocityRisk.MODERATE == "moderate"

    def test_risk_low(self):
        assert VelocityRisk.LOW == "low"

    def test_risk_minimal(self):
        assert VelocityRisk.MINIMAL == "minimal"

    def test_risk_none(self):
        assert VelocityRisk.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_velocity_record_defaults(self):
        r = VelocityRecord()
        assert r.id
        assert r.period_id == ""
        assert r.velocity_trend == VelocityTrend.STABLE
        assert r.change_scope == ChangeScope.PATCH
        assert r.velocity_risk == VelocityRisk.NONE
        assert r.changes_per_day == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_velocity_metric_defaults(self):
        m = VelocityMetric()
        assert m.id
        assert m.period_id == ""
        assert m.velocity_trend == VelocityTrend.STABLE
        assert m.metric_value == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_change_velocity_report_defaults(self):
        r = ChangeVelocityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.high_velocity_count == 0
        assert r.avg_changes_per_day == 0.0
        assert r.by_trend == {}
        assert r.by_scope == {}
        assert r.by_risk == {}
        assert r.top_fast_movers == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_velocity
# ---------------------------------------------------------------------------


class TestRecordVelocity:
    def test_basic(self):
        eng = _engine()
        r = eng.record_velocity(
            period_id="PER-001",
            velocity_trend=VelocityTrend.ACCELERATING,
            change_scope=ChangeScope.MAJOR,
            velocity_risk=VelocityRisk.HIGH,
            changes_per_day=60.0,
            service="api-gateway",
            team="sre",
        )
        assert r.period_id == "PER-001"
        assert r.velocity_trend == VelocityTrend.ACCELERATING
        assert r.change_scope == ChangeScope.MAJOR
        assert r.velocity_risk == VelocityRisk.HIGH
        assert r.changes_per_day == 60.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_velocity(period_id=f"PER-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_velocity
# ---------------------------------------------------------------------------


class TestGetVelocity:
    def test_found(self):
        eng = _engine()
        r = eng.record_velocity(
            period_id="PER-001",
            velocity_trend=VelocityTrend.ACCELERATING,
        )
        result = eng.get_velocity(r.id)
        assert result is not None
        assert result.velocity_trend == VelocityTrend.ACCELERATING

    def test_not_found(self):
        eng = _engine()
        assert eng.get_velocity("nonexistent") is None


# ---------------------------------------------------------------------------
# list_velocities
# ---------------------------------------------------------------------------


class TestListVelocities:
    def test_list_all(self):
        eng = _engine()
        eng.record_velocity(period_id="PER-001")
        eng.record_velocity(period_id="PER-002")
        assert len(eng.list_velocities()) == 2

    def test_filter_by_trend(self):
        eng = _engine()
        eng.record_velocity(
            period_id="PER-001",
            velocity_trend=VelocityTrend.ACCELERATING,
        )
        eng.record_velocity(
            period_id="PER-002",
            velocity_trend=VelocityTrend.DECELERATING,
        )
        results = eng.list_velocities(trend=VelocityTrend.ACCELERATING)
        assert len(results) == 1

    def test_filter_by_scope(self):
        eng = _engine()
        eng.record_velocity(
            period_id="PER-001",
            change_scope=ChangeScope.MAJOR,
        )
        eng.record_velocity(
            period_id="PER-002",
            change_scope=ChangeScope.PATCH,
        )
        results = eng.list_velocities(scope=ChangeScope.MAJOR)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_velocity(period_id="PER-001", service="api-gateway")
        eng.record_velocity(period_id="PER-002", service="auth-svc")
        results = eng.list_velocities(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_velocity(period_id="PER-001", team="sre")
        eng.record_velocity(period_id="PER-002", team="platform")
        results = eng.list_velocities(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_velocity(period_id=f"PER-{i}")
        assert len(eng.list_velocities(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            period_id="PER-001",
            velocity_trend=VelocityTrend.ACCELERATING,
            metric_value=85.0,
            threshold=90.0,
            breached=True,
            description="Velocity spike detected",
        )
        assert m.period_id == "PER-001"
        assert m.velocity_trend == VelocityTrend.ACCELERATING
        assert m.metric_value == 85.0
        assert m.threshold == 90.0
        assert m.breached is True
        assert m.description == "Velocity spike detected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(period_id=f"PER-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_velocity_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeVelocityDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_velocity(
            period_id="PER-001",
            velocity_trend=VelocityTrend.STABLE,
            changes_per_day=10.0,
        )
        eng.record_velocity(
            period_id="PER-002",
            velocity_trend=VelocityTrend.STABLE,
            changes_per_day=20.0,
        )
        result = eng.analyze_velocity_distribution()
        assert "stable" in result
        assert result["stable"]["count"] == 2
        assert result["stable"]["avg_changes_per_day"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_velocity_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_velocity_services
# ---------------------------------------------------------------------------


class TestIdentifyHighVelocityServices:
    def test_detects(self):
        eng = _engine()
        eng.record_velocity(
            period_id="PER-001",
            changes_per_day=60.0,
        )
        eng.record_velocity(
            period_id="PER-002",
            changes_per_day=10.0,
        )
        results = eng.identify_high_velocity_services()
        assert len(results) == 1
        assert results[0]["period_id"] == "PER-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_velocity_services() == []


# ---------------------------------------------------------------------------
# rank_by_velocity
# ---------------------------------------------------------------------------


class TestRankByVelocity:
    def test_ranked(self):
        eng = _engine()
        eng.record_velocity(
            period_id="PER-001",
            service="api-gateway",
            changes_per_day=120.0,
        )
        eng.record_velocity(
            period_id="PER-002",
            service="auth-svc",
            changes_per_day=30.0,
        )
        eng.record_velocity(
            period_id="PER-003",
            service="api-gateway",
            changes_per_day=80.0,
        )
        results = eng.rank_by_velocity()
        assert len(results) == 2
        # descending: api-gateway (100.0) first, auth-svc (30.0) second
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_changes_per_day"] == 100.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_velocity() == []


# ---------------------------------------------------------------------------
# detect_velocity_trends
# ---------------------------------------------------------------------------


class TestDetectVelocityTrends:
    def test_stable(self):
        eng = _engine()
        for val in [60.0, 60.0, 60.0, 60.0]:
            eng.add_metric(period_id="PER-1", metric_value=val)
        result = eng.detect_velocity_trends()
        assert result["trend"] == "stable"

    def test_accelerating(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_metric(period_id="PER-1", metric_value=val)
        result = eng.detect_velocity_trends()
        assert result["trend"] == "accelerating"
        assert result["delta"] > 0

    def test_decelerating(self):
        eng = _engine()
        for val in [20.0, 20.0, 5.0, 5.0]:
            eng.add_metric(period_id="PER-1", metric_value=val)
        result = eng.detect_velocity_trends()
        assert result["trend"] == "decelerating"
        assert result["delta"] < 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_velocity_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_velocity(
            period_id="PER-001",
            velocity_trend=VelocityTrend.ACCELERATING,
            change_scope=ChangeScope.MAJOR,
            velocity_risk=VelocityRisk.HIGH,
            changes_per_day=60.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, ChangeVelocityReport)
        assert report.total_records == 1
        assert report.high_velocity_count == 1
        assert len(report.top_fast_movers) >= 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_velocity(period_id="PER-001")
        eng.add_metric(period_id="PER-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["trend_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_velocity(
            period_id="PER-001",
            velocity_trend=VelocityTrend.STABLE,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "stable" in stats["trend_distribution"]
