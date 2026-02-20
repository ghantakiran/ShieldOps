"""Tests for playbook CRUD API endpoints.

Tests cover:
- POST /playbooks/custom (create with valid/invalid YAML)
- GET /playbooks/custom (list custom + builtin)
- GET /playbooks/custom/{id} (get by ID)
- PUT /playbooks/custom/{id} (update)
- DELETE /playbooks/custom/{id} (soft delete)
- POST /playbooks/custom/{id}/validate (validate)
- POST /playbooks/validate (validate raw content)
- POST /playbooks/custom/{id}/dry-run (preview)
- Required fields validation
- Dangerous action rejection
- Authentication required
- Builtin playbook protection
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.routes import playbook_crud

# ── Valid / Invalid YAML fixtures ────────────────────────────

VALID_YAML = """name: test-playbook
description: "A test playbook"
trigger:
  alert_type: "HighCPU"
  severity:
    - critical
steps:
  - action: check_status
    target: web-server
    params:
      timeout: 30
  - action: restart_service
    target: web-server
    params:
      grace_period: 10
"""

INVALID_YAML_SYNTAX = """
name: broken
description: [unterminated
"""

MISSING_FIELDS_YAML = """name: incomplete
description: "Missing trigger and steps"
"""

DANGEROUS_ACTION_YAML = """name: dangerous
description: "Has dangerous actions"
trigger:
  alert_type: "Test"
steps:
  - action: drop_database
    target: production-db
    params:
      confirm: true
"""


def _make_playbook_dict(
    playbook_id: str = "pb-test123",
    name: str = "test-playbook",
    content: str = VALID_YAML,
    is_active: bool = True,
) -> dict[str, Any]:
    return {
        "id": playbook_id,
        "name": name,
        "description": "A test playbook",
        "content": content,
        "tags": ["test", "cpu"],
        "is_active": is_active,
        "created_by": "admin-1",
        "created_at": "2026-02-19T12:00:00+00:00",
        "updated_at": "2026-02-19T12:00:00+00:00",
    }


# ── Test app and client helpers ──────────────────────────────


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(playbook_crud.router, prefix="/api/v1")
    return app


@pytest.fixture(autouse=True)
def _reset_module_repo():
    original = playbook_crud._repository
    playbook_crud._repository = None
    yield
    playbook_crud._repository = original


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.create_playbook = AsyncMock(return_value=_make_playbook_dict())
    repo.get_playbook = AsyncMock(return_value=_make_playbook_dict())
    repo.list_playbooks = AsyncMock(
        return_value=[
            _make_playbook_dict(),
            _make_playbook_dict(
                playbook_id="pb-second",
                name="second-playbook",
            ),
        ]
    )
    repo.update_playbook = AsyncMock(return_value=_make_playbook_dict(name="updated-playbook"))
    repo.delete_playbook = AsyncMock(return_value=True)
    return repo


def _build_client_with_admin(
    app: FastAPI,
    mock_repo: AsyncMock | None = None,
) -> TestClient:
    """Wire dependency overrides for an admin user."""
    if mock_repo is not None:
        playbook_crud.set_repository(mock_repo)

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

    # Override all role-protected deps
    for roles in [
        (UserRole.ADMIN, UserRole.OPERATOR),
    ]:
        dep = require_role(*roles)
        app.dependency_overrides[dep] = _mock_user

    return TestClient(app, raise_server_exceptions=False)


def _build_client_no_auth(
    app: FastAPI,
) -> TestClient:
    """Build a client without any auth overrides."""
    return TestClient(app, raise_server_exceptions=False)


# =================================================================
# 1. POST /playbooks/custom — create with valid YAML
# =================================================================


class TestCreatePlaybookValid:
    def test_create_playbook_valid_yaml(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.post(
            "/api/v1/playbooks/custom",
            json={
                "name": "test-playbook",
                "description": "A test playbook",
                "content": VALID_YAML,
                "tags": ["test"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "pb-test123"
        assert data["name"] == "test-playbook"
        assert data["source"] == "custom"
        assert data["is_valid"] is True

        mock_repo.create_playbook.assert_called_once()


# =================================================================
# 2. POST /playbooks/custom — create with invalid YAML (400)
# =================================================================


class TestCreatePlaybookInvalidYaml:
    def test_create_playbook_invalid_yaml(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.post(
            "/api/v1/playbooks/custom",
            json={
                "name": "bad",
                "description": "Bad YAML",
                "content": INVALID_YAML_SYNTAX,
                "tags": [],
            },
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "errors" in data["detail"]
        mock_repo.create_playbook.assert_not_called()


# =================================================================
# 3. GET /playbooks/custom — list playbooks
# =================================================================


class TestListPlaybooks:
    @patch.object(
        playbook_crud,
        "_load_builtin_playbooks",
        return_value=[
            {
                "id": "builtin-pod-crash-loop",
                "name": "pod-crash-loop",
                "description": "Pod crash loop",
                "content": "name: pod-crash-loop",
                "tags": [],
                "source": "builtin",
                "is_valid": True,
                "created_at": None,
                "updated_at": None,
            }
        ],
    )
    def test_list_playbooks_custom_and_builtin(
        self,
        _mock_builtin: Any,
        mock_repo: AsyncMock,
    ) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.get("/api/v1/playbooks/custom?include_builtin=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["custom_count"] == 2
        assert data["builtin_count"] == 1
        assert data["total"] == 3


# =================================================================
# 4. GET /playbooks/custom/{id} — get by ID
# =================================================================


class TestGetPlaybook:
    def test_get_playbook_by_id(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.get("/api/v1/playbooks/custom/pb-test123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "pb-test123"
        assert data["source"] == "custom"

    def test_get_playbook_not_found(self, mock_repo: AsyncMock) -> None:
        mock_repo.get_playbook = AsyncMock(return_value=None)
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.get("/api/v1/playbooks/custom/pb-nonexistent")
        assert resp.status_code == 404


# =================================================================
# 5. PUT /playbooks/custom/{id} — update playbook
# =================================================================


class TestUpdatePlaybook:
    def test_update_playbook(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.put(
            "/api/v1/playbooks/custom/pb-test123",
            json={
                "name": "updated-playbook",
                "content": VALID_YAML,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "updated-playbook"
        assert data["source"] == "custom"

    def test_update_playbook_invalid_yaml(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.put(
            "/api/v1/playbooks/custom/pb-test123",
            json={"content": INVALID_YAML_SYNTAX},
        )
        assert resp.status_code == 400
        mock_repo.update_playbook.assert_not_called()


# =================================================================
# 6. DELETE /playbooks/custom/{id} — soft delete
# =================================================================


class TestDeletePlaybook:
    def test_delete_playbook(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.delete("/api/v1/playbooks/custom/pb-test123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
        assert data["playbook_id"] == "pb-test123"
        mock_repo.delete_playbook.assert_called_once_with("pb-test123")

    def test_delete_playbook_not_found(self, mock_repo: AsyncMock) -> None:
        mock_repo.delete_playbook = AsyncMock(return_value=False)
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.delete("/api/v1/playbooks/custom/pb-none")
        assert resp.status_code == 404


# =================================================================
# 7. POST /playbooks/custom/{id}/validate — validate endpoint
# =================================================================


class TestValidatePlaybook:
    def test_validate_valid_playbook(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.post("/api/v1/playbooks/custom/pb-test123/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is True
        assert data["errors"] == []

    def test_validate_invalid_playbook(self, mock_repo: AsyncMock) -> None:
        mock_repo.get_playbook = AsyncMock(
            return_value=_make_playbook_dict(content=MISSING_FIELDS_YAML)
        )
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.post("/api/v1/playbooks/custom/pb-test123/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is False
        assert len(data["errors"]) > 0


# =================================================================
# 8. POST /playbooks/validate — validate raw content
# =================================================================


class TestValidateRawContent:
    def test_validate_raw_valid(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.post(
            "/api/v1/playbooks/validate",
            json={
                "name": "test",
                "description": "test",
                "content": VALID_YAML,
                "tags": [],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is True

    def test_validate_raw_invalid(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.post(
            "/api/v1/playbooks/validate",
            json={
                "name": "test",
                "description": "test",
                "content": INVALID_YAML_SYNTAX,
                "tags": [],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is False


# =================================================================
# 9. Required fields validation
# =================================================================


class TestRequiredFieldsValidation:
    def test_missing_required_yaml_fields(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.post(
            "/api/v1/playbooks/custom",
            json={
                "name": "incomplete",
                "description": "Missing fields",
                "content": MISSING_FIELDS_YAML,
                "tags": [],
            },
        )
        assert resp.status_code == 400
        data = resp.json()
        errors = data["detail"]["errors"]
        # Should flag missing 'trigger' and 'steps'
        error_text = " ".join(errors)
        assert "trigger" in error_text
        assert "steps" in error_text


# =================================================================
# 10. Dangerous action rejection
# =================================================================


class TestDangerousActionRejection:
    def test_dangerous_action_rejected(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.post(
            "/api/v1/playbooks/custom",
            json={
                "name": "dangerous",
                "description": "Has bad actions",
                "content": DANGEROUS_ACTION_YAML,
                "tags": [],
            },
        )
        assert resp.status_code == 400
        data = resp.json()
        errors = data["detail"]["errors"]
        error_text = " ".join(errors)
        assert "drop_database" in error_text
        assert "prohibited" in error_text


# =================================================================
# 11. Authentication required
# =================================================================


class TestAuthenticationRequired:
    def test_create_requires_auth(self) -> None:
        app = _create_test_app()
        client = _build_client_no_auth(app)

        resp = client.post(
            "/api/v1/playbooks/custom",
            json={
                "name": "test",
                "description": "test",
                "content": VALID_YAML,
                "tags": [],
            },
        )
        assert resp.status_code in (401, 403)

    def test_delete_requires_auth(self) -> None:
        app = _create_test_app()
        client = _build_client_no_auth(app)

        resp = client.delete("/api/v1/playbooks/custom/pb-test123")
        assert resp.status_code in (401, 403)


# =================================================================
# 12. Builtin playbook protection
# =================================================================


class TestBuiltinProtection:
    def test_cannot_delete_builtin(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.delete("/api/v1/playbooks/custom/builtin-pod-crash-loop")
        assert resp.status_code == 400
        assert "built-in" in resp.json()["detail"]

    def test_cannot_update_builtin(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.put(
            "/api/v1/playbooks/custom/builtin-pod-crash-loop",
            json={"name": "hacked"},
        )
        assert resp.status_code == 400
        assert "built-in" in resp.json()["detail"]


# =================================================================
# 13. DB unavailable returns 503
# =================================================================


class TestDbUnavailable:
    def test_create_returns_503_without_db(
        self,
    ) -> None:
        app = _create_test_app()

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
        dep = require_role(UserRole.ADMIN, UserRole.OPERATOR)
        app.dependency_overrides[dep] = _mock_user

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/playbooks/custom",
            json={
                "name": "test",
                "description": "test",
                "content": VALID_YAML,
                "tags": [],
            },
        )
        assert resp.status_code == 503
        assert resp.json()["detail"] == "DB unavailable"


# =================================================================
# 14. Dry-run endpoint
# =================================================================


class TestDryRun:
    def test_dry_run_returns_steps(self, mock_repo: AsyncMock) -> None:
        app = _create_test_app()
        client = _build_client_with_admin(app, mock_repo)

        resp = client.post("/api/v1/playbooks/custom/pb-test123/dry-run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["playbook_name"] == "test-playbook"
        assert data["total_steps"] == 2
        assert len(data["steps"]) == 2
        assert data["steps"][0]["action"] == "check_status"
        assert data["steps"][1]["action"] == "restart_service"
