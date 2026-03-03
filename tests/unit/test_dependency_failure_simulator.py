"""Tests for shieldops.operations.dependency_failure_simulator."""

from __future__ import annotations

from shieldops.operations.dependency_failure_simulator import (
    DependencyFailureSimulator,
    DependencySimulation,
    DependencySimulationReport,
    DependencyType,
    FallbackBehavior,
    SimulationAnalysis,
    SimulationMode,
)


def _engine(**kw) -> DependencyFailureSimulator:
    return DependencyFailureSimulator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_dep_type_database(self):
        assert DependencyType.DATABASE == "database"

    def test_dep_type_cache(self):
        assert DependencyType.CACHE == "cache"

    def test_dep_type_message_queue(self):
        assert DependencyType.MESSAGE_QUEUE == "message_queue"

    def test_dep_type_api(self):
        assert DependencyType.API == "api"

    def test_dep_type_dns(self):
        assert DependencyType.DNS == "dns"

    def test_mode_gradual(self):
        assert SimulationMode.GRADUAL == "gradual"

    def test_mode_sudden(self):
        assert SimulationMode.SUDDEN == "sudden"

    def test_mode_intermittent(self):
        assert SimulationMode.INTERMITTENT == "intermittent"

    def test_mode_partial(self):
        assert SimulationMode.PARTIAL == "partial"

    def test_mode_complete(self):
        assert SimulationMode.COMPLETE == "complete"

    def test_fallback_graceful_degradation(self):
        assert FallbackBehavior.GRACEFUL_DEGRADATION == "graceful_degradation"

    def test_fallback_circuit_break(self):
        assert FallbackBehavior.CIRCUIT_BREAK == "circuit_break"

    def test_fallback_retry(self):
        assert FallbackBehavior.RETRY == "retry"

    def test_fallback_failover(self):
        assert FallbackBehavior.FAILOVER == "failover"

    def test_fallback_error(self):
        assert FallbackBehavior.ERROR == "error"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_dependency_simulation_defaults(self):
        r = DependencySimulation()
        assert r.id
        assert r.dependency_type == DependencyType.DATABASE
        assert r.simulation_mode == SimulationMode.GRADUAL
        assert r.fallback_behavior == FallbackBehavior.GRACEFUL_DEGRADATION
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_simulation_analysis_defaults(self):
        a = SimulationAnalysis()
        assert a.id
        assert a.dependency_type == DependencyType.DATABASE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_dependency_simulation_report_defaults(self):
        r = DependencySimulationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_dependency_type == {}
        assert r.by_mode == {}
        assert r.by_fallback == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_defaults(self):
        eng = _engine()
        assert eng._max_records == 200000
        assert eng._threshold == 50.0
        assert eng._records == []
        assert eng._analyses == []

    def test_custom_max_records(self):
        eng = _engine(max_records=3000)
        assert eng._max_records == 3000

    def test_custom_threshold(self):
        eng = _engine(threshold=55.0)
        assert eng._threshold == 55.0


# ---------------------------------------------------------------------------
# record_simulation / get_simulation
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_record_basic(self):
        eng = _engine()
        r = eng.record_simulation(
            service="cache-svc",
            dependency_type=DependencyType.CACHE,
            simulation_mode=SimulationMode.SUDDEN,
            fallback_behavior=FallbackBehavior.CIRCUIT_BREAK,
            score=78.0,
            team="platform",
        )
        assert r.service == "cache-svc"
        assert r.dependency_type == DependencyType.CACHE
        assert r.simulation_mode == SimulationMode.SUDDEN
        assert r.fallback_behavior == FallbackBehavior.CIRCUIT_BREAK
        assert r.score == 78.0
        assert r.team == "platform"

    def test_record_stored(self):
        eng = _engine()
        eng.record_simulation(service="svc-a")
        assert len(eng._records) == 1

    def test_get_found(self):
        eng = _engine()
        r = eng.record_simulation(service="svc-a", score=62.0)
        result = eng.get_simulation(r.id)
        assert result is not None
        assert result.score == 62.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_simulation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_simulations
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_simulation(service="svc-a")
        eng.record_simulation(service="svc-b")
        assert len(eng.list_simulations()) == 2

    def test_filter_by_dependency_type(self):
        eng = _engine()
        eng.record_simulation(service="svc-a", dependency_type=DependencyType.DATABASE)
        eng.record_simulation(service="svc-b", dependency_type=DependencyType.DNS)
        results = eng.list_simulations(dependency_type=DependencyType.DATABASE)
        assert len(results) == 1

    def test_filter_by_mode(self):
        eng = _engine()
        eng.record_simulation(service="svc-a", simulation_mode=SimulationMode.GRADUAL)
        eng.record_simulation(service="svc-b", simulation_mode=SimulationMode.COMPLETE)
        results = eng.list_simulations(simulation_mode=SimulationMode.GRADUAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_simulation(service="svc-a", team="platform")
        eng.record_simulation(service="svc-b", team="data")
        assert len(eng.list_simulations(team="platform")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_simulation(service=f"svc-{i}")
        assert len(eng.list_simulations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            dependency_type=DependencyType.MESSAGE_QUEUE,
            analysis_score=35.0,
            threshold=50.0,
            breached=True,
            description="mq failure handled poorly",
        )
        assert a.dependency_type == DependencyType.MESSAGE_QUEUE
        assert a.analysis_score == 35.0
        assert a.breached is True

    def test_stored(self):
        eng = _engine()
        eng.add_analysis()
        assert len(eng._analyses) == 1

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _ in range(5):
            eng.add_analysis()
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_simulation(service="s1", dependency_type=DependencyType.API, score=90.0)
        eng.record_simulation(service="s2", dependency_type=DependencyType.API, score=70.0)
        result = eng.analyze_distribution()
        assert "api" in result
        assert result["api"]["count"] == 2
        assert result["api"]["avg_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_fallback_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_simulation(service="svc-a", score=60.0)
        eng.record_simulation(service="svc-b", score=90.0)
        results = eng.identify_fallback_gaps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_simulation(service="svc-a", score=55.0)
        eng.record_simulation(service="svc-b", score=35.0)
        results = eng.identify_fallback_gaps()
        assert results[0]["score"] == 35.0


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_simulation(service="svc-a", score=90.0)
        eng.record_simulation(service="svc-b", score=40.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "svc-b"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_score_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_score_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_score_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_score_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_simulation(
            service="svc-a",
            dependency_type=DependencyType.CACHE,
            simulation_mode=SimulationMode.INTERMITTENT,
            fallback_behavior=FallbackBehavior.RETRY,
            score=45.0,
        )
        report = eng.generate_report()
        assert isinstance(report, DependencySimulationReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_simulation(service="svc-a")
        eng.add_analysis()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_simulation(
            service="svc-a",
            dependency_type=DependencyType.DATABASE,
            team="data",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert "database" in stats["dependency_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_simulation(service=f"svc-{i}")
        assert len(eng._records) == 3
