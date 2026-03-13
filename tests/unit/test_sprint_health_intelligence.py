"""Tests for SprintHealthIntelligence."""

from __future__ import annotations

from shieldops.analytics.sprint_health_intelligence import (
    AntipatternType,
    HealthIndicator,
    SprintHealthIntelligence,
    SprintOutcome,
)


def _engine(**kw) -> SprintHealthIntelligence:
    return SprintHealthIntelligence(**kw)


class TestEnums:
    def test_sprint_outcome_values(self):
        for v in SprintOutcome:
            assert isinstance(v.value, str)

    def test_antipattern_type_values(self):
        for v in AntipatternType:
            assert isinstance(v.value, str)

    def test_health_indicator_values(self):
        for v in HealthIndicator:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(sprint_id="s1")
        assert r.sprint_id == "s1"

    def test_all_fields(self):
        eng = _engine()
        r = eng.add_record(
            sprint_id="s1",
            health_score=85.0,
            completion_pct=90.0,
        )
        assert r.health_score == 85.0

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(sprint_id=f"s-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(sprint_id="s1", health_score=80.0)
        a = eng.process(r.id)
        assert hasattr(a, "sprint_id")
        assert a.sprint_id == "s1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(sprint_id="s1")
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
        eng.add_record(sprint_id="s1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(sprint_id="s1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeSprintHealthScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(sprint_id="s1", health_score=85.0)
        result = eng.compute_sprint_health_score()
        assert len(result) == 1
        assert result[0]["health_score"] == 85.0

    def test_empty(self):
        r = _engine().compute_sprint_health_score()
        assert r == []


class TestDetectSprintAntipatterns:
    def test_with_antipattern(self):
        eng = _engine()
        eng.add_record(
            sprint_id="s1",
            antipattern=(AntipatternType.SCOPE_CREEP),
            scope_change_pct=50.0,
        )
        result = eng.detect_sprint_antipatterns()
        assert len(result) == 1
        assert result[0]["occurrences"] >= 1

    def test_empty(self):
        r = _engine().detect_sprint_antipatterns()
        assert r == []


class TestRankSprintsByPredictability:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(sprint_id="s1", completion_pct=95.0)
        eng.add_record(sprint_id="s2", completion_pct=60.0)
        result = eng.rank_sprints_by_predictability()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        eng = _engine()
        r = eng.rank_sprints_by_predictability()
        assert r == []
