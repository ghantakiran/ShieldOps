"""Tests for shieldops.incidents.severity_calibrator — IncidentSeverityCalibrator."""

from __future__ import annotations

from shieldops.incidents.severity_calibrator import (
    CalibrationReport,
    CalibrationResult,
    CalibrationRule,
    ImpactDimension,
    IncidentSeverityCalibrator,
    SeverityLevel,
    SeverityRecord,
)


def _engine(**kw) -> IncidentSeverityCalibrator:
    return IncidentSeverityCalibrator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # SeverityLevel (5)
    def test_severity_sev1(self):
        assert SeverityLevel.SEV1 == "sev1"

    def test_severity_sev2(self):
        assert SeverityLevel.SEV2 == "sev2"

    def test_severity_sev3(self):
        assert SeverityLevel.SEV3 == "sev3"

    def test_severity_sev4(self):
        assert SeverityLevel.SEV4 == "sev4"

    def test_severity_sev5(self):
        assert SeverityLevel.SEV5 == "sev5"

    # CalibrationResult (5)
    def test_result_correct(self):
        assert CalibrationResult.CORRECT == "correct"

    def test_result_over_classified(self):
        assert CalibrationResult.OVER_CLASSIFIED == "over_classified"

    def test_result_under_classified(self):
        assert CalibrationResult.UNDER_CLASSIFIED == "under_classified"

    def test_result_needs_review(self):
        assert CalibrationResult.NEEDS_REVIEW == "needs_review"

    def test_result_ambiguous(self):
        assert CalibrationResult.AMBIGUOUS == "ambiguous"

    # ImpactDimension (5)
    def test_dim_user_count(self):
        assert ImpactDimension.USER_COUNT == "user_count"

    def test_dim_revenue(self):
        assert ImpactDimension.REVENUE == "revenue"

    def test_dim_duration(self):
        assert ImpactDimension.DURATION == "duration"

    def test_dim_service_count(self):
        assert ImpactDimension.SERVICE_COUNT == "service_count"

    def test_dim_data_loss(self):
        assert ImpactDimension.DATA_LOSS == "data_loss"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = SeverityRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.initial_severity == SeverityLevel.SEV3
        assert r.calibrated_severity == SeverityLevel.SEV3
        assert r.calibration_result == (CalibrationResult.NEEDS_REVIEW)
        assert r.users_affected == 0
        assert r.revenue_impact == 0.0
        assert r.duration_minutes == 0
        assert r.impact_scores == {}
        assert r.created_at > 0

    def test_rule_defaults(self):
        r = CalibrationRule()
        assert r.id
        assert r.dimension == ImpactDimension.USER_COUNT
        assert r.threshold == 0.0
        assert r.maps_to_severity == SeverityLevel.SEV3
        assert r.weight == 1.0

    def test_report_defaults(self):
        r = CalibrationReport()
        assert r.total_records == 0
        assert r.accuracy_pct == 0.0
        assert r.over_classified_pct == 0.0
        assert r.under_classified_pct == 0.0
        assert r.by_severity == {}
        assert r.by_result == {}
        assert r.recommendations == []


# -------------------------------------------------------------------
# record_severity
# -------------------------------------------------------------------


class TestRecordSeverity:
    def test_basic_record(self):
        eng = _engine()
        r = eng.record_severity("INC-001", SeverityLevel.SEV2)
        assert r.incident_id == "INC-001"
        assert r.initial_severity == SeverityLevel.SEV2

    def test_with_impact_data(self):
        eng = _engine()
        r = eng.record_severity(
            "INC-002",
            SeverityLevel.SEV1,
            users_affected=50000,
            revenue_impact=250000.0,
            duration_minutes=120,
        )
        assert r.users_affected == 50000
        assert r.revenue_impact == 250000.0
        assert r.duration_minutes == 120

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_severity("INC-001", SeverityLevel.SEV3)
        r2 = eng.record_severity("INC-002", SeverityLevel.SEV3)
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_severity(f"INC-{i}", SeverityLevel.SEV3)
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_record
# -------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_severity("INC-001", SeverityLevel.SEV3)
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# -------------------------------------------------------------------
# list_records
# -------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_severity("INC-001", SeverityLevel.SEV3)
        eng.record_severity("INC-002", SeverityLevel.SEV3)
        assert len(eng.list_records()) == 2

    def test_filter_by_incident(self):
        eng = _engine()
        eng.record_severity("INC-001", SeverityLevel.SEV3)
        eng.record_severity("INC-002", SeverityLevel.SEV3)
        results = eng.list_records(incident_id="INC-001")
        assert len(results) == 1

    def test_filter_by_result(self):
        eng = _engine()
        r = eng.record_severity(
            "INC-001",
            SeverityLevel.SEV3,
            users_affected=5,
        )
        eng.calibrate_severity(r.id)
        results = eng.list_records(calibration_result=CalibrationResult.CORRECT)
        # SEV3 with 5 users => SEV5, so over_classified
        assert len(results) == 0


# -------------------------------------------------------------------
# calibrate_severity
# -------------------------------------------------------------------


class TestCalibrateSeverity:
    def test_correct_classification(self):
        eng = _engine()
        r = eng.record_severity(
            "INC-001",
            SeverityLevel.SEV1,
            users_affected=50000,
            revenue_impact=200000.0,
        )
        result = eng.calibrate_severity(r.id)
        assert result["result"] == "correct"

    def test_over_classified(self):
        eng = _engine()
        r = eng.record_severity(
            "INC-002",
            SeverityLevel.SEV1,
            users_affected=5,
            revenue_impact=10.0,
            duration_minutes=2,
        )
        result = eng.calibrate_severity(r.id)
        assert result["result"] == "over_classified"

    def test_under_classified(self):
        eng = _engine()
        r = eng.record_severity(
            "INC-003",
            SeverityLevel.SEV5,
            users_affected=50000,
            revenue_impact=500000.0,
        )
        result = eng.calibrate_severity(r.id)
        assert result["result"] == "under_classified"

    def test_not_found(self):
        eng = _engine()
        result = eng.calibrate_severity("bad")
        assert result.get("error") == "record_not_found"


# -------------------------------------------------------------------
# add_calibration_rule
# -------------------------------------------------------------------


class TestAddCalibrationRule:
    def test_add_rule(self):
        eng = _engine()
        rule = eng.add_calibration_rule(
            ImpactDimension.USER_COUNT,
            threshold=10000.0,
            maps_to_severity=SeverityLevel.SEV1,
        )
        assert rule.dimension == ImpactDimension.USER_COUNT
        assert rule.threshold == 10000.0
        assert len(eng._rules) == 1

    def test_rule_applied_in_calibration(self):
        eng = _engine()
        eng.add_calibration_rule(
            ImpactDimension.USER_COUNT,
            threshold=100.0,
            maps_to_severity=SeverityLevel.SEV2,
        )
        r = eng.record_severity(
            "INC-001",
            SeverityLevel.SEV4,
            users_affected=200,
        )
        result = eng.calibrate_severity(r.id)
        assert result["calibrated"] == "sev2"


# -------------------------------------------------------------------
# calculate_accuracy
# -------------------------------------------------------------------


class TestCalculateAccuracy:
    def test_empty(self):
        eng = _engine()
        result = eng.calculate_accuracy()
        assert result["accuracy_pct"] == 0.0

    def test_all_correct(self):
        eng = _engine()
        for i in range(5):
            r = eng.record_severity(
                f"INC-{i}",
                SeverityLevel.SEV1,
                users_affected=50000,
            )
            eng.calibrate_severity(r.id)
        result = eng.calculate_accuracy()
        assert result["accuracy_pct"] == 100.0

    def test_partial_accuracy(self):
        eng = _engine()
        r1 = eng.record_severity(
            "INC-1",
            SeverityLevel.SEV1,
            users_affected=50000,
        )
        eng.calibrate_severity(r1.id)
        r2 = eng.record_severity(
            "INC-2",
            SeverityLevel.SEV1,
            users_affected=1,
        )
        eng.calibrate_severity(r2.id)
        result = eng.calculate_accuracy()
        assert result["accuracy_pct"] == 50.0


# -------------------------------------------------------------------
# detect_classification_drift
# -------------------------------------------------------------------


class TestDetectClassificationDrift:
    def test_not_enough_data(self):
        eng = _engine()
        result = eng.detect_classification_drift()
        assert result["drift_detected"] is False

    def test_over_classification_drift(self):
        eng = _engine()
        for i in range(12):
            r = eng.record_severity(
                f"INC-{i}",
                SeverityLevel.SEV1,
                users_affected=1,
            )
            eng.calibrate_severity(r.id)
        result = eng.detect_classification_drift()
        assert result["drift_detected"] is True
        assert "over" in result["reason"].lower()

    def test_no_drift(self):
        eng = _engine()
        for i in range(12):
            r = eng.record_severity(
                f"INC-{i}",
                SeverityLevel.SEV1,
                users_affected=50000,
            )
            eng.calibrate_severity(r.id)
        result = eng.detect_classification_drift()
        assert result["drift_detected"] is False


# -------------------------------------------------------------------
# identify_miscalibrated_services
# -------------------------------------------------------------------


class TestIdentifyMiscalibratedServices:
    def test_with_miscalibrated(self):
        eng = _engine()
        r = eng.record_severity(
            "INC-001",
            SeverityLevel.SEV1,
            users_affected=1,
        )
        eng.calibrate_severity(r.id)
        results = eng.identify_miscalibrated_services()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"

    def test_no_miscalibrated(self):
        eng = _engine()
        r = eng.record_severity(
            "INC-001",
            SeverityLevel.SEV1,
            users_affected=50000,
        )
        eng.calibrate_severity(r.id)
        results = eng.identify_miscalibrated_services()
        assert len(results) == 0


# -------------------------------------------------------------------
# generate_calibration_report
# -------------------------------------------------------------------


class TestGenerateCalibrationReport:
    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_calibration_report()
        assert report.total_records == 0
        assert report.accuracy_pct == 0.0

    def test_with_data(self):
        eng = _engine()
        r1 = eng.record_severity(
            "INC-1",
            SeverityLevel.SEV1,
            users_affected=50000,
        )
        eng.calibrate_severity(r1.id)
        r2 = eng.record_severity(
            "INC-2",
            SeverityLevel.SEV1,
            users_affected=1,
        )
        eng.calibrate_severity(r2.id)
        report = eng.generate_calibration_report()
        assert report.total_records == 2
        assert report.accuracy_pct == 50.0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_severity("INC-001", SeverityLevel.SEV3)
        eng.add_calibration_rule(
            ImpactDimension.USER_COUNT,
            threshold=100.0,
            maps_to_severity=SeverityLevel.SEV2,
        )
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0

    def test_populated(self):
        eng = _engine()
        r = eng.record_severity(
            "INC-001",
            SeverityLevel.SEV2,
            users_affected=5000,
        )
        eng.calibrate_severity(r.id)
        eng.add_calibration_rule(
            ImpactDimension.REVENUE,
            threshold=50000.0,
            maps_to_severity=SeverityLevel.SEV1,
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["total_rules"] == 1
        assert stats["unique_incidents"] == 1
