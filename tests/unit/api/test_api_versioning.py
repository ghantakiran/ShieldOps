"""Tests for API versioning middleware, changelog route, and response models.

Covers:
- X-API-Version header presence and value
- X-Powered-By header
- /changelog endpoint shape
- Basic model validation for HealthResponse, InvestigationResponse,
  PaginatedResponse, and ErrorResponse
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.middleware.versioning import API_VERSION, APIVersionMiddleware
from shieldops.api.routes.changelog import CHANGELOG
from shieldops.api.routes.changelog import router as changelog_router
from shieldops.api.schemas.responses import (
    ErrorResponse,
    HealthResponse,
    InvestigationResponse,
    PaginatedResponse,
)


def _create_test_app() -> FastAPI:
    """Minimal app with versioning middleware and changelog route."""
    app = FastAPI()
    app.add_middleware(APIVersionMiddleware)
    app.include_router(changelog_router, prefix="/api/v1")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy", "version": "1.0.0"}

    return app


# ------------------------------------------------------------------
# Versioning middleware tests
# ------------------------------------------------------------------


class TestAPIVersionMiddleware:
    """Verify the APIVersionMiddleware adds expected headers."""

    def test_version_header_present(self) -> None:
        """X-API-Version header must appear on every response."""
        app = _create_test_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert "X-API-Version" in resp.headers

    def test_version_header_value(self) -> None:
        """X-API-Version header must match the API_VERSION constant."""
        app = _create_test_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.headers["X-API-Version"] == API_VERSION

    def test_powered_by_header(self) -> None:
        """X-Powered-By header must be set to 'ShieldOps'."""
        app = _create_test_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.headers["X-Powered-By"] == "ShieldOps"


# ------------------------------------------------------------------
# Changelog endpoint tests
# ------------------------------------------------------------------


class TestChangelogEndpoint:
    """Verify the /changelog endpoint returns structured data."""

    def test_changelog_returns_list(self) -> None:
        """Endpoint must return a JSON list."""
        app = _create_test_app()
        client = TestClient(app)
        resp = client.get("/api/v1/changelog")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_changelog_has_version_field(self) -> None:
        """Every changelog entry must contain a 'version' key."""
        app = _create_test_app()
        client = TestClient(app)
        resp = client.get("/api/v1/changelog")
        for entry in resp.json():
            assert "version" in entry
            assert "date" in entry
            assert "changes" in entry

    def test_changelog_constant_matches_endpoint(self) -> None:
        """The CHANGELOG constant must be the canonical source."""
        app = _create_test_app()
        client = TestClient(app)
        resp = client.get("/api/v1/changelog")
        assert resp.json() == CHANGELOG


# ------------------------------------------------------------------
# Response model smoke tests
# ------------------------------------------------------------------


class TestResponseModelSmokeTests:
    """Quick validation that core Pydantic response models work."""

    def test_health_response_model(self) -> None:
        """HealthResponse must accept and serialize correctly."""
        model = HealthResponse(
            status="healthy",
            version="1.0.0",
            services={"database": "ok", "redis": "ok"},
        )
        assert model.status == "healthy"
        assert model.services["database"] == "ok"

    def test_investigation_response_model_validation(self) -> None:
        """InvestigationResponse must enforce required fields."""
        model = InvestigationResponse(
            id="inv-001",
            alert_id="alert-42",
            alert_name="HighCPU",
            severity="critical",
            status="complete",
            confidence=0.92,
            environment="production",
            created_at=datetime.now(UTC),
        )
        assert model.id == "inv-001"
        assert model.confidence == 0.92
        assert model.environment == "production"

    def test_paginated_response_model(self) -> None:
        """PaginatedResponse[str] must work as a generic container."""
        model = PaginatedResponse[str](
            items=["a", "b", "c"],
            total=10,
            limit=3,
            offset=0,
        )
        assert len(model.items) == 3
        assert model.total == 10

    def test_error_response_model(self) -> None:
        """ErrorResponse must hold a detail string."""
        model = ErrorResponse(detail="Not found")
        assert model.detail == "Not found"
        dumped = model.model_dump()
        assert dumped == {"detail": "Not found"}
