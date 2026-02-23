"""Tests for shieldops.changes.deployment_risk — DeploymentRiskPredictor."""

from __future__ import annotations

import pytest

from shieldops.changes.deployment_risk import (
    DeploymentRecord,
    DeploymentRiskPredictor,
    RiskAssessment,
    RiskFactor,
    RiskLevel,
)


def _predictor(**kw) -> DeploymentRiskPredictor:
    return DeploymentRiskPredictor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # RiskLevel (4 values)

    def test_risk_level_low(self):
        assert RiskLevel.LOW == "low"

    def test_risk_level_medium(self):
        assert RiskLevel.MEDIUM == "medium"

    def test_risk_level_high(self):
        assert RiskLevel.HIGH == "high"

    def test_risk_level_critical(self):
        assert RiskLevel.CRITICAL == "critical"

    # RiskFactor (5 values)

    def test_risk_factor_change_size(self):
        assert RiskFactor.CHANGE_SIZE == "change_size"

    def test_risk_factor_time_of_day(self):
        assert RiskFactor.TIME_OF_DAY == "time_of_day"

    def test_risk_factor_service_complexity(self):
        assert RiskFactor.SERVICE_COMPLEXITY == "service_complexity"

    def test_risk_factor_recent_failures(self):
        assert RiskFactor.RECENT_FAILURES == "recent_failures"

    def test_risk_factor_dependency_count(self):
        assert RiskFactor.DEPENDENCY_COUNT == "dependency_count"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_deployment_record_defaults(self):
        rec = DeploymentRecord(service="web", version="v1.0")
        assert rec.id
        assert rec.service == "web"
        assert rec.version == "v1.0"
        assert rec.change_size == 0
        assert rec.success is True
        assert rec.rollback_needed is False
        assert rec.deployer == ""
        assert rec.duration_seconds == 0.0
        assert rec.deployed_at > 0

    def test_risk_assessment_defaults(self):
        ra = RiskAssessment(service="web")
        assert ra.id
        assert ra.overall_risk == RiskLevel.LOW
        assert ra.risk_score == 0.0
        assert ra.factors == {}
        assert ra.recommendations == []
        assert ra.version == ""
        assert ra.assessed_at > 0


# ---------------------------------------------------------------------------
# record_deployment
# ---------------------------------------------------------------------------


class TestRecordDeployment:
    def test_basic_record(self):
        pred = _predictor()
        rec = pred.record_deployment("web", "v1.0")
        assert rec.service == "web"
        assert rec.version == "v1.0"
        assert rec.success is True
        history = pred.get_service_history("web")
        assert len(history) == 1

    def test_record_with_extra_fields(self):
        pred = _predictor()
        rec = pred.record_deployment(
            "web",
            "v2.0",
            change_size=150,
            success=False,
            rollback_needed=True,
        )
        assert rec.change_size == 150
        assert rec.success is False
        assert rec.rollback_needed is True

    def test_trims_to_max_records(self):
        pred = _predictor(max_records=3)
        pred.record_deployment("s1", "v1")
        pred.record_deployment("s2", "v2")
        pred.record_deployment("s3", "v3")
        pred.record_deployment("s4", "v4")
        stats = pred.get_stats()
        assert stats["total_records"] == 3


# ---------------------------------------------------------------------------
# assess_risk
# ---------------------------------------------------------------------------


class TestAssessRisk:
    def test_no_history_returns_low_risk(self):
        pred = _predictor()
        assessment = pred.assess_risk("web")
        assert assessment.overall_risk == RiskLevel.LOW
        assert assessment.risk_score == pytest.approx(0.0, abs=0.01)

    def test_all_failures_raises_risk(self):
        pred = _predictor()
        for _ in range(10):
            pred.record_deployment("web", "v1", success=False)
        assessment = pred.assess_risk("web")
        # failure_rate=1.0 => 40 pts alone
        assert assessment.risk_score >= 40.0

    def test_large_change_size_increases_risk(self):
        pred = _predictor()
        assessment = pred.assess_risk("web", change_size=600)
        # cs_factor=1.0 => 30 pts from change_size
        assert assessment.risk_score >= 30.0

    def test_rollback_history_increases_risk(self):
        pred = _predictor()
        for _ in range(5):
            pred.record_deployment(
                "web",
                "v1",
                rollback_needed=True,
            )
        assessment = pred.assess_risk("web")
        # rollback_rate=1.0 => 30 pts from rollback
        assert assessment.risk_score >= 30.0


# ---------------------------------------------------------------------------
# risk levels from score
# ---------------------------------------------------------------------------


class TestRiskLevels:
    def test_score_below_25_is_low(self):
        pred = _predictor()
        # No history, small change => score near 0
        assessment = pred.assess_risk("clean_svc")
        assert assessment.overall_risk == RiskLevel.LOW

    def test_score_25_to_49_is_medium(self):
        pred = _predictor()
        # All failures (40 pts) + tiny change (0) + no rollback (0) = 40
        for _ in range(10):
            pred.record_deployment("web", "v1", success=False)
        assessment = pred.assess_risk("web", change_size=0)
        assert assessment.overall_risk == RiskLevel.MEDIUM

    def test_score_50_to_74_is_high(self):
        pred = _predictor()
        for _ in range(10):
            pred.record_deployment(
                "web",
                "v1",
                success=False,
                rollback_needed=True,
            )
        # failure=40 + rollback=30 + change_size(0)=0 => 70
        assessment = pred.assess_risk("web", change_size=0)
        assert assessment.overall_risk == RiskLevel.HIGH

    def test_score_75_plus_is_critical(self):
        pred = _predictor()
        for _ in range(10):
            pred.record_deployment(
                "web",
                "v1",
                success=False,
                rollback_needed=True,
            )
        # failure=40 + rollback=30 + change_size(600)=30 => 100
        assessment = pred.assess_risk("web", change_size=600)
        assert assessment.overall_risk == RiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# change_size_factor
# ---------------------------------------------------------------------------


class TestChangeSizeFactor:
    def test_zero_returns_zero(self):
        pred = _predictor()
        assert pred._change_size_factor(0) == 0.0

    def test_below_50_returns_0_2(self):
        pred = _predictor()
        assert pred._change_size_factor(30) == pytest.approx(0.2)

    def test_below_200_returns_0_5(self):
        pred = _predictor()
        assert pred._change_size_factor(100) == pytest.approx(0.5)

    def test_below_500_returns_0_7(self):
        pred = _predictor()
        assert pred._change_size_factor(400) == pytest.approx(0.7)

    def test_500_plus_returns_1_0(self):
        pred = _predictor()
        assert pred._change_size_factor(500) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# recommendations
# ---------------------------------------------------------------------------


class TestRecommendations:
    def test_high_failure_rate_adds_recommendation(self):
        pred = _predictor()
        for _ in range(10):
            pred.record_deployment("web", "v1", success=False)
        assessment = pred.assess_risk("web")
        assert any("failure rate" in r.lower() for r in assessment.recommendations)

    def test_large_change_adds_recommendation(self):
        pred = _predictor()
        assessment = pred.assess_risk("web", change_size=600)
        assert any("change size" in r.lower() for r in assessment.recommendations)

    def test_high_rollback_adds_recommendation(self):
        pred = _predictor()
        for _ in range(10):
            pred.record_deployment(
                "web",
                "v1",
                rollback_needed=True,
            )
        assessment = pred.assess_risk("web")
        assert any("rollback" in r.lower() for r in assessment.recommendations)


# ---------------------------------------------------------------------------
# get_service_history
# ---------------------------------------------------------------------------


class TestGetServiceHistory:
    def test_returns_for_service(self):
        pred = _predictor()
        pred.record_deployment("web", "v1")
        pred.record_deployment("db", "v1")
        history = pred.get_service_history("web")
        assert len(history) == 1
        assert history[0].service == "web"

    def test_respects_limit(self):
        pred = _predictor()
        for i in range(10):
            pred.record_deployment("web", f"v{i}")
        history = pred.get_service_history("web", limit=3)
        assert len(history) == 3


# ---------------------------------------------------------------------------
# get_failure_rate
# ---------------------------------------------------------------------------


class TestGetFailureRate:
    def test_zero_when_no_data(self):
        pred = _predictor()
        assert pred.get_failure_rate("web") == 0.0

    def test_correct_rate(self):
        pred = _predictor()
        pred.record_deployment("web", "v1", success=True)
        pred.record_deployment("web", "v2", success=False)
        pred.record_deployment("web", "v3", success=True)
        pred.record_deployment("web", "v4", success=False)
        rate = pred.get_failure_rate("web")
        assert rate == pytest.approx(0.5, abs=0.001)


# ---------------------------------------------------------------------------
# list_assessments
# ---------------------------------------------------------------------------


class TestListAssessments:
    def test_filter_by_service(self):
        pred = _predictor()
        pred.assess_risk("web")
        pred.assess_risk("db")
        results = pred.list_assessments(service="web")
        assert len(results) == 1
        assert results[0].service == "web"

    def test_filter_by_risk(self):
        pred = _predictor()
        pred.assess_risk("clean_svc")  # LOW
        for _ in range(10):
            pred.record_deployment("bad", "v1", success=False)
        pred.assess_risk("bad")  # MEDIUM+
        low_results = pred.list_assessments(risk="low")
        assert all(a.overall_risk == RiskLevel.LOW for a in low_results)


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        pred = _predictor()
        stats = pred.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["services_tracked"] == 0
        assert stats["overall_success_rate"] == 0.0
        assert stats["overall_rollback_rate"] == 0.0

    def test_stats_populated(self):
        pred = _predictor()
        pred.record_deployment("web", "v1", success=True)
        pred.record_deployment("web", "v2", success=False)
        pred.record_deployment(
            "web",
            "v3",
            success=True,
            rollback_needed=True,
        )
        pred.assess_risk("web")
        stats = pred.get_stats()
        assert stats["total_records"] == 3
        assert stats["total_assessments"] == 1
        assert stats["services_tracked"] == 1
        assert stats["overall_success_rate"] == pytest.approx(
            2 / 3,
            abs=0.001,
        )
        assert stats["overall_rollback_rate"] == pytest.approx(
            1 / 3,
            abs=0.001,
        )
