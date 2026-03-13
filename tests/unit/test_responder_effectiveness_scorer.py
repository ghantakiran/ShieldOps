"""Tests for ResponderEffectivenessScorer."""

from __future__ import annotations

from shieldops.analytics.responder_effectiveness_scorer import (
    BenchmarkScope,
    MetricCategory,
    PerformanceTier,
    ResponderEffectivenessScorer,
)


def _engine(**kw) -> ResponderEffectivenessScorer:
    return ResponderEffectivenessScorer(**kw)


class TestEnums:
    def test_performance_tier_values(self):
        for v in PerformanceTier:
            assert isinstance(v.value, str)

    def test_metric_category_values(self):
        for v in MetricCategory:
            assert isinstance(v.value, str)

    def test_benchmark_scope_values(self):
        for v in BenchmarkScope:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(responder_id="r1")
        assert r.responder_id == "r1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(responder_id=f"r-{i}")
        assert len(eng._records) == 5

    def test_with_params(self):
        eng = _engine()
        r = eng.add_record(
            responder_id="r1",
            score=85.0,
            incidents_resolved=10,
        )
        assert r.score == 85.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(responder_id="r1", score=90.0)
        a = eng.process(r.id)
        assert hasattr(a, "responder_id")
        assert a.responder_id == "r1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(responder_id="r1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(responder_id="r1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(responder_id="r1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestScoreResponderPerformance:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            responder_id="r1",
            score=85.0,
            incidents_resolved=10,
        )
        result = eng.score_responder_performance()
        assert len(result) == 1
        assert "avg_score" in result[0]

    def test_empty(self):
        r = _engine().score_responder_performance()
        assert r == []


class TestBenchmarkAgainstPeers:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            responder_id="r1",
            team="sre",
            score=90.0,
        )
        eng.add_record(
            responder_id="r2",
            team="sre",
            score=70.0,
        )
        result = eng.benchmark_against_peers()
        assert len(result) == 2

    def test_empty(self):
        r = _engine().benchmark_against_peers()
        assert r == []


class TestIdentifySkillDevelopmentAreas:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            responder_id="r1",
            metric_category=MetricCategory.SPEED,
            score=90.0,
        )
        eng.add_record(
            responder_id="r1",
            metric_category=(MetricCategory.QUALITY),
            score=50.0,
        )
        result = eng.identify_skill_development_areas()
        assert len(result) == 1
        assert result[0]["weakest_area"] == "quality"

    def test_empty(self):
        r = _engine().identify_skill_development_areas()
        assert r == []
