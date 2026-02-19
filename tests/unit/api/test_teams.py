"""Tests for team management API endpoints.

Tests cover all 5 endpoints:
- POST /teams (create)
- GET /teams (list)
- GET /teams/{team_id}
- POST /teams/{team_id}/members (add)
- DELETE /teams/{team_id}/members/{user_id} (remove)
"""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.routes import teams


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(teams.router, prefix="/api/v1")
    return app


def _make_team(
    team_id: str = "team-1",
    name: str = "Platform",
) -> dict[str, Any]:
    return {
        "id": team_id,
        "name": name,
        "description": "Platform team",
        "slack_channel": "#platform",
        "pagerduty_service_id": "PD123",
        "email": "platform@example.com",
    }


@pytest.fixture(autouse=True)
def _reset_module_repo():
    original = teams._repository
    teams._repository = None
    yield
    teams._repository = original


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.create_team = AsyncMock(return_value=_make_team())
    repo.list_teams = AsyncMock(return_value=[_make_team()])
    repo.get_team = AsyncMock(return_value=_make_team())
    repo.list_team_members = AsyncMock(return_value=[])
    repo.list_vulnerabilities = AsyncMock(return_value=[])
    repo.add_team_member = AsyncMock(return_value="member-1")
    repo.remove_team_member = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def client(mock_repo: AsyncMock) -> TestClient:
    app = _create_test_app()
    teams.set_repository(mock_repo)

    from shieldops.api.auth.dependencies import get_current_user, require_role
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
    for roles in [("admin",), ("admin", "operator")]:
        dep = require_role(*roles)
        app.dependency_overrides[dep] = _mock_user

    return TestClient(app, raise_server_exceptions=False)


# ============================================================================
# POST /teams
# ============================================================================


class TestCreateTeam:
    def test_create_team_success(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/teams",
            json={
                "name": "Platform",
                "description": "Platform team",
                "slack_channel": "#platform",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Platform"

    def test_create_team_minimal(self, client: TestClient) -> None:
        resp = client.post("/api/v1/teams", json={"name": "Security"})
        assert resp.status_code == 200

    def test_503_when_no_repo(self) -> None:
        app = _create_test_app()
        # Do not set repository
        from shieldops.api.auth.dependencies import get_current_user, require_role
        from shieldops.api.auth.models import UserResponse, UserRole

        async def _mock_user() -> UserResponse:
            return UserResponse(
                id="u1",
                email="",
                name="",
                role=UserRole.ADMIN,
                is_active=True,
            )

        app.dependency_overrides[get_current_user] = _mock_user
        for roles in [("admin",)]:
            dep = require_role(*roles)
            app.dependency_overrides[dep] = _mock_user

        c = TestClient(app, raise_server_exceptions=False)
        resp = c.post("/api/v1/teams", json={"name": "Test"})
        assert resp.status_code == 503


# ============================================================================
# GET /teams
# ============================================================================


class TestListTeams:
    def test_list_teams(self, client: TestClient) -> None:
        resp = client.get("/api/v1/teams")
        assert resp.status_code == 200
        data = resp.json()
        assert "teams" in data
        assert data["total"] == 1

    def test_empty_list(self, client: TestClient, mock_repo: AsyncMock) -> None:
        mock_repo.list_teams.return_value = []
        resp = client.get("/api/v1/teams")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ============================================================================
# GET /teams/{team_id}
# ============================================================================


class TestGetTeam:
    def test_returns_team_with_members(self, client: TestClient) -> None:
        resp = client.get("/api/v1/teams/team-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "team-1"
        assert "members" in data
        assert "vulnerability_count" in data

    def test_404_when_not_found(self, client: TestClient, mock_repo: AsyncMock) -> None:
        mock_repo.get_team.return_value = None
        resp = client.get("/api/v1/teams/nonexistent")
        assert resp.status_code == 404


# ============================================================================
# POST /teams/{team_id}/members
# ============================================================================


class TestAddMember:
    def test_add_member_success(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/teams/team-1/members",
            json={"user_id": "user-2", "role": "member"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["team_id"] == "team-1"
        assert data["user_id"] == "user-2"
        assert data["role"] == "member"

    def test_404_team_not_found(self, client: TestClient, mock_repo: AsyncMock) -> None:
        mock_repo.get_team.return_value = None
        resp = client.post(
            "/api/v1/teams/nonexistent/members",
            json={"user_id": "user-2"},
        )
        assert resp.status_code == 404


# ============================================================================
# DELETE /teams/{team_id}/members/{user_id}
# ============================================================================


class TestRemoveMember:
    def test_remove_member_success(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/teams/team-1/members/user-2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["removed"] is True
        assert data["team_id"] == "team-1"
        assert data["user_id"] == "user-2"

    def test_404_member_not_found(self, client: TestClient, mock_repo: AsyncMock) -> None:
        mock_repo.remove_team_member.return_value = False
        resp = client.delete("/api/v1/teams/team-1/members/nonexistent")
        assert resp.status_code == 404
