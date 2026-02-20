"""Tests for TenantMiddleware.

Tests cover:
- Public paths skip org resolution
- X-Organization-ID header extraction
- No org_id passes None
- Middleware preserves existing state set by auth
- Non-public path without header sets None
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from shieldops.api.middleware.tenant import (
    _PUBLIC_PATHS,
    TenantMiddleware,
)


def _build_app_with_capture() -> tuple[FastAPI, dict[str, Any]]:
    """Build a minimal app that captures request.state."""
    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    captured: dict[str, Any] = {}

    @app.get("/health")
    async def health(request: Request) -> dict[str, str]:
        captured["org_id"] = getattr(request.state, "organization_id", "MISSING")
        return {"status": "ok"}

    @app.get("/api/v1/resource")
    async def resource(request: Request) -> dict[str, Any]:
        captured["org_id"] = getattr(request.state, "organization_id", "MISSING")
        return {"ok": True}

    return app, captured


class TestPublicPathSkipsOrg:
    def test_public_path_skips_org(self) -> None:
        """Public paths should set organization_id = None."""
        app, captured = _build_app_with_capture()
        client = TestClient(app)

        resp = client.get("/health")
        assert resp.status_code == 200
        assert captured["org_id"] is None

    def test_known_public_paths(self) -> None:
        """Validate the public paths set is non-empty."""
        assert "/health" in _PUBLIC_PATHS
        assert "/ready" in _PUBLIC_PATHS
        assert "/metrics" in _PUBLIC_PATHS


class TestHeaderOrgIdExtracted:
    def test_header_org_id_extracted(self) -> None:
        """X-Organization-ID header should populate state."""
        app, captured = _build_app_with_capture()
        client = TestClient(app)

        resp = client.get(
            "/api/v1/resource",
            headers={"X-Organization-ID": "org-tenant1"},
        )
        assert resp.status_code == 200
        assert captured["org_id"] == "org-tenant1"


class TestNoOrgIdPassesNone:
    def test_no_org_id_passes_none(self) -> None:
        """Without header or prior auth, org_id should be None."""
        app, captured = _build_app_with_capture()
        client = TestClient(app)

        resp = client.get("/api/v1/resource")
        assert resp.status_code == 200
        assert captured["org_id"] is None


class TestMiddlewarePreservesExistingState:
    def test_middleware_preserves_existing_state(self) -> None:
        """If auth already set organization_id, middleware keeps it."""
        from starlette.middleware.base import (
            BaseHTTPMiddleware,
            RequestResponseEndpoint,
        )
        from starlette.requests import Request as StarletteRequest
        from starlette.responses import Response

        class FakeAuthMiddleware(BaseHTTPMiddleware):
            """Simulates auth setting org_id on request.state."""

            async def dispatch(
                self,
                request: StarletteRequest,
                call_next: RequestResponseEndpoint,
            ) -> Response:
                request.state.organization_id = "org-from-jwt"
                return await call_next(request)

        app = FastAPI()
        # TenantMiddleware added first (LIFO: processes second)
        app.add_middleware(TenantMiddleware)
        # FakeAuthMiddleware added second (LIFO: processes first)
        app.add_middleware(FakeAuthMiddleware)

        captured: dict[str, Any] = {}

        @app.get("/api/v1/protected")
        async def protected(request: Request) -> dict[str, Any]:
            captured["org_id"] = getattr(request.state, "organization_id", "MISSING")
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/api/v1/protected")
        assert resp.status_code == 200
        # Auth middleware set it; tenant middleware should not overwrite
        assert captured["org_id"] == "org-from-jwt"


class TestNonPublicWithoutHeader:
    def test_non_public_without_header_sets_none(self) -> None:
        """Non-public endpoint with no header => org_id is None."""
        app, captured = _build_app_with_capture()
        client = TestClient(app)

        resp = client.get("/api/v1/resource")
        assert resp.status_code == 200
        assert captured["org_id"] is None
