"""Tests for shieldops.analytics.training_data_validator — TrainingDataValidator."""

from __future__ import annotations

from shieldops.analytics.training_data_validator import (
    DataQuality,
    TrainingDataValidator,
    ValidationAnalysis,
    ValidationCheck,
    ValidationRecord,
    ValidationReport,
    ValidationStatus,
)


def _engine(**kw) -> TrainingDataValidator:
    return TrainingDataValidator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_check_schema(self):
        assert ValidationCheck.SCHEMA == "schema"

    def test_check_distribution(self):
        assert ValidationCheck.DISTRIBUTION == "distribution"

    def test_check_outlier(self):
        assert ValidationCheck.OUTLIER == "outlier"

    def test_check_missing(self):
        assert ValidationCheck.MISSING == "missing"

    def test_check_bias(self):
        assert ValidationCheck.BIAS == "bias"

    def test_quality_excellent(self):
        assert DataQuality.EXCELLENT == "excellent"

    def test_quality_good(self):
        assert DataQuality.GOOD == "good"

    def test_quality_acceptable(self):
        assert DataQuality.ACCEPTABLE == "acceptable"

    def test_quality_poor(self):
        assert DataQuality.POOR == "poor"

    def test_quality_unacceptable(self):
        assert DataQuality.UNACCEPTABLE == "unacceptable"

    def test_status_passed(self):
        assert ValidationStatus.PASSED == "passed"  # noqa: S105

    def test_status_failed(self):
        assert ValidationStatus.FAILED == "failed"

    def test_status_warning(self):
        assert ValidationStatus.WARNING == "warning"

    def test_status_skipped(self):
        assert ValidationStatus.SKIPPED == "skipped"

    def test_status_in_progress(self):
        assert ValidationStatus.IN_PROGRESS == "in_progress"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_validation_record_defaults(self):
        r = ValidationRecord()
        assert r.id
        assert r.dataset_id == ""
        assert r.model_id == ""
        assert r.validation_check == ValidationCheck.SCHEMA
        assert r.data_quality == DataQuality.ACCEPTABLE
        assert r.validation_status == ValidationStatus.IN_PROGRESS
        assert r.quality_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_validation_analysis_defaults(self):
        a = ValidationAnalysis()
        assert a.id
        assert a.dataset_id == ""
        assert a.validation_check == ValidationCheck.SCHEMA
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_validation_report_defaults(self):
        r = ValidationReport()
        assert r.id
        assert r.total_records == 0
        assert r.failed_count == 0
        assert r.avg_quality_score == 0.0
        assert r.by_check == {}
        assert r.by_quality == {}
        assert r.by_status == {}
        assert r.top_failures == []
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
        assert eng._quality_threshold == 0.75

    def test_custom_init(self):
        eng = _engine(max_records=500, quality_threshold=0.9)
        assert eng._max_records == 500
        assert eng._quality_threshold == 0.9

    def test_empty_stats(self):
        eng = _engine()
        assert eng.get_stats()["total_records"] == 0


# ---------------------------------------------------------------------------
# record_validation / get_validation
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic_record(self):
        eng = _engine()
        r = eng.record_validation(
            dataset_id="ds-001",
            model_id="model-001",
            validation_check=ValidationCheck.DISTRIBUTION,
            data_quality=DataQuality.GOOD,
            validation_status=ValidationStatus.PASSED,
            quality_score=0.9,
            service="ml-svc",
            team="data-team",
        )
        assert r.dataset_id == "ds-001"
        assert r.validation_check == ValidationCheck.DISTRIBUTION
        assert r.quality_score == 0.9

    def test_get_found(self):
        eng = _engine()
        r = eng.record_validation(dataset_id="ds-001", quality_score=0.8)
        assert eng.get_validation(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_validation("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_validation(dataset_id=f"ds-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_validations
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_validation(dataset_id="ds-001")
        eng.record_validation(dataset_id="ds-002")
        assert len(eng.list_validations()) == 2

    def test_filter_by_check(self):
        eng = _engine()
        eng.record_validation(dataset_id="ds-001", validation_check=ValidationCheck.SCHEMA)
        eng.record_validation(dataset_id="ds-002", validation_check=ValidationCheck.BIAS)
        assert len(eng.list_validations(validation_check=ValidationCheck.SCHEMA)) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_validation(dataset_id="ds-001", validation_status=ValidationStatus.PASSED)
        eng.record_validation(dataset_id="ds-002", validation_status=ValidationStatus.FAILED)
        assert len(eng.list_validations(validation_status=ValidationStatus.PASSED)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_validation(dataset_id="ds-001", team="data-team")
        eng.record_validation(dataset_id="ds-002", team="ml-team")
        assert len(eng.list_validations(team="data-team")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_validation(dataset_id=f"ds-{i}")
        assert len(eng.list_validations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic_analysis(self):
        eng = _engine()
        a = eng.add_analysis(
            dataset_id="ds-001",
            validation_check=ValidationCheck.BIAS,
            analysis_score=60.0,
            threshold=75.0,
            breached=True,
            description="bias detected",
        )
        assert a.dataset_id == "ds-001"
        assert a.analysis_score == 60.0
        assert a.breached is True

    def test_analysis_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(dataset_id=f"ds-{i}")
        assert len(eng._analyses) == 2

    def test_analysis_defaults(self):
        eng = _engine()
        a = eng.add_analysis(dataset_id="ds-test")
        assert a.validation_check == ValidationCheck.SCHEMA
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_validation(
            dataset_id="ds-001", validation_check=ValidationCheck.SCHEMA, quality_score=0.8
        )
        eng.record_validation(
            dataset_id="ds-002", validation_check=ValidationCheck.SCHEMA, quality_score=0.9
        )
        result = eng.analyze_distribution()
        assert "schema" in result
        assert result["schema"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_severe_drifts
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(quality_threshold=0.75)
        eng.record_validation(dataset_id="ds-001", quality_score=0.5)
        eng.record_validation(dataset_id="ds-002", quality_score=0.9)
        results = eng.identify_severe_drifts()
        assert len(results) == 1
        assert results[0]["dataset_id"] == "ds-001"

    def test_sorted_ascending(self):
        eng = _engine(quality_threshold=0.75)
        eng.record_validation(dataset_id="ds-001", quality_score=0.6)
        eng.record_validation(dataset_id="ds-002", quality_score=0.4)
        results = eng.identify_severe_drifts()
        assert results[0]["quality_score"] == 0.4

    def test_empty(self):
        eng = _engine()
        assert eng.identify_severe_drifts() == []


# ---------------------------------------------------------------------------
# rank_by_severity
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_validation(dataset_id="ds-001", quality_score=0.9)
        eng.record_validation(dataset_id="ds-002", quality_score=0.4)
        results = eng.rank_by_severity()
        assert results[0]["dataset_id"] == "ds-002"

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
            eng.add_analysis(dataset_id="ds-001", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(dataset_id="ds-001", analysis_score=20.0)
        eng.add_analysis(dataset_id="ds-002", analysis_score=20.0)
        eng.add_analysis(dataset_id="ds-003", analysis_score=80.0)
        eng.add_analysis(dataset_id="ds-004", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(quality_threshold=0.75)
        eng.record_validation(
            dataset_id="ds-001",
            validation_check=ValidationCheck.SCHEMA,
            data_quality=DataQuality.POOR,
            validation_status=ValidationStatus.FAILED,
            quality_score=0.5,
        )
        report = eng.generate_report()
        assert isinstance(report, ValidationReport)
        assert report.total_records == 1
        assert report.failed_count == 1
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
        eng.record_validation(dataset_id="ds-001")
        eng.add_analysis(dataset_id="ds-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["check_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_validation(
            dataset_id="ds-001", validation_check=ValidationCheck.SCHEMA, team="data-team"
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_datasets"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_record_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_validation(dataset_id=f"ds-{i}")
        assert len(eng._records) == 3
        assert eng._records[0].dataset_id == "ds-2"
