"""Comprehensive tests for observability source clients.

Tests cover:
- SplunkSource (LogSource) — SPL queries via Splunk REST API
- DatadogSource (MetricSource) — Datadog Metrics API
- JaegerSource (TraceSource) — Jaeger HTTP API
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from shieldops.models.base import TimeRange
from shieldops.observability.datadog.client import DatadogSource
from shieldops.observability.otel.client import JaegerSource
from shieldops.observability.splunk.client import SplunkSource

# --- Helpers ---


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response with sync .json() and .raise_for_status()."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def _mock_response_error(exc: Exception) -> MagicMock:
    """Create a mock httpx.Response whose raise_for_status raises."""
    resp = MagicMock()
    resp.raise_for_status.side_effect = exc
    return resp


# --- Shared fixtures ---


@pytest.fixture
def time_range():
    now = datetime.now(UTC)
    return TimeRange(start=now - timedelta(hours=1), end=now)


@pytest.fixture
def baseline_range():
    now = datetime.now(UTC)
    return TimeRange(start=now - timedelta(days=1, hours=1), end=now - timedelta(days=1))


# ============================================================================
# SplunkSource tests
# ============================================================================


class TestSplunkSource:
    @pytest.fixture
    def splunk(self):
        source = SplunkSource(
            url="https://splunk.corp.com:8089",
            token="test-token",
            index="main",
        )
        yield source

    @pytest.fixture
    def mock_splunk_data(self):
        return {
            "results": [
                {
                    "_time": "2025-01-01T00:00:00Z",
                    "_raw": "ERROR OOMKilled: container exceeded memory limit",
                    "source": "default/api-server",
                    "log_level": "error",
                },
                {
                    "_time": "2025-01-01T00:00:01Z",
                    "_raw": "INFO Starting container api-server",
                    "source": "default/api-server",
                    "level": "info",
                },
            ]
        }

    @pytest.mark.asyncio
    async def test_query_logs_returns_normalized_entries(
        self, splunk, time_range, mock_splunk_data
    ):
        splunk._client.post = AsyncMock(return_value=_mock_response(mock_splunk_data))

        results = await splunk.query_logs("default/api-server", time_range)

        assert len(results) == 2
        assert results[0]["timestamp"] == "2025-01-01T00:00:00Z"
        assert results[0]["level"] == "error"
        assert "OOMKilled" in results[0]["message"]
        assert results[1]["level"] == "info"

    @pytest.mark.asyncio
    async def test_query_logs_spl_construction(self, splunk, time_range):
        splunk._client.post = AsyncMock(return_value=_mock_response({"results": []}))

        await splunk.query_logs("default/api-server", time_range, limit=50)

        call_kwargs = splunk._client.post.call_args
        spl = call_kwargs.kwargs.get("data", call_kwargs[1].get("data", {})).get("search", "")
        assert "index=main" in spl
        assert 'source="default/api-server"' in spl
        assert "head 50" in spl

    @pytest.mark.asyncio
    async def test_query_logs_auth_header(self, splunk):
        assert splunk._client.headers["Authorization"] == "Bearer test-token"

    @pytest.mark.asyncio
    async def test_query_logs_connection_error(self, splunk, time_range):
        splunk._client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        results = await splunk.query_logs("default/api-server", time_range)
        assert results == []

    @pytest.mark.asyncio
    async def test_query_logs_bad_status(self, splunk, time_range):
        resp = MagicMock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=httpx.Request("POST", "http://test"), response=resp
        )
        splunk._client.post = AsyncMock(return_value=resp)
        results = await splunk.query_logs("default/api-server", time_range)
        assert results == []

    @pytest.mark.asyncio
    async def test_query_logs_empty_results(self, splunk, time_range):
        splunk._client.post = AsyncMock(return_value=_mock_response({"results": []}))
        results = await splunk.query_logs("default/api-server", time_range)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_patterns_returns_matches(self, splunk, time_range, mock_splunk_data):
        splunk._client.post = AsyncMock(return_value=_mock_response(mock_splunk_data))

        results = await splunk.search_patterns(
            "default/api-server", ["OOMKilled", "timeout"], time_range
        )

        assert "OOMKilled" in results
        assert "timeout" in results
        assert splunk._client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_search_patterns_error_handling(self, splunk, time_range):
        splunk._client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        results = await splunk.search_patterns("default/api-server", ["error"], time_range)
        assert results == {"error": []}

    @pytest.mark.asyncio
    async def test_detect_level_from_raw(self, splunk):
        assert splunk._detect_level({"_raw": "FATAL panic"}) == "fatal"
        assert splunk._detect_level({"_raw": "ERROR something broke"}) == "error"
        assert splunk._detect_level({"_raw": "WARN disk usage high"}) == "warning"
        assert splunk._detect_level({"_raw": "DEBUG trace"}) == "debug"
        assert splunk._detect_level({"_raw": "normal log"}) == "info"

    @pytest.mark.asyncio
    async def test_detect_level_from_field(self, splunk):
        assert splunk._detect_level({"log_level": "ERROR", "_raw": ""}) == "error"
        assert splunk._detect_level({"level": "WARNING", "_raw": ""}) == "warning"
        assert splunk._detect_level({"severity": "CRITICAL", "_raw": ""}) == "critical"

    @pytest.mark.asyncio
    async def test_close(self, splunk):
        splunk._client.aclose = AsyncMock()
        await splunk.close()
        splunk._client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_logs_timeout(self, splunk, time_range):
        splunk._client.post = AsyncMock(side_effect=httpx.ReadTimeout("Read timed out"))
        results = await splunk.query_logs("default/api-server", time_range)
        assert results == []

    @pytest.mark.asyncio
    async def test_normalize_results_missing_fields(self, splunk, time_range):
        splunk._client.post = AsyncMock(
            return_value=_mock_response({"results": [{"_time": "2025-01-01T00:00:00Z"}]})
        )
        results = await splunk.query_logs("default/pod", time_range)
        assert len(results) == 1
        assert results[0]["message"] == ""
        assert results[0]["level"] == "info"

    @pytest.mark.asyncio
    async def test_query_logs_uses_oneshot_mode(self, splunk, time_range):
        splunk._client.post = AsyncMock(return_value=_mock_response({"results": []}))
        await splunk.query_logs("default/pod", time_range)

        call_kwargs = splunk._client.post.call_args
        data = call_kwargs.kwargs.get("data", call_kwargs[1].get("data", {}))
        assert data.get("exec_mode") == "oneshot"


# ============================================================================
# DatadogSource tests
# ============================================================================


class TestDatadogSource:
    @pytest.fixture
    def datadog(self):
        source = DatadogSource(
            api_key="dd-api-key",
            app_key="dd-app-key",
            site="datadoghq.com",
        )
        yield source

    @pytest.fixture
    def mock_dd_series(self):
        return {
            "series": [
                {
                    "metric": "system.cpu.user",
                    "pointlist": [
                        [1704067200000, 45.5],
                        [1704067260000, 48.2],
                        [1704067320000, 50.1],
                    ],
                    "tag_set": ["host:web-01", "env:production"],
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_query_metric_returns_timeseries(self, datadog, time_range, mock_dd_series):
        datadog._client.get = AsyncMock(return_value=_mock_response(mock_dd_series))

        results = await datadog.query_metric("system.cpu.user", {"host": "web-01"}, time_range)

        assert len(results) == 3
        assert results[0]["value"] == 45.5
        assert results[0]["labels"] == {"host": "web-01", "env": "production"}
        assert "timestamp" in results[0]

    @pytest.mark.asyncio
    async def test_query_metric_datadog_query_construction(self, datadog, time_range):
        datadog._client.get = AsyncMock(return_value=_mock_response({"series": []}))

        await datadog.query_metric("system.cpu.user", {"host": "web-01", "env": "prod"}, time_range)

        call_kwargs = datadog._client.get.call_args
        params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
        query = params.get("query", "")
        assert "avg:system.cpu.user{" in query
        assert "host:web-01" in query

    @pytest.mark.asyncio
    async def test_query_metric_auth_headers(self, datadog):
        assert datadog._client.headers["DD-API-KEY"] == "dd-api-key"
        assert datadog._client.headers["DD-APPLICATION-KEY"] == "dd-app-key"

    @pytest.mark.asyncio
    async def test_query_metric_connection_error(self, datadog, time_range):
        datadog._client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        results = await datadog.query_metric("system.cpu.user", {}, time_range)
        assert results == []

    @pytest.mark.asyncio
    async def test_query_metric_empty_series(self, datadog, time_range):
        datadog._client.get = AsyncMock(return_value=_mock_response({"series": []}))
        results = await datadog.query_metric("cpu", {}, time_range)
        assert results == []

    @pytest.mark.asyncio
    async def test_query_instant_returns_latest(self, datadog, mock_dd_series):
        datadog._client.get = AsyncMock(return_value=_mock_response(mock_dd_series))

        results = await datadog.query_instant("avg:system.cpu.user{*}")

        assert len(results) == 1
        assert results[0]["value"] == 50.1  # Last data point
        assert results[0]["metric"] == "system.cpu.user"

    @pytest.mark.asyncio
    async def test_query_instant_error(self, datadog):
        datadog._client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        results = await datadog.query_instant("avg:system.cpu.user{*}")
        assert results == []

    @pytest.mark.asyncio
    async def test_detect_anomalies_flags_deviation(self, datadog, time_range, baseline_range):
        current_data = {
            "series": [
                {
                    "metric": "mem",
                    "pointlist": [[1704067200000, 100.0], [1704067260000, 110.0]],
                    "tag_set": [],
                }
            ]
        }
        baseline_data = {
            "series": [
                {
                    "metric": "mem",
                    "pointlist": [[1704067200000, 50.0], [1704067260000, 50.0]],
                    "tag_set": [],
                }
            ]
        }

        responses = [_mock_response(current_data), _mock_response(baseline_data)]
        datadog._client.get = AsyncMock(side_effect=responses)

        results = await datadog.detect_anomalies(
            "memory_usage", {}, time_range, baseline_range, threshold_percent=50.0
        )

        assert len(results) == 2
        assert results[0]["deviation_percent"] == 100.0
        assert results[0]["baseline_value"] == 50.0
        assert results[0]["metric_name"] == "memory_usage"

    @pytest.mark.asyncio
    async def test_detect_anomalies_no_data(self, datadog, time_range, baseline_range):
        datadog._client.get = AsyncMock(return_value=_mock_response({"series": []}))
        results = await datadog.detect_anomalies("cpu", {}, time_range, baseline_range)
        assert results == []

    @pytest.mark.asyncio
    async def test_detect_anomalies_zero_baseline(self, datadog, time_range, baseline_range):
        current_data = {"series": [{"pointlist": [[1704067200000, 10.0]], "tag_set": []}]}
        baseline_data = {"series": [{"pointlist": [[1704067200000, 0.0]], "tag_set": []}]}
        responses = [_mock_response(current_data), _mock_response(baseline_data)]
        datadog._client.get = AsyncMock(side_effect=responses)

        results = await datadog.detect_anomalies("cpu", {}, time_range, baseline_range)
        assert results == []

    @pytest.mark.asyncio
    async def test_build_query_with_labels(self):
        q = DatadogSource._build_query("system.cpu.user", {"host": "web-01"})
        assert q == "avg:system.cpu.user{host:web-01}"

    @pytest.mark.asyncio
    async def test_build_query_without_labels(self):
        q = DatadogSource._build_query("system.cpu.user", {})
        assert q == "avg:system.cpu.user{*}"

    @pytest.mark.asyncio
    async def test_parse_tags(self):
        tags = DatadogSource._parse_tags(["host:web-01", "env:production", "standalone"])
        assert tags == {"host": "web-01", "env": "production", "standalone": ""}

    @pytest.mark.asyncio
    async def test_close(self, datadog):
        datadog._client.aclose = AsyncMock()
        await datadog.close()
        datadog._client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_metric_null_points_skipped(self, datadog, time_range):
        datadog._client.get = AsyncMock(
            return_value=_mock_response(
                {
                    "series": [
                        {
                            "pointlist": [[1704067200000, None], [1704067260000, 42.0]],
                            "tag_set": [],
                        }
                    ]
                }
            )
        )
        results = await datadog.query_metric("cpu", {}, time_range)
        assert len(results) == 1
        assert results[0]["value"] == 42.0

    @pytest.mark.asyncio
    async def test_query_metric_bad_status(self, datadog, time_range):
        resp = MagicMock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403", request=httpx.Request("GET", "http://test"), response=resp
        )
        datadog._client.get = AsyncMock(return_value=resp)
        results = await datadog.query_metric("cpu", {}, time_range)
        assert results == []


# ============================================================================
# JaegerSource tests
# ============================================================================


class TestJaegerSource:
    @pytest.fixture
    def jaeger(self):
        source = JaegerSource(url="http://localhost:16686")
        yield source

    @pytest.fixture
    def mock_jaeger_trace(self):
        return {
            "data": [
                {
                    "traceID": "abc123",
                    "processes": {
                        "p1": {"serviceName": "api-gateway"},
                        "p2": {"serviceName": "user-service"},
                        "p3": {"serviceName": "database"},
                    },
                    "spans": [
                        {
                            "spanID": "span-1",
                            "operationName": "HTTP GET /users",
                            "processID": "p1",
                            "duration": 5000000,  # 5s in microseconds
                            "tags": [],
                            "references": [],
                        },
                        {
                            "spanID": "span-2",
                            "operationName": "grpc.GetUser",
                            "processID": "p2",
                            "duration": 3000000,  # 3s
                            "tags": [],
                            "references": [{"refType": "CHILD_OF", "spanID": "span-1"}],
                        },
                        {
                            "spanID": "span-3",
                            "operationName": "SELECT * FROM users",
                            "processID": "p3",
                            "duration": 2500000,  # 2.5s
                            "tags": [{"key": "error", "value": True}],
                            "references": [{"refType": "CHILD_OF", "spanID": "span-2"}],
                        },
                    ],
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_get_trace_parses_spans(self, jaeger, mock_jaeger_trace):
        jaeger._client.get = AsyncMock(return_value=_mock_response(mock_jaeger_trace))

        result = await jaeger.get_trace("abc123")

        assert result is not None
        assert result["trace_id"] == "abc123"
        assert result["root_service"] == "api-gateway"
        assert result["span_count"] == 3

        spans = result["spans"]
        assert spans[0]["service"] == "api-gateway"
        assert spans[0]["duration_ms"] == 5000.0
        assert spans[0]["parent_span_id"] is None

        assert spans[1]["service"] == "user-service"
        assert spans[1]["parent_span_id"] == "span-1"

        assert spans[2]["service"] == "database"
        assert spans[2]["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_trace_not_found(self, jaeger):
        jaeger._client.get = AsyncMock(return_value=_mock_response({"data": []}))
        result = await jaeger.get_trace("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_trace_connection_error(self, jaeger):
        jaeger._client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        result = await jaeger.get_trace("abc123")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_trace_bad_status(self, jaeger):
        resp = MagicMock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=httpx.Request("GET", "http://test"), response=resp
        )
        jaeger._client.get = AsyncMock(return_value=resp)
        result = await jaeger.get_trace("abc123")
        assert result is None

    @pytest.mark.asyncio
    async def test_search_traces_returns_summaries(self, jaeger, time_range, mock_jaeger_trace):
        jaeger._client.get = AsyncMock(return_value=_mock_response(mock_jaeger_trace))

        results = await jaeger.search_traces("api-gateway", time_range)

        assert len(results) == 1
        assert results[0]["trace_id"] == "abc123"
        assert results[0]["root_service"] == "api-gateway"
        assert results[0]["span_count"] == 3
        assert results[0]["has_error"] is True
        assert "database" in results[0]["services"]

    @pytest.mark.asyncio
    async def test_search_traces_with_min_duration(self, jaeger, time_range):
        jaeger._client.get = AsyncMock(return_value=_mock_response({"data": []}))

        await jaeger.search_traces("api-gateway", time_range, min_duration_ms=1000)

        call_kwargs = jaeger._client.get.call_args
        params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
        assert params["minDuration"] == "1000ms"

    @pytest.mark.asyncio
    async def test_search_traces_with_error_filter(self, jaeger, time_range):
        jaeger._client.get = AsyncMock(return_value=_mock_response({"data": []}))

        await jaeger.search_traces("api-gateway", time_range, status="error")

        call_kwargs = jaeger._client.get.call_args
        params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
        assert "error" in params.get("tags", "")

    @pytest.mark.asyncio
    async def test_search_traces_connection_error(self, jaeger, time_range):
        jaeger._client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        results = await jaeger.search_traces("api-gateway", time_range)
        assert results == []

    @pytest.mark.asyncio
    async def test_find_bottleneck_finds_slowest_span(self, jaeger, time_range, mock_jaeger_trace):
        jaeger._client.get = AsyncMock(return_value=_mock_response(mock_jaeger_trace))

        result = await jaeger.find_bottleneck("api-gateway", time_range)

        assert result is not None
        assert result["service"] == "api-gateway"  # 5000ms is the slowest
        assert result["duration_ms"] == 5000.0
        assert result["operation"] == "HTTP GET /users"
        assert result["span_count"] == 3

    @pytest.mark.asyncio
    async def test_find_bottleneck_no_traces(self, jaeger, time_range):
        jaeger._client.get = AsyncMock(return_value=_mock_response({"data": []}))
        result = await jaeger.find_bottleneck("api-gateway", time_range)
        assert result is None

    @pytest.mark.asyncio
    async def test_parse_spans_empty(self, jaeger):
        trace = {"processes": {}, "spans": []}
        spans = jaeger._parse_spans(trace)
        assert spans == []

    @pytest.mark.asyncio
    async def test_find_root_service_no_parent(self, jaeger):
        trace = {
            "processes": {"p1": {"serviceName": "root-svc"}},
            "spans": [
                {"spanID": "s1", "processID": "p1", "references": []},
            ],
        }
        assert jaeger._find_root_service(trace) == "root-svc"

    @pytest.mark.asyncio
    async def test_find_root_service_fallback(self, jaeger):
        trace = {
            "processes": {"p1": {"serviceName": "svc"}},
            "spans": [
                {
                    "spanID": "s1",
                    "processID": "p1",
                    "references": [{"refType": "CHILD_OF", "spanID": "parent"}],
                },
            ],
        }
        assert jaeger._find_root_service(trace) == "svc"

    @pytest.mark.asyncio
    async def test_close(self, jaeger):
        jaeger._client.aclose = AsyncMock()
        await jaeger.close()
        jaeger._client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_traces_uses_microseconds(self, jaeger, time_range):
        jaeger._client.get = AsyncMock(return_value=_mock_response({"data": []}))

        await jaeger.search_traces("svc", time_range)

        call_kwargs = jaeger._client.get.call_args
        params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
        assert params["start"] > 1_000_000_000_000

    @pytest.mark.asyncio
    async def test_get_trace_url_construction(self, jaeger):
        jaeger._client.get = AsyncMock(return_value=_mock_response({"data": []}))
        await jaeger.get_trace("trace-xyz")

        call_args = jaeger._client.get.call_args
        url = call_args[0][0]
        assert url == "http://localhost:16686/api/traces/trace-xyz"


# ============================================================================
# Import re-export tests
# ============================================================================


class TestImports:
    def test_splunk_import(self):
        from shieldops.observability.splunk import SplunkSource as S

        assert S is SplunkSource

    def test_datadog_import(self):
        from shieldops.observability.datadog import DatadogSource as D

        assert D is DatadogSource

    def test_jaeger_import(self):
        from shieldops.observability.otel import JaegerSource as J

        assert J is JaegerSource
