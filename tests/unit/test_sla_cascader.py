"""Tests for shieldops.sla.sla_cascader — ServiceSLACascader."""

from __future__ import annotations

from shieldops.sla.sla_cascader import (
    CascadeImpact,
    CascadePath,
    CascadeRecord,
    CascadeReport,
    DependencyRelation,
    PropagationMode,
    ServiceSLACascader,
)


def _engine(**kw) -> ServiceSLACascader:
    return ServiceSLACascader(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # CascadeImpact (5)
    def test_impact_none(self):
        assert CascadeImpact.NONE == "none"

    def test_impact_degraded(self):
        assert CascadeImpact.DEGRADED == "degraded"

    def test_impact_partial_outage(self):
        assert CascadeImpact.PARTIAL_OUTAGE == "partial_outage"

    def test_impact_major_outage(self):
        assert CascadeImpact.MAJOR_OUTAGE == "major_outage"

    def test_impact_total_outage(self):
        assert CascadeImpact.TOTAL_OUTAGE == "total_outage"

    # DependencyRelation (5)
    def test_relation_hard(self):
        assert DependencyRelation.HARD == "hard"

    def test_relation_soft(self):
        assert DependencyRelation.SOFT == "soft"

    def test_relation_optional(self):
        assert DependencyRelation.OPTIONAL == "optional"

    def test_relation_fallback_available(self):
        assert DependencyRelation.FALLBACK_AVAILABLE == "fallback_available"

    def test_relation_circuit_broken(self):
        assert DependencyRelation.CIRCUIT_BROKEN == "circuit_broken"

    # PropagationMode (5)
    def test_propagation_serial(self):
        assert PropagationMode.SERIAL == "serial"

    def test_propagation_parallel(self):
        assert PropagationMode.PARALLEL == "parallel"

    def test_propagation_fan_out(self):
        assert PropagationMode.FAN_OUT == "fan_out"

    def test_propagation_conditional(self):
        assert PropagationMode.CONDITIONAL == "conditional"

    def test_propagation_aggregated(self):
        assert PropagationMode.AGGREGATED == "aggregated"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_cascade_record_defaults(self):
        r = CascadeRecord()
        assert r.id
        assert r.upstream_service == ""
        assert r.downstream_service == ""
        assert r.upstream_sla_pct == 99.9
        assert r.downstream_sla_pct == 99.9
        assert r.effective_sla_pct == 99.9
        assert r.relation == DependencyRelation.HARD
        assert r.propagation == PropagationMode.SERIAL
        assert r.impact == CascadeImpact.NONE
        assert r.team == ""
        assert r.created_at > 0

    def test_cascade_path_defaults(self):
        p = CascadePath()
        assert p.id
        assert p.source_service == ""
        assert p.target_service == ""
        assert p.path == []
        assert p.effective_sla_pct == 99.9
        assert p.weakest_link == ""
        assert p.hop_count == 0
        assert p.created_at > 0

    def test_cascade_report_defaults(self):
        r = CascadeReport()
        assert r.total_dependencies == 0
        assert r.avg_effective_sla_pct == 0.0
        assert r.below_threshold_count == 0
        assert r.by_impact == {}
        assert r.by_relation == {}
        assert r.weakest_links == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_dependency
# ---------------------------------------------------------------------------


class TestRecordDependency:
    def test_hard_dependency(self):
        eng = _engine()
        r = eng.record_dependency(
            upstream_service="auth",
            downstream_service="api",
            upstream_sla_pct=99.9,
            downstream_sla_pct=99.9,
            relation=DependencyRelation.HARD,
        )
        assert r.upstream_service == "auth"
        assert r.downstream_service == "api"
        assert r.relation == DependencyRelation.HARD
        # HARD: 99.9 * 99.9 / 100 = 99.8001
        assert r.effective_sla_pct == 99.8001

    def test_soft_dependency(self):
        eng = _engine()
        r = eng.record_dependency(
            upstream_service="cache",
            downstream_service="api",
            upstream_sla_pct=99.9,
            downstream_sla_pct=99.5,
            relation=DependencyRelation.SOFT,
        )
        # SOFT: max(99.9, 99.5) - 0.01 = 99.89
        assert r.effective_sla_pct == 99.89

    def test_optional_dependency(self):
        eng = _engine()
        r = eng.record_dependency(
            upstream_service="analytics",
            downstream_service="api",
            upstream_sla_pct=99.9,
            downstream_sla_pct=95.0,
            relation=DependencyRelation.OPTIONAL,
        )
        # OPTIONAL: upstream only = 99.9
        assert r.effective_sla_pct == 99.9

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_dependency(
                upstream_service=f"svc-{i}",
                downstream_service="api",
            )
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_dependency(
            upstream_service="auth",
            downstream_service="api",
        )
        result = eng.get_record(r.id)
        assert result is not None
        assert result.upstream_service == "auth"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# ---------------------------------------------------------------------------
# list_records
# ---------------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_dependency(upstream_service="auth", downstream_service="api")
        eng.record_dependency(upstream_service="db", downstream_service="api")
        assert len(eng.list_records()) == 2

    def test_filter_by_upstream_service(self):
        eng = _engine()
        eng.record_dependency(upstream_service="auth", downstream_service="api")
        eng.record_dependency(upstream_service="db", downstream_service="api")
        results = eng.list_records(upstream_service="auth")
        assert len(results) == 1
        assert results[0].upstream_service == "auth"

    def test_filter_by_impact(self):
        eng = _engine()
        eng.record_dependency(
            upstream_service="auth",
            downstream_service="api",
            upstream_sla_pct=99.9,
            downstream_sla_pct=99.9,
            relation=DependencyRelation.HARD,
        )
        eng.record_dependency(
            upstream_service="db",
            downstream_service="api",
            upstream_sla_pct=90.0,
            downstream_sla_pct=90.0,
            relation=DependencyRelation.HARD,
        )
        # 90*90/100=81.0 => TOTAL_OUTAGE
        results = eng.list_records(impact=CascadeImpact.TOTAL_OUTAGE)
        assert len(results) == 1
        assert results[0].upstream_service == "db"


# ---------------------------------------------------------------------------
# compute_effective_sla
# ---------------------------------------------------------------------------


class TestComputeEffectiveSla:
    def test_hard_computation(self):
        eng = _engine()
        result = eng.compute_effective_sla(
            upstream_sla_pct=99.9,
            downstream_sla_pct=99.9,
            relation=DependencyRelation.HARD,
        )
        # 99.9 * 99.9 / 100 = 99.8001
        assert result["effective_sla_pct"] == 99.8001
        assert result["relation"] == "hard"
        assert result["impact"] == "degraded"

    def test_soft_computation(self):
        eng = _engine()
        result = eng.compute_effective_sla(
            upstream_sla_pct=99.9,
            downstream_sla_pct=99.5,
            relation=DependencyRelation.SOFT,
        )
        # max(99.9, 99.5) - 0.01 = 99.89
        assert result["effective_sla_pct"] == 99.89
        assert result["below_threshold"] is False

    def test_optional_computation(self):
        eng = _engine()
        result = eng.compute_effective_sla(
            upstream_sla_pct=99.9,
            downstream_sla_pct=80.0,
            relation=DependencyRelation.OPTIONAL,
        )
        # OPTIONAL: upstream only = 99.9
        assert result["effective_sla_pct"] == 99.9
        assert result["impact"] == "none"


# ---------------------------------------------------------------------------
# trace_cascade_paths
# ---------------------------------------------------------------------------


class TestTraceCascadePaths:
    def test_finds_downstream_paths(self):
        eng = _engine()
        eng.record_dependency(
            upstream_service="gateway",
            downstream_service="auth",
            upstream_sla_pct=99.9,
            downstream_sla_pct=99.9,
        )
        eng.record_dependency(
            upstream_service="auth",
            downstream_service="db",
            upstream_sla_pct=99.9,
            downstream_sla_pct=99.5,
        )
        paths = eng.trace_cascade_paths("gateway")
        assert len(paths) >= 1
        assert all(isinstance(p, CascadePath) for p in paths)
        # Should find a path gateway -> auth -> db
        target_services = [p.target_service for p in paths]
        assert "db" in target_services

    def test_no_downstream(self):
        eng = _engine()
        eng.record_dependency(
            upstream_service="auth",
            downstream_service="db",
        )
        # "db" has no downstream
        paths = eng.trace_cascade_paths("db")
        assert paths == []


# ---------------------------------------------------------------------------
# identify_weakest_links
# ---------------------------------------------------------------------------


class TestIdentifyWeakestLinks:
    def test_has_weak_links(self):
        eng = _engine()
        eng.record_dependency(
            upstream_service="gateway",
            downstream_service="auth",
            upstream_sla_pct=99.9,
            downstream_sla_pct=99.5,
        )
        eng.record_dependency(
            upstream_service="auth",
            downstream_service="db",
            upstream_sla_pct=99.5,
            downstream_sla_pct=99.0,
        )
        eng.trace_cascade_paths("gateway")
        links = eng.identify_weakest_links()
        assert len(links) >= 1
        assert "service" in links[0]
        assert "weakest_link_count" in links[0]

    def test_no_paths_no_links(self):
        eng = _engine()
        links = eng.identify_weakest_links()
        assert links == []


# ---------------------------------------------------------------------------
# simulate_degradation
# ---------------------------------------------------------------------------


class TestSimulateDegradation:
    def test_degrades_downstream(self):
        eng = _engine()
        eng.record_dependency(
            upstream_service="auth",
            downstream_service="api",
            upstream_sla_pct=99.9,
            downstream_sla_pct=99.9,
            relation=DependencyRelation.HARD,
        )
        result = eng.simulate_degradation("auth", degraded_sla_pct=90.0)
        assert result["service"] == "auth"
        assert result["degraded_sla_pct"] == 90.0
        assert result["affected_services"] == 1
        detail = result["details"][0]
        assert detail["downstream_service"] == "api"
        # new effective: 90.0 * 99.9 / 100 = 89.91
        assert detail["new_effective_sla_pct"] == 89.91
        assert detail["worsened"] is True

    def test_service_not_found(self):
        eng = _engine()
        result = eng.simulate_degradation("unknown", degraded_sla_pct=90.0)
        assert result["affected_services"] == 0
        assert result["details"] == []


# ---------------------------------------------------------------------------
# rank_by_cascade_risk
# ---------------------------------------------------------------------------


class TestRankByCascadeRisk:
    def test_ranked_correctly(self):
        eng = _engine()
        eng.record_dependency(upstream_service="gateway", downstream_service="auth")
        eng.record_dependency(upstream_service="gateway", downstream_service="api")
        eng.record_dependency(upstream_service="gateway", downstream_service="worker")
        eng.record_dependency(upstream_service="auth", downstream_service="db")
        ranked = eng.rank_by_cascade_risk()
        assert len(ranked) >= 2
        # gateway has 3 downstream, auth has 1 => gateway first
        assert ranked[0]["service"] == "gateway"
        assert ranked[0]["downstream_count"] == 3

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_cascade_risk() == []


# ---------------------------------------------------------------------------
# generate_cascade_report
# ---------------------------------------------------------------------------


class TestGenerateCascadeReport:
    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_cascade_report()
        assert isinstance(report, CascadeReport)
        assert report.total_dependencies == 0
        assert report.avg_effective_sla_pct == 0.0
        assert "All dependency chains within acceptable SLA bounds" in report.recommendations

    def test_populated_report(self):
        eng = _engine()
        eng.record_dependency(
            upstream_service="auth",
            downstream_service="api",
            upstream_sla_pct=99.9,
            downstream_sla_pct=99.9,
            relation=DependencyRelation.HARD,
        )
        eng.record_dependency(
            upstream_service="db",
            downstream_service="worker",
            upstream_sla_pct=90.0,
            downstream_sla_pct=90.0,
            relation=DependencyRelation.HARD,
        )
        report = eng.generate_cascade_report()
        assert report.total_dependencies == 2
        assert report.avg_effective_sla_pct > 0
        assert len(report.by_impact) > 0
        assert len(report.by_relation) > 0
        assert report.generated_at > 0


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.record_dependency(upstream_service="auth", downstream_service="api")
        eng.record_dependency(upstream_service="auth", downstream_service="worker")
        eng.trace_cascade_paths("auth")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._paths) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_paths"] == 0
        assert stats["min_acceptable_sla_pct"] == 99.0
        assert stats["impact_distribution"] == {}
        assert stats["unique_upstream"] == 0
        assert stats["unique_downstream"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_dependency(
            upstream_service="auth",
            downstream_service="api",
            upstream_sla_pct=99.9,
            downstream_sla_pct=99.9,
            relation=DependencyRelation.HARD,
        )
        eng.record_dependency(
            upstream_service="auth",
            downstream_service="worker",
            upstream_sla_pct=99.9,
            downstream_sla_pct=99.5,
            relation=DependencyRelation.SOFT,
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["unique_upstream"] == 1
        assert stats["unique_downstream"] == 2
        assert len(stats["impact_distribution"]) > 0
