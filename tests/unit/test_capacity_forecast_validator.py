"""Tests for shieldops.analytics.capacity_forecast_validator — CapacityForecastValidator."""

from __future__ import annotations

from shieldops.analytics.capacity_forecast_validator import (
    CapacityForecastReport,
    CapacityForecastValidator,
    ForecastAccuracy,
    ForecastBias,
    ForecastCheck,
    ForecastMethod,
    ForecastValidationRecord,
)


def _engine(**kw) -> CapacityForecastValidator:
    return CapacityForecastValidator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_accuracy_excellent(self):
        assert ForecastAccuracy.EXCELLENT == "excellent"

    def test_accuracy_good(self):
        assert ForecastAccuracy.GOOD == "good"

    def test_accuracy_acceptable(self):
        assert ForecastAccuracy.ACCEPTABLE == "acceptable"

    def test_accuracy_poor(self):
        assert ForecastAccuracy.POOR == "poor"

    def test_accuracy_inaccurate(self):
        assert ForecastAccuracy.INACCURATE == "inaccurate"

    def test_bias_over_estimate(self):
        assert ForecastBias.OVER_ESTIMATE == "over_estimate"

    def test_bias_slight_over(self):
        assert ForecastBias.SLIGHT_OVER == "slight_over"

    def test_bias_balanced(self):
        assert ForecastBias.BALANCED == "balanced"

    def test_bias_slight_under(self):
        assert ForecastBias.SLIGHT_UNDER == "slight_under"

    def test_bias_under_estimate(self):
        assert ForecastBias.UNDER_ESTIMATE == "under_estimate"

    def test_method_linear(self):
        assert ForecastMethod.LINEAR == "linear"

    def test_method_exponential(self):
        assert ForecastMethod.EXPONENTIAL == "exponential"

    def test_method_seasonal(self):
        assert ForecastMethod.SEASONAL == "seasonal"

    def test_method_ml_based(self):
        assert ForecastMethod.ML_BASED == "ml_based"

    def test_method_manual(self):
        assert ForecastMethod.MANUAL == "manual"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_forecast_validation_record_defaults(self):
        r = ForecastValidationRecord()
        assert r.id
        assert r.forecast_id == ""
        assert r.forecast_accuracy == ForecastAccuracy.ACCEPTABLE
        assert r.forecast_bias == ForecastBias.BALANCED
        assert r.forecast_method == ForecastMethod.LINEAR
        assert r.accuracy_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_forecast_check_defaults(self):
        c = ForecastCheck()
        assert c.id
        assert c.forecast_id == ""
        assert c.forecast_accuracy == ForecastAccuracy.ACCEPTABLE
        assert c.check_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_forecast_report_defaults(self):
        r = CapacityForecastReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_checks == 0
        assert r.inaccurate_count == 0
        assert r.avg_accuracy_pct == 0.0
        assert r.by_accuracy == {}
        assert r.by_bias == {}
        assert r.by_method == {}
        assert r.top_inaccurate == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_validation
# ---------------------------------------------------------------------------


class TestRecordValidation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_validation(
            forecast_id="FC-001",
            forecast_accuracy=ForecastAccuracy.GOOD,
            forecast_bias=ForecastBias.SLIGHT_OVER,
            forecast_method=ForecastMethod.ML_BASED,
            accuracy_pct=88.0,
            service="api-gateway",
            team="sre",
        )
        assert r.forecast_id == "FC-001"
        assert r.forecast_accuracy == ForecastAccuracy.GOOD
        assert r.forecast_bias == ForecastBias.SLIGHT_OVER
        assert r.forecast_method == ForecastMethod.ML_BASED
        assert r.accuracy_pct == 88.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_validation(forecast_id=f"FC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_validation
# ---------------------------------------------------------------------------


class TestGetValidation:
    def test_found(self):
        eng = _engine()
        r = eng.record_validation(
            forecast_id="FC-001",
            forecast_accuracy=ForecastAccuracy.EXCELLENT,
        )
        result = eng.get_validation(r.id)
        assert result is not None
        assert result.forecast_accuracy == ForecastAccuracy.EXCELLENT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_validation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_validations
# ---------------------------------------------------------------------------


class TestListValidations:
    def test_list_all(self):
        eng = _engine()
        eng.record_validation(forecast_id="FC-001")
        eng.record_validation(forecast_id="FC-002")
        assert len(eng.list_validations()) == 2

    def test_filter_by_accuracy(self):
        eng = _engine()
        eng.record_validation(
            forecast_id="FC-001",
            forecast_accuracy=ForecastAccuracy.EXCELLENT,
        )
        eng.record_validation(
            forecast_id="FC-002",
            forecast_accuracy=ForecastAccuracy.POOR,
        )
        results = eng.list_validations(accuracy=ForecastAccuracy.EXCELLENT)
        assert len(results) == 1

    def test_filter_by_bias(self):
        eng = _engine()
        eng.record_validation(
            forecast_id="FC-001",
            forecast_bias=ForecastBias.OVER_ESTIMATE,
        )
        eng.record_validation(
            forecast_id="FC-002",
            forecast_bias=ForecastBias.BALANCED,
        )
        results = eng.list_validations(bias=ForecastBias.OVER_ESTIMATE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_validation(forecast_id="FC-001", team="sre")
        eng.record_validation(forecast_id="FC-002", team="platform")
        results = eng.list_validations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_validation(forecast_id=f"FC-{i}")
        assert len(eng.list_validations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_check
# ---------------------------------------------------------------------------


class TestAddCheck:
    def test_basic(self):
        eng = _engine()
        c = eng.add_check(
            forecast_id="FC-001",
            forecast_accuracy=ForecastAccuracy.GOOD,
            check_score=82.0,
            threshold=80.0,
            breached=True,
            description="Accuracy check",
        )
        assert c.forecast_id == "FC-001"
        assert c.forecast_accuracy == ForecastAccuracy.GOOD
        assert c.check_score == 82.0
        assert c.threshold == 80.0
        assert c.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_check(forecast_id=f"FC-{i}")
        assert len(eng._checks) == 2


# ---------------------------------------------------------------------------
# analyze_forecast_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeForecastDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_validation(
            forecast_id="FC-001",
            forecast_accuracy=ForecastAccuracy.GOOD,
            accuracy_pct=85.0,
        )
        eng.record_validation(
            forecast_id="FC-002",
            forecast_accuracy=ForecastAccuracy.GOOD,
            accuracy_pct=90.0,
        )
        result = eng.analyze_forecast_distribution()
        assert "good" in result
        assert result["good"]["count"] == 2
        assert result["good"]["avg_accuracy_pct"] == 87.5

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_forecast_distribution() == {}


# ---------------------------------------------------------------------------
# identify_inaccurate_forecasts
# ---------------------------------------------------------------------------


class TestIdentifyInaccurateForecasts:
    def test_detects_poor(self):
        eng = _engine()
        eng.record_validation(
            forecast_id="FC-001",
            forecast_accuracy=ForecastAccuracy.POOR,
        )
        eng.record_validation(
            forecast_id="FC-002",
            forecast_accuracy=ForecastAccuracy.EXCELLENT,
        )
        results = eng.identify_inaccurate_forecasts()
        assert len(results) == 1
        assert results[0]["forecast_id"] == "FC-001"

    def test_detects_inaccurate(self):
        eng = _engine()
        eng.record_validation(
            forecast_id="FC-001",
            forecast_accuracy=ForecastAccuracy.INACCURATE,
        )
        results = eng.identify_inaccurate_forecasts()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_inaccurate_forecasts() == []


# ---------------------------------------------------------------------------
# rank_by_accuracy
# ---------------------------------------------------------------------------


class TestRankByAccuracy:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_validation(forecast_id="FC-001", accuracy_pct=95.0, service="svc-a")
        eng.record_validation(forecast_id="FC-002", accuracy_pct=60.0, service="svc-b")
        results = eng.rank_by_accuracy()
        assert len(results) == 2
        assert results[0]["service"] == "svc-b"
        assert results[0]["avg_accuracy_pct"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_accuracy() == []


# ---------------------------------------------------------------------------
# detect_forecast_trends
# ---------------------------------------------------------------------------


class TestDetectForecastTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_check(forecast_id="FC-001", check_score=70.0)
        result = eng.detect_forecast_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_check(forecast_id="FC-001", check_score=50.0)
        eng.add_check(forecast_id="FC-002", check_score=50.0)
        eng.add_check(forecast_id="FC-003", check_score=80.0)
        eng.add_check(forecast_id="FC-004", check_score=80.0)
        result = eng.detect_forecast_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_forecast_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_validation(
            forecast_id="FC-001",
            forecast_accuracy=ForecastAccuracy.POOR,
            accuracy_pct=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, CapacityForecastReport)
        assert report.total_records == 1
        assert report.inaccurate_count == 1
        assert len(report.top_inaccurate) == 1
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
        eng.record_validation(forecast_id="FC-001")
        eng.add_check(forecast_id="FC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._checks) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_checks"] == 0
        assert stats["accuracy_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_validation(
            forecast_id="FC-001",
            forecast_accuracy=ForecastAccuracy.GOOD,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "good" in stats["accuracy_distribution"]
