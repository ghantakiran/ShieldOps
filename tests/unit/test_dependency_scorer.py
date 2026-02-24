"""Tests for shieldops.topology.dependency_scorer — DependencyHealthScorer."""

from __future__ import annotations

from shieldops.topology.dependency_scorer import (
    CircuitBreakerRecommendation,
    DegradationType,
    DependencyHealthScorer,
    DependencyScore,
    HealthGrade,
    PropagationRisk,
    PropagationSimulation,
)


def _engine(**kw) -> DependencyHealthScorer:
    return DependencyHealthScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_grade_a(self):
        assert HealthGrade.A == "A"

    def test_grade_b(self):
        assert HealthGrade.B == "B"

    def test_grade_c(self):
        assert HealthGrade.C == "C"

    def test_grade_d(self):
        assert HealthGrade.D == "D"

    def test_grade_f(self):
        assert HealthGrade.F == "F"

    def test_degradation_latency(self):
        assert DegradationType.LATENCY == "latency"

    def test_degradation_error(self):
        assert DegradationType.ERROR_RATE == "error_rate"

    def test_degradation_availability(self):
        assert DegradationType.AVAILABILITY == "availability"

    def test_degradation_throughput(self):
        assert DegradationType.THROUGHPUT == "throughput"

    def test_degradation_timeout(self):
        assert DegradationType.TIMEOUT == "timeout"

    def test_prop_none(self):
        assert PropagationRisk.NONE == "none"

    def test_prop_contained(self):
        assert PropagationRisk.CONTAINED == "contained"

    def test_prop_spreading(self):
        assert PropagationRisk.SPREADING == "spreading"

    def test_prop_cascade(self):
        assert PropagationRisk.CASCADE == "cascade"

    def test_prop_catastrophic(self):
        assert PropagationRisk.CATASTROPHIC == "catastrophic"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_score_defaults(self):
        d = DependencyScore()
        assert d.id
        assert d.grade == HealthGrade.A
        assert d.availability_pct == 100.0

    def test_simulation_defaults(self):
        s = PropagationSimulation()
        assert s.propagation_risk == PropagationRisk.NONE

    def test_recommendation_defaults(self):
        r = CircuitBreakerRecommendation()
        assert r.recommended is False


# ---------------------------------------------------------------------------
# register_dependency
# ---------------------------------------------------------------------------


class TestRegisterDependency:
    def test_basic_register(self):
        eng = _engine()
        dep = eng.register_dependency("redis", service="cache")
        assert dep.name == "redis"
        assert dep.service == "cache"

    def test_unique_ids(self):
        eng = _engine()
        d1 = eng.register_dependency("redis")
        d2 = eng.register_dependency("postgres")
        assert d1.id != d2.id

    def test_eviction_at_max(self):
        eng = _engine(max_dependencies=3)
        for i in range(5):
            eng.register_dependency(f"dep-{i}")
        assert len(eng._dependencies) == 3

    def test_with_dependents(self):
        eng = _engine()
        eng.register_dependency("redis", dependents=["svc-a", "svc-b"])
        assert "redis" in eng._dep_graph


# ---------------------------------------------------------------------------
# get / list dependencies
# ---------------------------------------------------------------------------


class TestGetDependency:
    def test_found(self):
        eng = _engine()
        dep = eng.register_dependency("redis")
        assert eng.get_dependency(dep.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_dependency("nonexistent") is None


class TestListDependencies:
    def test_list_all(self):
        eng = _engine()
        eng.register_dependency("redis")
        eng.register_dependency("postgres")
        assert len(eng.list_dependencies()) == 2

    def test_filter_by_grade(self):
        eng = _engine()
        eng.register_dependency("healthy")
        results = eng.list_dependencies(grade=HealthGrade.A)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# record_health_check
# ---------------------------------------------------------------------------


class TestRecordHealthCheck:
    def test_basic_check(self):
        eng = _engine()
        dep = eng.register_dependency("redis")
        result = eng.record_health_check(dep.id, latency_ms=5.0)
        assert result["grade"] == "A"

    def test_failed_check(self):
        eng = _engine()
        dep = eng.register_dependency("redis")
        for _ in range(10):
            eng.record_health_check(dep.id, latency_ms=100.0, success=False, error_rate=0.5)
        assert dep.grade in (HealthGrade.D, HealthGrade.F)

    def test_invalid_dep(self):
        eng = _engine()
        result = eng.record_health_check("bad_id")
        assert result.get("error") == "dependency_not_found"


# ---------------------------------------------------------------------------
# compute_health_score
# ---------------------------------------------------------------------------


class TestComputeHealthScore:
    def test_score(self):
        eng = _engine()
        dep = eng.register_dependency("redis")
        eng.record_health_check(dep.id, latency_ms=5.0)
        score = eng.compute_health_score(dep.id)
        assert score is not None
        assert score["grade"] == "A"

    def test_score_not_found(self):
        eng = _engine()
        assert eng.compute_health_score("bad") is None


# ---------------------------------------------------------------------------
# simulate_failure
# ---------------------------------------------------------------------------


class TestSimulateFailure:
    def test_no_impact(self):
        eng = _engine()
        eng.register_dependency("isolated")
        sim = eng.simulate_failure("isolated")
        assert sim.propagation_risk == PropagationRisk.NONE

    def test_with_dependents(self):
        eng = _engine()
        eng.register_dependency("redis", dependents=["svc-a", "svc-b"])
        sim = eng.simulate_failure("redis")
        assert len(sim.affected_services) >= 2


# ---------------------------------------------------------------------------
# circuit breakers / degraded / risk ranking / stats
# ---------------------------------------------------------------------------


class TestCircuitBreakers:
    def test_no_recommendations(self):
        eng = _engine()
        eng.register_dependency("healthy")
        recs = eng.recommend_circuit_breakers()
        assert len(recs) == 0

    def test_recommendation_for_degraded(self):
        eng = _engine()
        dep = eng.register_dependency("bad")
        for _ in range(20):
            eng.record_health_check(dep.id, success=False, error_rate=0.5)
        recs = eng.recommend_circuit_breakers()
        assert len(recs) >= 1


class TestDegradedDependencies:
    def test_none_degraded(self):
        eng = _engine()
        eng.register_dependency("healthy")
        assert len(eng.get_degraded_dependencies()) == 0


class TestRiskRanking:
    def test_ranking(self):
        eng = _engine()
        eng.register_dependency("redis")
        eng.register_dependency("postgres")
        ranking = eng.get_risk_ranking()
        assert len(ranking) == 2


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_dependencies"] == 0

    def test_populated_stats(self):
        eng = _engine()
        eng.register_dependency("redis")
        eng.simulate_failure("redis")
        stats = eng.get_stats()
        assert stats["total_dependencies"] == 1
        assert stats["total_simulations"] == 1
