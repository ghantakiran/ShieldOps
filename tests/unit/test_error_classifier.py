"""Tests for shieldops.analytics.error_classifier — ErrorPatternClassifier."""

from __future__ import annotations

from shieldops.analytics.error_classifier import (
    ErrorCategory,
    ErrorClassifierReport,
    ErrorPattern,
    ErrorPatternClassifier,
    ErrorRecord,
    ErrorSeverity,
    PatternType,
)


def _engine(**kw) -> ErrorPatternClassifier:
    return ErrorPatternClassifier(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ErrorCategory (5)
    def test_category_timeout(self):
        assert ErrorCategory.TIMEOUT == "timeout"

    def test_category_connection_failure(self):
        assert ErrorCategory.CONNECTION_FAILURE == "connection_failure"

    def test_category_authentication(self):
        assert ErrorCategory.AUTHENTICATION == "authentication"

    def test_category_validation(self):
        assert ErrorCategory.VALIDATION == "validation"

    def test_category_internal_error(self):
        assert ErrorCategory.INTERNAL_ERROR == "internal_error"

    # ErrorSeverity (5)
    def test_severity_critical(self):
        assert ErrorSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert ErrorSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert ErrorSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert ErrorSeverity.LOW == "low"

    def test_severity_info(self):
        assert ErrorSeverity.INFO == "info"

    # PatternType (5)
    def test_pattern_recurring(self):
        assert PatternType.RECURRING == "recurring"

    def test_pattern_sporadic(self):
        assert PatternType.SPORADIC == "sporadic"

    def test_pattern_burst(self):
        assert PatternType.BURST == "burst"

    def test_pattern_cascading(self):
        assert PatternType.CASCADING == "cascading"

    def test_pattern_isolated(self):
        assert PatternType.ISOLATED == "isolated"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_error_record_defaults(self):
        r = ErrorRecord()
        assert r.id
        assert r.service_name == ""
        assert r.error_category == ErrorCategory.INTERNAL_ERROR
        assert r.severity == ErrorSeverity.MEDIUM
        assert r.error_code == ""
        assert r.message == ""
        assert r.occurrence_count == 1
        assert r.created_at > 0

    def test_error_pattern_defaults(self):
        p = ErrorPattern()
        assert p.id
        assert p.pattern_name == ""
        assert p.pattern_type == PatternType.ISOLATED
        assert p.error_category == ErrorCategory.INTERNAL_ERROR
        assert p.frequency_per_hour == 0.0
        assert p.affected_services == []
        assert p.created_at > 0

    def test_error_classifier_report_defaults(self):
        r = ErrorClassifierReport()
        assert r.id
        assert r.total_errors == 0
        assert r.total_patterns == 0
        assert r.error_rate_pct == 0.0
        assert r.by_category == {}
        assert r.by_severity == {}
        assert r.critical_count == 0
        assert r.recurring_pattern_count == 0
        assert r.recommendations == []
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_error
# -------------------------------------------------------------------


class TestRecordError:
    def test_basic(self):
        eng = _engine()
        r = eng.record_error("api-gateway", error_category=ErrorCategory.TIMEOUT)
        assert r.service_name == "api-gateway"
        assert r.error_category == ErrorCategory.TIMEOUT

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_error(
            "payment-service",
            error_category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.CRITICAL,
            error_code="AUTH_401",
            message="Token expired",
            occurrence_count=10,
        )
        assert r.severity == ErrorSeverity.CRITICAL
        assert r.error_code == "AUTH_401"
        assert r.message == "Token expired"
        assert r.occurrence_count == 10

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_error(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_error
# -------------------------------------------------------------------


class TestGetError:
    def test_found(self):
        eng = _engine()
        r = eng.record_error("api-gateway")
        assert eng.get_error(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_error("nonexistent") is None


# -------------------------------------------------------------------
# list_errors
# -------------------------------------------------------------------


class TestListErrors:
    def test_list_all(self):
        eng = _engine()
        eng.record_error("svc-a")
        eng.record_error("svc-b")
        assert len(eng.list_errors()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_error("svc-a")
        eng.record_error("svc-b")
        results = eng.list_errors(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_error_category(self):
        eng = _engine()
        eng.record_error("svc-a", error_category=ErrorCategory.TIMEOUT)
        eng.record_error("svc-b", error_category=ErrorCategory.VALIDATION)
        results = eng.list_errors(error_category=ErrorCategory.VALIDATION)
        assert len(results) == 1
        assert results[0].service_name == "svc-b"


# -------------------------------------------------------------------
# add_pattern
# -------------------------------------------------------------------


class TestAddPattern:
    def test_basic(self):
        eng = _engine()
        p = eng.add_pattern(
            "burst-detector",
            pattern_type=PatternType.BURST,
            error_category=ErrorCategory.TIMEOUT,
            frequency_per_hour=100.0,
            affected_services=["svc-a", "svc-b"],
        )
        assert p.pattern_name == "burst-detector"
        assert p.pattern_type == PatternType.BURST
        assert p.frequency_per_hour == 100.0
        assert p.affected_services == ["svc-a", "svc-b"]

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_pattern(f"pattern-{i}")
        assert len(eng._patterns) == 2


# -------------------------------------------------------------------
# analyze_error_distribution
# -------------------------------------------------------------------


class TestAnalyzeErrorDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_error("svc-a", error_category=ErrorCategory.TIMEOUT, occurrence_count=5)
        eng.record_error("svc-a", error_category=ErrorCategory.VALIDATION, occurrence_count=3)
        result = eng.analyze_error_distribution("svc-a")
        assert result["record_count"] == 2
        assert result["total_occurrences"] == 8
        assert result["category_distribution"]["timeout"] == 5

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_error_distribution("unknown-svc")
        assert result["status"] == "no_data"

    def test_multiple_categories(self):
        eng = _engine()
        eng.record_error("svc-a", error_category=ErrorCategory.AUTHENTICATION)
        eng.record_error("svc-a", error_category=ErrorCategory.AUTHENTICATION)
        result = eng.analyze_error_distribution("svc-a")
        assert result["category_distribution"]["authentication"] == 2


# -------------------------------------------------------------------
# identify_recurring_patterns
# -------------------------------------------------------------------


class TestIdentifyRecurringPatterns:
    def test_with_recurring(self):
        eng = _engine()
        for _ in range(5):
            eng.record_error("svc-a")
        eng.record_error("svc-b")
        results = eng.identify_recurring_patterns()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["error_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.identify_recurring_patterns() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_error("svc-a")
        assert eng.identify_recurring_patterns() == []


# -------------------------------------------------------------------
# rank_by_frequency
# -------------------------------------------------------------------


class TestRankByFrequency:
    def test_with_data(self):
        eng = _engine()
        eng.record_error("svc-a", occurrence_count=2)
        eng.record_error("svc-b", occurrence_count=10)
        results = eng.rank_by_frequency()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["total_occurrences"] == 10

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_frequency() == []


# -------------------------------------------------------------------
# detect_error_trends
# -------------------------------------------------------------------


class TestDetectErrorTrends:
    def test_with_high_severity(self):
        eng = _engine()
        eng.record_error("svc-a", severity=ErrorSeverity.CRITICAL)
        eng.record_error("svc-a", severity=ErrorSeverity.HIGH)
        eng.record_error("svc-b", severity=ErrorSeverity.LOW)
        results = eng.detect_error_trends()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["high_severity_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.detect_error_trends() == []

    def test_single_high_not_returned(self):
        eng = _engine()
        eng.record_error("svc-a", severity=ErrorSeverity.CRITICAL)
        assert eng.detect_error_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_error("svc-a", severity=ErrorSeverity.CRITICAL)
        eng.record_error("svc-b", severity=ErrorSeverity.LOW)
        eng.add_pattern("pattern-1")
        report = eng.generate_report()
        assert report.total_errors == 2
        assert report.total_patterns == 1
        assert report.critical_count == 1
        assert report.by_category != {}
        assert report.by_severity != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_errors == 0
        assert report.error_rate_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_error("svc-a")
        eng.add_pattern("pattern-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._patterns) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_errors"] == 0
        assert stats["total_patterns"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine(max_error_rate_pct=3.0)
        eng.record_error("svc-a", error_category=ErrorCategory.TIMEOUT)
        eng.record_error("svc-b", error_category=ErrorCategory.VALIDATION)
        eng.add_pattern("pattern-1")
        stats = eng.get_stats()
        assert stats["total_errors"] == 2
        assert stats["total_patterns"] == 1
        assert stats["unique_services"] == 2
        assert stats["max_error_rate_pct"] == 3.0
