"""Tests for shieldops.api.routes.security_chat — Security Chat API routes."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.api.routes.security_chat import (
    ChatRequest,
    ChatResponse,
    _sessions,
    get_session,
    list_sessions,
    send_message,
    set_chat_agent,
    set_repository,
    set_session_store,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user(**overrides: Any) -> UserResponse:
    defaults: dict[str, Any] = {
        "id": "user-001",
        "email": "ops@example.com",
        "name": "Test Operator",
        "role": UserRole.OPERATOR,
        "is_active": True,
    }
    defaults.update(overrides)
    return UserResponse(**defaults)


@pytest.fixture(autouse=True)
def _clear_state():
    """Reset module-level state between tests."""
    _sessions.clear()
    set_chat_agent(None)
    set_repository(None)
    set_session_store(None)
    yield
    _sessions.clear()
    set_chat_agent(None)
    set_repository(None)
    set_session_store(None)


# ---------------------------------------------------------------------------
# ChatRequest validation
# ---------------------------------------------------------------------------


class TestChatRequestValidation:
    def test_valid_request(self):
        req = ChatRequest(message="Hello")
        assert req.message == "Hello"
        assert req.session_id is None
        assert req.context == {}

    def test_with_session_id(self):
        req = ChatRequest(message="Hi", session_id="sess-123")
        assert req.session_id == "sess-123"

    def test_message_too_short(self):
        with pytest.raises(ValueError):
            ChatRequest(message="")

    def test_with_context(self):
        req = ChatRequest(message="Check vulns", context={"page": "/security"})
        assert req.context["page"] == "/security"


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_creates_new_session_when_no_id(self):
        body = ChatRequest(message="What's my security posture?")
        user = _make_user()
        result = await send_message(body, user)

        assert isinstance(result, ChatResponse)
        assert result.session_id.startswith("chat-")
        assert isinstance(result.response, str)
        assert len(result.response) > 0

    @pytest.mark.asyncio
    async def test_uses_provided_session_id(self):
        body = ChatRequest(message="Hello", session_id="my-sess-001")
        user = _make_user()
        result = await send_message(body, user)

        assert result.session_id == "my-sess-001"

    @pytest.mark.asyncio
    async def test_stores_messages_in_session(self):
        body = ChatRequest(message="First message", session_id="sess-store")
        user = _make_user()
        await send_message(body, user)

        assert "sess-store" in _sessions
        msgs = _sessions["sess-store"]
        assert len(msgs) == 2  # user + assistant
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "First message"
        assert msgs[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_continues_existing_session(self):
        user = _make_user()
        body1 = ChatRequest(message="First", session_id="sess-cont")
        await send_message(body1, user)

        body2 = ChatRequest(message="Second", session_id="sess-cont")
        await send_message(body2, user)

        assert len(_sessions["sess-cont"]) == 4  # 2 user + 2 assistant

    @pytest.mark.asyncio
    async def test_uses_chat_agent_when_available(self):
        mock_agent = AsyncMock()
        mock_agent.respond.return_value = {
            "response": "Agent response here",
            "actions": [{"type": "scan"}],
            "sources": ["vuln-db"],
        }
        set_chat_agent(mock_agent)

        body = ChatRequest(message="Check vulnerabilities")
        user = _make_user()
        result = await send_message(body, user)

        assert result.response == "Agent response here"
        assert len(result.actions) == 1
        assert result.sources == ["vuln-db"]
        mock_agent.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_agent_error_gracefully(self):
        mock_agent = AsyncMock()
        mock_agent.respond.side_effect = RuntimeError("agent crash")
        set_chat_agent(mock_agent)

        body = ChatRequest(message="Do something")
        user = _make_user()
        result = await send_message(body, user)

        assert "error" in result.response.lower()

    @pytest.mark.asyncio
    async def test_enriches_context_with_vuln_keywords(self):
        mock_repo = AsyncMock()
        mock_repo.get_vulnerability_stats.return_value = {"total": 10}
        mock_repo.list_vulnerabilities.return_value = []
        set_repository(mock_repo)

        body = ChatRequest(message="Show me critical CVE findings")
        user = _make_user()
        await send_message(body, user)

        mock_repo.get_vulnerability_stats.assert_called_once()


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------


class TestListSessions:
    @pytest.mark.asyncio
    async def test_empty_sessions(self):
        user = _make_user()
        result = await list_sessions(user)
        assert result["sessions"] == []

    @pytest.mark.asyncio
    async def test_returns_session_summaries(self):
        _sessions["sess-a"] = [
            {"role": "user", "content": "Hello", "timestamp": "2026-01-01T00:00:00Z"},
            {"role": "assistant", "content": "Hi", "timestamp": "2026-01-01T00:00:01Z"},
        ]
        _sessions["sess-b"] = [
            {"role": "user", "content": "Bye", "timestamp": "2026-01-02T00:00:00Z"},
        ]

        user = _make_user()
        result = await list_sessions(user)

        assert len(result["sessions"]) == 2
        ids = {s.id for s in result["sessions"]}
        assert "sess-a" in ids
        assert "sess-b" in ids

        sess_a = next(s for s in result["sessions"] if s.id == "sess-a")
        assert sess_a.message_count == 2


# ---------------------------------------------------------------------------
# get_session
# ---------------------------------------------------------------------------


class TestGetSession:
    @pytest.mark.asyncio
    async def test_returns_session_history(self):
        _sessions["sess-x"] = [
            {"role": "user", "content": "Hello", "timestamp": "2026-01-01T00:00:00Z"},
        ]

        user = _make_user()
        result = await get_session("sess-x", user)

        assert result["session_id"] == "sess-x"
        assert result["message_count"] == 1
        assert result["messages"][0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_404_for_missing_session(self):
        user = _make_user()
        with pytest.raises(HTTPException) as exc_info:
            await get_session("nonexistent", user)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_empty_session_if_key_exists(self):
        _sessions["empty-sess"] = []
        user = _make_user()
        result = await get_session("empty-sess", user)
        assert result["message_count"] == 0
