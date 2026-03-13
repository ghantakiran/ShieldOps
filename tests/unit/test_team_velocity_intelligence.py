"""Tests for TeamVelocityIntelligence."""

from __future__ import annotations

from shieldops.analytics.team_velocity_intelligence import (
    TeamSize,
    TeamVelocityIntelligence,
    TrendDirection,
    VelocityMetric,
)


def _engine(**kw) -> TeamVelocityIntelligence:
    return TeamVelocityIntelligence(**kw)


class TestEnums:
    def test_velocity_metric_values(self):
        for v in VelocityMetric:
            assert isinstance(v.value, str)

    def test_trend_direction_values(self):
        for v in TrendDirection:
            assert isinstance(v.value, str)

    def test_team_size_values(self):
        for v in TeamSize:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(team_id="t1")
        assert r.team_id == "t1"

    def test_all_fields(self):
        eng = _engine()
        r = eng.add_record(
            team_id="t1",
            metric=VelocityMetric.DEPLOYMENTS,
            velocity_value=42.0,
        )
        assert r.velocity_value == 42.0

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(team_id=f"t-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(team_id="t1", velocity_value=50.0)
        a = eng.process(r.id)
        assert hasattr(a, "team_id")
        assert a.team_id == "t1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_consistency(self):
        eng = _engine()
        r = eng.add_record(team_id="t1", velocity_value=50.0)
        eng.add_record(team_id="t1", velocity_value=50.0)
        a = eng.process(r.id)
        assert a.consistency_score == 100.0


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(team_id="t1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(team_id="t1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(team_id="t1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeVelocityTrends:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(team_id="t1", velocity_value=50.0)
        result = eng.compute_velocity_trends()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().compute_velocity_trends() == []


class TestDetectVelocityAnomalies:
    def test_with_anomaly(self):
        eng = _engine()
        for _ in range(10):
            eng.add_record(team_id="t1", velocity_value=50.0)
        eng.add_record(team_id="t1", velocity_value=200.0)
        result = eng.detect_velocity_anomalies()
        assert len(result) >= 1

    def test_empty(self):
        r = _engine().detect_velocity_anomalies()
        assert r == []


class TestRankTeamsByDeliveryConsistency:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(team_id="t1", velocity_value=50.0)
        eng.add_record(team_id="t2", velocity_value=80.0)
        result = eng.rank_teams_by_delivery_consistency()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine()
        assert r.rank_teams_by_delivery_consistency() == []
