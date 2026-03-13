"""Tests for DetectionRiskCalibrator."""

from __future__ import annotations

from shieldops.security.detection_risk_calibrator import (
    CalibrationMethod,
    DetectionAccuracy,
    DetectionRiskCalibrator,
    RiskAdjustment,
)


def _engine(**kw) -> DetectionRiskCalibrator:
    return DetectionRiskCalibrator(**kw)


class TestEnums:
    def test_calibration_method_values(self):
        for v in CalibrationMethod:
            assert isinstance(v.value, str)

    def test_detection_accuracy_values(self):
        for v in DetectionAccuracy:
            assert isinstance(v.value, str)

    def test_risk_adjustment_values(self):
        for v in RiskAdjustment:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(detection_id="d1")
        assert r.detection_id == "d1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(detection_id=f"d-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            detection_id="d1",
            original_score=50.0,
            calibrated_score=45.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "detection_id")
        assert a.detection_id == "d1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(detection_id="d1")
        assert eng.generate_report().total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(detection_id="d1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(detection_id="d1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestCalibrateDetectionRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            detection_id="d1",
            original_score=50.0,
            calibrated_score=45.0,
        )
        result = eng.calibrate_detection_risk()
        assert len(result) == 1
        assert result[0]["detection_id"] == "d1"

    def test_empty(self):
        assert _engine().calibrate_detection_risk() == []


class TestComputeFalsePositiveImpact:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            detection_id="d1",
            false_positive_rate=0.6,
        )
        result = eng.compute_false_positive_impact()
        assert len(result) == 1
        assert result[0]["is_noisy"] is True

    def test_empty(self):
        assert _engine().compute_false_positive_impact() == []


class TestRecommendRiskAdjustment:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            detection_id="d1",
            false_positive_rate=0.9,
        )
        result = eng.recommend_risk_adjustment()
        assert len(result) == 1
        assert result[0]["recommendation"] == "suppress"

    def test_empty(self):
        assert _engine().recommend_risk_adjustment() == []
