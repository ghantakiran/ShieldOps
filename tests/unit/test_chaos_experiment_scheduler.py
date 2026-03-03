"""Tests for shieldops.operations.chaos_experiment_scheduler."""

from __future__ import annotations

from shieldops.operations.chaos_experiment_scheduler import (
    ChaosExperiment,
    ChaosExperimentScheduler,
    ExperimentAnalysis,
    ExperimentScheduleReport,
    ExperimentStatus,
    ExperimentType,
    ScheduleFrequency,
)


def _engine(**kw) -> ChaosExperimentScheduler:
    return ChaosExperimentScheduler(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_experiment_type_latency_injection(self):
        assert ExperimentType.LATENCY_INJECTION == "latency_injection"

    def test_experiment_type_failure_injection(self):
        assert ExperimentType.FAILURE_INJECTION == "failure_injection"

    def test_experiment_type_resource_stress(self):
        assert ExperimentType.RESOURCE_STRESS == "resource_stress"

    def test_experiment_type_network_partition(self):
        assert ExperimentType.NETWORK_PARTITION == "network_partition"

    def test_experiment_type_dns_failure(self):
        assert ExperimentType.DNS_FAILURE == "dns_failure"

    def test_frequency_daily(self):
        assert ScheduleFrequency.DAILY == "daily"

    def test_frequency_weekly(self):
        assert ScheduleFrequency.WEEKLY == "weekly"

    def test_frequency_biweekly(self):
        assert ScheduleFrequency.BIWEEKLY == "biweekly"

    def test_frequency_monthly(self):
        assert ScheduleFrequency.MONTHLY == "monthly"

    def test_frequency_quarterly(self):
        assert ScheduleFrequency.QUARTERLY == "quarterly"

    def test_status_scheduled(self):
        assert ExperimentStatus.SCHEDULED == "scheduled"

    def test_status_running(self):
        assert ExperimentStatus.RUNNING == "running"

    def test_status_completed(self):
        assert ExperimentStatus.COMPLETED == "completed"

    def test_status_failed(self):
        assert ExperimentStatus.FAILED == "failed"

    def test_status_cancelled(self):
        assert ExperimentStatus.CANCELLED == "cancelled"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_chaos_experiment_defaults(self):
        r = ChaosExperiment()
        assert r.id
        assert r.experiment_type == ExperimentType.LATENCY_INJECTION
        assert r.schedule_frequency == ScheduleFrequency.WEEKLY
        assert r.status == ExperimentStatus.SCHEDULED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_experiment_analysis_defaults(self):
        a = ExperimentAnalysis()
        assert a.id
        assert a.experiment_type == ExperimentType.LATENCY_INJECTION
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_experiment_schedule_report_defaults(self):
        r = ExperimentScheduleReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_type == {}
        assert r.by_frequency == {}
        assert r.by_status == {}
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
        eng = _engine(max_records=100)
        assert eng._max_records == 100

    def test_custom_threshold(self):
        eng = _engine(threshold=75.0)
        assert eng._threshold == 75.0


# ---------------------------------------------------------------------------
# record_experiment / get_experiment
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_record_basic(self):
        eng = _engine()
        r = eng.record_experiment(
            service="chaos-svc",
            experiment_type=ExperimentType.FAILURE_INJECTION,
            schedule_frequency=ScheduleFrequency.DAILY,
            status=ExperimentStatus.RUNNING,
            score=80.0,
            team="platform",
        )
        assert r.service == "chaos-svc"
        assert r.experiment_type == ExperimentType.FAILURE_INJECTION
        assert r.schedule_frequency == ScheduleFrequency.DAILY
        assert r.status == ExperimentStatus.RUNNING
        assert r.score == 80.0
        assert r.team == "platform"

    def test_record_stored(self):
        eng = _engine()
        eng.record_experiment(service="svc-a")
        assert len(eng._records) == 1

    def test_get_found(self):
        eng = _engine()
        r = eng.record_experiment(service="svc-a", score=60.0)
        result = eng.get_experiment(r.id)
        assert result is not None
        assert result.score == 60.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_experiment("nonexistent") is None


# ---------------------------------------------------------------------------
# list_experiments
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_experiment(service="svc-a")
        eng.record_experiment(service="svc-b")
        assert len(eng.list_experiments()) == 2

    def test_filter_by_experiment_type(self):
        eng = _engine()
        eng.record_experiment(service="svc-a", experiment_type=ExperimentType.LATENCY_INJECTION)
        eng.record_experiment(service="svc-b", experiment_type=ExperimentType.DNS_FAILURE)
        results = eng.list_experiments(experiment_type=ExperimentType.LATENCY_INJECTION)
        assert len(results) == 1
        assert results[0].service == "svc-a"

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_experiment(service="svc-a", status=ExperimentStatus.COMPLETED)
        eng.record_experiment(service="svc-b", status=ExperimentStatus.FAILED)
        results = eng.list_experiments(status=ExperimentStatus.COMPLETED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_experiment(service="svc-a", team="platform")
        eng.record_experiment(service="svc-b", team="security")
        assert len(eng.list_experiments(team="platform")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_experiment(service=f"svc-{i}")
        assert len(eng.list_experiments(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            experiment_type=ExperimentType.RESOURCE_STRESS,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="stress detected",
        )
        assert a.experiment_type == ExperimentType.RESOURCE_STRESS
        assert a.analysis_score == 88.5
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
        eng.record_experiment(
            service="s1", experiment_type=ExperimentType.LATENCY_INJECTION, score=90.0
        )
        eng.record_experiment(
            service="s2", experiment_type=ExperimentType.LATENCY_INJECTION, score=70.0
        )
        result = eng.analyze_distribution()
        assert "latency_injection" in result
        assert result["latency_injection"]["count"] == 2
        assert result["latency_injection"]["avg_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_coverage_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_experiment(service="svc-a", score=60.0)
        eng.record_experiment(service="svc-b", score=90.0)
        results = eng.identify_coverage_gaps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_experiment(service="svc-a", score=50.0)
        eng.record_experiment(service="svc-b", score=30.0)
        results = eng.identify_coverage_gaps()
        assert results[0]["score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_experiment(service="svc-a", score=90.0)
        eng.record_experiment(service="svc-b", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "svc-b"
        assert results[0]["avg_score"] == 50.0

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
        eng.record_experiment(
            service="svc-a",
            experiment_type=ExperimentType.FAILURE_INJECTION,
            schedule_frequency=ScheduleFrequency.WEEKLY,
            status=ExperimentStatus.COMPLETED,
            score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ExperimentScheduleReport)
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
        eng.record_experiment(service="svc-a")
        eng.add_analysis()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_experiment(
            service="svc-a",
            experiment_type=ExperimentType.LATENCY_INJECTION,
            team="platform",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "latency_injection" in stats["type_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_experiment(service=f"svc-{i}")
        assert len(eng._records) == 3
