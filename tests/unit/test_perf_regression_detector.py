"""Tests for PerfRegressionDetector."""

from __future__ import annotations

from shieldops.analytics.perf_regression_detector import (
    DetectionMethod,
    PerfRegressionDetector,
    RegressionSeverity,
    RegressionType,
)


def _engine(**kw) -> PerfRegressionDetector:
    return PerfRegressionDetector(**kw)


class TestEnums:
    def test_regression_severity_values(self):
        for v in RegressionSeverity:
            assert isinstance(v.value, str)

    def test_detection_method_values(self):
        for v in DetectionMethod:
            assert isinstance(v.value, str)

    def test_regression_type_values(self):
        for v in RegressionType:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(deployment_id="d1")
        assert r.deployment_id == "d1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(deployment_id=f"d-{i}")
        assert len(eng._records) == 5

    def test_with_all_params(self):
        eng = _engine()
        r = eng.add_record(
            deployment_id="d1",
            regression_severity=RegressionSeverity.CRITICAL,
            detection_method=DetectionMethod.ML_BASED,
            regression_type=RegressionType.THROUGHPUT,
            magnitude=25.0,
        )
        assert r.magnitude == 25.0


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(deployment_id="d1", magnitude=10.0)
        a = eng.process(r.id)
        assert hasattr(a, "deployment_id")
        assert a.deployment_id == "d1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(deployment_id="d1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(deployment_id="d1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(deployment_id="d1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeRegressionMagnitude:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(deployment_id="d1", magnitude=15.0)
        result = eng.compute_regression_magnitude()
        assert len(result) == 1
        assert result[0]["deployment_id"] == "d1"

    def test_empty(self):
        assert _engine().compute_regression_magnitude() == []


class TestDetectLatentRegressions:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            deployment_id="d1",
            magnitude=5.0,
            regression_severity=RegressionSeverity.MINOR,
        )
        result = eng.detect_latent_regressions()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().detect_latent_regressions() == []


class TestRankDeploymentsByRegressionRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(deployment_id="d1", magnitude=15.0)
        eng.add_record(deployment_id="d2", magnitude=25.0)
        result = eng.rank_deployments_by_regression_risk()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_deployments_by_regression_risk() == []
