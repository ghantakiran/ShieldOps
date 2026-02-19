"""Unit tests for the security headers middleware."""

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from shieldops.api.middleware.security_headers import (
    SECURITY_HEADERS,
    SecurityHeadersMiddleware,
)


@pytest.fixture()
def app_with_security_headers():
    """Create a minimal FastAPI app with the security headers middleware."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/api/v1/test")
    async def test_endpoint():
        return {"ok": True}

    @app.get("/api/v1/error")
    async def error_endpoint():
        return JSONResponse(status_code=500, content={"error": "internal"})

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/metrics")
    async def metrics():
        return "# metrics"

    @app.get("/ready")
    async def ready():
        return {"status": "ready"}

    return app


@pytest.fixture()
async def client(app_with_security_headers):
    transport = ASGITransport(app=app_with_security_headers)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestSecurityHeadersPresent:
    @pytest.mark.asyncio
    async def test_all_headers_present_on_normal_response(self, client):
        resp = await client.get("/api/v1/test")
        assert resp.status_code == 200

        for header, value in SECURITY_HEADERS.items():
            assert resp.headers.get(header) == value, f"Missing or wrong header: {header}"

    @pytest.mark.asyncio
    async def test_hsts_header(self, client):
        resp = await client.get("/api/v1/test")
        assert resp.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"

    @pytest.mark.asyncio
    async def test_csp_header(self, client):
        resp = await client.get("/api/v1/test")
        csp = resp.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp

    @pytest.mark.asyncio
    async def test_x_frame_options_deny(self, client):
        resp = await client.get("/api/v1/test")
        assert resp.headers["X-Frame-Options"] == "DENY"

    @pytest.mark.asyncio
    async def test_x_content_type_options_nosniff(self, client):
        resp = await client.get("/api/v1/test")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"

    @pytest.mark.asyncio
    async def test_permissions_policy(self, client):
        resp = await client.get("/api/v1/test")
        assert resp.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"


class TestSecurityHeadersOnErrors:
    @pytest.mark.asyncio
    async def test_headers_present_on_error_responses(self, client):
        resp = await client.get("/api/v1/error")
        assert resp.status_code == 500

        for header in SECURITY_HEADERS:
            assert header in resp.headers, f"Missing header on error response: {header}"


class TestExemptPaths:
    @pytest.mark.asyncio
    async def test_health_endpoint_skipped(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert "Strict-Transport-Security" not in resp.headers

    @pytest.mark.asyncio
    async def test_metrics_endpoint_skipped(self, client):
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert "Content-Security-Policy" not in resp.headers

    @pytest.mark.asyncio
    async def test_ready_endpoint_skipped(self, client):
        resp = await client.get("/ready")
        assert resp.status_code == 200
        assert "X-Frame-Options" not in resp.headers
