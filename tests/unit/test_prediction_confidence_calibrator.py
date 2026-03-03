"""Tests for shieldops.analytics.prediction_confidence_calibrator."""

from __future__ import annotations

from shieldops.analytics.prediction_confidence_calibrator import (
    CalibrationAnalysis,
    CalibrationMethod,
    CalibrationRecord,
    CalibrationReport,
    CalibrationStatus,
    ConfidenceBand,
    PredictionConfidenceCalibrator,
)


def _engine(**kw) -> PredictionConfidenceCalibrator:
    return PredictionConfidenceCalibrator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_method_platt_scaling(self):
        assert CalibrationMethod.PLATT_SCALING == "platt_scaling"

    def test_method_isotonic(self):
        assert CalibrationMethod.ISOTONIC == "isotonic"

    def test_method_temperature(self):
        assert CalibrationMethod.TEMPERATURE == "temperature"

    def test_method_beta(self):
        assert CalibrationMethod.BETA == "beta"

    def test_method_histogram(self):
        assert CalibrationMethod.HISTOGRAM == "histogram"

    def test_band_very_high(self):
        assert ConfidenceBand.VERY_HIGH == "very_high"

    def test_band_high(self):
        assert ConfidenceBand.HIGH == "high"

    def test_band_medium(self):
        assert ConfidenceBand.MEDIUM == "medium"

    def test_band_low(self):
        assert ConfidenceBand.LOW == "low"

    def test_band_very_low(self):
        assert ConfidenceBand.VERY_LOW == "very_low"

    def test_status_calibrated(self):
        assert CalibrationStatus.CALIBRATED == "calibrated"

    def test_status_needs_calibration(self):
        assert CalibrationStatus.NEEDS_CALIBRATION == "needs_calibration"

    def test_status_in_progress(self):
        assert CalibrationStatus.IN_PROGRESS == "in_progress"

    def test_status_failed(self):
        assert CalibrationStatus.FAILED == "failed"

    def test_status_skipped(self):
        assert CalibrationStatus.SKIPPED == "skipped"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_calibration_record_defaults(self):
        r = CalibrationRecord()
        assert r.id
        assert r.model_id == ""
        assert r.calibration_method == CalibrationMethod.PLATT_SCALING
        assert r.confidence_band == ConfidenceBand.MEDIUM
        assert r.calibration_status == CalibrationStatus.NEEDS_CALIBRATION
        assert r.calibration_error == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_calibration_analysis_defaults(self):
        a = CalibrationAnalysis()
        assert a.id
        assert a.model_id == ""
        assert a.calibration_method == CalibrationMethod.PLATT_SCALING
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_calibration_report_defaults(self):
        r = CalibrationReport()
        assert r.id
        assert r.total_records == 0
        assert r.uncalibrated_count == 0
        assert r.avg_calibration_error == 0.0
        assert r.by_method == {}
        assert r.by_band == {}
        assert r.by_status == {}
        assert r.top_uncalibrated == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_init(self):
        eng = _engine()
        assert eng._max_records == 200000
        assert eng._calibration_error_threshold == 0.05

    def test_custom_init(self):
        eng = _engine(max_records=100, calibration_error_threshold=0.1)
        assert eng._max_records == 100
        assert eng._calibration_error_threshold == 0.1

    def test_empty_stats(self):
        eng = _engine()
        assert eng.get_stats()["total_records"] == 0


# ---------------------------------------------------------------------------
# record_calibration / get_calibration
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic_record(self):
        eng = _engine()
        r = eng.record_calibration(
            model_id="model-001",
            calibration_method=CalibrationMethod.ISOTONIC,
            confidence_band=ConfidenceBand.HIGH,
            calibration_status=CalibrationStatus.CALIBRATED,
            calibration_error=0.02,
            service="pred-svc",
            team="ml-team",
        )
        assert r.model_id == "model-001"
        assert r.calibration_method == CalibrationMethod.ISOTONIC
        assert r.calibration_error == 0.02

    def test_get_found(self):
        eng = _engine()
        r = eng.record_calibration(model_id="m-001", calibration_error=0.03)
        assert eng.get_calibration(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_calibration("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_calibration(model_id=f"m-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_calibrations
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_calibration(model_id="m-001")
        eng.record_calibration(model_id="m-002")
        assert len(eng.list_calibrations()) == 2

    def test_filter_by_method(self):
        eng = _engine()
        eng.record_calibration(model_id="m-001", calibration_method=CalibrationMethod.ISOTONIC)
        eng.record_calibration(model_id="m-002", calibration_method=CalibrationMethod.BETA)
        results = eng.list_calibrations(calibration_method=CalibrationMethod.ISOTONIC)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_calibration(model_id="m-001", calibration_status=CalibrationStatus.CALIBRATED)
        eng.record_calibration(model_id="m-002", calibration_status=CalibrationStatus.FAILED)
        results = eng.list_calibrations(calibration_status=CalibrationStatus.CALIBRATED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_calibration(model_id="m-001", team="ml-team")
        eng.record_calibration(model_id="m-002", team="data-team")
        assert len(eng.list_calibrations(team="ml-team")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_calibration(model_id=f"m-{i}")
        assert len(eng.list_calibrations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic_analysis(self):
        eng = _engine()
        a = eng.add_analysis(
            model_id="m-001",
            calibration_method=CalibrationMethod.TEMPERATURE,
            analysis_score=70.0,
            threshold=80.0,
            breached=True,
            description="high calibration error",
        )
        assert a.model_id == "m-001"
        assert a.analysis_score == 70.0
        assert a.breached is True

    def test_analysis_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(model_id=f"m-{i}")
        assert len(eng._analyses) == 2

    def test_analysis_defaults(self):
        eng = _engine()
        a = eng.add_analysis(model_id="m-test")
        assert a.calibration_method == CalibrationMethod.PLATT_SCALING
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_calibration(
            model_id="m-001",
            calibration_method=CalibrationMethod.PLATT_SCALING,
            calibration_error=0.02,
        )
        eng.record_calibration(
            model_id="m-002",
            calibration_method=CalibrationMethod.PLATT_SCALING,
            calibration_error=0.04,
        )
        result = eng.analyze_distribution()
        assert "platt_scaling" in result
        assert result["platt_scaling"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_severe_drifts
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_above_threshold(self):
        eng = _engine(calibration_error_threshold=0.05)
        eng.record_calibration(model_id="m-001", calibration_error=0.1)
        eng.record_calibration(model_id="m-002", calibration_error=0.02)
        results = eng.identify_severe_drifts()
        assert len(results) == 1
        assert results[0]["model_id"] == "m-001"

    def test_sorted_descending(self):
        eng = _engine(calibration_error_threshold=0.01)
        eng.record_calibration(model_id="m-001", calibration_error=0.08)
        eng.record_calibration(model_id="m-002", calibration_error=0.15)
        results = eng.identify_severe_drifts()
        assert results[0]["calibration_error"] == 0.15

    def test_empty(self):
        eng = _engine()
        assert eng.identify_severe_drifts() == []


# ---------------------------------------------------------------------------
# rank_by_severity
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_calibration(model_id="m-001", calibration_error=0.1)
        eng.record_calibration(model_id="m-002", calibration_error=0.02)
        results = eng.rank_by_severity()
        assert results[0]["model_id"] == "m-001"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_severity() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(model_id="m-001", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(model_id="m-001", analysis_score=20.0)
        eng.add_analysis(model_id="m-002", analysis_score=20.0)
        eng.add_analysis(model_id="m-003", analysis_score=80.0)
        eng.add_analysis(model_id="m-004", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(calibration_error_threshold=0.05)
        eng.record_calibration(
            model_id="m-001",
            calibration_method=CalibrationMethod.PLATT_SCALING,
            confidence_band=ConfidenceBand.LOW,
            calibration_status=CalibrationStatus.NEEDS_CALIBRATION,
            calibration_error=0.12,
        )
        report = eng.generate_report()
        assert isinstance(report, CalibrationReport)
        assert report.total_records == 1
        assert report.uncalibrated_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_calibration(model_id="m-001")
        eng.add_analysis(model_id="m-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["method_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_calibration(
            model_id="m-001",
            calibration_method=CalibrationMethod.PLATT_SCALING,
            team="ml-team",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_record_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_calibration(model_id=f"m-{i}")
        assert len(eng._records) == 3
        assert eng._records[0].model_id == "m-2"
