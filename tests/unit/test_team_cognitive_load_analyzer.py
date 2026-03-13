"""Tests for TeamCognitiveLoadAnalyzer."""

from __future__ import annotations

from shieldops.analytics.team_cognitive_load_analyzer import (
    LoadLevel,
    LoadSource,
    LoadType,
    TeamCognitiveLoadAnalyzer,
)


def _engine(**kw) -> TeamCognitiveLoadAnalyzer:
    return TeamCognitiveLoadAnalyzer(**kw)


class TestEnums:
    def test_load_type_values(self):
        for v in LoadType:
            assert isinstance(v.value, str)

    def test_load_level_values(self):
        for v in LoadLevel:
            assert isinstance(v.value, str)

    def test_load_source_values(self):
        for v in LoadSource:
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
            load_score=75.0,
            services_owned=5,
        )
        assert r.load_score == 75.0

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(team_id=f"t-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(team_id="t1", load_score=60.0)
        a = eng.process(r.id)
        assert hasattr(a, "team_id")
        assert a.team_id == "t1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


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


class TestComputeCognitiveLoadIndex:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            team_id="t1",
            load_score=70.0,
            services_owned=3,
        )
        result = eng.compute_cognitive_load_index()
        assert len(result) == 1
        assert result[0]["load_index"] == 70.0

    def test_empty(self):
        r = _engine().compute_cognitive_load_index()
        assert r == []


class TestDetectOverloadPatterns:
    def test_with_overload(self):
        eng = _engine()
        for _ in range(5):
            eng.add_record(
                team_id="t1",
                level=LoadLevel.OVERLOADED,
            )
        result = eng.detect_overload_patterns()
        assert len(result) == 1
        assert result[0]["overload_ratio"] == 1.0

    def test_empty(self):
        r = _engine().detect_overload_patterns()
        assert r == []


class TestRankTeamsByLoadSustainability:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(team_id="t1", load_score=30.0)
        eng.add_record(team_id="t2", load_score=80.0)
        result = eng.rank_teams_by_load_sustainability()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        eng = _engine()
        r = eng.rank_teams_by_load_sustainability()
        assert r == []
