"""Tests for the AI Security Chat API endpoints.

Covers:
- POST /api/v1/security/chat — send message, get response
- GET /api/v1/security/chat/sessions — list active sessions
- GET /api/v1/security/chat/sessions/{id} — session history
- Error handling when agent raises
- Session creation and 404 on missing session
- In-memory session store reset between tests
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from shieldops.api.app import app
from shieldops.api.routes import security_chat

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_module_state():
    """Reset module-level singletons and session store between tests."""
    original_agent = security_chat._chat_agent
    original_repo = security_chat._repository
    original_sessions = security_chat._sessions.copy()
    security_chat._chat_agent = None
    security_chat._repository = None
    security_chat._sessions.clear()
    yield
    security_chat._chat_agent = original_agent
    security_chat._repository = original_repo
    security_chat._sessions.clear()
    security_chat._sessions.update(original_sessions)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def mock_chat_agent() -> AsyncMock:
    agent = AsyncMock()
    agent.respond = AsyncMock(
        return_value={
            "response": "Found 5 critical vulnerabilities.",
            "actions": [],
            "sources": ["vulnerability_db"],
        }
    )
    return agent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPostSecurityChat:
    """POST /api/v1/security/chat"""

    def test_send_message_returns_response(self, client: TestClient, mock_chat_agent: AsyncMock):
        security_chat.set_chat_agent(mock_chat_agent)
        resp = client.post(
            "/api/v1/security/chat",
            json={"message": "show critical vulns"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert data["response"] == "Found 5 critical vulnerabilities."
        assert "session_id" in data

    def test_send_message_creates_session(self, client: TestClient, mock_chat_agent: AsyncMock):
        security_chat.set_chat_agent(mock_chat_agent)
        resp = client.post(
            "/api/v1/security/chat",
            json={"message": "hello"},
        )
        session_id = resp.json()["session_id"]
        assert session_id.startswith("chat-")
        assert session_id in security_chat._sessions

    def test_send_message_continues_existing_session(
        self, client: TestClient, mock_chat_agent: AsyncMock
    ):
        security_chat.set_chat_agent(mock_chat_agent)
        # First turn
        resp1 = client.post(
            "/api/v1/security/chat",
            json={"message": "hello"},
        )
        sid = resp1.json()["session_id"]
        # Second turn in same session
        resp2 = client.post(
            "/api/v1/security/chat",
            json={"message": "show vulns", "session_id": sid},
        )
        assert resp2.json()["session_id"] == sid
        # Session should have 4 messages (2 user + 2 assistant)
        assert len(security_chat._sessions[sid]) == 4

    def test_send_message_without_agent_uses_fallback(self, client: TestClient):
        """When no agent is configured, the fallback LLM path is used."""
        with patch(
            "shieldops.api.routes.security_chat._fallback_response",
            new_callable=AsyncMock,
            return_value="Fallback response",
        ):
            resp = client.post(
                "/api/v1/security/chat",
                json={"message": "hello"},
            )
        assert resp.status_code == 200

    def test_send_message_agent_error_returns_error_text(
        self, client: TestClient, mock_chat_agent: AsyncMock
    ):
        mock_chat_agent.respond.side_effect = RuntimeError("LLM unavailable")
        security_chat.set_chat_agent(mock_chat_agent)
        resp = client.post(
            "/api/v1/security/chat",
            json={"message": "show vulns"},
        )
        assert resp.status_code == 200
        assert "error" in resp.json()["response"].lower()

    def test_send_message_empty_body_returns_422(self, client: TestClient):
        resp = client.post("/api/v1/security/chat", json={"message": ""})
        assert resp.status_code == 422


class TestListSessions:
    """GET /api/v1/security/chat/sessions"""

    def test_list_sessions_empty(self, client: TestClient):
        resp = client.get("/api/v1/security/chat/sessions")
        assert resp.status_code == 200
        assert resp.json()["sessions"] == []

    def test_list_sessions_after_chat(self, client: TestClient, mock_chat_agent: AsyncMock):
        security_chat.set_chat_agent(mock_chat_agent)
        client.post("/api/v1/security/chat", json={"message": "hello"})
        resp = client.get("/api/v1/security/chat/sessions")
        assert resp.status_code == 200
        sessions = resp.json()["sessions"]
        assert len(sessions) == 1
        assert sessions[0]["message_count"] == 2  # user + assistant


class TestGetSession:
    """GET /api/v1/security/chat/sessions/{session_id}"""

    def test_get_existing_session(self, client: TestClient, mock_chat_agent: AsyncMock):
        security_chat.set_chat_agent(mock_chat_agent)
        resp = client.post("/api/v1/security/chat", json={"message": "hello"})
        sid = resp.json()["session_id"]

        resp = client.get(f"/api/v1/security/chat/sessions/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == sid
        assert data["message_count"] == 2

    def test_get_nonexistent_session_returns_404(self, client: TestClient):
        resp = client.get("/api/v1/security/chat/sessions/does-not-exist")
        assert resp.status_code == 404
