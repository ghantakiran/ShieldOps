"""Tests for request middleware — request ID, logging, error handling."""

import pytest
from httpx import ASGITransport, AsyncClient

from shieldops.api.app import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


class TestRequestIDMiddleware:
    @pytest.mark.asyncio
    async def test_response_includes_request_id(self, client):
        response = await client.get("/health")
        assert "x-request-id" in response.headers

    @pytest.mark.asyncio
    async def test_propagates_incoming_request_id(self, client):
        custom_id = "my-custom-request-id"
        response = await client.get(
            "/health", headers={"X-Request-ID": custom_id}
        )
        assert response.headers["x-request-id"] == custom_id

    @pytest.mark.asyncio
    async def test_generates_request_id_when_absent(self, client):
        response = await client.get("/health")
        rid = response.headers.get("x-request-id")
        assert rid is not None
        assert len(rid) > 0


class TestRequestLoggingMiddleware:
    @pytest.mark.asyncio
    async def test_request_completes_with_logging(self, client):
        """Logging middleware should not interfere with normal responses."""
        response = await client.get("/health")
        assert response.status_code == 200


class TestErrorHandlerMiddleware:
    @pytest.mark.asyncio
    async def test_normal_request_not_affected(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
