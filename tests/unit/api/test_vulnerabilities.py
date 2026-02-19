"""Tests for vulnerability management API endpoints.

Tests cover all 9 endpoints:
- GET /vulnerabilities (list with filters)
- GET /vulnerabilities/stats
- GET /vulnerabilities/sla-breaches
- GET /vulnerabilities/{vuln_id}
- PUT /vulnerabilities/{vuln_id}/status
- POST /vulnerabilities/{vuln_id}/assign
- POST /vulnerabilities/{vuln_id}/comments
- GET /vulnerabilities/{vuln_id}/comments
- POST /vulnerabilities/{vuln_id}/accept-risk
"""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.routes import vulnerabilities

# Patch target and admin payload for auth bypass
_AUTH_PATCH = "shieldops.api.auth.dependencies.decode_token"
_ADMIN_PAYLOAD = {
    "sub": "user-1",
    "role": "admin",
    "email": "admin@test.com",
    "name": "Admin",
    "exp": 9999999999,
}
_AUTH_HEADER = {"Authorization": "Bearer fake-token"}


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with the vulnerabilities router."""
    app = FastAPI()
    app.include_router(vulnerabilities.router, prefix="/api/v1")
    return app


def _make_vuln(
    vuln_id: str = "vuln-001",
    status: str = "new",
    severity: str = "high",
) -> dict[str, Any]:
    return {
        "id": vuln_id,
        "status": status,
        "severity": severity,
        "cve_id": "CVE-2024-1234",
        "affected_resource": "nginx:1.25",
        "scanner_type": "cve",
        "title": "Test vulnerability",
    }


@pytest.fixture(autouse=True)
def _reset_module_repo():
    """Reset the module-level repository between tests."""
    original = vulnerabilities._repository
    vulnerabilities._repository = None
    yield
    vulnerabilities._repository = original


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.list_vulnerabilities = AsyncMock(return_value=[_make_vuln()])
    repo.count_vulnerabilities = AsyncMock(return_value=1)
    repo.get_vulnerability = AsyncMock(return_value=_make_vuln())
    repo.get_vulnerability_stats = AsyncMock(return_value={"total": 10})
    repo.update_vulnerability_status = AsyncMock(return_value=True)
    repo.assign_vulnerability = AsyncMock(return_value=True)
    repo.add_vulnerability_comment = AsyncMock(return_value="comment-id")
    repo.list_vulnerability_comments = AsyncMock(return_value=[])
    repo.create_risk_acceptance = AsyncMock(return_value="acceptance-id")
    return repo


@pytest.fixture
def client(mock_repo: AsyncMock) -> TestClient:
    """TestClient with auth bypassed via get_current_user override."""
    from shieldops.api.auth.dependencies import get_current_user
    from shieldops.api.auth.models import UserResponse, UserRole

    app = _create_test_app()
    vulnerabilities.set_repository(mock_repo)

    async def _mock_user() -> UserResponse:
        return UserResponse(
            id="user-1",
            email="admin@test.com",
            name="Admin",
            role=UserRole.ADMIN,
            is_active=True,
        )

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


# ============================================================================
# GET /vulnerabilities
# ============================================================================


class TestListVulnerabilities:
    def test_returns_200_with_list(self, client: TestClient, mock_repo: AsyncMock) -> None:
        resp = client.get("/api/v1/vulnerabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert "vulnerabilities" in data
        assert "total" in data
        assert data["total"] == 1

    def test_passes_query_filters(self, client: TestClient, mock_repo: AsyncMock) -> None:
        client.get("/api/v1/vulnerabilities?status=new&severity=high&limit=10")
        call_kwargs = mock_repo.list_vulnerabilities.call_args.kwargs
        assert call_kwargs["status"] == "new"
        assert call_kwargs["severity"] == "high"
        assert call_kwargs["limit"] == 10

    def test_503_when_no_repo(self) -> None:
        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole

        app = _create_test_app()
        # Do NOT set repository

        async def _mock_user_dep() -> UserResponse:
            return UserResponse(id="u1", email="", name="", role=UserRole.ADMIN, is_active=True)

        app.dependency_overrides[get_current_user] = _mock_user_dep
        c = TestClient(app, raise_server_exceptions=False)
        resp = c.get("/api/v1/vulnerabilities")
        assert resp.status_code == 503


# ============================================================================
# GET /vulnerabilities/stats
# ============================================================================


class TestGetVulnerabilityStats:
    def test_returns_stats(self, client: TestClient) -> None:
        resp = client.get("/api/v1/vulnerabilities/stats")
        assert resp.status_code == 200
        assert resp.json() == {"total": 10}


# ============================================================================
# GET /vulnerabilities/sla-breaches
# ============================================================================


class TestListSLABreaches:
    def test_returns_breached_vulns(self, client: TestClient, mock_repo: AsyncMock) -> None:
        mock_repo.list_vulnerabilities.return_value = [
            _make_vuln("vuln-breach", status="new"),
        ]
        resp = client.get("/api/v1/vulnerabilities/sla-breaches")
        assert resp.status_code == 200
        data = resp.json()
        assert "vulnerabilities" in data
        mock_repo.list_vulnerabilities.assert_called_with(sla_breached=True, limit=50)


# ============================================================================
# GET /vulnerabilities/{vuln_id}
# ============================================================================


class TestGetVulnerability:
    def test_returns_vuln_with_comments(self, client: TestClient, mock_repo: AsyncMock) -> None:
        resp = client.get("/api/v1/vulnerabilities/vuln-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "vuln-001"
        assert "comments" in data

    def test_404_when_not_found(self, client: TestClient, mock_repo: AsyncMock) -> None:
        mock_repo.get_vulnerability.return_value = None
        resp = client.get("/api/v1/vulnerabilities/nonexistent")
        assert resp.status_code == 404


# ============================================================================
# PUT /vulnerabilities/{vuln_id}/status
# ============================================================================


class TestUpdateVulnerabilityStatus:
    def test_valid_transition(self, client: TestClient, mock_repo: AsyncMock) -> None:
        mock_repo.get_vulnerability.return_value = _make_vuln(status="new")
        resp = client.put(
            "/api/v1/vulnerabilities/vuln-001/status",
            json={"status": "triaged", "reason": "Reviewed by security team"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "triaged"
        assert data["previous_status"] == "new"

    def test_invalid_status_400(self, client: TestClient) -> None:
        resp = client.put(
            "/api/v1/vulnerabilities/vuln-001/status",
            json={"status": "nonexistent"},
        )
        assert resp.status_code == 400

    def test_invalid_transition_400(self, client: TestClient, mock_repo: AsyncMock) -> None:
        mock_repo.get_vulnerability.return_value = _make_vuln(status="new")
        resp = client.put(
            "/api/v1/vulnerabilities/vuln-001/status",
            json={"status": "closed"},
        )
        assert resp.status_code == 400
        assert "Cannot transition" in resp.json()["detail"]

    def test_404_vuln_not_found(self, client: TestClient, mock_repo: AsyncMock) -> None:
        mock_repo.get_vulnerability.return_value = None
        resp = client.put(
            "/api/v1/vulnerabilities/vuln-001/status",
            json={"status": "triaged"},
        )
        assert resp.status_code == 404

    def test_500_update_failure(self, client: TestClient, mock_repo: AsyncMock) -> None:
        mock_repo.get_vulnerability.return_value = _make_vuln(status="new")
        mock_repo.update_vulnerability_status.return_value = False
        resp = client.put(
            "/api/v1/vulnerabilities/vuln-001/status",
            json={"status": "triaged"},
        )
        assert resp.status_code == 500

    def test_comment_logged_on_status_change(
        self, client: TestClient, mock_repo: AsyncMock
    ) -> None:
        mock_repo.get_vulnerability.return_value = _make_vuln(status="new")
        client.put(
            "/api/v1/vulnerabilities/vuln-001/status",
            json={"status": "triaged", "reason": "Reviewing"},
        )
        mock_repo.add_vulnerability_comment.assert_called_once()
        call_kwargs = mock_repo.add_vulnerability_comment.call_args.kwargs
        assert call_kwargs["comment_type"] == "status_change"
        assert "Reviewing" in call_kwargs["content"]


# ============================================================================
# POST /vulnerabilities/{vuln_id}/assign
# ============================================================================


class TestAssignVulnerability:
    def test_assign_team_and_user(self, client: TestClient, mock_repo: AsyncMock) -> None:
        resp = client.post(
            "/api/v1/vulnerabilities/vuln-001/assign",
            json={"team_id": "team-1", "user_id": "user-2"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assigned_team_id"] == "team-1"
        assert data["assigned_user_id"] == "user-2"

    def test_404_vuln_not_found(self, client: TestClient, mock_repo: AsyncMock) -> None:
        mock_repo.get_vulnerability.return_value = None
        resp = client.post(
            "/api/v1/vulnerabilities/vuln-001/assign",
            json={"team_id": "team-1"},
        )
        assert resp.status_code == 404

    def test_500_assign_failure(self, client: TestClient, mock_repo: AsyncMock) -> None:
        mock_repo.assign_vulnerability.return_value = False
        resp = client.post(
            "/api/v1/vulnerabilities/vuln-001/assign",
            json={"team_id": "team-1"},
        )
        assert resp.status_code == 500

    def test_comment_logged_on_assignment(self, client: TestClient, mock_repo: AsyncMock) -> None:
        client.post(
            "/api/v1/vulnerabilities/vuln-001/assign",
            json={"team_id": "team-1", "user_id": "user-2"},
        )
        mock_repo.add_vulnerability_comment.assert_called_once()
        call_kwargs = mock_repo.add_vulnerability_comment.call_args.kwargs
        assert call_kwargs["comment_type"] == "assignment"


# ============================================================================
# POST /vulnerabilities/{vuln_id}/comments
# ============================================================================


class TestAddComment:
    def test_add_comment(self, client: TestClient, mock_repo: AsyncMock) -> None:
        resp = client.post(
            "/api/v1/vulnerabilities/vuln-001/comments",
            json={"content": "This needs attention", "comment_type": "comment"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "comment-id"
        assert data["vulnerability_id"] == "vuln-001"

    def test_404_vuln_not_found(self, client: TestClient, mock_repo: AsyncMock) -> None:
        mock_repo.get_vulnerability.return_value = None
        resp = client.post(
            "/api/v1/vulnerabilities/vuln-001/comments",
            json={"content": "Test comment"},
        )
        assert resp.status_code == 404


# ============================================================================
# GET /vulnerabilities/{vuln_id}/comments
# ============================================================================


class TestListComments:
    def test_returns_comments(self, client: TestClient, mock_repo: AsyncMock) -> None:
        mock_repo.list_vulnerability_comments.return_value = [
            {"id": "c1", "content": "hello"},
        ]
        resp = client.get("/api/v1/vulnerabilities/vuln-001/comments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["comments"]) == 1


# ============================================================================
# POST /vulnerabilities/{vuln_id}/accept-risk
# ============================================================================


class TestAcceptRisk:
    def test_accept_risk_success(self, client: TestClient, mock_repo: AsyncMock) -> None:
        resp = client.post(
            "/api/v1/vulnerabilities/vuln-001/accept-risk",
            json={"reason": "Low impact; compensating controls in place"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "acceptance-id"
        assert data["status"] == "accepted_risk"

    def test_accept_risk_with_expiry(self, client: TestClient, mock_repo: AsyncMock) -> None:
        resp = client.post(
            "/api/v1/vulnerabilities/vuln-001/accept-risk",
            json={
                "reason": "Temporary acceptance",
                "expires_at": "2025-06-01T00:00:00+00:00",
            },
        )
        assert resp.status_code == 200
        call_kwargs = mock_repo.create_risk_acceptance.call_args.kwargs
        assert call_kwargs["expires_at"] is not None

    def test_accept_risk_invalid_expiry(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/vulnerabilities/vuln-001/accept-risk",
            json={"reason": "test", "expires_at": "not-a-date"},
        )
        assert resp.status_code == 400

    def test_accept_risk_404(self, client: TestClient, mock_repo: AsyncMock) -> None:
        mock_repo.get_vulnerability.return_value = None
        resp = client.post(
            "/api/v1/vulnerabilities/vuln-001/accept-risk",
            json={"reason": "test"},
        )
        assert resp.status_code == 404


# ============================================================================
# Transition map sanity checks
# ============================================================================


class TestTransitionMap:
    def test_valid_statuses_consistent(self) -> None:
        assert {
            "new",
            "triaged",
            "in_progress",
            "remediated",
            "verified",
            "closed",
            "accepted_risk",
        } == vulnerabilities.VALID_STATUSES

    def test_all_statuses_have_transitions(self) -> None:
        for status in vulnerabilities.VALID_STATUSES:
            assert status in vulnerabilities.VALID_TRANSITIONS
