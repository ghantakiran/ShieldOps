"""Tests for audit log API endpoints.

Tests cover:
- GET /audit-logs (list, filter, auth, unavailable DB)
"""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.routes import audit


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(audit.router, prefix="/api/v1")
    return app


def _make_entry(
    entry_id: str = "aud-abc123",
    agent_type: str = "remediation",
    action: str = "restart_service",
    environment: str = "production",
    risk_level: str = "medium",
    outcome: str = "success",
    actor: str = "agent:remediation-01",
) -> dict[str, Any]:
    return {
        "id": entry_id,
        "timestamp": "2026-02-19T12:00:00+00:00",
        "agent_type": agent_type,
        "action": action,
        "target_resource": "web-api-pod-7f8b",
        "environment": environment,
        "risk_level": risk_level,
        "policy_evaluation": "allowed",
        "approval_status": None,
        "outcome": outcome,
        "reasoning": "Service unresponsive for 5 min",
        "actor": actor,
    }


@pytest.fixture(autouse=True)
def _reset_module_repo():
    original = audit._repository
    audit._repository = None
    yield
    audit._repository = original


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.list_audit_logs = AsyncMock(
        return_value=[_make_entry(), _make_entry(entry_id="aud-def456")]
    )
    return repo


def _build_client_with_admin(
    app: FastAPI,
    mock_repo: AsyncMock | None = None,
) -> TestClient:
    """Wire dependency overrides for an admin user."""
    if mock_repo is not None:
        audit.set_repository(mock_repo)

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


# ==========================================================================
# GET /audit-logs — success
# ==========================================================================


class TestListAuditLogsSuccess:
    def test_list_audit_logs_success(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.get("/api/v1/audit-logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert len(data["items"]) == 2
        assert data["total"] == 2

        # Verify entry shape
        entry = data["items"][0]
        assert entry["id"] == "aud-abc123"
        assert entry["agent_type"] == "remediation"
        assert entry["outcome"] == "success"


# ==========================================================================
# GET /audit-logs?environment=staging — filter by environment
# ==========================================================================


class TestListAuditLogsFilterByEnvironment:
    def test_list_audit_logs_filter_by_environment(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.get("/api/v1/audit-logs?environment=staging")
        assert resp.status_code == 200

        # Verify environment was passed to the repository
        mock_repo.list_audit_logs.assert_called_once_with(environment="staging", limit=50, offset=0)


# ==========================================================================
# GET /audit-logs — requires admin role
# ==========================================================================


class TestListAuditLogsRequiresAdmin:
    def test_list_audit_logs_requires_admin(self) -> None:
        """Without an admin override the endpoint rejects the request."""
        app = _create_test_app()

        # Do NOT override require_role — no auth token means 401/403
        # Set a mock repo so the 503 path isn't hit
        repo = AsyncMock()
        repo.list_audit_logs = AsyncMock(return_value=[])
        audit.set_repository(repo)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/audit-logs")

        # Without a valid bearer token the request is rejected
        assert resp.status_code in (401, 403)
        # Confirm the repo was never called
        repo.list_audit_logs.assert_not_called()


# ==========================================================================
# GET /audit-logs — no DB returns 503
# ==========================================================================


class TestListAuditLogsNoDb:
    def test_list_audit_logs_no_db_returns_503(self) -> None:
        app = _create_test_app()

        # Wire admin auth but do NOT set any repository
        from shieldops.api.auth.dependencies import (
            get_current_user,
            require_role,
        )
        from shieldops.api.auth.models import (
            UserResponse,
            UserRole,
        )

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

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/audit-logs")
        assert resp.status_code == 503
        assert resp.json()["detail"] == "DB unavailable"
