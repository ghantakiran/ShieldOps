"""API endpoint deprecation and versioning lifecycle per RFC 8594.

Manages endpoint lifecycle states (active → deprecated → sunset → retired),
generates RFC 8594 Deprecation/Sunset headers, and auto-discovers routes.
"""

from __future__ import annotations

import enum
import time
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class DeprecationStatus(enum.StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    RETIRED = "retired"


# ── Models ───────────────────────────────────────────────────────────


class APIEndpointVersion(BaseModel):
    """Lifecycle state of a single API endpoint."""

    path: str
    method: str = "GET"
    version: str = "v1"
    status: DeprecationStatus = DeprecationStatus.ACTIVE
    deprecated_at: float | None = None
    sunset_date: str | None = None  # ISO 8601 date
    replacement_path: str | None = None
    migration_guide: str = ""
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class DeprecationNotice(BaseModel):
    """Deprecation info returned as response headers."""

    deprecation: str = ""  # RFC 8594 Deprecation header value
    sunset: str = ""  # Sunset header (HTTP date format)
    link: str = ""  # Link header pointing to replacement


# ── Manager ──────────────────────────────────────────────────────────


class APILifecycleManager:
    """Manage API endpoint lifecycle states.

    Parameters
    ----------
    deprecation_header_enabled:
        When True, deprecation headers are included in responses.
    sunset_warning_days:
        Days before sunset date to start showing warnings.
    """

    def __init__(
        self,
        deprecation_header_enabled: bool = True,
        sunset_warning_days: int = 30,
    ) -> None:
        self._endpoints: dict[str, APIEndpointVersion] = {}
        self._header_enabled = deprecation_header_enabled
        self._sunset_warning_days = sunset_warning_days

    @staticmethod
    def _endpoint_key(path: str, method: str) -> str:
        return f"{method.upper()}:{path}"

    # ── Registration ─────────────────────────────────────────────

    def register_endpoint(
        self,
        path: str,
        method: str = "GET",
        version: str = "v1",
    ) -> APIEndpointVersion:
        key = self._endpoint_key(path, method)
        endpoint = APIEndpointVersion(path=path, method=method.upper(), version=version)
        self._endpoints[key] = endpoint
        return endpoint

    def get_endpoint(self, path: str, method: str = "GET") -> APIEndpointVersion | None:
        return self._endpoints.get(self._endpoint_key(path, method))

    def list_endpoints(self, status: DeprecationStatus | None = None) -> list[APIEndpointVersion]:
        eps = list(self._endpoints.values())
        if status:
            eps = [e for e in eps if e.status == status]
        return eps

    # ── Lifecycle transitions ────────────────────────────────────

    def deprecate(
        self,
        path: str,
        method: str = "GET",
        sunset_date: str | None = None,
        replacement_path: str | None = None,
        migration_guide: str = "",
    ) -> APIEndpointVersion | None:
        """Mark an endpoint as deprecated."""
        key = self._endpoint_key(path, method)
        endpoint = self._endpoints.get(key)
        if endpoint is None:
            # Auto-register if not known
            endpoint = self.register_endpoint(path, method)
        endpoint.status = DeprecationStatus.DEPRECATED
        endpoint.deprecated_at = time.time()
        endpoint.sunset_date = sunset_date
        endpoint.replacement_path = replacement_path
        endpoint.migration_guide = migration_guide
        endpoint.updated_at = time.time()
        logger.info(
            "endpoint_deprecated",
            path=path,
            method=method,
            sunset=sunset_date,
        )
        return endpoint

    def sunset(self, path: str, method: str = "GET") -> APIEndpointVersion | None:
        """Mark an endpoint as sunset (no longer available)."""
        key = self._endpoint_key(path, method)
        endpoint = self._endpoints.get(key)
        if endpoint is None:
            return None
        endpoint.status = DeprecationStatus.SUNSET
        endpoint.updated_at = time.time()
        return endpoint

    def retire(self, path: str, method: str = "GET") -> APIEndpointVersion | None:
        """Mark an endpoint as fully retired."""
        key = self._endpoint_key(path, method)
        endpoint = self._endpoints.get(key)
        if endpoint is None:
            return None
        endpoint.status = DeprecationStatus.RETIRED
        endpoint.updated_at = time.time()
        return endpoint

    def activate(self, path: str, method: str = "GET") -> APIEndpointVersion | None:
        """Reactivate a deprecated/sunset endpoint."""
        key = self._endpoint_key(path, method)
        endpoint = self._endpoints.get(key)
        if endpoint is None:
            return None
        endpoint.status = DeprecationStatus.ACTIVE
        endpoint.deprecated_at = None
        endpoint.sunset_date = None
        endpoint.updated_at = time.time()
        return endpoint

    # ── Headers ──────────────────────────────────────────────────

    def get_deprecation_headers(self, path: str, method: str = "GET") -> dict[str, str]:
        """Return RFC 8594 Deprecation and Sunset headers for an endpoint."""
        if not self._header_enabled:
            return {}
        key = self._endpoint_key(path, method)
        endpoint = self._endpoints.get(key)
        if endpoint is None or endpoint.status == DeprecationStatus.ACTIVE:
            return {}

        headers: dict[str, str] = {}

        if endpoint.status in (
            DeprecationStatus.DEPRECATED,
            DeprecationStatus.SUNSET,
        ):
            # RFC 8594: Deprecation header is a date or "true"
            if endpoint.deprecated_at:
                dt = datetime.fromtimestamp(endpoint.deprecated_at, tz=UTC)
                headers["Deprecation"] = dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
            else:
                headers["Deprecation"] = "true"

        if endpoint.sunset_date:
            try:
                dt = datetime.fromisoformat(endpoint.sunset_date)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                headers["Sunset"] = dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
            except (ValueError, TypeError):
                pass

        if endpoint.replacement_path:
            headers["Link"] = f'<{endpoint.replacement_path}>; rel="successor-version"'

        return headers

    # ── Queries ──────────────────────────────────────────────────

    def get_deprecated(self) -> list[APIEndpointVersion]:
        return [
            e
            for e in self._endpoints.values()
            if e.status in (DeprecationStatus.DEPRECATED, DeprecationStatus.SUNSET)
        ]

    def get_sunset_soon(self, within_days: int | None = None) -> list[APIEndpointVersion]:
        """Return endpoints sunsetting within N days."""
        days = within_days or self._sunset_warning_days
        cutoff = time.time() + days * 86400
        results: list[APIEndpointVersion] = []
        for ep in self._endpoints.values():
            if ep.sunset_date:
                try:
                    dt = datetime.fromisoformat(ep.sunset_date)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                    if dt.timestamp() <= cutoff:
                        results.append(ep)
                except (ValueError, TypeError):
                    pass
        return results

    def get_migration_guide(self, path: str, method: str = "GET") -> str:
        key = self._endpoint_key(path, method)
        endpoint = self._endpoints.get(key)
        if endpoint is None:
            return ""
        return endpoint.migration_guide

    # ── Auto-discovery ───────────────────────────────────────────

    def scan_routes(self, app: Any) -> int:
        """Auto-discover all FastAPI routes and register them."""
        count = 0
        for route in getattr(app, "routes", []):
            path = getattr(route, "path", "")
            methods: set[str] = getattr(route, "methods", set())
            if not path or not methods:
                continue
            for method in methods:
                key = self._endpoint_key(path, method)
                if key not in self._endpoints:
                    self.register_endpoint(path, method)
                    count += 1
        logger.info("api_routes_scanned", registered=count)
        return count

    # ── Stats ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        for ep in self._endpoints.values():
            by_status[ep.status.value] = by_status.get(ep.status.value, 0) + 1
        return {
            "total_endpoints": len(self._endpoints),
            "by_status": by_status,
            "sunset_soon": len(self.get_sunset_soon()),
        }
