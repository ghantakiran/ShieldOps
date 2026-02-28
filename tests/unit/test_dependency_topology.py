"""Tests for shieldops.topology.dependency_topology — DependencyTopologyAnalyzer."""

from __future__ import annotations

from shieldops.topology.dependency_topology import (
    CouplingLevel,
    DependencyTopologyAnalyzer,
    TopologyAnalyzerReport,
    TopologyPattern,
    TopologyRecord,
    TopologyRisk,
    TopologyRule,
)


def _engine(**kw) -> DependencyTopologyAnalyzer:
    return DependencyTopologyAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # TopologyPattern (5)
    def test_pattern_linear(self):
        assert TopologyPattern.LINEAR_CHAIN == "linear_chain"

    def test_pattern_fan_out(self):
        assert TopologyPattern.FAN_OUT == "fan_out"

    def test_pattern_fan_in(self):
        assert TopologyPattern.FAN_IN == "fan_in"

    def test_pattern_mesh(self):
        assert TopologyPattern.MESH == "mesh"

    def test_pattern_star(self):
        assert TopologyPattern.STAR == "star"

    # CouplingLevel (5)
    def test_coupling_tight(self):
        assert CouplingLevel.TIGHT == "tight"

    def test_coupling_moderate(self):
        assert CouplingLevel.MODERATE == "moderate"

    def test_coupling_loose(self):
        assert CouplingLevel.LOOSE == "loose"

    def test_coupling_decoupled(self):
        assert CouplingLevel.DECOUPLED == "decoupled"

    def test_coupling_isolated(self):
        assert CouplingLevel.ISOLATED == "isolated"

    # TopologyRisk (5)
    def test_risk_critical(self):
        assert TopologyRisk.CRITICAL == "critical"

    def test_risk_high(self):
        assert TopologyRisk.HIGH == "high"

    def test_risk_moderate(self):
        assert TopologyRisk.MODERATE == "moderate"

    def test_risk_low(self):
        assert TopologyRisk.LOW == "low"

    def test_risk_minimal(self):
        assert TopologyRisk.MINIMAL == "minimal"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_topology_record_defaults(self):
        r = TopologyRecord()
        assert r.id
        assert r.service_name == ""
        assert r.pattern == TopologyPattern.LINEAR_CHAIN
        assert r.coupling == CouplingLevel.MODERATE
        assert r.risk == TopologyRisk.LOW
        assert r.depth_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_topology_rule_defaults(self):
        r = TopologyRule()
        assert r.id
        assert r.rule_name == ""
        assert r.pattern == TopologyPattern.LINEAR_CHAIN
        assert r.coupling == CouplingLevel.MODERATE
        assert r.max_depth == 5
        assert r.max_fan_out == 10.0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = TopologyAnalyzerReport()
        assert r.total_observations == 0
        assert r.total_rules == 0
        assert r.low_risk_rate_pct == 0.0
        assert r.by_pattern == {}
        assert r.by_coupling == {}
        assert r.critical_count == 0
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
            pattern=TopologyPattern.MESH,
            coupling=CouplingLevel.TIGHT,
        )
        assert r.service_name == "svc-a"
        assert r.pattern == TopologyPattern.MESH

    def test_with_depth(self):
        eng = _engine()
        r = eng.record_observation("svc-b", depth_score=7.5)
        assert r.depth_score == 7.5

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
        results = eng.list_observations(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_pattern(self):
        eng = _engine()
        eng.record_observation(
            "svc-a",
            pattern=TopologyPattern.MESH,
        )
        eng.record_observation(
            "svc-b",
            pattern=TopologyPattern.STAR,
        )
        results = eng.list_observations(pattern=TopologyPattern.MESH)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        r = eng.add_rule(
            "max-depth-rule",
            pattern=TopologyPattern.FAN_OUT,
            coupling=CouplingLevel.LOOSE,
            max_depth=3,
            max_fan_out=5.0,
        )
        assert r.rule_name == "max-depth-rule"
        assert r.max_depth == 3

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rule(f"rule-{i}")
        assert len(eng._rules) == 2


# -------------------------------------------------------------------
# analyze_topology_health
# -------------------------------------------------------------------


class TestAnalyzeTopologyHealth:
    def test_with_data(self):
        eng = _engine()
        eng.record_observation(
            "svc-a",
            risk=TopologyRisk.LOW,
            depth_score=3.0,
        )
        eng.record_observation(
            "svc-a",
            risk=TopologyRisk.CRITICAL,
            depth_score=7.0,
        )
        result = eng.analyze_topology_health("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["observation_count"] == 2
        assert result["low_risk_count"] == 1
        assert result["low_risk_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_topology_health("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_tightly_coupled
# -------------------------------------------------------------------


class TestIdentifyTightlyCoupled:
    def test_with_tight(self):
        eng = _engine()
        eng.record_observation(
            "svc-a",
            coupling=CouplingLevel.TIGHT,
        )
        eng.record_observation(
            "svc-a",
            coupling=CouplingLevel.TIGHT,
        )
        eng.record_observation(
            "svc-b",
            coupling=CouplingLevel.LOOSE,
        )
        results = eng.identify_tightly_coupled()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_tightly_coupled() == []


# -------------------------------------------------------------------
# rank_by_depth
# -------------------------------------------------------------------


class TestRankByDepth:
    def test_with_data(self):
        eng = _engine()
        eng.record_observation("svc-a", depth_score=8.0)
        eng.record_observation("svc-a", depth_score=6.0)
        eng.record_observation("svc-b", depth_score=3.0)
        results = eng.rank_by_depth()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["avg_depth"] == 7.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_depth() == []


# -------------------------------------------------------------------
# detect_topology_risks
# -------------------------------------------------------------------


class TestDetectTopologyRisks:
    def test_with_risks(self):
        eng = _engine()
        for _ in range(5):
            eng.record_observation(
                "svc-a",
                risk=TopologyRisk.CRITICAL,
            )
        eng.record_observation(
            "svc-b",
            risk=TopologyRisk.LOW,
        )
        results = eng.detect_topology_risks()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["risk_detected"] is True

    def test_no_risks(self):
        eng = _engine()
        eng.record_observation(
            "svc-a",
            risk=TopologyRisk.HIGH,
        )
        assert eng.detect_topology_risks() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_observation(
            "svc-a",
            risk=TopologyRisk.CRITICAL,
            coupling=CouplingLevel.TIGHT,
        )
        eng.record_observation(
            "svc-a",
            risk=TopologyRisk.CRITICAL,
            coupling=CouplingLevel.TIGHT,
        )
        eng.record_observation(
            "svc-b",
            risk=TopologyRisk.LOW,
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
        assert "healthy" in report.recommendations[0]


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
            pattern=TopologyPattern.MESH,
        )
        eng.record_observation(
            "svc-b",
            pattern=TopologyPattern.STAR,
        )
        eng.add_rule("r1")
        stats = eng.get_stats()
        assert stats["total_observations"] == 2
        assert stats["total_rules"] == 1
        assert stats["unique_services"] == 2
