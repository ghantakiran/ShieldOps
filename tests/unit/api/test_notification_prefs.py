"""Tests for per-user notification preference API endpoints.

Tests cover:
- GET  /users/me/notification-preferences (empty, with data)
- PUT  /users/me/notification-preferences (single, bulk, duplicate upsert)
- DELETE /users/me/notification-preferences/{pref_id} (success, ownership)
- GET  /notification-events (list available event types)
- Validation: invalid channel, invalid event_type
- Authentication required
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.routes import notification_prefs


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(notification_prefs.router, prefix="/api/v1")
    return app


def _make_pref(
    pref_id: str = "np-abc123",
    user_id: str = "usr-test1",
    channel: str = "slack",
    event_type: str = "investigation.created",
    enabled: bool = True,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": pref_id,
        "user_id": user_id,
        "channel": channel,
        "event_type": event_type,
        "enabled": enabled,
        "config": config,
        "created_at": "2026-02-19T12:00:00+00:00",
        "updated_at": None,
    }


@pytest.fixture(autouse=True)
def _reset_module_repo() -> Any:
    original = notification_prefs._repository
    notification_prefs._repository = None
    yield
    notification_prefs._repository = original


@pytest.fixture()
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_notification_preferences = AsyncMock(return_value=[])
    repo.upsert_notification_preference = AsyncMock(return_value=_make_pref())
    repo.delete_notification_preference = AsyncMock(return_value=True)
    repo.get_subscribers_for_event = AsyncMock(return_value=["usr-test1"])
    return repo


def _build_client(
    app: FastAPI,
    mock_repo: AsyncMock | None = None,
    user_id: str = "usr-test1",
) -> TestClient:
    """Wire dependency overrides for an authenticated user."""
    if mock_repo is not None:
        notification_prefs.set_repository(mock_repo)

    from shieldops.api.auth.dependencies import get_current_user
    from shieldops.api.auth.models import UserResponse, UserRole

    user = UserResponse(
        id=user_id,
        email="test@example.com",
        name="Test User",
        role=UserRole.OPERATOR,
        is_active=True,
    )

    async def _mock_user() -> UserResponse:
        return user

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


# ================================================================
# GET /users/me/notification-preferences
# ================================================================


class TestListPreferences:
    def test_list_empty(self, mock_repo: AsyncMock) -> None:
        """Empty list returns total=0."""
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.get("/api/v1/users/me/notification-preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        mock_repo.get_notification_preferences.assert_called_once_with("usr-test1")

    def test_list_with_data(self, mock_repo: AsyncMock) -> None:
        """Existing preferences are returned."""
        mock_repo.get_notification_preferences = AsyncMock(
            return_value=[
                _make_pref(pref_id="np-1", channel="slack"),
                _make_pref(pref_id="np-2", channel="email"),
            ]
        )
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.get("/api/v1/users/me/notification-preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["id"] == "np-1"
        assert data["items"][1]["id"] == "np-2"


# ================================================================
# PUT /users/me/notification-preferences
# ================================================================


class TestBulkUpsertPreferences:
    def test_upsert_single(self, mock_repo: AsyncMock) -> None:
        """Upsert a single preference."""
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.put(
            "/api/v1/users/me/notification-preferences",
            json={
                "preferences": [
                    {
                        "channel": "slack",
                        "event_type": "investigation.created",
                        "enabled": True,
                    }
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["channel"] == "slack"
        mock_repo.upsert_notification_preference.assert_called_once_with(
            user_id="usr-test1",
            channel="slack",
            event_type="investigation.created",
            enabled=True,
            config=None,
        )

    def test_bulk_upsert(self, mock_repo: AsyncMock) -> None:
        """Upsert multiple preferences at once."""
        mock_repo.upsert_notification_preference = AsyncMock(
            side_effect=[
                _make_pref(channel="slack"),
                _make_pref(channel="email"),
                _make_pref(channel="pagerduty"),
            ]
        )
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.put(
            "/api/v1/users/me/notification-preferences",
            json={
                "preferences": [
                    {
                        "channel": "slack",
                        "event_type": "investigation.created",
                        "enabled": True,
                    },
                    {
                        "channel": "email",
                        "event_type": "remediation.completed",
                        "enabled": False,
                    },
                    {
                        "channel": "pagerduty",
                        "event_type": "security.critical_cve",
                        "enabled": True,
                    },
                ]
            },
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 3
        assert mock_repo.upsert_notification_preference.call_count == 3

    def test_duplicate_upsert_updates(self, mock_repo: AsyncMock) -> None:
        """Upserting the same (channel, event_type) updates it."""
        updated = _make_pref(enabled=False)
        mock_repo.upsert_notification_preference = AsyncMock(return_value=updated)
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.put(
            "/api/v1/users/me/notification-preferences",
            json={
                "preferences": [
                    {
                        "channel": "slack",
                        "event_type": "investigation.created",
                        "enabled": False,
                    }
                ]
            },
        )
        assert resp.status_code == 200
        assert resp.json()["items"][0]["enabled"] is False

    def test_invalid_channel_rejected(self, mock_repo: AsyncMock) -> None:
        """Invalid channel name returns 400."""
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.put(
            "/api/v1/users/me/notification-preferences",
            json={
                "preferences": [
                    {
                        "channel": "pigeon",
                        "event_type": "investigation.created",
                        "enabled": True,
                    }
                ]
            },
        )
        assert resp.status_code == 400
        assert "pigeon" in resp.json()["detail"]
        mock_repo.upsert_notification_preference.assert_not_called()

    def test_invalid_event_type_rejected(self, mock_repo: AsyncMock) -> None:
        """Invalid event_type returns 400."""
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.put(
            "/api/v1/users/me/notification-preferences",
            json={
                "preferences": [
                    {
                        "channel": "slack",
                        "event_type": "invalid.event",
                        "enabled": True,
                    }
                ]
            },
        )
        assert resp.status_code == 400
        assert "invalid.event" in resp.json()["detail"]
        mock_repo.upsert_notification_preference.assert_not_called()

    def test_empty_preferences_rejected(self, mock_repo: AsyncMock) -> None:
        """Empty preferences list is rejected by validation."""
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.put(
            "/api/v1/users/me/notification-preferences",
            json={"preferences": []},
        )
        assert resp.status_code == 422


# ================================================================
# DELETE /users/me/notification-preferences/{pref_id}
# ================================================================


class TestDeletePreference:
    def test_delete_success(self, mock_repo: AsyncMock) -> None:
        """Successfully delete own preference."""
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.delete("/api/v1/users/me/notification-preferences/np-abc123")
        assert resp.status_code == 204
        mock_repo.delete_notification_preference.assert_called_once_with(
            preference_id="np-abc123",
            user_id="usr-test1",
        )

    def test_delete_not_found(self, mock_repo: AsyncMock) -> None:
        """Deleting a non-existent pref returns 404."""
        mock_repo.delete_notification_preference = AsyncMock(return_value=False)
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.delete("/api/v1/users/me/notification-preferences/np-nonexist")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_delete_other_user_pref_rejected(self, mock_repo: AsyncMock) -> None:
        """Cannot delete a preference owned by another user.

        The repository enforces ownership by returning False.
        """
        mock_repo.delete_notification_preference = AsyncMock(return_value=False)
        app = _create_test_app()
        client = _build_client(app, mock_repo, user_id="usr-attacker")

        resp = client.delete("/api/v1/users/me/notification-preferences/np-abc123")
        assert resp.status_code == 404
        mock_repo.delete_notification_preference.assert_called_once_with(
            preference_id="np-abc123",
            user_id="usr-attacker",
        )


# ================================================================
# GET /notification-events
# ================================================================


class TestListEventTypes:
    def test_list_events(self, mock_repo: AsyncMock) -> None:
        """Returns all available event types."""
        app = _create_test_app()
        client = _build_client(app, mock_repo)

        resp = client.get("/api/v1/notification-events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        event_names = [e["event_type"] for e in data["items"]]
        assert "investigation.created" in event_names
        assert "security.critical_cve" in event_names
        assert "system.health_degraded" in event_names
        # Verify descriptions are present
        for item in data["items"]:
            assert "description" in item
            assert isinstance(item["description"], str)


# ================================================================
# Authentication required
# ================================================================


class TestAuthenticationRequired:
    def test_list_requires_auth(self) -> None:
        """Unauthenticated request returns 401/403."""
        app = _create_test_app()
        # No dependency override -- auth will fail
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/v1/users/me/notification-preferences")
        assert resp.status_code in (401, 403)

    def test_upsert_requires_auth(self) -> None:
        """Unauthenticated PUT returns 401/403."""
        app = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.put(
            "/api/v1/users/me/notification-preferences",
            json={
                "preferences": [
                    {
                        "channel": "slack",
                        "event_type": "investigation.created",
                        "enabled": True,
                    }
                ]
            },
        )
        assert resp.status_code in (401, 403)

    def test_events_requires_auth(self) -> None:
        """Unauthenticated GET /notification-events returns 401/403."""
        app = _create_test_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/v1/notification-events")
        assert resp.status_code in (401, 403)
