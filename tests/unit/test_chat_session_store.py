"""Tests for chat session store backends (F1)."""

from unittest.mock import AsyncMock, patch

import pytest

from shieldops.api.routes.chat_session_store import (
    ChatMessage,
    ChatSession,
    InMemoryChatStore,
    RedisChatSessionStore,
)

# ── Model Tests ──────────────────────────────────────────────────


class TestChatMessage:
    def test_create_message(self):
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.timestamp

    def test_message_defaults(self):
        msg = ChatMessage(role="assistant", content="hi")
        assert isinstance(msg.timestamp, str)

    def test_message_custom_timestamp(self):
        msg = ChatMessage(role="user", content="x", timestamp="2024-01-01T00:00:00")
        assert msg.timestamp == "2024-01-01T00:00:00"


class TestChatSession:
    def test_create_session(self):
        s = ChatSession(session_id="test-1")
        assert s.session_id == "test-1"
        assert s.messages == []
        assert s.created_at
        assert s.updated_at

    def test_session_with_messages(self):
        msgs = [ChatMessage(role="user", content="hi")]
        s = ChatSession(session_id="s1", messages=msgs)
        assert len(s.messages) == 1

    def test_session_serialization(self):
        s = ChatSession(session_id="s1", messages=[ChatMessage(role="user", content="hi")])
        j = s.model_dump_json()
        restored = ChatSession.model_validate_json(j)
        assert restored.session_id == "s1"
        assert len(restored.messages) == 1


# ── InMemoryChatStore Tests ──────────────────────────────────────


class TestInMemoryChatStore:
    @pytest.fixture
    def store(self):
        return InMemoryChatStore(max_messages=5)

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, store):
        result = await store.get_session("nope")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_and_get(self, store):
        session = ChatSession(session_id="s1", messages=[ChatMessage(role="user", content="hi")])
        await store.save_session(session)
        result = await store.get_session("s1")
        assert result is not None
        assert result.session_id == "s1"
        assert len(result.messages) == 1

    @pytest.mark.asyncio
    async def test_save_trims_messages(self, store):
        msgs = [ChatMessage(role="user", content=f"msg-{i}") for i in range(10)]
        session = ChatSession(session_id="s1", messages=msgs)
        await store.save_session(session)
        result = await store.get_session("s1")
        assert len(result.messages) == 5
        assert result.messages[0].content == "msg-5"

    @pytest.mark.asyncio
    async def test_delete_existing(self, store):
        session = ChatSession(session_id="s1")
        await store.save_session(session)
        assert await store.delete_session("s1") is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, store):
        assert await store.delete_session("nope") is False

    @pytest.mark.asyncio
    async def test_list_sessions(self, store):
        await store.save_session(ChatSession(session_id="a"))
        await store.save_session(ChatSession(session_id="b"))
        sessions = await store.list_sessions()
        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, store):
        sessions = await store.list_sessions()
        assert sessions == []

    @pytest.mark.asyncio
    async def test_overwrite_session(self, store):
        await store.save_session(ChatSession(session_id="s1", messages=[]))
        await store.save_session(
            ChatSession(session_id="s1", messages=[ChatMessage(role="user", content="new")])
        )
        result = await store.get_session("s1")
        assert len(result.messages) == 1
        assert result.messages[0].content == "new"

    @pytest.mark.asyncio
    async def test_updated_at_changes(self, store):
        session = ChatSession(session_id="s1")
        old_updated = session.updated_at
        await store.save_session(session)
        result = await store.get_session("s1")
        # updated_at should be refreshed
        assert result.updated_at >= old_updated

    @pytest.mark.asyncio
    async def test_store_name(self, store):
        assert store.store_name == "in_memory"

    @pytest.mark.asyncio
    async def test_max_messages_default(self):
        store = InMemoryChatStore()
        msgs = [ChatMessage(role="user", content=f"m{i}") for i in range(60)]
        await store.save_session(ChatSession(session_id="s1", messages=msgs))
        result = await store.get_session("s1")
        assert len(result.messages) == 50

    @pytest.mark.asyncio
    async def test_delete_then_get(self, store):
        await store.save_session(ChatSession(session_id="s1"))
        await store.delete_session("s1")
        assert await store.get_session("s1") is None


# ── RedisChatSessionStore Tests ──────────────────────────────────


class TestRedisChatSessionStore:
    @pytest.fixture
    def mock_redis(self):
        client = AsyncMock()
        client.get = AsyncMock(return_value=None)
        client.set = AsyncMock()
        client.delete = AsyncMock(return_value=1)
        client.ping = AsyncMock()
        client.aclose = AsyncMock()

        async def scan_iter(match=None):
            return
            yield  # noqa: E741 — async generator

        client.scan_iter = scan_iter
        return client

    @pytest.fixture
    def store(self, mock_redis):
        s = RedisChatSessionStore(redis_url="redis://localhost:6379/0", ttl=3600, max_messages=5)
        s._client = mock_redis
        return s

    def test_store_name(self):
        s = RedisChatSessionStore(redis_url="redis://localhost")
        assert s.store_name == "redis"

    def test_make_key(self):
        key = RedisChatSessionStore._make_key("abc")
        assert key == "shieldops:chat:abc"

    def test_ensure_connected_raises(self):
        s = RedisChatSessionStore(redis_url="redis://localhost")
        with pytest.raises(RuntimeError, match="not connected"):
            s._ensure_connected()

    @pytest.mark.asyncio
    async def test_get_session_miss(self, store, mock_redis):
        mock_redis.get.return_value = None
        result = await store.get_session("nope")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_hit(self, store, mock_redis):
        session = ChatSession(session_id="s1", messages=[ChatMessage(role="user", content="hi")])
        mock_redis.get.return_value = session.model_dump_json()
        result = await store.get_session("s1")
        assert result is not None
        assert result.session_id == "s1"

    @pytest.mark.asyncio
    async def test_get_session_corrupt_data(self, store, mock_redis):
        mock_redis.get.return_value = "not-json{"
        result = await store.get_session("bad")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_session(self, store, mock_redis):
        session = ChatSession(session_id="s1", messages=[ChatMessage(role="user", content="hi")])
        await store.save_session(session)
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert "shieldops:chat:s1" in str(call_args)

    @pytest.mark.asyncio
    async def test_save_trims_messages(self, store, mock_redis):
        msgs = [ChatMessage(role="user", content=f"m{i}") for i in range(10)]
        session = ChatSession(session_id="s1", messages=msgs)
        await store.save_session(session)
        saved_json = mock_redis.set.call_args[0][1]
        saved = ChatSession.model_validate_json(saved_json)
        assert len(saved.messages) == 5

    @pytest.mark.asyncio
    async def test_save_session_error(self, store, mock_redis):
        mock_redis.set.side_effect = Exception("Redis down")
        session = ChatSession(session_id="s1")
        with pytest.raises(Exception, match="Redis down"):
            await store.save_session(session)

    @pytest.mark.asyncio
    async def test_delete_session_exists(self, store, mock_redis):
        mock_redis.delete.return_value = 1
        assert await store.delete_session("s1") is True

    @pytest.mark.asyncio
    async def test_delete_session_missing(self, store, mock_redis):
        mock_redis.delete.return_value = 0
        assert await store.delete_session("nope") is False

    @pytest.mark.asyncio
    async def test_delete_session_error(self, store, mock_redis):
        mock_redis.delete.side_effect = Exception("fail")
        assert await store.delete_session("s1") is False

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, store, mock_redis):
        result = await store.health_check()
        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, store, mock_redis):
        mock_redis.ping.side_effect = Exception("connection refused")
        result = await store.health_check()
        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_disconnect(self, store, mock_redis):
        await store.disconnect()
        assert store._client is None
        mock_redis.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect(self):
        store = RedisChatSessionStore(redis_url="redis://localhost:6379/0")
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_from_url.return_value = AsyncMock()
            await store.connect()
            assert store._client is not None

    @pytest.mark.asyncio
    async def test_serialize_deserialize(self):
        session = ChatSession(
            session_id="s1",
            messages=[ChatMessage(role="user", content="hello")],
        )
        raw = RedisChatSessionStore._serialize(session)
        restored = RedisChatSessionStore._deserialize(raw)
        assert restored.session_id == session.session_id
        assert len(restored.messages) == 1

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, store, mock_redis):
        sessions = await store.list_sessions()
        assert sessions == []

    @pytest.mark.asyncio
    async def test_get_session_redis_error(self, store, mock_redis):
        mock_redis.get.side_effect = Exception("timeout")
        result = await store.get_session("s1")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_passed_to_set(self, store, mock_redis):
        session = ChatSession(session_id="s1")
        await store.save_session(session)
        call_kwargs = mock_redis.set.call_args
        assert call_kwargs[1].get("ex") == 3600 or 3600 in call_kwargs[0]
