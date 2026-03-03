"""Tests for shieldops.operations.fleet_management_optimizer — FleetManagementOptimizer."""

from __future__ import annotations

from shieldops.operations.fleet_management_optimizer import (
    FleetAnalysis,
    FleetHealth,
    FleetManagementOptimizer,
    FleetManagementReport,
    FleetRecord,
    FleetType,
    OptimizationAction,
)


def _engine(**kw) -> FleetManagementOptimizer:
    return FleetManagementOptimizer(**kw)


class TestEnums:
    def test_fleet_type_ec2_fleet(self):
        assert FleetType.EC2_FLEET == "ec2_fleet"

    def test_fleet_type_k8s_cluster(self):
        assert FleetType.K8S_CLUSTER == "k8s_cluster"

    def test_fleet_type_container_fleet(self):
        assert FleetType.CONTAINER_FLEET == "container_fleet"

    def test_fleet_type_vm_scale_set(self):
        assert FleetType.VM_SCALE_SET == "vm_scale_set"

    def test_fleet_type_serverless(self):
        assert FleetType.SERVERLESS == "serverless"

    def test_optimization_action_right_size(self):
        assert OptimizationAction.RIGHT_SIZE == "right_size"

    def test_optimization_action_rebalance(self):
        assert OptimizationAction.REBALANCE == "rebalance"

    def test_optimization_action_consolidate(self):
        assert OptimizationAction.CONSOLIDATE == "consolidate"

    def test_optimization_action_modernize(self):
        assert OptimizationAction.MODERNIZE == "modernize"

    def test_optimization_action_migrate(self):
        assert OptimizationAction.MIGRATE == "migrate"

    def test_fleet_health_optimal(self):
        assert FleetHealth.OPTIMAL == "optimal"

    def test_fleet_health_good(self):
        assert FleetHealth.GOOD == "good"

    def test_fleet_health_suboptimal(self):
        assert FleetHealth.SUBOPTIMAL == "suboptimal"

    def test_fleet_health_degraded(self):
        assert FleetHealth.DEGRADED == "degraded"

    def test_fleet_health_critical(self):
        assert FleetHealth.CRITICAL == "critical"


class TestModels:
    def test_record_defaults(self):
        r = FleetRecord()
        assert r.id
        assert r.name == ""
        assert r.fleet_type == FleetType.EC2_FLEET
        assert r.optimization_action == OptimizationAction.RIGHT_SIZE
        assert r.fleet_health == FleetHealth.CRITICAL
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = FleetAnalysis()
        assert a.id
        assert a.name == ""
        assert a.fleet_type == FleetType.EC2_FLEET
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = FleetManagementReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_fleet_type == {}
        assert r.by_optimization_action == {}
        assert r.by_fleet_health == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            fleet_type=FleetType.EC2_FLEET,
            optimization_action=OptimizationAction.REBALANCE,
            fleet_health=FleetHealth.OPTIMAL,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.fleet_type == FleetType.EC2_FLEET
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_fleet_type(self):
        eng = _engine()
        eng.record_entry(name="a", fleet_type=FleetType.EC2_FLEET)
        eng.record_entry(name="b", fleet_type=FleetType.K8S_CLUSTER)
        assert len(eng.list_records(fleet_type=FleetType.EC2_FLEET)) == 1

    def test_filter_by_optimization_action(self):
        eng = _engine()
        eng.record_entry(name="a", optimization_action=OptimizationAction.RIGHT_SIZE)
        eng.record_entry(name="b", optimization_action=OptimizationAction.REBALANCE)
        assert len(eng.list_records(optimization_action=OptimizationAction.RIGHT_SIZE)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", fleet_type=FleetType.K8S_CLUSTER, score=90.0)
        eng.record_entry(name="b", fleet_type=FleetType.K8S_CLUSTER, score=70.0)
        result = eng.analyze_distribution()
        assert "k8s_cluster" in result
        assert result["k8s_cluster"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
