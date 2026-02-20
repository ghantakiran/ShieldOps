"""Tests for organization management API endpoints.

Tests cover:
- GET /organizations (list, admin-only)
- POST /organizations (create, duplicate slug)
- GET /organizations/{org_id} (get, not-found)
- PUT /organizations/{org_id} (update, not-found)
- TenantMiddleware org_id injection
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.routes import organizations
from tests.unit.api._tenant_test_helper import (
    make_tenant_test_app as _make_tenant_test_app,
)


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(organizations.router, prefix="/api/v1")
    return app


def _make_org(
    org_id: str = "org-abc123",
    name: str = "Acme Corp",
    slug: str = "acme-corp",
    plan: str = "pro",
    is_active: bool = True,
) -> dict[str, Any]:
    return {
        "id": org_id,
        "name": name,
        "slug": slug,
        "plan": plan,
        "is_active": is_active,
        "settings": {},
        "rate_limit": 1000,
        "created_at": "2026-02-19T12:00:00+00:00",
        "updated_at": "2026-02-19T12:00:00+00:00",
    }


@pytest.fixture(autouse=True)
def _reset_module_repo() -> Any:
    original = organizations._repository
    organizations._repository = None
    yield
    organizations._repository = original


@pytest.fixture()
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.list_organizations = AsyncMock(return_value=[_make_org(), _make_org(org_id="org-def456")])
    repo.create_organization = AsyncMock(return_value=_make_org())
    repo.get_organization = AsyncMock(return_value=_make_org())
    repo.update_organization = AsyncMock(return_value=_make_org(plan="enterprise"))
    return repo


def _build_client_with_admin(
    app: FastAPI,
    mock_repo: AsyncMock | None = None,
) -> TestClient:
    """Wire dependency overrides for an admin user."""
    if mock_repo is not None:
        organizations.set_repository(mock_repo)

    from shieldops.api.auth.dependencies import (
        get_current_user,
        require_role,
    )
    from shieldops.api.auth.models import UserResponse, UserRole

    user = UserResponse(
        id="admin-1",
        email="admin@test.com",
        name="Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )

    async def _mock_user() -> UserResponse:
        return user

    app.dependency_overrides[get_current_user] = _mock_user
    for roles in [("admin",)]:
        dep = require_role(*roles)
        app.dependency_overrides[dep] = _mock_user

    return TestClient(app, raise_server_exceptions=False)


# ================================================================
# GET /organizations
# ================================================================


class TestListOrganizations:
    def test_list_organizations(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.get("/api/v1/organizations")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) == 2
        assert data["items"][0]["id"] == "org-abc123"
        mock_repo.list_organizations.assert_called_once_with(limit=50, offset=0)


# ================================================================
# POST /organizations
# ================================================================


class TestCreateOrganization:
    def test_create_organization(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.post(
            "/api/v1/organizations",
            json={
                "name": "Acme Corp",
                "slug": "acme-corp",
                "plan": "pro",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Acme Corp"
        assert data["slug"] == "acme-corp"
        mock_repo.create_organization.assert_called_once_with(
            name="Acme Corp", slug="acme-corp", plan="pro"
        )

    def test_create_organization_duplicate_slug(self, mock_repo: AsyncMock) -> None:
        mock_repo.create_organization = AsyncMock(
            side_effect=Exception("unique constraint violated")
        )
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.post(
            "/api/v1/organizations",
            json={
                "name": "Acme Corp",
                "slug": "acme-corp",
                "plan": "free",
            },
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]


# ================================================================
# GET /organizations/{org_id}
# ================================================================


class TestGetOrganization:
    def test_get_organization(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.get("/api/v1/organizations/org-abc123")
        assert resp.status_code == 200
        assert resp.json()["id"] == "org-abc123"
        mock_repo.get_organization.assert_called_once_with("org-abc123")

    def test_get_organization_not_found(self, mock_repo: AsyncMock) -> None:
        mock_repo.get_organization = AsyncMock(return_value=None)
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.get("/api/v1/organizations/org-nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ================================================================
# PUT /organizations/{org_id}
# ================================================================


class TestUpdateOrganization:
    def test_update_organization(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.put(
            "/api/v1/organizations/org-abc123",
            json={"plan": "enterprise"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "enterprise"
        mock_repo.update_organization.assert_called_once_with("org-abc123", plan="enterprise")

    def test_update_organization_not_found(self, mock_repo: AsyncMock) -> None:
        mock_repo.update_organization = AsyncMock(return_value=None)
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.put(
            "/api/v1/organizations/org-nonexistent",
            json={"plan": "enterprise"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ================================================================
# TenantMiddleware sets org_id
# ================================================================


class TestTenantMiddlewareSetsOrgId:
    def test_tenant_middleware_sets_org_id(self) -> None:
        """Middleware injects org_id from X-Organization-ID header."""
        from shieldops.api.middleware.tenant import (
            TenantMiddleware,
        )

        # Build app without `from __future__ import annotations`
        # in scope so FastAPI resolves Request properly.
        app = _make_tenant_test_app(TenantMiddleware)

        client = TestClient(app)
        resp = client.get(
            "/test-tenant",
            headers={"X-Organization-ID": "org-xyz789"},
        )
        assert resp.status_code == 200
        assert resp.json()["org_id"] == "org-xyz789"
