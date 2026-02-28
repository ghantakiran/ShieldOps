"""Tests for shieldops.topology.service_mesh_intel — ServiceMeshIntelligence."""

from __future__ import annotations

from shieldops.topology.service_mesh_intel import (
    MeshAntiPattern,
    MeshHealth,
    MeshPattern,
    MeshRecord,
    MeshRule,
    ServiceMeshIntelligence,
    ServiceMeshReport,
)


def _engine(**kw) -> ServiceMeshIntelligence:
    return ServiceMeshIntelligence(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # MeshPattern (5)
    def test_pattern_direct_call(self):
        assert MeshPattern.DIRECT_CALL == "direct_call"

    def test_pattern_load_balanced(self):
        assert MeshPattern.LOAD_BALANCED == "load_balanced"

    def test_pattern_circuit_broken(self):
        assert MeshPattern.CIRCUIT_BROKEN == "circuit_broken"

    def test_pattern_retry_loop(self):
        assert MeshPattern.RETRY_LOOP == "retry_loop"

    def test_pattern_timeout_cascade(self):
        assert MeshPattern.TIMEOUT_CASCADE == "timeout_cascade"

    # MeshHealth (5)
    def test_health_optimal(self):
        assert MeshHealth.OPTIMAL == "optimal"

    def test_health_healthy(self):
        assert MeshHealth.HEALTHY == "healthy"

    def test_health_degraded(self):
        assert MeshHealth.DEGRADED == "degraded"

    def test_health_unhealthy(self):
        assert MeshHealth.UNHEALTHY == "unhealthy"

    def test_health_critical(self):
        assert MeshHealth.CRITICAL == "critical"

    # MeshAntiPattern (5)
    def test_ap_unnecessary_hop(self):
        assert MeshAntiPattern.UNNECESSARY_HOP == "unnecessary_hop"

    def test_ap_circular_dependency(self):
        assert MeshAntiPattern.CIRCULAR_DEPENDENCY == "circular_dependency"

    def test_ap_chatty_service(self):
        assert MeshAntiPattern.CHATTY_SERVICE == "chatty_service"

    def test_ap_single_point_failure(self):
        assert MeshAntiPattern.SINGLE_POINT_FAILURE == "single_point_failure"

    def test_ap_tight_coupling(self):
        assert MeshAntiPattern.TIGHT_COUPLING == "tight_coupling"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_mesh_record_defaults(self):
        r = MeshRecord()
        assert r.id
        assert r.service_name == ""
        assert r.pattern == MeshPattern.DIRECT_CALL
        assert r.health == MeshHealth.OPTIMAL
        assert r.anti_pattern == MeshAntiPattern.UNNECESSARY_HOP
        assert r.latency_ms == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_mesh_rule_defaults(self):
        r = MeshRule()
        assert r.id
        assert r.rule_name == ""
        assert r.pattern == MeshPattern.DIRECT_CALL
        assert r.health == MeshHealth.OPTIMAL
        assert r.max_latency_ms == 500.0
        assert r.auto_optimize is False
        assert r.created_at > 0

    def test_service_mesh_report_defaults(self):
        r = ServiceMeshReport()
        assert r.total_observations == 0
        assert r.total_rules == 0
        assert r.healthy_rate_pct == 0.0
        assert r.by_pattern == {}
        assert r.by_health == {}
        assert r.anti_pattern_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_observation
# -------------------------------------------------------------------


class TestRecordObservation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_observation(
            "svc-a",
            pattern=MeshPattern.DIRECT_CALL,
            health=MeshHealth.OPTIMAL,
        )
        assert r.service_name == "svc-a"
        assert r.pattern == MeshPattern.DIRECT_CALL

    def test_with_health(self):
        eng = _engine()
        r = eng.record_observation(
            "svc-b",
            health=MeshHealth.DEGRADED,
        )
        assert r.health == MeshHealth.DEGRADED

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_observation(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_observation
# -------------------------------------------------------------------


class TestGetObservation:
    def test_found(self):
        eng = _engine()
        r = eng.record_observation("svc-a")
        assert eng.get_observation(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_observation("nonexistent") is None


# -------------------------------------------------------------------
# list_observations
# -------------------------------------------------------------------


class TestListObservations:
    def test_list_all(self):
        eng = _engine()
        eng.record_observation("svc-a")
        eng.record_observation("svc-b")
        assert len(eng.list_observations()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_observation("svc-a")
        eng.record_observation("svc-b")
        results = eng.list_observations(
            service_name="svc-a",
        )
        assert len(results) == 1

    def test_filter_by_pattern(self):
        eng = _engine()
        eng.record_observation(
            "svc-a",
            pattern=MeshPattern.CIRCUIT_BROKEN,
        )
        eng.record_observation(
            "svc-b",
            pattern=MeshPattern.RETRY_LOOP,
        )
        results = eng.list_observations(
            pattern=MeshPattern.CIRCUIT_BROKEN,
        )
        assert len(results) == 1


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        p = eng.add_rule(
            "latency-check",
            pattern=MeshPattern.DIRECT_CALL,
            health=MeshHealth.OPTIMAL,
            max_latency_ms=250.0,
            auto_optimize=True,
        )
        assert p.rule_name == "latency-check"
        assert p.max_latency_ms == 250.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rule(f"rule-{i}")
        assert len(eng._rules) == 2


# -------------------------------------------------------------------
# analyze_mesh_health
# -------------------------------------------------------------------


class TestAnalyzeMeshHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_observation(
            "svc-a",
            health=MeshHealth.OPTIMAL,
            latency_ms=100.0,
        )
        eng.record_observation(
            "svc-a",
            health=MeshHealth.DEGRADED,
            latency_ms=200.0,
        )
        result = eng.analyze_mesh_health("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["observation_count"] == 2
        assert result["healthy_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_mesh_health("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_anti_patterns
# -------------------------------------------------------------------


class TestIdentifyAntiPatterns:
    def test_with_anti_patterns(self):
        eng = _engine()
        eng.record_observation(
            "svc-a",
            health=MeshHealth.DEGRADED,
        )
        eng.record_observation(
            "svc-a",
            health=MeshHealth.UNHEALTHY,
        )
        eng.record_observation(
            "svc-b",
            health=MeshHealth.OPTIMAL,
        )
        results = eng.identify_anti_patterns()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_anti_patterns() == []


# -------------------------------------------------------------------
# rank_by_latency
# -------------------------------------------------------------------


class TestRankByLatency:
    def test_with_data(self):
        eng = _engine()
        eng.record_observation(
            "svc-a",
            latency_ms=500.0,
        )
        eng.record_observation(
            "svc-a",
            latency_ms=300.0,
        )
        eng.record_observation(
            "svc-b",
            latency_ms=100.0,
        )
        results = eng.rank_by_latency()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["avg_latency_ms"] == 400.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_latency() == []


# -------------------------------------------------------------------
# detect_mesh_issues
# -------------------------------------------------------------------


class TestDetectMeshIssues:
    def test_with_issues(self):
        eng = _engine()
        for _ in range(5):
            eng.record_observation(
                "svc-a",
                health=MeshHealth.DEGRADED,
            )
        eng.record_observation(
            "svc-b",
            health=MeshHealth.OPTIMAL,
        )
        results = eng.detect_mesh_issues()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["issue_detected"] is True

    def test_no_issues(self):
        eng = _engine()
        eng.record_observation(
            "svc-a",
            health=MeshHealth.DEGRADED,
        )
        assert eng.detect_mesh_issues() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_observation(
            "svc-a",
            health=MeshHealth.OPTIMAL,
        )
        eng.record_observation(
            "svc-b",
            health=MeshHealth.DEGRADED,
        )
        eng.record_observation(
            "svc-b",
            health=MeshHealth.DEGRADED,
        )
        eng.add_rule("rule-1")
        report = eng.generate_report()
        assert report.total_observations == 3
        assert report.total_rules == 1
        assert report.by_pattern != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_observations == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_observation("svc-a")
        eng.add_rule("rule-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_observations"] == 0
        assert stats["total_rules"] == 0
        assert stats["pattern_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_observation(
            "svc-a",
            pattern=MeshPattern.DIRECT_CALL,
        )
        eng.record_observation(
            "svc-b",
            pattern=MeshPattern.CIRCUIT_BROKEN,
        )
        eng.add_rule("r1")
        stats = eng.get_stats()
        assert stats["total_observations"] == 2
        assert stats["total_rules"] == 1
        assert stats["unique_services"] == 2
