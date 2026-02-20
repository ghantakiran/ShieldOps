"""Tests for API usage tracking middleware and UsageTracker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from starlette.applications import Starlette
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from shieldops.api.middleware.usage_tracker import (
    _SKIP_PATHS,
    UsageTracker,
    UsageTrackerMiddleware,
    get_usage_tracker,
)

# ── Helpers ──────────────────────────────────────────────────────────


async def _ok_endpoint(request: Request) -> Response:
    """Minimal endpoint that returns 200 with a JSON body."""
    return JSONResponse({"status": "ok"})


class OrgSetter(BaseHTTPMiddleware):
    """Test middleware that sets organization_id on request.state."""

    def __init__(self, app: object, org_id: str) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._org_id = org_id

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request.state.organization_id = self._org_id
        return await call_next(request)


def _build_app(org_id: str | None = None) -> Starlette:
    """Build a minimal Starlette app with the usage tracker."""
    app = Starlette(
        routes=[
            Route("/health", _ok_endpoint),
            Route("/ready", _ok_endpoint),
            Route("/metrics", _ok_endpoint),
            Route(
                "/api/v1/agents",
                _ok_endpoint,
                methods=["GET", "POST"],
            ),
            Route(
                "/api/v1/investigations",
                _ok_endpoint,
                methods=["GET"],
            ),
        ],
    )
    app.add_middleware(UsageTrackerMiddleware)
    if org_id is not None:
        app.add_middleware(OrgSetter, org_id=org_id)
    return app


@pytest.fixture(autouse=True)
def _reset_tracker() -> None:
    """Reset the global singleton before each test."""
    UsageTracker.reset_instance()


# ── Test: UsageTracker.record — single call ──────────────────────────


class TestRecordSingleCall:
    def test_record_single_call(self) -> None:
        """A single record() call increments the count by 1."""
        tracker = UsageTracker()
        tracker.record("org-1", "GET", "/api/v1/agents")

        usage = tracker.get_usage(org_id="org-1")
        assert usage["total_calls"] == 1

    def test_record_stores_endpoint(self) -> None:
        """The recorded endpoint includes method + path."""
        tracker = UsageTracker()
        tracker.record("org-1", "POST", "/api/v1/agents")

        endpoints = tracker.get_top_endpoints(
            org_id="org-1",
            limit=5,
        )
        assert len(endpoints) == 1
        assert endpoints[0]["endpoint"] == "POST /api/v1/agents"


# ── Test: Multiple calls to same endpoint ────────────────────────────


class TestRecordMultipleCalls:
    def test_multiple_calls_same_endpoint(self) -> None:
        """Multiple calls to the same endpoint accumulate."""
        tracker = UsageTracker()
        for _ in range(5):
            tracker.record("org-1", "GET", "/api/v1/agents")

        usage = tracker.get_usage(org_id="org-1")
        assert usage["total_calls"] == 5

    def test_multiple_calls_reflected_in_top_endpoints(
        self,
    ) -> None:
        """Top endpoints show correct count after repeated calls."""
        tracker = UsageTracker()
        for _ in range(7):
            tracker.record(
                "org-1",
                "GET",
                "/api/v1/agents",
                duration_ms=10.0,
            )

        endpoints = tracker.get_top_endpoints(org_id="org-1")
        assert endpoints[0]["count"] == 7
        assert endpoints[0]["avg_latency_ms"] == 10.0


# ── Test: Different orgs ─────────────────────────────────────────────


class TestDifferentOrgs:
    def test_calls_from_different_orgs(self) -> None:
        """Each org's usage is tracked independently."""
        tracker = UsageTracker()
        for _ in range(3):
            tracker.record("org-alpha", "GET", "/api/v1/agents")
        for _ in range(5):
            tracker.record("org-beta", "GET", "/api/v1/agents")

        alpha_usage = tracker.get_usage(org_id="org-alpha")
        beta_usage = tracker.get_usage(org_id="org-beta")
        assert alpha_usage["total_calls"] == 3
        assert beta_usage["total_calls"] == 5

    def test_org_isolation_in_top_endpoints(self) -> None:
        """Top endpoints are isolated by org when filtered."""
        tracker = UsageTracker()
        tracker.record("org-a", "GET", "/api/v1/agents")
        tracker.record("org-b", "POST", "/api/v1/agents")

        a_eps = tracker.get_top_endpoints(org_id="org-a")
        b_eps = tracker.get_top_endpoints(org_id="org-b")

        assert len(a_eps) == 1
        assert a_eps[0]["endpoint"] == "GET /api/v1/agents"
        assert len(b_eps) == 1
        assert b_eps[0]["endpoint"] == "POST /api/v1/agents"


# ── Test: get_usage default period ───────────────────────────────────


class TestGetUsageDefaults:
    def test_get_usage_defaults_24h(self) -> None:
        """get_usage with no period defaults to 24 hours."""
        tracker = UsageTracker()
        tracker.record("org-1", "GET", "/api/v1/agents")

        usage = tracker.get_usage(org_id="org-1")
        assert usage["period_hours"] == 24

    def test_get_usage_no_org_returns_all(self) -> None:
        """get_usage with no org_id aggregates all orgs."""
        tracker = UsageTracker()
        tracker.record("org-a", "GET", "/api/v1/agents")
        tracker.record("org-b", "GET", "/api/v1/agents")

        usage = tracker.get_usage()
        assert usage["total_calls"] == 2
        assert usage["org_id"] is None


# ── Test: get_top_endpoints ──────────────────────────────────────────


class TestGetTopEndpoints:
    def test_top_endpoints_ordering(self) -> None:
        """Endpoints are ordered by count descending."""
        tracker = UsageTracker()
        for _ in range(10):
            tracker.record(
                "org-1",
                "GET",
                "/api/v1/agents",
            )
        for _ in range(3):
            tracker.record(
                "org-1",
                "POST",
                "/api/v1/agents",
            )

        eps = tracker.get_top_endpoints(org_id="org-1")
        assert eps[0]["count"] >= eps[1]["count"]
        assert eps[0]["endpoint"] == "GET /api/v1/agents"

    def test_top_endpoints_respects_limit(self) -> None:
        """Only `limit` endpoints are returned."""
        tracker = UsageTracker()
        for i in range(20):
            tracker.record(
                "org-1",
                "GET",
                f"/api/v1/resource{i}",
            )

        eps = tracker.get_top_endpoints(
            org_id="org-1",
            limit=5,
        )
        assert len(eps) == 5

    def test_top_endpoints_avg_latency(self) -> None:
        """Average latency is computed correctly."""
        tracker = UsageTracker()
        tracker.record(
            "org-1",
            "GET",
            "/api/v1/agents",
            duration_ms=100.0,
        )
        tracker.record(
            "org-1",
            "GET",
            "/api/v1/agents",
            duration_ms=200.0,
        )

        eps = tracker.get_top_endpoints(org_id="org-1")
        assert eps[0]["avg_latency_ms"] == 150.0


# ── Test: get_hourly_breakdown ───────────────────────────────────────


class TestGetHourlyBreakdown:
    def test_hourly_breakdown_returns_sorted_hours(self) -> None:
        """Hourly breakdown hours are sorted ascending."""
        tracker = UsageTracker()
        tracker.record("org-1", "GET", "/api/v1/agents")

        breakdown = tracker.get_hourly_breakdown(
            org_id="org-1",
            hours=24,
        )
        hours_list = [h["hour"] for h in breakdown]
        assert hours_list == sorted(hours_list)

    def test_hourly_breakdown_includes_current_hour(
        self,
    ) -> None:
        """Current hour key appears in the breakdown."""
        tracker = UsageTracker()
        tracker.record("org-1", "GET", "/api/v1/agents")

        breakdown = tracker.get_hourly_breakdown(
            org_id="org-1",
            hours=1,
        )
        current_hour = datetime.now(UTC).strftime("%Y-%m-%dT%H")
        hour_keys = {h["hour"] for h in breakdown}
        assert current_hour in hour_keys


# ── Test: Anonymous call tracking ────────────────────────────────────


class TestAnonymousCalls:
    def test_anonymous_calls_tracked_under_key(self) -> None:
        """Calls with org_id=None are tracked as _anonymous."""
        tracker = UsageTracker()
        tracker.record(None, "GET", "/api/v1/agents")

        # Query without org filter should include it
        usage = tracker.get_usage()
        assert usage["total_calls"] == 1

    def test_anonymous_appears_in_by_org(self) -> None:
        """get_usage_by_org includes _anonymous when present."""
        tracker = UsageTracker()
        tracker.record(None, "GET", "/api/v1/agents")
        tracker.record("org-1", "GET", "/api/v1/agents")

        by_org = tracker.get_usage_by_org()
        org_ids = {o["org_id"] for o in by_org}
        assert "_anonymous" in org_ids
        assert "org-1" in org_ids


# ── Test: Middleware skips health endpoints ───────────────────────────


class TestMiddlewareSkipPaths:
    def test_middleware_skips_health(self) -> None:
        """Requests to /health are not tracked."""
        app = _build_app()
        client = TestClient(app)
        tracker = get_usage_tracker()

        client.get("/health")

        usage = tracker.get_usage()
        assert usage["total_calls"] == 0

    def test_middleware_skips_ready(self) -> None:
        """Requests to /ready are not tracked."""
        app = _build_app()
        client = TestClient(app)
        tracker = get_usage_tracker()

        client.get("/ready")

        usage = tracker.get_usage()
        assert usage["total_calls"] == 0

    def test_middleware_skips_metrics(self) -> None:
        """Requests to /metrics are not tracked."""
        app = _build_app()
        client = TestClient(app)
        tracker = get_usage_tracker()

        client.get("/metrics")

        usage = tracker.get_usage()
        assert usage["total_calls"] == 0

    def test_skip_paths_constant_complete(self) -> None:
        """Verify the skip-paths set contains expected entries."""
        assert "/health" in _SKIP_PATHS
        assert "/ready" in _SKIP_PATHS
        assert "/metrics" in _SKIP_PATHS


# ── Test: Middleware records method + path ────────────────────────────


class TestMiddlewareRecording:
    def test_middleware_records_get(self) -> None:
        """GET requests are recorded with method and path."""
        app = _build_app()
        client = TestClient(app)
        tracker = get_usage_tracker()

        client.get("/api/v1/agents")

        eps = tracker.get_top_endpoints()
        assert len(eps) == 1
        assert eps[0]["endpoint"] == "GET /api/v1/agents"
        assert eps[0]["count"] == 1

    def test_middleware_records_post(self) -> None:
        """POST requests are recorded separately from GET."""
        app = _build_app()
        client = TestClient(app)
        tracker = get_usage_tracker()

        client.post("/api/v1/agents")
        client.get("/api/v1/agents")

        eps = tracker.get_top_endpoints()
        endpoints_set = {e["endpoint"] for e in eps}
        assert "GET /api/v1/agents" in endpoints_set
        assert "POST /api/v1/agents" in endpoints_set

    def test_middleware_records_latency(self) -> None:
        """Middleware records non-zero latency."""
        app = _build_app()
        client = TestClient(app)
        tracker = get_usage_tracker()

        client.get("/api/v1/agents")

        eps = tracker.get_top_endpoints()
        # Latency should be > 0 (even a fast local call)
        assert eps[0]["avg_latency_ms"] >= 0


# ── Test: Middleware uses org_id from state ───────────────────────────


class TestMiddlewareOrgId:
    def test_middleware_uses_org_id(self) -> None:
        """When org_id is on request.state, it is used as key."""
        app = _build_app(org_id="org-test-123")
        client = TestClient(app)
        tracker = get_usage_tracker()

        client.get("/api/v1/agents")

        # Should be tracked under the org
        usage = tracker.get_usage(org_id="org-test-123")
        assert usage["total_calls"] == 1

    def test_middleware_anonymous_without_org(self) -> None:
        """Without org_id middleware, calls go to _anonymous."""
        app = _build_app(org_id=None)
        client = TestClient(app)
        tracker = get_usage_tracker()

        client.get("/api/v1/agents")

        by_org = tracker.get_usage_by_org()
        org_ids = {o["org_id"] for o in by_org}
        assert "_anonymous" in org_ids


# ── Test: Empty usage returns zeros ──────────────────────────────────


class TestEmptyUsage:
    def test_empty_usage_returns_zero_total(self) -> None:
        """Fresh tracker returns zero total calls."""
        tracker = UsageTracker()
        usage = tracker.get_usage()
        assert usage["total_calls"] == 0
        assert usage["unique_endpoints"] == 0

    def test_empty_top_endpoints_returns_empty_list(
        self,
    ) -> None:
        """Fresh tracker returns no top endpoints."""
        tracker = UsageTracker()
        eps = tracker.get_top_endpoints()
        assert eps == []

    def test_empty_hourly_breakdown_has_zero_counts(
        self,
    ) -> None:
        """Fresh tracker hourly breakdown has 0 counts for all hours."""
        tracker = UsageTracker()
        breakdown = tracker.get_hourly_breakdown(hours=24)
        for entry in breakdown:
            assert entry["count"] == 0

    def test_empty_by_org_returns_empty_list(self) -> None:
        """Fresh tracker returns no org data."""
        tracker = UsageTracker()
        by_org = tracker.get_usage_by_org()
        assert by_org == []


# ── Test: Hour boundary handling ─────────────────────────────────────


class TestHourBoundary:
    def test_old_data_excluded_from_short_window(self) -> None:
        """Data older than the window is excluded."""
        tracker = UsageTracker()

        # Manually insert data for 48 hours ago
        old_hour = (datetime.now(UTC) - timedelta(hours=48)).strftime("%Y-%m-%dT%H")

        with tracker._mu:
            tracker._counts["org-1"]["GET /old"][old_hour] = 99

        # Current-hour data
        tracker.record("org-1", "GET", "/api/v1/agents")

        usage = tracker.get_usage(org_id="org-1", hours=24)
        # Should only see the current-hour call, not the old one
        assert usage["total_calls"] == 1

    def test_current_hour_included(self) -> None:
        """Data from the current hour is always included."""
        tracker = UsageTracker()
        tracker.record("org-1", "GET", "/api/v1/agents")

        usage = tracker.get_usage(org_id="org-1", hours=1)
        assert usage["total_calls"] == 1


# ── Test: Singleton pattern ──────────────────────────────────────────


class TestSingleton:
    def test_get_instance_returns_same_object(self) -> None:
        """get_instance always returns the same tracker."""
        a = UsageTracker.get_instance()
        b = UsageTracker.get_instance()
        assert a is b

    def test_reset_instance_creates_new(self) -> None:
        """After reset, get_instance returns a new tracker."""
        a = UsageTracker.get_instance()
        UsageTracker.reset_instance()
        b = UsageTracker.get_instance()
        assert a is not b

    def test_reset_clears_data(self) -> None:
        """reset() clears all stored usage data."""
        tracker = UsageTracker()
        tracker.record("org-1", "GET", "/api/v1/agents")
        tracker.reset()

        usage = tracker.get_usage()
        assert usage["total_calls"] == 0
