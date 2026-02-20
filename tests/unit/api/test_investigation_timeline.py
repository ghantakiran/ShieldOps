"""Tests for investigation timeline API endpoint.

Tests cover:
- GET /investigations/{id}/timeline (mixed events, empty, ordering,
  404, event_type filter, auth, DB unavailable)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.routes import investigations


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(
        investigations.router,
        prefix="/api/v1",
    )
    return app


def _make_investigation(
    investigation_id: str = "inv-abc123",
) -> dict[str, Any]:
    return {
        "investigation_id": investigation_id,
        "alert_id": "alert-001",
        "alert_name": "HighCPU",
        "severity": "warning",
        "status": "completed",
        "confidence": 0.92,
        "hypotheses_count": 3,
        "hypotheses": [],
        "reasoning_chain": [],
        "alert_context": {},
        "log_findings": [],
        "metric_anomalies": [],
        "recommended_action": None,
        "duration_ms": 4500,
        "error": None,
        "created_at": "2026-02-19T10:00:00+00:00",
        "updated_at": "2026-02-19T10:01:00+00:00",
    }


def _make_timeline_events() -> list[dict[str, Any]]:
    """Return a mixed list of timeline events."""
    return [
        {
            "id": "inv-inv-abc123",
            "timestamp": "2026-02-19T10:00:00+00:00",
            "type": "investigation",
            "action": "investigation_completed",
            "actor": "agent:investigation",
            "severity": "warning",
            "details": {
                "alert_id": "alert-001",
                "alert_name": "HighCPU",
                "confidence": 0.92,
                "duration_ms": 4500,
                "error": None,
            },
        },
        {
            "id": "rem-rem-001",
            "timestamp": "2026-02-19T10:01:00+00:00",
            "type": "remediation",
            "action": "restart_service_completed",
            "actor": "agent:remediation",
            "severity": "medium",
            "details": {
                "remediation_id": "rem-001",
                "action_type": "restart_service",
                "target_resource": "web-api",
                "environment": "production",
                "validation_passed": True,
                "duration_ms": 2000,
                "error": None,
            },
        },
        {
            "id": "aud-aud-001",
            "timestamp": "2026-02-19T10:02:00+00:00",
            "type": "audit",
            "action": "restart_service",
            "actor": "agent:remediation-01",
            "severity": "medium",
            "details": {
                "audit_id": "aud-001",
                "agent_type": "remediation",
                "target_resource": "web-api",
                "environment": "production",
                "policy_evaluation": "allowed",
                "approval_status": None,
                "outcome": "success",
                "reasoning": "inv-abc123: service restart",
            },
        },
    ]


@pytest.fixture(autouse=True)
def _reset_module_repo():
    original = investigations._repository
    investigations._repository = None
    yield
    investigations._repository = original


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_investigation = AsyncMock(
        return_value=_make_investigation(),
    )
    repo.get_investigation_timeline = AsyncMock(
        return_value=_make_timeline_events(),
    )
    return repo


def _build_client_with_viewer(
    app: FastAPI,
    mock_repo: AsyncMock | None = None,
) -> TestClient:
    """Wire dependency overrides for a viewer user."""
    if mock_repo is not None:
        investigations.set_repository(mock_repo)

    from shieldops.api.auth.dependencies import (
        get_current_user,
    )
    from shieldops.api.auth.models import (
        UserResponse,
        UserRole,
    )

    user = UserResponse(
        id="viewer-1",
        email="viewer@test.com",
        name="Viewer",
        role=UserRole.VIEWER,
        is_active=True,
    )

    async def _mock_user() -> UserResponse:
        return user

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


# ================================================================
# Mixed event types
# ================================================================


class TestTimelineMixedEvents:
    def test_returns_mixed_event_types(
        self,
        mock_repo: AsyncMock,
    ) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get(
            "/api/v1/investigations/inv-abc123/timeline",
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["investigation_id"] == "inv-abc123"
        assert data["total"] == 3
        assert len(data["events"]) == 3

        event_types = {e["type"] for e in data["events"]}
        assert event_types == {
            "investigation",
            "remediation",
            "audit",
        }

    def test_event_shape(
        self,
        mock_repo: AsyncMock,
    ) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get(
            "/api/v1/investigations/inv-abc123/timeline",
        )
        event = resp.json()["events"][0]

        assert "id" in event
        assert "timestamp" in event
        assert "type" in event
        assert "action" in event
        assert "actor" in event
        assert "details" in event


# ================================================================
# Empty timeline
# ================================================================


class TestTimelineEmpty:
    def test_empty_timeline(
        self,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_investigation_timeline.return_value = []
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get(
            "/api/v1/investigations/inv-abc123/timeline",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == []
        assert data["total"] == 0


# ================================================================
# Chronological ordering
# ================================================================


class TestTimelineOrdering:
    def test_events_chronologically_ordered(
        self,
        mock_repo: AsyncMock,
    ) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get(
            "/api/v1/investigations/inv-abc123/timeline",
        )
        events = resp.json()["events"]
        timestamps = [e["timestamp"] for e in events]

        assert timestamps == sorted(timestamps)


# ================================================================
# Investigation not found (404)
# ================================================================


class TestTimelineNotFound:
    def test_returns_404_for_unknown_investigation(
        self,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_investigation.return_value = None
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get(
            "/api/v1/investigations/nonexistent/timeline",
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

        # Verify timeline was never queried
        mock_repo.get_investigation_timeline.assert_not_called()


# ================================================================
# Event type filtering
# ================================================================


class TestTimelineEventTypeFilter:
    def test_filter_by_remediation_type(
        self,
        mock_repo: AsyncMock,
    ) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get(
            "/api/v1/investigations/inv-abc123/timeline?event_type=remediation",
        )
        assert resp.status_code == 200
        data = resp.json()

        # Only remediation events should be returned
        assert data["total"] == 1
        assert all(e["type"] == "remediation" for e in data["events"])

    def test_filter_by_nonexistent_type_returns_empty(
        self,
        mock_repo: AsyncMock,
    ) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        resp = client.get(
            "/api/v1/investigations/inv-abc123/timeline?event_type=security",
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["events"] == []


# ================================================================
# Authentication required
# ================================================================


class TestTimelineAuth:
    def test_unauthenticated_request_rejected(
        self,
        mock_repo: AsyncMock,
    ) -> None:
        """Without auth the endpoint rejects the request."""
        app = _create_test_app()
        investigations.set_repository(mock_repo)

        # No dependency overrides -- no valid bearer token
        client = TestClient(
            app,
            raise_server_exceptions=False,
        )
        resp = client.get(
            "/api/v1/investigations/inv-abc123/timeline",
        )
        assert resp.status_code in (401, 403)

        # Repo should not be called
        mock_repo.get_investigation.assert_not_called()
        mock_repo.get_investigation_timeline.assert_not_called()


# ================================================================
# DB unavailable (503)
# ================================================================


class TestTimelineDbUnavailable:
    def test_returns_503_when_no_repository(self) -> None:
        app = _create_test_app()
        # No repository set at all

        from shieldops.api.auth.dependencies import (
            get_current_user,
        )
        from shieldops.api.auth.models import (
            UserResponse,
            UserRole,
        )

        user = UserResponse(
            id="v-1",
            email="v@test.com",
            name="V",
            role=UserRole.VIEWER,
            is_active=True,
        )

        async def _mock_user() -> UserResponse:
            return user

        app.dependency_overrides[get_current_user] = _mock_user

        client = TestClient(
            app,
            raise_server_exceptions=False,
        )
        resp = client.get(
            "/api/v1/investigations/inv-abc123/timeline",
        )
        assert resp.status_code == 503
        assert resp.json()["detail"] == "DB unavailable"


# ================================================================
# Repository called with correct investigation_id
# ================================================================


class TestTimelineRepoCall:
    def test_passes_correct_id_to_repository(
        self,
        mock_repo: AsyncMock,
    ) -> None:
        app = _create_test_app()
        client = _build_client_with_viewer(app, mock_repo)

        client.get(
            "/api/v1/investigations/inv-xyz/timeline",
        )
        mock_repo.get_investigation.assert_called_once_with(
            "inv-xyz",
        )
