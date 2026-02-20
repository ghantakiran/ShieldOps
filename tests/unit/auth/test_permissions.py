"""Tests for fine-grained RBAC permissions module.

Covers:
- check_permission for admin, operator, viewer, and unknown roles
- require_permission dependency (allow and deny paths)
- Permission matrix API routes
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.api.auth.permissions import (
    DEFAULT_PERMISSIONS,
    check_permission,
    require_permission,
)
from shieldops.api.routes.permissions import router

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user(role: UserRole) -> UserResponse:
    return UserResponse(
        id="test-user-001",
        email="test@shieldops.io",
        name="Test User",
        role=role,
        is_active=True,
    )


def _create_test_app(user: UserResponse) -> FastAPI:
    """Create a minimal FastAPI app with the permissions router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def _mock_user() -> UserResponse:
        return user

    app.dependency_overrides[get_current_user] = _mock_user
    return app


@pytest.fixture
def admin_user() -> UserResponse:
    return _make_user(UserRole.ADMIN)


@pytest.fixture
def operator_user() -> UserResponse:
    return _make_user(UserRole.OPERATOR)


@pytest.fixture
def viewer_user() -> UserResponse:
    return _make_user(UserRole.VIEWER)


# ---------------------------------------------------------------------------
# check_permission unit tests
# ---------------------------------------------------------------------------


class TestCheckPermissionAdmin:
    """Admin role should have unrestricted access."""

    def test_admin_has_all_permissions(self) -> None:
        """Admin wildcard grants access to any resource+action."""
        assert check_permission("admin", "investigations", "read") is True
        assert check_permission("admin", "remediations", "create") is True
        assert check_permission("admin", "users", "delete") is True
        assert check_permission("admin", "anything", "whatever") is True


class TestCheckPermissionOperator:
    """Operator role should have scoped read/write access."""

    def test_operator_can_read_investigations(self) -> None:
        assert check_permission("operator", "investigations", "read") is True

    def test_operator_can_create_remediations(self) -> None:
        assert check_permission("operator", "remediations", "create") is True

    def test_operator_cannot_manage_users(self) -> None:
        """Operator has no 'users' resource in the permission matrix."""
        assert check_permission("operator", "users", "create") is False
        assert check_permission("operator", "users", "delete") is False

    def test_operator_cannot_delete_investigations(self) -> None:
        """Operator can read/create/update investigations but not delete."""
        assert (
            check_permission(
                "operator",
                "investigations",
                "delete",
            )
            is False
        )


class TestCheckPermissionViewer:
    """Viewer role should only have read access."""

    def test_viewer_can_only_read(self) -> None:
        for resource in DEFAULT_PERMISSIONS["viewer"]:
            assert check_permission("viewer", resource, "read") is True

    def test_viewer_cannot_create_investigations(self) -> None:
        assert (
            check_permission(
                "viewer",
                "investigations",
                "create",
            )
            is False
        )

    def test_viewer_cannot_trigger_playbooks(self) -> None:
        assert check_permission("viewer", "playbooks", "trigger") is False

    def test_viewer_cannot_update_vulnerabilities(self) -> None:
        assert (
            check_permission(
                "viewer",
                "vulnerabilities",
                "update",
            )
            is False
        )


class TestCheckPermissionEdgeCases:
    """Edge cases: unknown roles, wildcard matching."""

    def test_unknown_role_denied(self) -> None:
        """A role not in the matrix should be denied everything."""
        assert check_permission("intern", "investigations", "read") is False
        assert check_permission("", "agents", "read") is False

    def test_check_permission_wildcard(self) -> None:
        """Admin wildcard grants access to fabricated resources."""
        assert check_permission("admin", "nonexistent_resource", "x") is True

    def test_unknown_resource_for_known_role(self) -> None:
        """Operator asked about a resource not in their matrix."""
        assert check_permission("operator", "billing", "read") is False


# ---------------------------------------------------------------------------
# require_permission dependency tests
# ---------------------------------------------------------------------------


class TestRequirePermissionDependency:
    """Test the FastAPI dependency wrapper."""

    def test_require_permission_dependency_allows(
        self,
        operator_user: UserResponse,
    ) -> None:
        """Operator should be allowed to read investigations."""
        app = FastAPI()
        dep = require_permission("investigations", "read")

        @app.get("/test")
        async def _endpoint(
            user: Any = Depends(dep),  # noqa: B008
        ) -> dict[str, str]:
            return {"ok": "true"}

        async def _mock_user() -> UserResponse:
            return operator_user

        app.dependency_overrides[get_current_user] = _mock_user
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.json() == {"ok": "true"}

    def test_require_permission_dependency_denies(
        self,
        viewer_user: UserResponse,
    ) -> None:
        """Viewer should be denied creating investigations."""
        app = FastAPI()
        dep = require_permission("investigations", "create")

        @app.get("/test")
        async def _endpoint(
            user: Any = Depends(dep),  # noqa: B008
        ) -> dict[str, str]:
            return {"ok": "true"}

        async def _mock_user() -> UserResponse:
            return viewer_user

        app.dependency_overrides[get_current_user] = _mock_user
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 403
        assert "Permission denied" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Route tests: /permissions and /permissions/matrix
# ---------------------------------------------------------------------------


class TestPermissionsRoutes:
    """Integration-level tests for the permissions API routes."""

    def test_get_my_permissions_as_operator(
        self,
        operator_user: UserResponse,
    ) -> None:
        app = _create_test_app(operator_user)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/permissions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "operator"
        assert "investigations" in data["permissions"]

    def test_get_my_permissions_as_viewer(
        self,
        viewer_user: UserResponse,
    ) -> None:
        app = _create_test_app(viewer_user)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/permissions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "viewer"
        # Viewer should only have read actions
        for actions in data["permissions"].values():
            assert actions == ["read"]

    def test_permission_matrix_as_admin(
        self,
        admin_user: UserResponse,
    ) -> None:
        app = _create_test_app(admin_user)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/permissions/matrix")
        assert resp.status_code == 200
        matrix = resp.json()["matrix"]
        assert "admin" in matrix
        assert "operator" in matrix
        assert "viewer" in matrix

    def test_permission_matrix_denied_for_viewer(
        self,
        viewer_user: UserResponse,
    ) -> None:
        app = _create_test_app(viewer_user)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/permissions/matrix")
        assert resp.status_code == 403
