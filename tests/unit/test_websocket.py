"""Tests for WebSocket real-time updates."""

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from shieldops.api.app import app
from shieldops.api.auth.service import create_access_token
from shieldops.api.ws.manager import ConnectionManager


class TestConnectionManager:
    @pytest.mark.asyncio
    async def test_initial_state(self):
        mgr = ConnectionManager()
        assert mgr.active_connections == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_channel(self):
        """Broadcasting to a channel with no subscribers should not error."""
        mgr = ConnectionManager()
        await mgr.broadcast("nonexistent", {"type": "test"})


class TestWebSocketRoutes:
    def test_ws_requires_auth(self):
        """WebSocket connection without token should be rejected."""
        client = TestClient(app)
        with pytest.raises(Exception):
            # Without token, the WS should close with 4001
            with client.websocket_connect("/ws/events"):
                pass

    def test_ws_connects_with_valid_token(self):
        """WebSocket connection with valid token should succeed."""
        token = create_access_token(subject="test-user", role="admin")
        client = TestClient(app)
        with client.websocket_connect(f"/ws/events?token={token}") as ws:
            # Connection should be established
            assert ws is not None

    def test_ws_investigation_channel_requires_auth(self):
        client = TestClient(app)
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/investigations/inv-123"):
                pass

    def test_ws_remediation_channel_requires_auth(self):
        client = TestClient(app)
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/remediations/rem-123"):
                pass

    def test_ws_investigation_channel_with_token(self):
        token = create_access_token(subject="test-user", role="operator")
        client = TestClient(app)
        with client.websocket_connect(
            f"/ws/investigations/inv-123?token={token}"
        ) as ws:
            assert ws is not None

    def test_ws_remediation_channel_with_token(self):
        token = create_access_token(subject="test-user", role="viewer")
        client = TestClient(app)
        with client.websocket_connect(
            f"/ws/remediations/rem-456?token={token}"
        ) as ws:
            assert ws is not None
