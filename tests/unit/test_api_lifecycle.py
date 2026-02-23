"""Tests for shieldops.api.versioning.lifecycle – APILifecycleManager."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from shieldops.api.versioning.lifecycle import (
    APILifecycleManager,
    DeprecationStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _future_iso(days: int = 30) -> str:
    """Return an ISO-8601 date string *days* from now."""
    return (datetime.now(tz=UTC) + timedelta(days=days)).isoformat()


def _past_iso(days: int = 10) -> str:
    """Return an ISO-8601 date string *days* ago."""
    return (datetime.now(tz=UTC) - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_endpoint(self):
        mgr = APILifecycleManager()
        ep = mgr.register_endpoint("/api/v1/users", "GET", "v1")
        assert ep.path == "/api/v1/users"
        assert ep.method == "GET"
        assert ep.version == "v1"
        assert ep.status == DeprecationStatus.ACTIVE

    def test_register_normalizes_method_to_upper(self):
        mgr = APILifecycleManager()
        ep = mgr.register_endpoint("/api/v1/items", "post")
        assert ep.method == "POST"

    def test_get_registered_endpoint(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/users", "GET")
        ep = mgr.get_endpoint("/api/v1/users", "GET")
        assert ep is not None
        assert ep.path == "/api/v1/users"

    def test_get_unregistered_endpoint_returns_none(self):
        mgr = APILifecycleManager()
        assert mgr.get_endpoint("/unknown", "GET") is None

    def test_same_path_different_methods(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/items", "GET")
        mgr.register_endpoint("/api/v1/items", "POST")
        assert mgr.get_endpoint("/api/v1/items", "GET") is not None
        assert mgr.get_endpoint("/api/v1/items", "POST") is not None


# ---------------------------------------------------------------------------
# Deprecation
# ---------------------------------------------------------------------------


class TestDeprecation:
    def test_deprecate_sets_status(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/old", "GET")
        ep = mgr.deprecate("/api/v1/old", "GET", sunset_date=_future_iso(90))
        assert ep is not None
        assert ep.status == DeprecationStatus.DEPRECATED
        assert ep.deprecated_at is not None

    def test_deprecate_sets_sunset_date(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/old", "GET")
        sunset = _future_iso(60)
        ep = mgr.deprecate("/api/v1/old", "GET", sunset_date=sunset)
        assert ep.sunset_date == sunset

    def test_deprecate_sets_replacement_path(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/old", "GET")
        ep = mgr.deprecate("/api/v1/old", "GET", replacement_path="/api/v2/new")
        assert ep.replacement_path == "/api/v2/new"

    def test_deprecate_sets_migration_guide(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/old", "GET")
        ep = mgr.deprecate("/api/v1/old", "GET", migration_guide="Use v2 endpoint.")
        assert ep.migration_guide == "Use v2 endpoint."

    def test_auto_register_on_deprecate_if_not_known(self):
        mgr = APILifecycleManager()
        # Do NOT register first
        ep = mgr.deprecate("/api/v1/surprise", "POST")
        assert ep is not None
        assert ep.status == DeprecationStatus.DEPRECATED
        # Should now be in the registry
        assert mgr.get_endpoint("/api/v1/surprise", "POST") is not None


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


class TestLifecycleTransitions:
    def test_sunset_sets_status(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/ep", "GET")
        ep = mgr.sunset("/api/v1/ep", "GET")
        assert ep is not None
        assert ep.status == DeprecationStatus.SUNSET

    def test_retire_sets_status(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/ep", "DELETE")
        ep = mgr.retire("/api/v1/ep", "DELETE")
        assert ep is not None
        assert ep.status == DeprecationStatus.RETIRED

    def test_activate_restores_active(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/ep", "GET")
        mgr.deprecate("/api/v1/ep", "GET", sunset_date=_future_iso(30))
        ep = mgr.activate("/api/v1/ep", "GET")
        assert ep is not None
        assert ep.status == DeprecationStatus.ACTIVE
        assert ep.deprecated_at is None
        assert ep.sunset_date is None

    def test_sunset_unknown_returns_none(self):
        mgr = APILifecycleManager()
        assert mgr.sunset("/nope", "GET") is None

    def test_retire_unknown_returns_none(self):
        mgr = APILifecycleManager()
        assert mgr.retire("/nope", "GET") is None

    def test_activate_unknown_returns_none(self):
        mgr = APILifecycleManager()
        assert mgr.activate("/nope", "GET") is None


# ---------------------------------------------------------------------------
# Deprecation headers (RFC 8594)
# ---------------------------------------------------------------------------


class TestDeprecationHeaders:
    def test_headers_include_deprecation(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/ep", "GET")
        mgr.deprecate("/api/v1/ep", "GET")
        headers = mgr.get_deprecation_headers("/api/v1/ep", "GET")
        assert "Deprecation" in headers

    def test_headers_include_sunset(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/ep", "GET")
        mgr.deprecate("/api/v1/ep", "GET", sunset_date=_future_iso(30))
        headers = mgr.get_deprecation_headers("/api/v1/ep", "GET")
        assert "Sunset" in headers
        assert "GMT" in headers["Sunset"]

    def test_headers_include_link_for_replacement(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/ep", "GET")
        mgr.deprecate("/api/v1/ep", "GET", replacement_path="/api/v2/ep")
        headers = mgr.get_deprecation_headers("/api/v1/ep", "GET")
        assert "Link" in headers
        assert "/api/v2/ep" in headers["Link"]
        assert 'rel="successor-version"' in headers["Link"]

    def test_active_endpoint_returns_no_headers(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/ep", "GET")
        headers = mgr.get_deprecation_headers("/api/v1/ep", "GET")
        assert headers == {}

    def test_headers_disabled_returns_empty_dict(self):
        mgr = APILifecycleManager(deprecation_header_enabled=False)
        mgr.register_endpoint("/api/v1/ep", "GET")
        mgr.deprecate("/api/v1/ep", "GET")
        headers = mgr.get_deprecation_headers("/api/v1/ep", "GET")
        assert headers == {}

    def test_unknown_endpoint_returns_no_headers(self):
        mgr = APILifecycleManager()
        headers = mgr.get_deprecation_headers("/nope", "GET")
        assert headers == {}

    def test_deprecation_header_is_http_date_format(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/ep", "GET")
        mgr.deprecate("/api/v1/ep", "GET")
        headers = mgr.get_deprecation_headers("/api/v1/ep", "GET")
        # Should look like "Thu, 01 Jan 2026 00:00:00 GMT"
        dep_val = headers["Deprecation"]
        assert "GMT" in dep_val

    def test_sunset_header_for_sunset_status(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/ep", "GET")
        mgr.deprecate("/api/v1/ep", "GET", sunset_date=_future_iso(10))
        mgr.sunset("/api/v1/ep", "GET")
        headers = mgr.get_deprecation_headers("/api/v1/ep", "GET")
        assert "Deprecation" in headers
        assert "Sunset" in headers


# ---------------------------------------------------------------------------
# Queries: get_deprecated, get_sunset_soon
# ---------------------------------------------------------------------------


class TestQueries:
    def test_get_deprecated_list(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/a", "GET")
        mgr.register_endpoint("/b", "GET")
        mgr.deprecate("/a", "GET")
        deprecated = mgr.get_deprecated()
        assert len(deprecated) == 1
        assert deprecated[0].path == "/a"

    def test_get_deprecated_includes_sunset(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/a", "GET")
        mgr.deprecate("/a", "GET")
        mgr.sunset("/a", "GET")
        deprecated = mgr.get_deprecated()
        assert len(deprecated) == 1

    def test_get_deprecated_excludes_active_and_retired(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/active", "GET")
        mgr.register_endpoint("/retired", "GET")
        mgr.retire("/retired", "GET")
        deprecated = mgr.get_deprecated()
        assert len(deprecated) == 0

    def test_get_sunset_soon_within_days(self):
        mgr = APILifecycleManager(sunset_warning_days=60)
        mgr.register_endpoint("/a", "GET")
        mgr.deprecate("/a", "GET", sunset_date=_future_iso(10))
        mgr.register_endpoint("/b", "GET")
        mgr.deprecate("/b", "GET", sunset_date=_future_iso(90))
        soon = mgr.get_sunset_soon(within_days=30)
        paths = [e.path for e in soon]
        assert "/a" in paths
        assert "/b" not in paths

    def test_get_sunset_soon_uses_default_warning_days(self):
        mgr = APILifecycleManager(sunset_warning_days=15)
        mgr.register_endpoint("/x", "GET")
        mgr.deprecate("/x", "GET", sunset_date=_future_iso(10))
        soon = mgr.get_sunset_soon()
        assert len(soon) == 1

    def test_get_sunset_soon_past_date_included(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/old", "GET")
        mgr.deprecate("/old", "GET", sunset_date=_past_iso(5))
        soon = mgr.get_sunset_soon(within_days=1)
        assert len(soon) == 1


# ---------------------------------------------------------------------------
# Migration guide
# ---------------------------------------------------------------------------


class TestMigrationGuide:
    def test_get_migration_guide(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/ep", "GET")
        mgr.deprecate("/api/v1/ep", "GET", migration_guide="Switch to v2.")
        guide = mgr.get_migration_guide("/api/v1/ep", "GET")
        assert guide == "Switch to v2."

    def test_get_migration_guide_unknown_returns_empty(self):
        mgr = APILifecycleManager()
        assert mgr.get_migration_guide("/nope", "GET") == ""

    def test_get_migration_guide_no_guide_set(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/ep", "GET")
        assert mgr.get_migration_guide("/api/v1/ep", "GET") == ""


# ---------------------------------------------------------------------------
# list_endpoints with status filter
# ---------------------------------------------------------------------------


class TestListEndpoints:
    def test_list_all_endpoints(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/a", "GET")
        mgr.register_endpoint("/b", "POST")
        eps = mgr.list_endpoints()
        assert len(eps) == 2

    def test_list_endpoints_by_status(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/a", "GET")
        mgr.register_endpoint("/b", "GET")
        mgr.deprecate("/b", "GET")
        active = mgr.list_endpoints(status=DeprecationStatus.ACTIVE)
        deprecated = mgr.list_endpoints(status=DeprecationStatus.DEPRECATED)
        assert len(active) == 1
        assert len(deprecated) == 1
        assert active[0].path == "/a"
        assert deprecated[0].path == "/b"


# ---------------------------------------------------------------------------
# scan_routes (auto-discovery)
# ---------------------------------------------------------------------------


class TestScanRoutes:
    def test_scan_routes_discovers_routes(self):
        mgr = APILifecycleManager()
        route1 = SimpleNamespace(path="/api/v1/a", methods={"GET"})
        route2 = SimpleNamespace(path="/api/v1/b", methods={"GET", "POST"})
        mock_app = SimpleNamespace(routes=[route1, route2])
        count = mgr.scan_routes(mock_app)
        assert count == 3  # GET from /a, GET+POST from /b
        assert mgr.get_endpoint("/api/v1/a", "GET") is not None
        assert mgr.get_endpoint("/api/v1/b", "POST") is not None

    def test_scan_routes_skips_already_registered(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/api/v1/existing", "GET")
        route = SimpleNamespace(path="/api/v1/existing", methods={"GET"})
        mock_app = SimpleNamespace(routes=[route])
        count = mgr.scan_routes(mock_app)
        assert count == 0

    def test_scan_routes_ignores_routes_without_path(self):
        mgr = APILifecycleManager()
        route = SimpleNamespace(methods={"GET"})  # no path attribute
        mock_app = SimpleNamespace(routes=[route])
        count = mgr.scan_routes(mock_app)
        assert count == 0

    def test_scan_routes_ignores_routes_without_methods(self):
        mgr = APILifecycleManager()
        route = SimpleNamespace(path="/api/v1/x")  # no methods attribute
        mock_app = SimpleNamespace(routes=[route])
        count = mgr.scan_routes(mock_app)
        assert count == 0


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_by_status(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/a", "GET")
        mgr.register_endpoint("/b", "GET")
        mgr.deprecate("/b", "GET")
        stats = mgr.get_stats()
        assert stats["total_endpoints"] == 2
        assert stats["by_status"]["active"] == 1
        assert stats["by_status"]["deprecated"] == 1

    def test_stats_sunset_soon_count(self):
        mgr = APILifecycleManager(sunset_warning_days=60)
        mgr.register_endpoint("/ep", "GET")
        mgr.deprecate("/ep", "GET", sunset_date=_future_iso(10))
        stats = mgr.get_stats()
        assert stats["sunset_soon"] >= 1

    def test_stats_empty(self):
        mgr = APILifecycleManager()
        stats = mgr.get_stats()
        assert stats["total_endpoints"] == 0
        assert stats["by_status"] == {}
        assert stats["sunset_soon"] == 0


# ---------------------------------------------------------------------------
# Sunset date parsing edge cases
# ---------------------------------------------------------------------------


class TestSunsetDateParsing:
    def test_invalid_sunset_date_ignored_in_headers(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/ep", "GET")
        mgr.deprecate("/ep", "GET", sunset_date="not-a-date")
        headers = mgr.get_deprecation_headers("/ep", "GET")
        assert "Sunset" not in headers
        assert "Deprecation" in headers

    def test_sunset_date_without_timezone(self):
        mgr = APILifecycleManager()
        mgr.register_endpoint("/ep", "GET")
        naive_date = "2026-06-01T00:00:00"
        mgr.deprecate("/ep", "GET", sunset_date=naive_date)
        headers = mgr.get_deprecation_headers("/ep", "GET")
        assert "Sunset" in headers
        assert "GMT" in headers["Sunset"]
