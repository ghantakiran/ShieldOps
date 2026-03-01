"""Tests for shieldops.changes.deploy_verification_tracker — DeployVerificationTracker."""

from __future__ import annotations

from shieldops.changes.deploy_verification_tracker import (
    DeployVerificationReport,
    DeployVerificationTracker,
    VerificationMetric,
    VerificationRecord,
    VerificationResult,
    VerificationScope,
    VerificationStep,
)


def _engine(**kw) -> DeployVerificationTracker:
    return DeployVerificationTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_step_smoke_test(self):
        assert VerificationStep.SMOKE_TEST == "smoke_test"

    def test_step_integration_test(self):
        assert VerificationStep.INTEGRATION_TEST == "integration_test"

    def test_step_canary_check(self):
        assert VerificationStep.CANARY_CHECK == "canary_check"

    def test_step_health_probe(self):
        assert VerificationStep.HEALTH_PROBE == "health_probe"

    def test_step_rollback_test(self):
        assert VerificationStep.ROLLBACK_TEST == "rollback_test"

    def test_result_passed(self):
        assert VerificationResult.PASSED == "passed"

    def test_result_failed(self):
        assert VerificationResult.FAILED == "failed"

    def test_result_skipped(self):
        assert VerificationResult.SKIPPED == "skipped"

    def test_result_timeout(self):
        assert VerificationResult.TIMEOUT == "timeout"

    def test_result_partial(self):
        assert VerificationResult.PARTIAL == "partial"

    def test_scope_unit(self):
        assert VerificationScope.UNIT == "unit"

    def test_scope_service(self):
        assert VerificationScope.SERVICE == "service"

    def test_scope_cluster(self):
        assert VerificationScope.CLUSTER == "cluster"

    def test_scope_region(self):
        assert VerificationScope.REGION == "region"

    def test_scope_global(self):
        assert VerificationScope.GLOBAL == "global"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_verification_record_defaults(self):
        r = VerificationRecord()
        assert r.id
        assert r.deploy_id == ""
        assert r.verification_step == VerificationStep.SMOKE_TEST
        assert r.verification_result == VerificationResult.PASSED
        assert r.verification_scope == VerificationScope.UNIT
        assert r.coverage_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_verification_metric_defaults(self):
        m = VerificationMetric()
        assert m.id
        assert m.deploy_id == ""
        assert m.verification_step == VerificationStep.SMOKE_TEST
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_deploy_verification_report_defaults(self):
        r = DeployVerificationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.failed_verifications == 0
        assert r.avg_coverage_pct == 0.0
        assert r.by_step == {}
        assert r.by_result == {}
        assert r.by_scope == {}
        assert r.top_failing == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_verification
# ---------------------------------------------------------------------------


class TestRecordVerification:
    def test_basic(self):
        eng = _engine()
        r = eng.record_verification(
            deploy_id="DEP-001",
            verification_step=VerificationStep.SMOKE_TEST,
            verification_result=VerificationResult.PASSED,
            verification_scope=VerificationScope.SERVICE,
            coverage_pct=95.0,
            service="api-gw",
            team="sre",
        )
        assert r.deploy_id == "DEP-001"
        assert r.verification_step == VerificationStep.SMOKE_TEST
        assert r.verification_result == VerificationResult.PASSED
        assert r.verification_scope == VerificationScope.SERVICE
        assert r.coverage_pct == 95.0
        assert r.service == "api-gw"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_verification(deploy_id=f"DEP-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_verification
# ---------------------------------------------------------------------------


class TestGetVerification:
    def test_found(self):
        eng = _engine()
        r = eng.record_verification(
            deploy_id="DEP-001",
            verification_result=VerificationResult.FAILED,
        )
        result = eng.get_verification(r.id)
        assert result is not None
        assert result.verification_result == VerificationResult.FAILED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_verification("nonexistent") is None


# ---------------------------------------------------------------------------
# list_verifications
# ---------------------------------------------------------------------------


class TestListVerifications:
    def test_list_all(self):
        eng = _engine()
        eng.record_verification(deploy_id="DEP-001")
        eng.record_verification(deploy_id="DEP-002")
        assert len(eng.list_verifications()) == 2

    def test_filter_by_step(self):
        eng = _engine()
        eng.record_verification(
            deploy_id="DEP-001",
            verification_step=VerificationStep.SMOKE_TEST,
        )
        eng.record_verification(
            deploy_id="DEP-002",
            verification_step=VerificationStep.CANARY_CHECK,
        )
        results = eng.list_verifications(
            step=VerificationStep.SMOKE_TEST,
        )
        assert len(results) == 1

    def test_filter_by_result(self):
        eng = _engine()
        eng.record_verification(
            deploy_id="DEP-001",
            verification_result=VerificationResult.PASSED,
        )
        eng.record_verification(
            deploy_id="DEP-002",
            verification_result=VerificationResult.FAILED,
        )
        results = eng.list_verifications(
            result=VerificationResult.PASSED,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_verification(deploy_id="DEP-001", service="api-gw")
        eng.record_verification(deploy_id="DEP-002", service="auth")
        results = eng.list_verifications(service="api-gw")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_verification(deploy_id=f"DEP-{i}")
        assert len(eng.list_verifications(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            deploy_id="DEP-001",
            verification_step=VerificationStep.HEALTH_PROBE,
            metric_score=88.5,
            threshold=80.0,
            breached=True,
            description="latency threshold exceeded",
        )
        assert m.deploy_id == "DEP-001"
        assert m.verification_step == VerificationStep.HEALTH_PROBE
        assert m.metric_score == 88.5
        assert m.threshold == 80.0
        assert m.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(deploy_id=f"DEP-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_verification_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeVerificationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_verification(
            deploy_id="DEP-001",
            verification_step=VerificationStep.SMOKE_TEST,
            coverage_pct=90.0,
        )
        eng.record_verification(
            deploy_id="DEP-002",
            verification_step=VerificationStep.SMOKE_TEST,
            coverage_pct=80.0,
        )
        result = eng.analyze_verification_distribution()
        assert "smoke_test" in result
        assert result["smoke_test"]["count"] == 2
        assert result["smoke_test"]["avg_coverage_pct"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_verification_distribution() == {}


# ---------------------------------------------------------------------------
# identify_failed_verifications
# ---------------------------------------------------------------------------


class TestIdentifyFailedVerifications:
    def test_detects_failed_and_skipped(self):
        eng = _engine()
        eng.record_verification(
            deploy_id="DEP-001",
            verification_result=VerificationResult.FAILED,
        )
        eng.record_verification(
            deploy_id="DEP-002",
            verification_result=VerificationResult.SKIPPED,
        )
        eng.record_verification(
            deploy_id="DEP-003",
            verification_result=VerificationResult.PASSED,
        )
        results = eng.identify_failed_verifications()
        assert len(results) == 2
        assert results[0]["deploy_id"] == "DEP-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failed_verifications() == []


# ---------------------------------------------------------------------------
# rank_by_coverage
# ---------------------------------------------------------------------------


class TestRankByCoverage:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_verification(deploy_id="DEP-001", service="api-gw", coverage_pct=90.0)
        eng.record_verification(deploy_id="DEP-002", service="auth", coverage_pct=60.0)
        results = eng.rank_by_coverage()
        assert len(results) == 2
        assert results[0]["service"] == "auth"
        assert results[0]["avg_coverage_pct"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_coverage() == []


# ---------------------------------------------------------------------------
# detect_verification_trends
# ---------------------------------------------------------------------------


class TestDetectVerificationTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_metric(deploy_id="DEP-001", metric_score=50.0)
        result = eng.detect_verification_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_metric(deploy_id="DEP-001", metric_score=20.0)
        eng.add_metric(deploy_id="DEP-002", metric_score=20.0)
        eng.add_metric(deploy_id="DEP-003", metric_score=80.0)
        eng.add_metric(deploy_id="DEP-004", metric_score=80.0)
        result = eng.detect_verification_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_verification_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_verification(
            deploy_id="DEP-001",
            verification_step=VerificationStep.SMOKE_TEST,
            verification_result=VerificationResult.FAILED,
            verification_scope=VerificationScope.SERVICE,
            coverage_pct=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, DeployVerificationReport)
        assert report.total_records == 1
        assert report.failed_verifications == 1
        assert len(report.top_failing) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_verification(deploy_id="DEP-001")
        eng.add_metric(deploy_id="DEP-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["step_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_verification(
            deploy_id="DEP-001",
            verification_step=VerificationStep.SMOKE_TEST,
            service="api-gw",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "smoke_test" in stats["step_distribution"]
