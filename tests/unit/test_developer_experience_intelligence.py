"""Tests for DeveloperExperienceIntelligence."""

from __future__ import annotations

from shieldops.analytics.developer_experience_intelligence import (
    DeveloperExperienceIntelligence,
    DevexDimension,
    FrictionType,
    SatisfactionLevel,
)


def _engine(**kw) -> DeveloperExperienceIntelligence:
    return DeveloperExperienceIntelligence(**kw)


class TestEnums:
    def test_devex_dimension_values(self):
        for v in DevexDimension:
            assert isinstance(v.value, str)

    def test_friction_type_values(self):
        for v in FrictionType:
            assert isinstance(v.value, str)

    def test_satisfaction_level_values(self):
        for v in SatisfactionLevel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(tool_id="t1")
        assert r.tool_id == "t1"

    def test_all_fields(self):
        eng = _engine()
        r = eng.add_record(
            tool_id="t1",
            score=85.0,
            time_lost_minutes=30.0,
        )
        assert r.score == 85.0

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(tool_id=f"t-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(tool_id="t1", score=75.0)
        a = eng.process(r.id)
        assert hasattr(a, "tool_id")
        assert a.tool_id == "t1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(tool_id="t1")
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
        eng.add_record(tool_id="t1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(tool_id="t1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeDevexScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(tool_id="t1", score=80.0)
        result = eng.compute_devex_score()
        assert len(result) == 1
        assert result[0]["devex_score"] == 80.0

    def test_empty(self):
        assert _engine().compute_devex_score() == []


class TestDetectFrictionPoints:
    def test_with_friction(self):
        eng = _engine()
        eng.add_record(
            tool_id="t1",
            satisfaction=(SatisfactionLevel.FRUSTRATED),
            friction=FrictionType.BUILD,
            time_lost_minutes=60.0,
        )
        result = eng.detect_friction_points()
        assert len(result) == 1
        assert result[0]["total_time_lost"] == 60.0

    def test_empty(self):
        r = _engine().detect_friction_points()
        assert r == []


class TestRankToolsByDeveloperSatisfaction:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(tool_id="t1", score=90.0)
        eng.add_record(tool_id="t2", score=60.0)
        result = eng.rank_tools_by_developer_satisfaction()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        eng = _engine()
        r = eng.rank_tools_by_developer_satisfaction()
        assert r == []
