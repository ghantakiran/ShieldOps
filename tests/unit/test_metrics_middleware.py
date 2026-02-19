"""Tests for the Prometheus metrics middleware and MetricsRegistry.

Covers: counter increments, histogram bucketing, gauge tracking,
path normalisation, Prometheus text exposition format, registry reset,
thread safety, and middleware integration via TestClient.
"""

from __future__ import annotations

import threading

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from shieldops.api.middleware.metrics import (
    DEFAULT_BUCKETS,
    MetricsMiddleware,
    MetricsRegistry,
    get_metrics_registry,
    normalize_path,
)

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_registry():
    """Ensure every test starts with a clean registry."""
    MetricsRegistry.reset_instance()
    yield
    MetricsRegistry.reset_instance()


def _make_app() -> Starlette:
    """Build a minimal Starlette app with the metrics middleware."""

    async def homepage(request: Request) -> Response:
        return PlainTextResponse("ok")

    async def item_detail(request: Request) -> Response:
        return PlainTextResponse(f"item {request.path_params['item_id']}")

    async def fail(request: Request) -> Response:
        raise ValueError("boom")

    async def slow(request: Request) -> Response:
        import asyncio

        await asyncio.sleep(0.05)
        return PlainTextResponse("slow")

    async def metrics_endpoint(request: Request) -> Response:
        body = get_metrics_registry().collect()
        return PlainTextResponse(
            body,
            media_type=("text/plain; version=0.0.4; charset=utf-8"),
        )

    app = Starlette(
        routes=[
            Route("/", homepage),
            Route("/items/{item_id}", item_detail),
            Route("/fail", fail),
            Route("/slow", slow),
            Route("/metrics", metrics_endpoint),
        ],
    )
    app.add_middleware(MetricsMiddleware)
    return app


@pytest.fixture
def app() -> Starlette:
    return _make_app()


@pytest.fixture
def client(app: Starlette) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ── MetricsRegistry unit tests ─────────────────────────────────────


class TestMetricsRegistrySingleton:
    def test_get_instance_returns_same_object(self):
        a = MetricsRegistry.get_instance()
        b = MetricsRegistry.get_instance()
        assert a is b

    def test_reset_instance_clears_singleton(self):
        a = MetricsRegistry.get_instance()
        MetricsRegistry.reset_instance()
        b = MetricsRegistry.get_instance()
        assert a is not b

    def test_get_metrics_registry_convenience(self):
        r = get_metrics_registry()
        assert isinstance(r, MetricsRegistry)
        assert r is MetricsRegistry.get_instance()


class TestCounterOperations:
    def test_inc_counter_creates_entry(self):
        r = get_metrics_registry()
        r.inc_counter("req", {"method": "GET"})
        assert len(r.counters) == 1
        key = next(iter(r.counters))
        assert r.counters[key] == 1

    def test_inc_counter_increments(self):
        r = get_metrics_registry()
        labels = {"method": "GET", "status_code": "200"}
        r.inc_counter("req", labels)
        r.inc_counter("req", labels)
        r.inc_counter("req", labels)
        key = next(iter(r.counters))
        assert r.counters[key] == 3

    def test_different_labels_separate_counters(self):
        r = get_metrics_registry()
        r.inc_counter("req", {"method": "GET"})
        r.inc_counter("req", {"method": "POST"})
        assert len(r.counters) == 2


class TestHistogramOperations:
    def test_observe_creates_buckets(self):
        r = get_metrics_registry()
        labels = {"method": "GET", "path_template": "/"}
        r.observe_histogram("dur", labels, 0.03)
        key = next(iter(r.histograms))
        # DEFAULT_BUCKETS + +Inf bucket
        assert len(r.histograms[key]) == len(DEFAULT_BUCKETS) + 1

    def test_observe_increments_correct_buckets(self):
        r = get_metrics_registry()
        labels = {"method": "GET", "path_template": "/"}
        # 0.03 falls into buckets >= 0.05, 0.1, ... and +Inf
        r.observe_histogram("dur", labels, 0.03)
        key = next(iter(r.histograms))
        buckets = r.histograms[key]
        # Buckets with le < 0.03 should have count 0
        for le, count in buckets:
            if le < 0.03:
                assert count == 0, f"bucket le={le} should be 0"
            else:
                assert count == 1, f"bucket le={le} should be 1"

    def test_observe_updates_sum_and_count(self):
        r = get_metrics_registry()
        labels = {"method": "GET", "path_template": "/"}
        r.observe_histogram("dur", labels, 0.1)
        r.observe_histogram("dur", labels, 0.2)
        key = next(iter(r._histogram_sums))
        assert r._histogram_sums[key] == pytest.approx(0.3)
        assert r._histogram_counts[key] == 2

    def test_observe_inf_bucket_always_incremented(self):
        r = get_metrics_registry()
        labels = {"method": "GET", "path_template": "/"}
        r.observe_histogram("dur", labels, 999.0)
        key = next(iter(r.histograms))
        inf_bucket = r.histograms[key][-1]
        assert inf_bucket[0] == float("inf")
        assert inf_bucket[1] == 1

    def test_value_at_boundary_goes_into_bucket(self):
        """A value exactly equal to a bucket boundary should
        be counted in that bucket."""
        r = get_metrics_registry()
        labels = {"method": "GET", "path_template": "/"}
        r.observe_histogram("dur", labels, 0.05)
        key = next(iter(r.histograms))
        # 0.05 bucket (le=0.05) should include the observation
        for le, count in r.histograms[key]:
            if le == 0.05:
                assert count == 1
                break


class TestGaugeOperations:
    def test_inc_gauge(self):
        r = get_metrics_registry()
        r.inc_gauge("in_progress", {"method": "GET"})
        key = next(iter(r.gauges))
        assert r.gauges[key] == 1

    def test_dec_gauge(self):
        r = get_metrics_registry()
        labels = {"method": "GET"}
        r.inc_gauge("in_progress", labels)
        r.inc_gauge("in_progress", labels)
        r.dec_gauge("in_progress", labels)
        key = next(iter(r.gauges))
        assert r.gauges[key] == 1

    def test_gauge_can_go_negative(self):
        r = get_metrics_registry()
        labels = {"method": "GET"}
        r.dec_gauge("in_progress", labels)
        key = next(iter(r.gauges))
        assert r.gauges[key] == -1


class TestRegistryReset:
    def test_reset_clears_all_metrics(self):
        r = get_metrics_registry()
        r.inc_counter("c", {"a": "b"})
        r.observe_histogram("h", {"a": "b"}, 0.1)
        r.inc_gauge("g", {"a": "b"})
        r.reset()
        assert r.counters == {}
        assert r.histograms == {}
        assert r.gauges == {}
        assert r._histogram_sums == {}
        assert r._histogram_counts == {}


# ── Prometheus text exposition ──────────────────────────────────────


class TestCollectOutput:
    def test_empty_registry_returns_empty(self):
        r = get_metrics_registry()
        assert r.collect() == ""

    def test_counter_format(self):
        r = get_metrics_registry()
        r.inc_counter(
            "http_requests_total",
            {"method": "GET", "status_code": "200"},
        )
        output = r.collect()
        assert "# HELP http_requests_total Total count" in output
        assert "# TYPE http_requests_total counter" in output
        assert 'http_requests_total{method="GET",status_code="200"} 1' in output

    def test_histogram_format(self):
        r = get_metrics_registry()
        r.observe_histogram(
            "http_request_duration_seconds",
            {"method": "GET", "path_template": "/"},
            0.03,
        )
        output = r.collect()
        assert "# TYPE http_request_duration_seconds histogram" in (output)
        # Check a specific bucket line
        assert (
            "http_request_duration_seconds_bucket"
            '{method="GET",path_template="/",le="0.05"} 1' in output
        )
        # +Inf bucket
        assert 'le="+Inf"} 1' in output
        # _sum and _count
        assert "http_request_duration_seconds_sum" in output
        assert "http_request_duration_seconds_count" in output

    def test_gauge_format(self):
        r = get_metrics_registry()
        r.inc_gauge("http_requests_in_progress", {"method": "GET"})
        output = r.collect()
        assert "# TYPE http_requests_in_progress gauge" in output
        assert 'http_requests_in_progress{method="GET"} 1' in output

    def test_help_and_type_emitted_once_per_metric(self):
        r = get_metrics_registry()
        r.inc_counter("c", {"a": "1"})
        r.inc_counter("c", {"a": "2"})
        output = r.collect()
        assert output.count("# TYPE c counter") == 1
        assert output.count("# HELP c Total count") == 1

    def test_collect_ends_with_newline(self):
        r = get_metrics_registry()
        r.inc_counter("c", {"a": "1"})
        output = r.collect()
        assert output.endswith("\n")


# ── Path normalisation ──────────────────────────────────────────────


class TestPathNormalization:
    def test_uuid_replaced(self):
        path = "/api/v1/investigations/550e8400-e29b-41d4-a716-446655440000"
        assert normalize_path(path) == "/api/v1/investigations/{id}"

    def test_numeric_id_replaced(self):
        assert normalize_path("/api/v1/items/42") == ("/api/v1/items/{id}")

    def test_hex_id_replaced(self):
        assert normalize_path("/api/v1/agents/abc123de") == ("/api/v1/agents/{id}")

    def test_short_hex_not_replaced(self):
        """Hex strings shorter than 8 chars are NOT replaced."""
        assert normalize_path("/api/v1/agents/abc") == ("/api/v1/agents/abc")

    def test_static_path_unchanged(self):
        assert normalize_path("/health") == "/health"
        assert normalize_path("/metrics") == "/metrics"

    def test_mixed_segments(self):
        path = "/api/v1/agents/abc12345/tasks/99"
        expected = "/api/v1/agents/{id}/tasks/{id}"
        assert normalize_path(path) == expected

    def test_root_path(self):
        assert normalize_path("/") == "/"

    def test_api_prefix_preserved(self):
        assert normalize_path("/api/v1/health") == ("/api/v1/health")


# ── Thread safety ───────────────────────────────────────────────────


class TestThreadSafety:
    def test_concurrent_counter_increments(self):
        r = get_metrics_registry()
        n_threads = 10
        n_ops = 1000
        labels = {"method": "GET", "status_code": "200"}

        def worker():
            for _ in range(n_ops):
                r.inc_counter("c", labels)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        key = next(iter(r.counters))
        assert r.counters[key] == n_threads * n_ops

    def test_concurrent_gauge_ops(self):
        r = get_metrics_registry()
        n_threads = 10
        labels = {"method": "POST"}

        def worker():
            for _ in range(100):
                r.inc_gauge("g", labels)
                r.dec_gauge("g", labels)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        key = next(iter(r.gauges))
        assert r.gauges[key] == 0


# ── Middleware integration tests (via Starlette TestClient) ─────────


class TestMetricsMiddlewareIntegration:
    def test_counter_incremented_on_request(self, client):
        client.get("/")
        r = get_metrics_registry()
        output = r.collect()
        assert "http_requests_total" in output
        assert 'status_code="200"' in output

    def test_histogram_recorded(self, client):
        client.get("/")
        r = get_metrics_registry()
        assert len(r.histograms) > 0

    def test_gauge_returns_to_zero(self, client):
        """After a completed request, in-progress gauge should be
        back to 0."""
        client.get("/")
        r = get_metrics_registry()
        for key, val in r.gauges.items():
            if "http_requests_in_progress" in key:
                assert val == 0

    def test_500_tracked_on_exception(self, client):
        resp = client.get("/fail")
        assert resp.status_code == 500
        r = get_metrics_registry()
        output = r.collect()
        assert 'status_code="500"' in output

    def test_gauge_decremented_on_exception(self, client):
        """Even if the handler raises, the gauge must decrement."""
        client.get("/fail")
        r = get_metrics_registry()
        for key, val in r.gauges.items():
            if "http_requests_in_progress" in key:
                assert val == 0

    def test_path_with_param_normalised(self, client):
        client.get("/items/12345678")
        r = get_metrics_registry()
        output = r.collect()
        assert 'path_template="/items/{id}"' in output

    def test_method_label_correct(self, client):
        client.get("/")
        r = get_metrics_registry()
        output = r.collect()
        assert 'method="GET"' in output

    def test_multiple_requests_accumulate(self, client):
        client.get("/")
        client.get("/")
        client.get("/")
        r = get_metrics_registry()
        # Find the counter for GET /
        found = False
        for key, val in r.counters.items():
            if "http_requests_total" in key and "/" in key:
                found = True
                assert val >= 3
        assert found

    def test_different_status_codes_separate(self, client):
        client.get("/")  # 200
        client.get("/fail")  # 500
        r = get_metrics_registry()
        keys_200 = [k for k in r.counters if 'status_code="200"' in k]
        keys_500 = [k for k in r.counters if 'status_code="500"' in k]
        assert len(keys_200) >= 1
        assert len(keys_500) >= 1

    def test_metrics_endpoint_returns_text(self, client):
        # Generate some traffic first
        client.get("/")
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        assert "http_requests_total" in resp.text

    def test_health_and_metrics_still_tracked(self, client):
        """Exempt paths like /metrics should still be tracked in
        the metrics middleware (exemption is only for rate
        limiting)."""
        client.get("/metrics")
        r = get_metrics_registry()
        output = r.collect()
        assert 'path_template="/metrics"' in output

    def test_slow_request_lands_in_higher_bucket(self, client):
        """A 50ms+ request should have counts in buckets >= 0.05."""
        client.get("/slow")
        r = get_metrics_registry()
        for key, buckets in r.histograms.items():
            if "/slow" in key:
                # The 0.005 bucket should NOT include this request
                for le, count in buckets:
                    if le == 0.005:
                        assert count == 0


class TestMultipleConcurrentRequests:
    def test_concurrent_http_requests(self, app):
        """Simulate concurrent requests in threads and verify
        total counter matches."""
        n_threads = 5
        n_per_thread = 10
        results: list[int] = []

        def worker():
            c = TestClient(app, raise_server_exceptions=False)
            for _ in range(n_per_thread):
                resp = c.get("/")
                results.append(resp.status_code)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == n_threads * n_per_thread
        r = get_metrics_registry()
        total = sum(
            v
            for k, v in r.counters.items()
            if "http_requests_total" in k and 'path_template="/"' in k
        )
        assert total == n_threads * n_per_thread
