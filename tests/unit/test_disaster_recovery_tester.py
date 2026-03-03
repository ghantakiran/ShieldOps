"""Tests for shieldops.operations.disaster_recovery_tester."""

from __future__ import annotations

from shieldops.operations.disaster_recovery_tester import (
    DisasterRecoveryTester,
    DRAnalysis,
    DRReadiness,
    DRScenario,
    DRTest,
    DRTestReport,
    DRTestType,
)


def _engine(**kw) -> DisasterRecoveryTester:
    return DisasterRecoveryTester(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_scenario_region_failure(self):
        assert DRScenario.REGION_FAILURE == "region_failure"

    def test_scenario_az_failure(self):
        assert DRScenario.AZ_FAILURE == "az_failure"

    def test_scenario_data_center_loss(self):
        assert DRScenario.DATA_CENTER_LOSS == "data_center_loss"

    def test_scenario_network_partition(self):
        assert DRScenario.NETWORK_PARTITION == "network_partition"

    def test_scenario_data_corruption(self):
        assert DRScenario.DATA_CORRUPTION == "data_corruption"

    def test_type_tabletop(self):
        assert DRTestType.TABLETOP == "tabletop"

    def test_type_simulation(self):
        assert DRTestType.SIMULATION == "simulation"

    def test_type_partial_failover(self):
        assert DRTestType.PARTIAL_FAILOVER == "partial_failover"

    def test_type_full_failover(self):
        assert DRTestType.FULL_FAILOVER == "full_failover"

    def test_type_switchback(self):
        assert DRTestType.SWITCHBACK == "switchback"

    def test_readiness_ready(self):
        assert DRReadiness.READY == "ready"

    def test_readiness_partially_ready(self):
        assert DRReadiness.PARTIALLY_READY == "partially_ready"

    def test_readiness_not_ready(self):
        assert DRReadiness.NOT_READY == "not_ready"

    def test_readiness_untested(self):
        assert DRReadiness.UNTESTED == "untested"

    def test_readiness_degraded(self):
        assert DRReadiness.DEGRADED == "degraded"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_dr_test_defaults(self):
        r = DRTest()
        assert r.id
        assert r.dr_scenario == DRScenario.REGION_FAILURE
        assert r.test_type == DRTestType.TABLETOP
        assert r.dr_readiness == DRReadiness.UNTESTED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_dr_analysis_defaults(self):
        a = DRAnalysis()
        assert a.id
        assert a.dr_scenario == DRScenario.REGION_FAILURE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_dr_test_report_defaults(self):
        r = DRTestReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_scenario == {}
        assert r.by_test_type == {}
        assert r.by_readiness == {}
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
        eng = _engine(max_records=9000)
        assert eng._max_records == 9000

    def test_custom_threshold(self):
        eng = _engine(threshold=85.0)
        assert eng._threshold == 85.0


# ---------------------------------------------------------------------------
# record_test / get_test
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_record_basic(self):
        eng = _engine()
        r = eng.record_test(
            service="global-platform",
            dr_scenario=DRScenario.AZ_FAILURE,
            test_type=DRTestType.FULL_FAILOVER,
            dr_readiness=DRReadiness.READY,
            score=93.0,
            team="infra",
        )
        assert r.service == "global-platform"
        assert r.dr_scenario == DRScenario.AZ_FAILURE
        assert r.test_type == DRTestType.FULL_FAILOVER
        assert r.dr_readiness == DRReadiness.READY
        assert r.score == 93.0
        assert r.team == "infra"

    def test_record_stored(self):
        eng = _engine()
        eng.record_test(service="svc-a")
        assert len(eng._records) == 1

    def test_get_found(self):
        eng = _engine()
        r = eng.record_test(service="svc-a", score=76.0)
        result = eng.get_test(r.id)
        assert result is not None
        assert result.score == 76.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_test("nonexistent") is None


# ---------------------------------------------------------------------------
# list_tests
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_test(service="svc-a")
        eng.record_test(service="svc-b")
        assert len(eng.list_tests()) == 2

    def test_filter_by_scenario(self):
        eng = _engine()
        eng.record_test(service="svc-a", dr_scenario=DRScenario.REGION_FAILURE)
        eng.record_test(service="svc-b", dr_scenario=DRScenario.DATA_CORRUPTION)
        results = eng.list_tests(dr_scenario=DRScenario.REGION_FAILURE)
        assert len(results) == 1

    def test_filter_by_readiness(self):
        eng = _engine()
        eng.record_test(service="svc-a", dr_readiness=DRReadiness.READY)
        eng.record_test(service="svc-b", dr_readiness=DRReadiness.NOT_READY)
        results = eng.list_tests(dr_readiness=DRReadiness.READY)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_test(service="svc-a", team="infra")
        eng.record_test(service="svc-b", team="security")
        assert len(eng.list_tests(team="infra")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_test(service=f"svc-{i}")
        assert len(eng.list_tests(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            dr_scenario=DRScenario.DATA_CENTER_LOSS,
            analysis_score=48.0,
            threshold=50.0,
            breached=True,
            description="datacenter DR gap",
        )
        assert a.dr_scenario == DRScenario.DATA_CENTER_LOSS
        assert a.analysis_score == 48.0
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
        eng.record_test(service="s1", dr_scenario=DRScenario.AZ_FAILURE, score=80.0)
        eng.record_test(service="s2", dr_scenario=DRScenario.AZ_FAILURE, score=60.0)
        result = eng.analyze_distribution()
        assert "az_failure" in result
        assert result["az_failure"]["count"] == 2
        assert result["az_failure"]["avg_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_dr_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_test(service="svc-a", score=60.0)
        eng.record_test(service="svc-b", score=90.0)
        results = eng.identify_dr_gaps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_test(service="svc-a", score=55.0)
        eng.record_test(service="svc-b", score=35.0)
        results = eng.identify_dr_gaps()
        assert results[0]["score"] == 35.0


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_test(service="svc-a", score=90.0)
        eng.record_test(service="svc-b", score=40.0)
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
        eng.record_test(
            service="svc-a",
            dr_scenario=DRScenario.NETWORK_PARTITION,
            test_type=DRTestType.SIMULATION,
            dr_readiness=DRReadiness.DEGRADED,
            score=45.0,
        )
        report = eng.generate_report()
        assert isinstance(report, DRTestReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "within" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_test(service="svc-a")
        eng.add_analysis()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_test(
            service="svc-a",
            dr_scenario=DRScenario.REGION_FAILURE,
            team="infra",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert "region_failure" in stats["scenario_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_test(service=f"svc-{i}")
        assert len(eng._records) == 3
