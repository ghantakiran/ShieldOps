"""Tests for shieldops.changes.deployment_confidence — DeploymentConfidenceScorer."""

from __future__ import annotations

from shieldops.changes.deployment_confidence import (
    ConfidenceAssessment,
    ConfidenceFactor,
    ConfidenceFactorRecord,
    ConfidenceLevel,
    DeployDecision,
    DeploymentConfidenceReport,
    DeploymentConfidenceScorer,
)


def _engine(**kw) -> DeploymentConfidenceScorer:
    return DeploymentConfidenceScorer(**kw)


class TestEnums:
    def test_level_very_high(self):
        assert ConfidenceLevel.VERY_HIGH == "very_high"

    def test_level_high(self):
        assert ConfidenceLevel.HIGH == "high"

    def test_level_moderate(self):
        assert ConfidenceLevel.MODERATE == "moderate"

    def test_level_low(self):
        assert ConfidenceLevel.LOW == "low"

    def test_level_very_low(self):
        assert ConfidenceLevel.VERY_LOW == "very_low"

    def test_factor_test_coverage(self):
        assert ConfidenceFactor.TEST_COVERAGE == "test_coverage"

    def test_factor_rollback(self):
        assert ConfidenceFactor.ROLLBACK_READINESS == "rollback_readiness"

    def test_factor_change_size(self):
        assert ConfidenceFactor.CHANGE_SIZE == "change_size"

    def test_factor_blast_radius(self):
        assert ConfidenceFactor.BLAST_RADIUS == "blast_radius"

    def test_factor_team_exp(self):
        assert ConfidenceFactor.TEAM_EXPERIENCE == "team_experience"

    def test_decision_proceed(self):
        assert DeployDecision.PROCEED == "proceed"

    def test_decision_caution(self):
        assert DeployDecision.PROCEED_WITH_CAUTION == "proceed_with_caution"

    def test_decision_approval(self):
        assert DeployDecision.REQUIRE_APPROVAL == "require_approval"

    def test_decision_delay(self):
        assert DeployDecision.DELAY == "delay"

    def test_decision_block(self):
        assert DeployDecision.BLOCK == "block"


class TestModels:
    def test_confidence_assessment_defaults(self):
        a = ConfidenceAssessment()
        assert a.id
        assert a.deployment_id == ""
        assert a.service == ""
        assert a.score == 0.0
        assert a.level == ConfidenceLevel.MODERATE
        assert a.decision == DeployDecision.REQUIRE_APPROVAL
        assert a.created_at > 0

    def test_factor_record_defaults(self):
        f = ConfidenceFactorRecord()
        assert f.id
        assert f.deployment_id == ""
        assert f.factor == ConfidenceFactor.TEST_COVERAGE
        assert f.score == 0.0
        assert f.weight == 1.0

    def test_report_defaults(self):
        r = DeploymentConfidenceReport()
        assert r.total_assessments == 0
        assert r.avg_confidence == 0.0
        assert r.recommendations == []


class TestRecordFactor:
    def test_basic(self):
        eng = _engine()
        f = eng.record_factor(
            deployment_id="dep-1",
            factor=ConfidenceFactor.TEST_COVERAGE,
            score=85.0,
        )
        assert f.deployment_id == "dep-1"
        assert f.score == 85.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_factor(deployment_id=f"dep-{i}", score=50.0)
        assert len(eng._factors) == 3


class TestGetAssessment:
    def test_not_found(self):
        eng = _engine()
        assert eng.get_assessment("nonexistent") is None


class TestListAssessments:
    def test_filter_by_service(self):
        eng = _engine()
        eng.record_factor(deployment_id="dep-1", score=90.0)
        eng.assess_deployment("dep-1", service="svc-a")
        results = eng.list_assessments(service="svc-a")
        assert len(results) == 1


class TestAssessDeployment:
    def test_with_factors(self):
        eng = _engine()
        eng.record_factor(deployment_id="dep-1", score=90.0, weight=1.0)
        eng.record_factor(deployment_id="dep-1", score=80.0, weight=1.0)
        result = eng.assess_deployment("dep-1", service="svc-a")
        assert result.score == 85.0
        assert result.level == ConfidenceLevel.HIGH

    def test_no_factors(self):
        eng = _engine()
        result = eng.assess_deployment("dep-empty")
        assert result.score == 0.0
        assert result.decision == DeployDecision.BLOCK

    def test_low_confidence(self):
        eng = _engine()
        eng.record_factor(deployment_id="dep-1", score=30.0)
        result = eng.assess_deployment("dep-1")
        assert result.level == ConfidenceLevel.VERY_LOW


class TestIdentifyLowConfidence:
    def test_finds_low(self):
        eng = _engine(min_confidence_score=70.0)
        eng.record_factor(deployment_id="dep-1", score=50.0)
        eng.assess_deployment("dep-1", service="svc-a")
        results = eng.identify_low_confidence_deployments()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_confidence_deployments() == []


class TestAnalyzeFactorTrends:
    def test_with_data(self):
        eng = _engine()
        eng.record_factor(deployment_id="dep-1", factor=ConfidenceFactor.TEST_COVERAGE, score=80.0)
        eng.record_factor(deployment_id="dep-2", factor=ConfidenceFactor.TEST_COVERAGE, score=90.0)
        results = eng.analyze_factor_trends()
        assert len(results) == 1
        assert results[0]["avg_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_factor_trends() == []


class TestCompareDeployments:
    def test_basic(self):
        eng = _engine()
        eng.record_factor(deployment_id="dep-a", factor=ConfidenceFactor.TEST_COVERAGE, score=90.0)
        eng.record_factor(deployment_id="dep-b", factor=ConfidenceFactor.TEST_COVERAGE, score=70.0)
        result = eng.compare_deployments("dep-a", "dep-b")
        assert result["deployment_a"] == "dep-a"
        assert "test_coverage" in result["factors_a"]


class TestServiceConfidenceTrend:
    def test_with_data(self):
        eng = _engine()
        eng.record_factor(deployment_id="dep-1", score=80.0)
        eng.assess_deployment("dep-1", service="svc-a")
        results = eng.calculate_service_confidence_trend("svc-a")
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.calculate_service_confidence_trend("unknown") == []


class TestGenerateReportDC:
    def test_populated(self):
        eng = _engine(min_confidence_score=70.0)
        eng.record_factor(deployment_id="dep-1", score=50.0)
        eng.assess_deployment("dep-1")
        report = eng.generate_report()
        assert isinstance(report, DeploymentConfidenceReport)
        assert report.total_assessments == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "Deployment confidence levels are healthy" in report.recommendations


class TestClearDataDC:
    def test_clears(self):
        eng = _engine()
        eng.record_factor(deployment_id="dep-1", score=80.0)
        eng.assess_deployment("dep-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._factors) == 0


class TestGetStatsDC:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_assessments"] == 0
        assert stats["total_factors"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_factor(deployment_id="dep-1", score=80.0)
        eng.assess_deployment("dep-1", service="svc-a")
        stats = eng.get_stats()
        assert stats["total_assessments"] == 1
        assert stats["total_factors"] == 1
        assert stats["unique_services"] == 1
