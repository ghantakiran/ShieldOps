"""Tests for shieldops.sla.sli_pipeline — SLICalculationPipeline."""

from __future__ import annotations

from shieldops.sla.sli_pipeline import (
    AggregationMethod,
    SLICalculationPipeline,
    SLIDataPoint,
    SLIDefinition,
    SLIHealth,
    SLIPipelineReport,
    SLIType,
)


def _engine(**kw) -> SLICalculationPipeline:
    return SLICalculationPipeline(**kw)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestSLIType:
    """Test every SLIType member."""

    def test_availability(self):
        assert SLIType.AVAILABILITY == "availability"

    def test_latency(self):
        assert SLIType.LATENCY == "latency"

    def test_throughput(self):
        assert SLIType.THROUGHPUT == "throughput"

    def test_error_rate(self):
        assert SLIType.ERROR_RATE == "error_rate"

    def test_saturation(self):
        assert SLIType.SATURATION == "saturation"


class TestAggregationMethod:
    """Test every AggregationMethod member."""

    def test_average(self):
        assert AggregationMethod.AVERAGE == "average"

    def test_percentile_95(self):
        assert AggregationMethod.PERCENTILE_95 == "percentile_95"

    def test_percentile_99(self):
        assert AggregationMethod.PERCENTILE_99 == "percentile_99"

    def test_sum(self):
        assert AggregationMethod.SUM == "sum"

    def test_count(self):
        assert AggregationMethod.COUNT == "count"


class TestSLIHealth:
    """Test every SLIHealth member."""

    def test_healthy(self):
        assert SLIHealth.HEALTHY == "healthy"

    def test_warning(self):
        assert SLIHealth.WARNING == "warning"

    def test_breaching(self):
        assert SLIHealth.BREACHING == "breaching"

    def test_critical(self):
        assert SLIHealth.CRITICAL == "critical"

    def test_no_data(self):
        assert SLIHealth.NO_DATA == "no_data"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestModels:
    """Test model defaults."""

    def test_sli_definition_defaults(self):
        m = SLIDefinition()
        assert m.id
        assert m.service_name == ""
        assert m.sli_type == SLIType.AVAILABILITY
        assert m.aggregation == AggregationMethod.AVERAGE
        assert m.target_value == 99.9
        assert m.warning_threshold == 99.5
        assert m.critical_threshold == 99.0
        assert m.unit == "percent"

    def test_sli_data_point_defaults(self):
        m = SLIDataPoint()
        assert m.id
        assert m.sli_id == ""
        assert m.value == 0.0
        assert m.labels == {}

    def test_sli_pipeline_report_defaults(self):
        m = SLIPipelineReport()
        assert m.total_definitions == 0
        assert m.total_data_points == 0
        assert m.healthy_count == 0
        assert m.by_type == {}
        assert m.recommendations == []


# ---------------------------------------------------------------------------
# register_sli
# ---------------------------------------------------------------------------


class TestRegisterSLI:
    """Test SLICalculationPipeline.register_sli."""

    def test_basic(self):
        eng = _engine()
        sli = eng.register_sli(
            service_name="api",
            sli_type=SLIType.AVAILABILITY,
            name="api-availability",
            target_value=99.9,
        )
        assert sli.service_name == "api"
        assert sli.sli_type == SLIType.AVAILABILITY
        assert sli.name == "api-availability"
        assert sli.id

    def test_eviction(self):
        eng = _engine(max_definitions=2)
        eng.register_sli(name="first")
        eng.register_sli(name="second")
        eng.register_sli(name="third")
        slis = eng.list_slis()
        assert len(slis) == 2
        assert slis[0].name == "second"
        assert slis[1].name == "third"


# ---------------------------------------------------------------------------
# get_sli
# ---------------------------------------------------------------------------


class TestGetSLI:
    """Test SLICalculationPipeline.get_sli."""

    def test_found(self):
        eng = _engine()
        sli = eng.register_sli(name="uptime")
        found = eng.get_sli(sli.id)
        assert found is not None
        assert found.name == "uptime"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_sli("nonexistent") is None


# ---------------------------------------------------------------------------
# list_slis
# ---------------------------------------------------------------------------


class TestListSLIs:
    """Test SLICalculationPipeline.list_slis."""

    def test_all(self):
        eng = _engine()
        eng.register_sli(name="a")
        eng.register_sli(name="b")
        assert len(eng.list_slis()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.register_sli(service_name="api", name="a")
        eng.register_sli(service_name="web", name="b")
        eng.register_sli(service_name="api", name="c")
        result = eng.list_slis(service_name="api")
        assert len(result) == 2
        assert all(s.service_name == "api" for s in result)

    def test_filter_by_sli_type(self):
        eng = _engine()
        eng.register_sli(sli_type=SLIType.AVAILABILITY, name="avail")
        eng.register_sli(sli_type=SLIType.LATENCY, name="lat")
        result = eng.list_slis(sli_type=SLIType.LATENCY)
        assert len(result) == 1
        assert result[0].name == "lat"


# ---------------------------------------------------------------------------
# ingest_data_point
# ---------------------------------------------------------------------------


class TestIngestDataPoint:
    """Test SLICalculationPipeline.ingest_data_point."""

    def test_basic(self):
        eng = _engine()
        sli = eng.register_sli(name="uptime")
        dp = eng.ingest_data_point(sli.id, value=99.95)
        assert dp is not None
        assert dp.sli_id == sli.id
        assert dp.value == 99.95

    def test_not_found_returns_none(self):
        eng = _engine()
        dp = eng.ingest_data_point("ghost-id", value=50.0)
        assert dp is None


# ---------------------------------------------------------------------------
# calculate_sli_value
# ---------------------------------------------------------------------------


class TestCalculateSLIValue:
    """Test SLICalculationPipeline.calculate_sli_value."""

    def test_average_aggregation(self):
        eng = _engine()
        sli = eng.register_sli(name="avail", aggregation=AggregationMethod.AVERAGE)
        eng.ingest_data_point(sli.id, value=99.0)
        eng.ingest_data_point(sli.id, value=100.0)
        eng.ingest_data_point(sli.id, value=98.0)
        result = eng.calculate_sli_value(sli.id)
        # average = (99 + 100 + 98) / 3 = 99.0
        assert result["aggregated_value"] == 99.0
        assert result["data_point_count"] == 3
        assert result["aggregation_method"] == "average"

    def test_count_aggregation(self):
        eng = _engine()
        sli = eng.register_sli(name="request-count", aggregation=AggregationMethod.COUNT)
        eng.ingest_data_point(sli.id, value=10.0)
        eng.ingest_data_point(sli.id, value=20.0)
        result = eng.calculate_sli_value(sli.id)
        assert result["aggregated_value"] == 2
        assert result["aggregation_method"] == "count"

    def test_no_data(self):
        eng = _engine()
        sli = eng.register_sli(name="empty")
        result = eng.calculate_sli_value(sli.id)
        assert result["aggregated_value"] == 0.0
        assert result["data_point_count"] == 0


# ---------------------------------------------------------------------------
# evaluate_sli_health
# ---------------------------------------------------------------------------


class TestEvaluateSLIHealth:
    """Test SLICalculationPipeline.evaluate_sli_health."""

    def test_healthy_value_meets_target(self):
        eng = _engine()
        sli = eng.register_sli(
            name="avail",
            sli_type=SLIType.AVAILABILITY,
            target_value=99.9,
            warning_threshold=99.5,
            critical_threshold=99.0,
        )
        eng.ingest_data_point(sli.id, value=99.95)
        result = eng.evaluate_sli_health(sli.id)
        assert result["health"] == SLIHealth.HEALTHY.value
        assert result["current_value"] == 99.95

    def test_breaching_between_critical_and_warning(self):
        eng = _engine()
        sli = eng.register_sli(
            name="avail",
            sli_type=SLIType.AVAILABILITY,
            target_value=99.9,
            warning_threshold=99.5,
            critical_threshold=99.0,
        )
        # Value 99.2 is >= critical (99.0) but < warning (99.5) -> BREACHING
        eng.ingest_data_point(sli.id, value=99.2)
        result = eng.evaluate_sli_health(sli.id)
        assert result["health"] == SLIHealth.BREACHING.value

    def test_no_data_when_no_points(self):
        eng = _engine()
        sli = eng.register_sli(name="empty")
        result = eng.evaluate_sli_health(sli.id)
        assert result["health"] == SLIHealth.NO_DATA.value


# ---------------------------------------------------------------------------
# detect_sli_regression
# ---------------------------------------------------------------------------


class TestDetectSLIRegression:
    """Test SLICalculationPipeline.detect_sli_regression."""

    def test_regression_detected_availability_drops(self):
        eng = _engine()
        sli = eng.register_sli(
            name="avail",
            sli_type=SLIType.AVAILABILITY,
        )
        # First half: high values
        eng.ingest_data_point(sli.id, value=99.9)
        eng.ingest_data_point(sli.id, value=99.8)
        # Second half: significantly lower values (> 5% drop)
        eng.ingest_data_point(sli.id, value=90.0)
        eng.ingest_data_point(sli.id, value=89.0)
        result = eng.detect_sli_regression(sli.id)
        assert result["regression_detected"] is True
        assert result["change_pct"] < -5.0

    def test_no_regression_when_stable(self):
        eng = _engine()
        sli = eng.register_sli(
            name="avail",
            sli_type=SLIType.AVAILABILITY,
        )
        eng.ingest_data_point(sli.id, value=99.9)
        eng.ingest_data_point(sli.id, value=99.8)
        eng.ingest_data_point(sli.id, value=99.9)
        eng.ingest_data_point(sli.id, value=99.85)
        result = eng.detect_sli_regression(sli.id)
        assert result["regression_detected"] is False


# ---------------------------------------------------------------------------
# aggregate_service_slis
# ---------------------------------------------------------------------------


class TestAggregateServiceSLIs:
    """Test SLICalculationPipeline.aggregate_service_slis."""

    def test_multiple_slis_overall_health_is_worst(self):
        eng = _engine()
        # Healthy SLI
        sli_good = eng.register_sli(
            service_name="api",
            name="avail",
            sli_type=SLIType.AVAILABILITY,
            target_value=99.0,
            warning_threshold=98.0,
            critical_threshold=97.0,
        )
        eng.ingest_data_point(sli_good.id, value=99.5)

        # Breaching SLI (value between critical and warning for higher-is-better)
        sli_bad = eng.register_sli(
            service_name="api",
            name="throughput",
            sli_type=SLIType.THROUGHPUT,
            target_value=1000.0,
            warning_threshold=800.0,
            critical_threshold=500.0,
        )
        eng.ingest_data_point(sli_bad.id, value=600.0)

        result = eng.aggregate_service_slis("api")
        assert result["sli_count"] == 2
        # The worst health should dominate
        assert result["overall_health"] == SLIHealth.BREACHING.value


# ---------------------------------------------------------------------------
# generate_pipeline_report
# ---------------------------------------------------------------------------


class TestGeneratePipelineReport:
    """Test SLICalculationPipeline.generate_pipeline_report."""

    def test_basic(self):
        eng = _engine()
        sli = eng.register_sli(
            service_name="api",
            sli_type=SLIType.AVAILABILITY,
            name="api-avail",
            target_value=99.0,
        )
        eng.ingest_data_point(sli.id, value=99.5)
        report = eng.generate_pipeline_report()
        assert isinstance(report, SLIPipelineReport)
        assert report.total_definitions == 1
        assert report.total_data_points == 1
        assert report.healthy_count == 1
        assert "availability" in report.by_type

    def test_report_includes_no_data_recommendation_when_empty(self):
        eng = _engine()
        eng.register_sli(name="orphan")
        report = eng.generate_pipeline_report()
        assert any("No data points" in r for r in report.recommendations)


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    """Test SLICalculationPipeline.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        sli = eng.register_sli(name="x")
        eng.ingest_data_point(sli.id, value=1.0)
        eng.clear_data()
        assert eng.list_slis() == []
        stats = eng.get_stats()
        assert stats["total_definitions"] == 0
        assert stats["total_data_points"] == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    """Test SLICalculationPipeline.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_definitions"] == 0
        assert stats["total_data_points"] == 0
        assert stats["unique_services"] == 0
        assert stats["type_distribution"] == {}
        assert stats["aggregation_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        sli1 = eng.register_sli(service_name="api", sli_type=SLIType.AVAILABILITY, name="a")
        sli2 = eng.register_sli(
            service_name="web",
            sli_type=SLIType.LATENCY,
            name="b",
            aggregation=AggregationMethod.PERCENTILE_99,
        )
        eng.ingest_data_point(sli1.id, value=99.9)
        eng.ingest_data_point(sli2.id, value=150.0)
        eng.ingest_data_point(sli2.id, value=200.0)
        stats = eng.get_stats()
        assert stats["total_definitions"] == 2
        assert stats["total_data_points"] == 3
        assert stats["unique_services"] == 2
        assert stats["type_distribution"]["availability"] == 1
        assert stats["type_distribution"]["latency"] == 1
        assert stats["aggregation_distribution"]["average"] == 1
        assert stats["aggregation_distribution"]["percentile_99"] == 1
