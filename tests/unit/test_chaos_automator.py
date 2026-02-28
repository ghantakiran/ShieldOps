"""Tests for shieldops.observability.chaos_automator."""

from __future__ import annotations

from shieldops.observability.chaos_automator import (
    BlastRadius,
    ChaosAutomatorReport,
    ChaosExperimentAutomator,
    ChaosOutcome,
    ChaosRecord,
    ChaosSchedule,
    ChaosType,
)


def _engine(**kw) -> ChaosExperimentAutomator:
    return ChaosExperimentAutomator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ChaosType (5)
    def test_type_latency(self):
        assert ChaosType.LATENCY_INJECTION == "latency_injection"

    def test_type_service_kill(self):
        assert ChaosType.SERVICE_KILL == "service_kill"

    def test_type_cpu_stress(self):
        assert ChaosType.CPU_STRESS == "cpu_stress"

    def test_type_memory_pressure(self):
        assert ChaosType.MEMORY_PRESSURE == "memory_pressure"

    def test_type_network_partition(self):
        assert ChaosType.NETWORK_PARTITION == "network_partition"

    # ChaosOutcome (5)
    def test_outcome_passed(self):
        assert ChaosOutcome.PASSED == "passed"

    def test_outcome_degraded(self):
        assert ChaosOutcome.DEGRADED == "degraded"

    def test_outcome_failed(self):
        assert ChaosOutcome.FAILED == "failed"

    def test_outcome_aborted(self):
        assert ChaosOutcome.ABORTED == "aborted"

    def test_outcome_inconclusive(self):
        assert ChaosOutcome.INCONCLUSIVE == "inconclusive"

    # BlastRadius (5)
    def test_radius_single_pod(self):
        assert BlastRadius.SINGLE_POD == "single_pod"

    def test_radius_single_service(self):
        assert BlastRadius.SINGLE_SERVICE == "single_service"

    def test_radius_service_group(self):
        assert BlastRadius.SERVICE_GROUP == "service_group"

    def test_radius_availability_zone(self):
        assert BlastRadius.AVAILABILITY_ZONE == "availability_zone"

    def test_radius_region(self):
        assert BlastRadius.REGION == "region"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_chaos_record_defaults(self):
        r = ChaosRecord()
        assert r.id
        assert r.experiment_name == ""
        assert r.chaos_type == ChaosType.LATENCY_INJECTION
        assert r.outcome == ChaosOutcome.PASSED
        assert r.blast_radius == BlastRadius.SINGLE_POD
        assert r.impact_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_chaos_schedule_defaults(self):
        r = ChaosSchedule()
        assert r.id
        assert r.schedule_name == ""
        assert r.chaos_type == ChaosType.LATENCY_INJECTION
        assert r.blast_radius == BlastRadius.SINGLE_POD
        assert r.frequency_days == 7
        assert r.auto_rollback is True
        assert r.created_at > 0

    def test_report_defaults(self):
        r = ChaosAutomatorReport()
        assert r.total_experiments == 0
        assert r.total_schedules == 0
        assert r.pass_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_outcome == {}
        assert r.failed_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_experiment
# -------------------------------------------------------------------


class TestRecordExperiment:
    def test_basic(self):
        eng = _engine()
        r = eng.record_experiment(
            "exp-a",
            chaos_type=ChaosType.CPU_STRESS,
            outcome=ChaosOutcome.PASSED,
        )
        assert r.experiment_name == "exp-a"
        assert r.chaos_type == ChaosType.CPU_STRESS

    def test_with_blast_radius(self):
        eng = _engine()
        r = eng.record_experiment(
            "exp-b",
            blast_radius=BlastRadius.REGION,
        )
        assert r.blast_radius == BlastRadius.REGION

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_experiment(f"exp-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_experiment
# -------------------------------------------------------------------


class TestGetExperiment:
    def test_found(self):
        eng = _engine()
        r = eng.record_experiment("exp-a")
        assert eng.get_experiment(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_experiment("nonexistent") is None


# -------------------------------------------------------------------
# list_experiments
# -------------------------------------------------------------------


class TestListExperiments:
    def test_list_all(self):
        eng = _engine()
        eng.record_experiment("exp-a")
        eng.record_experiment("exp-b")
        assert len(eng.list_experiments()) == 2

    def test_filter_by_name(self):
        eng = _engine()
        eng.record_experiment("exp-a")
        eng.record_experiment("exp-b")
        results = eng.list_experiments(experiment_name="exp-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_experiment(
            "exp-a",
            chaos_type=ChaosType.CPU_STRESS,
        )
        eng.record_experiment(
            "exp-b",
            chaos_type=ChaosType.SERVICE_KILL,
        )
        results = eng.list_experiments(
            chaos_type=ChaosType.CPU_STRESS,
        )
        assert len(results) == 1


# -------------------------------------------------------------------
# add_schedule
# -------------------------------------------------------------------


class TestAddSchedule:
    def test_basic(self):
        eng = _engine()
        s = eng.add_schedule(
            "weekly-latency",
            chaos_type=ChaosType.LATENCY_INJECTION,
            blast_radius=BlastRadius.SINGLE_SERVICE,
            frequency_days=7,
            auto_rollback=True,
        )
        assert s.schedule_name == "weekly-latency"
        assert s.frequency_days == 7

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_schedule(f"sched-{i}")
        assert len(eng._schedules) == 2


# -------------------------------------------------------------------
# analyze_experiment_results
# -------------------------------------------------------------------


class TestAnalyzeExperimentResults:
    def test_with_data(self):
        eng = _engine()
        eng.record_experiment(
            "exp-a",
            outcome=ChaosOutcome.PASSED,
        )
        eng.record_experiment(
            "exp-a",
            outcome=ChaosOutcome.FAILED,
        )
        result = eng.analyze_experiment_results("exp-a")
        assert result["experiment_name"] == "exp-a"
        assert result["experiment_count"] == 2
        assert result["pass_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_experiment_results("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_failed_experiments
# -------------------------------------------------------------------


class TestIdentifyFailedExperiments:
    def test_with_failures(self):
        eng = _engine()
        eng.record_experiment(
            "exp-a",
            outcome=ChaosOutcome.FAILED,
        )
        eng.record_experiment(
            "exp-a",
            outcome=ChaosOutcome.FAILED,
        )
        eng.record_experiment(
            "exp-b",
            outcome=ChaosOutcome.PASSED,
        )
        results = eng.identify_failed_experiments()
        assert len(results) == 1
        assert results[0]["experiment_name"] == "exp-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failed_experiments() == []


# -------------------------------------------------------------------
# rank_by_impact
# -------------------------------------------------------------------


class TestRankByImpact:
    def test_with_data(self):
        eng = _engine()
        eng.record_experiment("exp-a", impact_score=90.0)
        eng.record_experiment("exp-a", impact_score=80.0)
        eng.record_experiment("exp-b", impact_score=50.0)
        results = eng.rank_by_impact()
        assert results[0]["experiment_name"] == "exp-a"
        assert results[0]["avg_impact"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact() == []


# -------------------------------------------------------------------
# detect_experiment_regressions
# -------------------------------------------------------------------


class TestDetectExperimentRegressions:
    def test_with_regressions(self):
        eng = _engine()
        for _ in range(5):
            eng.record_experiment(
                "exp-a",
                outcome=ChaosOutcome.FAILED,
            )
        eng.record_experiment(
            "exp-b",
            outcome=ChaosOutcome.PASSED,
        )
        results = eng.detect_experiment_regressions()
        assert len(results) == 1
        assert results[0]["experiment_name"] == "exp-a"
        assert results[0]["regression_detected"] is True

    def test_no_regressions(self):
        eng = _engine()
        eng.record_experiment(
            "exp-a",
            outcome=ChaosOutcome.FAILED,
        )
        assert eng.detect_experiment_regressions() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_experiment(
            "exp-a",
            outcome=ChaosOutcome.PASSED,
        )
        eng.record_experiment(
            "exp-b",
            outcome=ChaosOutcome.FAILED,
        )
        eng.record_experiment(
            "exp-b",
            outcome=ChaosOutcome.FAILED,
        )
        eng.add_schedule("sched-1")
        report = eng.generate_report()
        assert report.total_experiments == 3
        assert report.total_schedules == 1
        assert report.by_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_experiments == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_experiment("exp-a")
        eng.add_schedule("sched-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._schedules) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_experiments"] == 0
        assert stats["total_schedules"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_experiment(
            "exp-a",
            chaos_type=ChaosType.CPU_STRESS,
        )
        eng.record_experiment(
            "exp-b",
            chaos_type=ChaosType.SERVICE_KILL,
        )
        eng.add_schedule("s1")
        stats = eng.get_stats()
        assert stats["total_experiments"] == 2
        assert stats["total_schedules"] == 1
        assert stats["unique_experiments"] == 2
