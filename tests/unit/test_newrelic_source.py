"""Comprehensive tests for the NewRelicSource observability client.

Tests cover:
- Initialization (api_key, account_id, region, base_url derivation)
- source_name class attribute
- query_logs — NRQL construction, return type, edge cases
- search_patterns — multi-pattern handling, return structure, empty patterns
- query_metric — NRQL construction, return type
- query_instant — return type
- detect_anomalies — return type, parameter passthrough
- close() — graceful shutdown
- ABC compliance — LogSource + MetricSource interface
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from shieldops.models.base import TimeRange
from shieldops.observability.base import LogSource, MetricSource
from shieldops.observability.newrelic.client import NewRelicSource

# --- Shared Fixtures ---


@pytest.fixture
def time_range():
    """Standard 1-hour time range ending now."""
    now = datetime.now(UTC)
    return TimeRange(start=now - timedelta(hours=1), end=now)


@pytest.fixture
def baseline_range():
    """Baseline time range from 1 day ago (1 hour window)."""
    now = datetime.now(UTC)
    return TimeRange(start=now - timedelta(days=1, hours=1), end=now - timedelta(days=1))


@pytest.fixture
def narrow_range():
    """Very narrow 1-minute time range for edge case testing."""
    now = datetime.now(UTC)
    return TimeRange(start=now - timedelta(minutes=1), end=now)


@pytest.fixture
def source_us():
    """NewRelicSource configured for US region."""
    return NewRelicSource(api_key="nr-test-key-123", account_id="12345", region="US")


@pytest.fixture
def source_eu():
    """NewRelicSource configured for EU region."""
    return NewRelicSource(api_key="nr-eu-key-456", account_id="67890", region="EU")


@pytest.fixture
def source_defaults():
    """NewRelicSource with all default parameters."""
    return NewRelicSource()


# ============================================================================
# Initialization Tests
# ============================================================================


class TestNewRelicSourceInit:
    """Tests for NewRelicSource constructor and attribute setup."""

    def test_init_stores_api_key(self, source_us):
        assert source_us._api_key == "nr-test-key-123"

    def test_init_stores_account_id(self, source_us):
        assert source_us._account_id == "12345"

    def test_init_stores_region(self, source_us):
        assert source_us._region == "US"

    def test_init_us_region_base_url(self, source_us):
        assert source_us._base_url == "https://api.newrelic.com"

    def test_init_eu_region_base_url(self, source_eu):
        assert source_eu._base_url == "https://api.eu.newrelic.com"

    def test_init_default_region_is_us(self):
        source = NewRelicSource(api_key="key", account_id="acc")
        assert source._region == "US"
        assert source._base_url == "https://api.newrelic.com"

    def test_init_default_api_key_is_empty(self, source_defaults):
        assert source_defaults._api_key == ""

    def test_init_default_account_id_is_empty(self, source_defaults):
        assert source_defaults._account_id == ""

    def test_init_default_region_fallback(self, source_defaults):
        assert source_defaults._region == "US"

    def test_init_unknown_region_uses_us_url(self):
        """Non-EU region strings fall through to US base URL."""
        source = NewRelicSource(api_key="key", account_id="acc", region="APAC")
        assert source._base_url == "https://api.newrelic.com"

    def test_init_eu_case_sensitive(self):
        """Only exact 'EU' string triggers the EU base URL."""
        source = NewRelicSource(api_key="key", account_id="acc", region="eu")
        assert source._base_url == "https://api.newrelic.com"  # lowercase 'eu' != 'EU'

    def test_init_eu_account_id(self, source_eu):
        assert source_eu._account_id == "67890"

    def test_init_eu_api_key(self, source_eu):
        assert source_eu._api_key == "nr-eu-key-456"


# ============================================================================
# source_name Property Tests
# ============================================================================


class TestSourceName:
    """Tests for the source_name class attribute."""

    def test_source_name_value(self, source_us):
        assert source_us.source_name == "newrelic"

    def test_source_name_is_class_attribute(self):
        assert NewRelicSource.source_name == "newrelic"

    def test_source_name_consistent_across_instances(self, source_us, source_eu):
        assert source_us.source_name == source_eu.source_name


# ============================================================================
# ABC Interface Compliance Tests
# ============================================================================


class TestABCCompliance:
    """Tests that NewRelicSource properly implements LogSource and MetricSource."""

    def test_is_instance_of_log_source(self, source_us):
        assert isinstance(source_us, LogSource)

    def test_is_instance_of_metric_source(self, source_us):
        assert isinstance(source_us, MetricSource)

    def test_subclass_of_log_source(self):
        assert issubclass(NewRelicSource, LogSource)

    def test_subclass_of_metric_source(self):
        assert issubclass(NewRelicSource, MetricSource)

    def test_has_query_logs_method(self, source_us):
        assert hasattr(source_us, "query_logs")
        assert callable(source_us.query_logs)

    def test_has_search_patterns_method(self, source_us):
        assert hasattr(source_us, "search_patterns")
        assert callable(source_us.search_patterns)

    def test_has_query_metric_method(self, source_us):
        assert hasattr(source_us, "query_metric")
        assert callable(source_us.query_metric)

    def test_has_query_instant_method(self, source_us):
        assert hasattr(source_us, "query_instant")
        assert callable(source_us.query_instant)

    def test_has_detect_anomalies_method(self, source_us):
        assert hasattr(source_us, "detect_anomalies")
        assert callable(source_us.detect_anomalies)

    def test_has_close_method(self, source_us):
        assert hasattr(source_us, "close")
        assert callable(source_us.close)


# ============================================================================
# query_logs Tests
# ============================================================================


class TestQueryLogs:
    """Tests for the query_logs async method."""

    @pytest.mark.asyncio
    async def test_query_logs_returns_list(self, source_us, time_range):
        result = await source_us.query_logs("error", time_range)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_query_logs_returns_empty_list(self, source_us, time_range):
        """Current stub implementation returns empty list."""
        result = await source_us.query_logs("something", time_range)
        assert result == []

    @pytest.mark.asyncio
    async def test_query_logs_default_limit(self, source_us, time_range):
        """query_logs uses limit=100 by default."""
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_logs("OOMKilled", time_range)
            call_kwargs = mock_logger.info.call_args
            nrql = call_kwargs.kwargs.get("nrql", "")
            assert "LIMIT 100" in nrql

    @pytest.mark.asyncio
    async def test_query_logs_custom_limit(self, source_us, time_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_logs("error", time_range, limit=50)
            call_kwargs = mock_logger.info.call_args
            nrql = call_kwargs.kwargs.get("nrql", "")
            assert "LIMIT 50" in nrql

    @pytest.mark.asyncio
    async def test_query_logs_nrql_contains_query_string(self, source_us, time_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_logs("OOMKilled", time_range)
            call_kwargs = mock_logger.info.call_args
            nrql = call_kwargs.kwargs.get("nrql", "")
            assert "OOMKilled" in nrql

    @pytest.mark.asyncio
    async def test_query_logs_nrql_selects_from_log(self, source_us, time_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_logs("test", time_range)
            call_kwargs = mock_logger.info.call_args
            nrql = call_kwargs.kwargs.get("nrql", "")
            assert "SELECT * FROM Log" in nrql

    @pytest.mark.asyncio
    async def test_query_logs_nrql_uses_like_operator(self, source_us, time_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_logs("timeout", time_range)
            call_kwargs = mock_logger.info.call_args
            nrql = call_kwargs.kwargs.get("nrql", "")
            assert "LIKE '%timeout%'" in nrql

    @pytest.mark.asyncio
    async def test_query_logs_logs_start_time(self, source_us, time_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_logs("test", time_range)
            call_kwargs = mock_logger.info.call_args
            assert call_kwargs.kwargs["start"] == time_range.start.isoformat()

    @pytest.mark.asyncio
    async def test_query_logs_logs_end_time(self, source_us, time_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_logs("test", time_range)
            call_kwargs = mock_logger.info.call_args
            assert call_kwargs.kwargs["end"] == time_range.end.isoformat()

    @pytest.mark.asyncio
    async def test_query_logs_empty_query_string(self, source_us, time_range):
        """Empty query string is embedded in the NRQL without error."""
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            result = await source_us.query_logs("", time_range)
            assert result == []
            call_kwargs = mock_logger.info.call_args
            nrql = call_kwargs.kwargs.get("nrql", "")
            assert "LIKE '%%'" in nrql

    @pytest.mark.asyncio
    async def test_query_logs_special_characters_in_query(self, source_us, time_range):
        """Special characters are embedded as-is in the NRQL."""
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_logs("error: 500 'internal'", time_range)
            call_kwargs = mock_logger.info.call_args
            nrql = call_kwargs.kwargs.get("nrql", "")
            assert "error: 500 'internal'" in nrql

    @pytest.mark.asyncio
    async def test_query_logs_limit_one(self, source_us, time_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_logs("test", time_range, limit=1)
            call_kwargs = mock_logger.info.call_args
            nrql = call_kwargs.kwargs.get("nrql", "")
            assert "LIMIT 1" in nrql

    @pytest.mark.asyncio
    async def test_query_logs_large_limit(self, source_us, time_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_logs("test", time_range, limit=5000)
            call_kwargs = mock_logger.info.call_args
            nrql = call_kwargs.kwargs.get("nrql", "")
            assert "LIMIT 5000" in nrql


# ============================================================================
# search_patterns Tests
# ============================================================================


class TestSearchPatterns:
    """Tests for the search_patterns async method."""

    @pytest.mark.asyncio
    async def test_search_patterns_returns_dict(self, source_us, time_range):
        result = await source_us.search_patterns("web-01", ["error", "timeout"], time_range)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_search_patterns_keys_match_input_patterns(self, source_us, time_range):
        patterns = ["OOMKilled", "CrashLoopBackOff", "timeout"]
        result = await source_us.search_patterns("pod-123", patterns, time_range)
        assert set(result.keys()) == set(patterns)

    @pytest.mark.asyncio
    async def test_search_patterns_values_are_lists(self, source_us, time_range):
        result = await source_us.search_patterns("res-1", ["error"], time_range)
        for value in result.values():
            assert isinstance(value, list)

    @pytest.mark.asyncio
    async def test_search_patterns_empty_results_per_pattern(self, source_us, time_range):
        """Current stub returns empty list for each pattern."""
        result = await source_us.search_patterns("res-1", ["error", "warn"], time_range)
        assert result["error"] == []
        assert result["warn"] == []

    @pytest.mark.asyncio
    async def test_search_patterns_single_pattern(self, source_us, time_range):
        result = await source_us.search_patterns("res-1", ["OOMKilled"], time_range)
        assert len(result) == 1
        assert "OOMKilled" in result

    @pytest.mark.asyncio
    async def test_search_patterns_empty_patterns_list(self, source_us, time_range):
        """Empty patterns list returns empty dict."""
        result = await source_us.search_patterns("res-1", [], time_range)
        assert result == {}

    @pytest.mark.asyncio
    async def test_search_patterns_many_patterns(self, source_us, time_range):
        patterns = [f"pattern_{i}" for i in range(20)]
        result = await source_us.search_patterns("res-1", patterns, time_range)
        assert len(result) == 20

    @pytest.mark.asyncio
    async def test_search_patterns_logs_each_pattern(self, source_us, time_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.search_patterns("web-01", ["error", "timeout"], time_range)
            assert mock_logger.debug.call_count == 2

    @pytest.mark.asyncio
    async def test_search_patterns_logs_resource_id(self, source_us, time_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.search_patterns("my-pod-xyz", ["error"], time_range)
            call_kwargs = mock_logger.debug.call_args
            assert call_kwargs.kwargs["resource"] == "my-pod-xyz"

    @pytest.mark.asyncio
    async def test_search_patterns_logs_pattern_value(self, source_us, time_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.search_patterns("res-1", ["CrashLoopBackOff"], time_range)
            call_kwargs = mock_logger.debug.call_args
            assert call_kwargs.kwargs["pattern"] == "CrashLoopBackOff"


# ============================================================================
# query_metric Tests
# ============================================================================


class TestQueryMetric:
    """Tests for the query_metric async method."""

    @pytest.mark.asyncio
    async def test_query_metric_returns_list(self, source_us, time_range):
        result = await source_us.query_metric("cpu.usage", {}, time_range)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_query_metric_returns_empty_list(self, source_us, time_range):
        """Current stub returns empty list."""
        result = await source_us.query_metric("memory.used", {"host": "web-01"}, time_range)
        assert result == []

    @pytest.mark.asyncio
    async def test_query_metric_nrql_contains_metric_name(self, source_us, time_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_metric("system.cpu.percent", {}, time_range)
            call_kwargs = mock_logger.info.call_args
            nrql = call_kwargs.kwargs.get("nrql", "")
            assert "system.cpu.percent" in nrql

    @pytest.mark.asyncio
    async def test_query_metric_nrql_uses_average_function(self, source_us, time_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_metric("disk.io", {}, time_range)
            call_kwargs = mock_logger.info.call_args
            nrql = call_kwargs.kwargs.get("nrql", "")
            assert "SELECT average(disk.io)" in nrql

    @pytest.mark.asyncio
    async def test_query_metric_nrql_queries_metric_table(self, source_us, time_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_metric("requests.count", {}, time_range)
            call_kwargs = mock_logger.info.call_args
            nrql = call_kwargs.kwargs.get("nrql", "")
            assert "FROM Metric" in nrql

    @pytest.mark.asyncio
    async def test_query_metric_nrql_includes_timeseries(self, source_us, time_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_metric("latency.p99", {}, time_range)
            call_kwargs = mock_logger.info.call_args
            nrql = call_kwargs.kwargs.get("nrql", "")
            assert "TIMESERIES" in nrql

    @pytest.mark.asyncio
    async def test_query_metric_with_labels(self, source_us, time_range):
        """Labels parameter is accepted without error."""
        result = await source_us.query_metric(
            "cpu.usage",
            {"host": "web-01", "env": "production"},
            time_range,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_query_metric_custom_step(self, source_us, time_range):
        """Custom step parameter is accepted without error."""
        result = await source_us.query_metric("cpu.usage", {}, time_range, step="5m")
        assert result == []

    @pytest.mark.asyncio
    async def test_query_metric_default_step(self, source_us, time_range):
        """Default step is '1m'."""
        result = await source_us.query_metric("cpu.usage", {}, time_range)
        assert result == []


# ============================================================================
# query_instant Tests
# ============================================================================


class TestQueryInstant:
    """Tests for the query_instant async method."""

    @pytest.mark.asyncio
    async def test_query_instant_returns_list(self, source_us):
        result = await source_us.query_instant("SELECT count(*) FROM Transaction")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_query_instant_returns_empty_list(self, source_us):
        """Current stub returns empty list."""
        result = await source_us.query_instant("SELECT average(duration) FROM Transaction")
        assert result == []

    @pytest.mark.asyncio
    async def test_query_instant_logs_query(self, source_us):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_instant("SELECT count(*) FROM Transaction")
            mock_logger.info.assert_called_once()
            call_kwargs = mock_logger.info.call_args
            assert call_kwargs.kwargs["query"] == "SELECT count(*) FROM Transaction"

    @pytest.mark.asyncio
    async def test_query_instant_empty_query(self, source_us):
        """Empty query string is handled without error."""
        result = await source_us.query_instant("")
        assert result == []

    @pytest.mark.asyncio
    async def test_query_instant_complex_nrql(self, source_us):
        complex_query = (
            "SELECT average(duration) FROM Transaction WHERE appName = 'my-app' SINCE 5 minutes ago"
        )
        result = await source_us.query_instant(complex_query)
        assert result == []


# ============================================================================
# detect_anomalies Tests
# ============================================================================


class TestDetectAnomalies:
    """Tests for the detect_anomalies async method."""

    @pytest.mark.asyncio
    async def test_detect_anomalies_returns_list(self, source_us, time_range, baseline_range):
        result = await source_us.detect_anomalies("cpu.usage", {}, time_range, baseline_range)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_detect_anomalies_returns_empty_list(self, source_us, time_range, baseline_range):
        """Current stub returns empty list."""
        result = await source_us.detect_anomalies(
            "memory.used", {"host": "web-01"}, time_range, baseline_range
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_anomalies_logs_metric_name(self, source_us, time_range, baseline_range):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.detect_anomalies("error_rate", {}, time_range, baseline_range)
            call_kwargs = mock_logger.info.call_args
            assert call_kwargs.kwargs["metric"] == "error_rate"

    @pytest.mark.asyncio
    async def test_detect_anomalies_default_threshold(self, source_us, time_range, baseline_range):
        """Default threshold_percent is 50.0 — method accepts it without error."""
        result = await source_us.detect_anomalies("cpu.usage", {}, time_range, baseline_range)
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_anomalies_custom_threshold(self, source_us, time_range, baseline_range):
        result = await source_us.detect_anomalies(
            "cpu.usage", {}, time_range, baseline_range, threshold_percent=25.0
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_anomalies_high_threshold(self, source_us, time_range, baseline_range):
        result = await source_us.detect_anomalies(
            "latency", {}, time_range, baseline_range, threshold_percent=200.0
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_anomalies_zero_threshold(self, source_us, time_range, baseline_range):
        """Zero threshold is accepted."""
        result = await source_us.detect_anomalies(
            "cpu.usage", {}, time_range, baseline_range, threshold_percent=0.0
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_anomalies_with_labels(self, source_us, time_range, baseline_range):
        result = await source_us.detect_anomalies(
            "requests.error_rate",
            {"service": "api-gateway", "env": "prod"},
            time_range,
            baseline_range,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_anomalies_narrow_time_range(
        self, source_us, narrow_range, baseline_range
    ):
        """Very narrow time range is handled without error."""
        result = await source_us.detect_anomalies("cpu.usage", {}, narrow_range, baseline_range)
        assert result == []


# ============================================================================
# close() Tests
# ============================================================================


class TestClose:
    """Tests for the close async method."""

    @pytest.mark.asyncio
    async def test_close_returns_none(self, source_us):
        result = await source_us.close()
        assert result is None

    @pytest.mark.asyncio
    async def test_close_logs_shutdown(self, source_us):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.close()
            mock_logger.debug.assert_called_once_with("newrelic_source_closed")

    @pytest.mark.asyncio
    async def test_close_can_be_called_multiple_times(self, source_us):
        """Calling close() multiple times does not raise."""
        await source_us.close()
        await source_us.close()
        await source_us.close()

    @pytest.mark.asyncio
    async def test_close_on_eu_source(self, source_eu):
        """close() works the same for EU-region sources."""
        result = await source_eu.close()
        assert result is None


# ============================================================================
# NRQL Query Building Tests
# ============================================================================


class TestNRQLQueryBuilding:
    """Tests focused on NRQL query string construction across methods."""

    @pytest.mark.asyncio
    async def test_log_nrql_full_structure(self, source_us, time_range):
        """Verify the complete NRQL query structure for log queries."""
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_logs("OutOfMemory", time_range, limit=25)
            nrql = mock_logger.info.call_args.kwargs["nrql"]
            expected = "SELECT * FROM Log WHERE message LIKE '%OutOfMemory%' LIMIT 25"
            assert nrql == expected

    @pytest.mark.asyncio
    async def test_metric_nrql_full_structure(self, source_us, time_range):
        """Verify the complete NRQL query structure for metric queries."""
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_metric("container.cpu.usage", {}, time_range)
            nrql = mock_logger.info.call_args.kwargs["nrql"]
            expected = "SELECT average(container.cpu.usage) FROM Metric TIMESERIES"
            assert nrql == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query,limit,expected_nrql",
        [
            (
                "error",
                100,
                "SELECT * FROM Log WHERE message LIKE '%error%' LIMIT 100",
            ),
            (
                "timeout",
                10,
                "SELECT * FROM Log WHERE message LIKE '%timeout%' LIMIT 10",
            ),
            (
                "",
                100,
                "SELECT * FROM Log WHERE message LIKE '%%' LIMIT 100",
            ),
            (
                "connection refused",
                500,
                "SELECT * FROM Log WHERE message LIKE '%connection refused%' LIMIT 500",
            ),
        ],
        ids=["basic_error", "custom_limit", "empty_query", "multi_word_query"],
    )
    async def test_log_nrql_parametrized(self, source_us, time_range, query, limit, expected_nrql):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_logs(query, time_range, limit=limit)
            nrql = mock_logger.info.call_args.kwargs["nrql"]
            assert nrql == expected_nrql

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "metric_name,expected_fragment",
        [
            ("cpu.usage", "SELECT average(cpu.usage)"),
            ("memory.percent", "SELECT average(memory.percent)"),
            ("disk.io.read_bytes", "SELECT average(disk.io.read_bytes)"),
            ("http.request.duration", "SELECT average(http.request.duration)"),
        ],
        ids=["cpu", "memory", "disk_io", "http_duration"],
    )
    async def test_metric_nrql_parametrized(
        self, source_us, time_range, metric_name, expected_fragment
    ):
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            await source_us.query_metric(metric_name, {}, time_range)
            nrql = mock_logger.info.call_args.kwargs["nrql"]
            assert expected_fragment in nrql


# ============================================================================
# Edge Cases and Robustness Tests
# ============================================================================


class TestEdgeCases:
    """Edge case tests for boundary conditions and unusual inputs."""

    @pytest.mark.asyncio
    async def test_query_logs_with_very_long_query(self, source_us, time_range):
        """Very long query string is embedded without truncation."""
        long_query = "x" * 10_000
        with patch("shieldops.observability.newrelic.client.logger") as mock_logger:
            result = await source_us.query_logs(long_query, time_range)
            assert result == []
            nrql = mock_logger.info.call_args.kwargs["nrql"]
            assert long_query in nrql

    @pytest.mark.asyncio
    async def test_search_patterns_duplicate_patterns(self, source_us, time_range):
        """Duplicate patterns result in last-write-wins in the dict."""
        result = await source_us.search_patterns("res-1", ["error", "error", "error"], time_range)
        # dict keys are unique, so "error" appears once
        assert len(result) == 1
        assert "error" in result

    @pytest.mark.asyncio
    async def test_query_metric_empty_labels(self, source_us, time_range):
        result = await source_us.query_metric("cpu", {}, time_range)
        assert result == []

    @pytest.mark.asyncio
    async def test_multiple_methods_same_source(self, source_us, time_range, baseline_range):
        """Calling multiple methods on the same source instance works correctly."""
        logs = await source_us.query_logs("test", time_range)
        patterns = await source_us.search_patterns("res", ["a"], time_range)
        metrics = await source_us.query_metric("cpu", {}, time_range)
        instant = await source_us.query_instant("SELECT 1")
        anomalies = await source_us.detect_anomalies("cpu", {}, time_range, baseline_range)

        assert logs == []
        assert patterns == {"a": []}
        assert metrics == []
        assert instant == []
        assert anomalies == []

    @pytest.mark.asyncio
    async def test_source_usable_after_close(self, source_us, time_range):
        """Source methods still work after close() (no connection to actually tear down)."""
        await source_us.close()
        result = await source_us.query_logs("test", time_range)
        assert result == []

    @pytest.mark.asyncio
    async def test_search_patterns_special_chars_in_resource_id(self, source_us, time_range):
        result = await source_us.search_patterns(
            "namespace/pod-name:container", ["error"], time_range
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_query_instant_with_unicode(self, source_us):
        result = await source_us.query_instant("SELECT * WHERE name = 'cafe\u0301'")
        assert result == []

    @pytest.mark.asyncio
    async def test_init_with_empty_strings(self):
        """Source can be created with empty string credentials."""
        source = NewRelicSource(api_key="", account_id="", region="")
        assert source._api_key == ""
        assert source._account_id == ""
        # Empty string region is not "EU", so defaults to US URL
        assert source._base_url == "https://api.newrelic.com"


# ============================================================================
# Import Tests
# ============================================================================


class TestImports:
    """Tests verifying the module can be imported correctly."""

    def test_import_from_client_module(self):
        from shieldops.observability.newrelic.client import NewRelicSource as NrSrc

        assert NrSrc is NewRelicSource

    def test_newrelic_package_exists(self):
        import shieldops.observability.newrelic

        assert shieldops.observability.newrelic is not None
