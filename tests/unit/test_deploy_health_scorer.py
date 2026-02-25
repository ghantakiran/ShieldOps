"""Tests for shieldops.changes.deploy_health_scorer."""

from __future__ import annotations

import pytest

from shieldops.changes.deploy_health_scorer import (
    DeployHealthGrade,
    DeployHealthReport,
    DeployHealthScore,
    DeploymentHealthScorer,
    DeployPhase,
    HealthDimension,
    HealthDimensionReading,
)


def _engine(**kw) -> DeploymentHealthScorer:
    return DeploymentHealthScorer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DeployHealthGrade (5 values)

    def test_grade_excellent(self):
        assert DeployHealthGrade.EXCELLENT == "excellent"

    def test_grade_good(self):
        assert DeployHealthGrade.GOOD == "good"

    def test_grade_fair(self):
        assert DeployHealthGrade.FAIR == "fair"

    def test_grade_poor(self):
        assert DeployHealthGrade.POOR == "poor"

    def test_grade_failing(self):
        assert DeployHealthGrade.FAILING == "failing"

    # HealthDimension (5 values)

    def test_dimension_error_rate_delta(self):
        assert HealthDimension.ERROR_RATE_DELTA == "error_rate_delta"

    def test_dimension_latency_delta(self):
        assert HealthDimension.LATENCY_DELTA == "latency_delta"

    def test_dimension_canary_pass_rate(self):
        assert HealthDimension.CANARY_PASS_RATE == "canary_pass_rate"  # noqa: S105

    def test_dimension_rollback_frequency(self):
        assert HealthDimension.ROLLBACK_FREQUENCY == "rollback_frequency"

    def test_dimension_customer_reports(self):
        assert HealthDimension.CUSTOMER_REPORTS == "customer_reports"

    # DeployPhase (5 values)

    def test_phase_canary(self):
        assert DeployPhase.CANARY == "canary"

    def test_phase_rolling(self):
        assert DeployPhase.ROLLING == "rolling"

    def test_phase_blue_green(self):
        assert DeployPhase.BLUE_GREEN == "blue_green"

    def test_phase_baking(self):
        assert DeployPhase.BAKING == "baking"

    def test_phase_complete(self):
        assert DeployPhase.COMPLETE == "complete"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_health_dimension_reading_defaults(self):
        r = HealthDimensionReading()
        assert r.id
        assert r.deployment_id == ""
        assert r.dimension == HealthDimension.ERROR_RATE_DELTA
        assert r.value == 0.0
        assert r.weight == 1.0
        assert r.created_at > 0

    def test_deploy_health_score_defaults(self):
        s = DeployHealthScore()
        assert s.id
        assert s.deployment_id == ""
        assert s.service_name == ""
        assert s.version == ""
        assert s.composite_score == 100.0
        assert s.grade == DeployHealthGrade.EXCELLENT
        assert s.phase == DeployPhase.CANARY
        assert s.reading_count == 0
        assert s.created_at > 0

    def test_deploy_health_report_defaults(self):
        r = DeployHealthReport()
        assert r.total_scores == 0
        assert r.total_readings == 0
        assert r.by_grade == {}
        assert r.by_phase == {}
        assert r.avg_score == 0.0
        assert r.failing_deployments == []
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# score_deployment
# -------------------------------------------------------------------


class TestScoreDeployment:
    def test_basic_score(self):
        eng = _engine()
        s = eng.score_deployment("dep-1", service_name="svc-a")
        assert s.deployment_id == "dep-1"
        assert s.service_name == "svc-a"
        assert len(eng.list_scores()) == 1

    def test_grade_assignment(self):
        eng = _engine()
        s = eng.score_deployment("dep-1", composite_score=50.0)
        assert s.grade == DeployHealthGrade.POOR

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        ids = []
        for i in range(4):
            s = eng.score_deployment(f"dep-{i}")
            ids.append(s.id)
        scores = eng.list_scores(limit=100)
        assert len(scores) == 3
        found = {s.id for s in scores}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_score
# -------------------------------------------------------------------


class TestGetScore:
    def test_get_existing(self):
        eng = _engine()
        s = eng.score_deployment("dep-1")
        found = eng.get_score(s.id)
        assert found is not None
        assert found.id == s.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_score("nonexistent") is None


# -------------------------------------------------------------------
# list_scores
# -------------------------------------------------------------------


class TestListScores:
    def test_list_all(self):
        eng = _engine()
        eng.score_deployment("dep-1", service_name="svc-a")
        eng.score_deployment("dep-2", service_name="svc-b")
        assert len(eng.list_scores()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.score_deployment("dep-1", service_name="svc-a")
        eng.score_deployment("dep-2", service_name="svc-b")
        eng.score_deployment("dep-3", service_name="svc-a")
        results = eng.list_scores(service_name="svc-a")
        assert len(results) == 2
        assert all(s.service_name == "svc-a" for s in results)

    def test_filter_by_grade(self):
        eng = _engine()
        eng.score_deployment("dep-1", composite_score=95.0)
        eng.score_deployment("dep-2", composite_score=30.0)
        results = eng.list_scores(grade=DeployHealthGrade.FAILING)
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.score_deployment(f"dep-{i}")
        results = eng.list_scores(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# record_dimension_reading
# -------------------------------------------------------------------


class TestRecordDimensionReading:
    def test_basic_reading(self):
        eng = _engine()
        r = eng.record_dimension_reading("dep-1", value=85.0)
        assert r.deployment_id == "dep-1"
        assert r.value == 85.0
        assert r.dimension == HealthDimension.ERROR_RATE_DELTA

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        eng.record_dimension_reading("dep-1", value=10.0)
        eng.record_dimension_reading("dep-2", value=20.0)
        eng.record_dimension_reading("dep-3", value=30.0)
        readings = eng.list_dimension_readings(limit=100)
        assert len(readings) == 2


# -------------------------------------------------------------------
# list_dimension_readings
# -------------------------------------------------------------------


class TestListDimensionReadings:
    def test_filter_by_deployment_id(self):
        eng = _engine()
        eng.record_dimension_reading("dep-1", value=10.0)
        eng.record_dimension_reading("dep-2", value=20.0)
        results = eng.list_dimension_readings(deployment_id="dep-1")
        assert len(results) == 1
        assert results[0].deployment_id == "dep-1"

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_dimension_reading(
            "dep-1",
            dimension=HealthDimension.LATENCY_DELTA,
        )
        eng.record_dimension_reading(
            "dep-1",
            dimension=HealthDimension.CANARY_PASS_RATE,
        )
        results = eng.list_dimension_readings(
            dimension=HealthDimension.LATENCY_DELTA,
        )
        assert len(results) == 1


# -------------------------------------------------------------------
# compute_composite_score
# -------------------------------------------------------------------


class TestComputeCompositeScore:
    def test_no_readings_returns_100(self):
        eng = _engine()
        s = eng.compute_composite_score("dep-1")
        assert s.composite_score == pytest.approx(100.0)

    def test_weighted_average(self):
        eng = _engine()
        eng.record_dimension_reading("dep-1", value=80.0, weight=1.0)
        eng.record_dimension_reading("dep-1", value=60.0, weight=1.0)
        s = eng.compute_composite_score("dep-1")
        assert s.composite_score == pytest.approx(70.0)
        assert s.reading_count == 2

    def test_zero_weight_returns_100(self):
        eng = _engine()
        eng.record_dimension_reading("dep-1", value=50.0, weight=0.0)
        s = eng.compute_composite_score("dep-1")
        assert s.composite_score == pytest.approx(100.0)


# -------------------------------------------------------------------
# compare_deployments
# -------------------------------------------------------------------


class TestCompareDeployments:
    def test_compare_sorted_by_score(self):
        eng = _engine()
        eng.score_deployment("dep-1", composite_score=90.0)
        eng.score_deployment("dep-2", composite_score=50.0)
        results = eng.compare_deployments(["dep-1", "dep-2"])
        assert len(results) == 2
        assert results[0]["deployment_id"] == "dep-1"

    def test_compare_missing_deployment(self):
        eng = _engine()
        eng.score_deployment("dep-1", composite_score=90.0)
        results = eng.compare_deployments(["dep-1", "dep-unknown"])
        assert len(results) == 1


# -------------------------------------------------------------------
# detect_degradation
# -------------------------------------------------------------------


class TestDetectDegradation:
    def test_insufficient_data(self):
        eng = _engine()
        eng.score_deployment("dep-1", composite_score=80.0)
        result = eng.detect_degradation("dep-1")
        assert result["degrading"] is False
        assert result["reason"] == "Insufficient data"

    def test_degradation_detected(self):
        eng = _engine()
        eng.score_deployment("dep-1", composite_score=90.0)
        eng.score_deployment("dep-1", composite_score=90.0)
        eng.score_deployment("dep-1", composite_score=30.0)
        eng.score_deployment("dep-1", composite_score=30.0)
        result = eng.detect_degradation("dep-1")
        assert result["degrading"] is True

    def test_stable_scores(self):
        eng = _engine()
        eng.score_deployment("dep-1", composite_score=80.0)
        eng.score_deployment("dep-1", composite_score=80.0)
        eng.score_deployment("dep-1", composite_score=78.0)
        eng.score_deployment("dep-1", composite_score=79.0)
        result = eng.detect_degradation("dep-1")
        assert result["degrading"] is False


# -------------------------------------------------------------------
# generate_health_report
# -------------------------------------------------------------------


class TestGenerateHealthReport:
    def test_basic_report(self):
        eng = _engine()
        eng.score_deployment("dep-1", composite_score=95.0)
        eng.score_deployment("dep-2", composite_score=30.0)
        eng.record_dimension_reading("dep-1", value=80.0)
        report = eng.generate_health_report()
        assert report.total_scores == 2
        assert report.total_readings == 1
        assert isinstance(report.by_grade, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_health_report()
        assert report.total_scores == 0
        assert report.avg_score == 0.0
        assert "All deployments within healthy range" in report.recommendations


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.score_deployment("dep-1")
        eng.record_dimension_reading("dep-1", value=50.0)
        count = eng.clear_data()
        assert count == 1
        assert len(eng.list_scores()) == 0
        assert len(eng.list_dimension_readings()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_scores"] == 0
        assert stats["total_readings"] == 0
        assert stats["failing_threshold"] == 40.0
        assert stats["grade_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.score_deployment("dep-1", composite_score=95.0)
        eng.score_deployment("dep-2", composite_score=30.0)
        stats = eng.get_stats()
        assert stats["total_scores"] == 2
        assert len(stats["grade_distribution"]) == 2
