"""Tests for SecurityPostureAggregator."""

from __future__ import annotations

from shieldops.security.security_posture_aggregator import (
    Environment,
    PostureBaseline,
    PostureCategory,
    PostureData,
    PostureGrade,
    PostureReport,
    SecurityPostureAggregator,
)


def _engine(**kw) -> SecurityPostureAggregator:
    return SecurityPostureAggregator(**kw)


# --- Enum tests ---


class TestEnums:
    def test_env_aws(self):
        assert Environment.AWS == "aws"

    def test_env_gcp(self):
        assert Environment.GCP == "gcp"

    def test_env_azure(self):
        assert Environment.AZURE == "azure"

    def test_env_k8s(self):
        assert Environment.KUBERNETES == "kubernetes"

    def test_env_onprem(self):
        assert Environment.ON_PREM == "on_prem"

    def test_grade_a(self):
        assert PostureGrade.A == "A"

    def test_grade_f(self):
        assert PostureGrade.F == "F"

    def test_category_identity(self):
        assert PostureCategory.IDENTITY == "identity"

    def test_category_network(self):
        assert PostureCategory.NETWORK == "network"

    def test_category_data(self):
        assert PostureCategory.DATA == "data"

    def test_category_compute(self):
        assert PostureCategory.COMPUTE == "compute"

    def test_category_compliance(self):
        assert PostureCategory.COMPLIANCE == "compliance"


# --- Model tests ---


class TestModels:
    def test_posture_defaults(self):
        p = PostureData()
        assert p.id
        assert p.environment == Environment.AWS
        assert p.score == 0.0
        assert p.grade == PostureGrade.F

    def test_baseline_defaults(self):
        b = PostureBaseline()
        assert b.id
        assert b.baseline_score == 0.0

    def test_report_defaults(self):
        r = PostureReport()
        assert r.total_entries == 0
        assert r.drift_detected is False


# --- collect_posture_data ---


class TestCollectPosture:
    def test_basic(self):
        eng = _engine()
        p = eng.collect_posture_data(
            environment=Environment.GCP,
            category=PostureCategory.NETWORK,
            score=85.0,
            service="vpc",
            team="infra",
        )
        assert p.environment == Environment.GCP
        assert p.score == 85.0
        assert p.grade == PostureGrade.B

    def test_grade_a(self):
        eng = _engine()
        p = eng.collect_posture_data(score=95.0)
        assert p.grade == PostureGrade.A

    def test_grade_f(self):
        eng = _engine()
        p = eng.collect_posture_data(score=20.0)
        assert p.grade == PostureGrade.F

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.collect_posture_data(score=float(i * 10))
        assert len(eng._entries) == 3


# --- aggregate_scores ---


class TestAggregateScores:
    def test_with_data(self):
        eng = _engine()
        eng.collect_posture_data(environment=Environment.AWS, score=80.0)
        eng.collect_posture_data(environment=Environment.AWS, score=60.0)
        eng.collect_posture_data(environment=Environment.GCP, score=90.0)
        result = eng.aggregate_scores()
        assert result["environments"]["aws"] == 70.0
        assert result["environments"]["gcp"] == 90.0
        assert result["overall"] > 0

    def test_empty(self):
        eng = _engine()
        result = eng.aggregate_scores()
        assert result["overall"] == 0.0


# --- detect_posture_drift ---


class TestDetectDrift:
    def test_drift_detected(self):
        eng = _engine()
        eng.compare_baselines(Environment.AWS, 90.0)
        eng.collect_posture_data(environment=Environment.AWS, score=70.0)
        drifts = eng.detect_posture_drift(drift_threshold=10.0)
        assert len(drifts) == 1
        assert drifts[0]["direction"] == "degraded"

    def test_no_drift(self):
        eng = _engine()
        eng.compare_baselines(Environment.AWS, 80.0)
        eng.collect_posture_data(environment=Environment.AWS, score=82.0)
        drifts = eng.detect_posture_drift(drift_threshold=10.0)
        assert len(drifts) == 0

    def test_improved(self):
        eng = _engine()
        eng.compare_baselines(Environment.AWS, 50.0)
        eng.collect_posture_data(environment=Environment.AWS, score=80.0)
        drifts = eng.detect_posture_drift(drift_threshold=10.0)
        assert drifts[0]["direction"] == "improved"


# --- generate_posture_report ---


class TestPostureReport:
    def test_populated(self):
        eng = _engine(score_threshold=80.0)
        eng.collect_posture_data(score=40.0, description="weak encryption")
        report = eng.generate_posture_report()
        assert isinstance(report, PostureReport)
        assert report.total_entries == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_posture_report()
        assert len(report.recommendations) > 0


# --- compare_baselines ---


class TestBaselines:
    def test_store(self):
        eng = _engine()
        b = eng.compare_baselines(Environment.AZURE, 75.0)
        assert b.environment == Environment.AZURE
        assert b.baseline_score == 75.0

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.compare_baselines(Environment.AWS, float(i * 10))
        assert len(eng._baselines) == 2


# --- stats / clear ---


class TestStatsAndClear:
    def test_stats(self):
        eng = _engine()
        eng.collect_posture_data(service="s", team="t")
        stats = eng.get_stats()
        assert stats["total_entries"] == 1
        assert stats["unique_teams"] == 1

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_entries"] == 0

    def test_clear(self):
        eng = _engine()
        eng.collect_posture_data()
        eng.compare_baselines(Environment.AWS, 50.0)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._entries) == 0
        assert len(eng._baselines) == 0
