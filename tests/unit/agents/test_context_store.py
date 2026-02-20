"""Tests for AgentContextStore — persistent cross-incident memory."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from shieldops.agents.context_store import AgentContextStore


class TestAgentContextStore:
    """Unit tests for AgentContextStore with mocked repository."""

    def _make_store(self) -> tuple[AgentContextStore, AsyncMock]:
        repo = AsyncMock()
        store = AgentContextStore(repository=repo)
        return store, repo

    # ── get / set ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_set_and_get_context(self):
        store, repo = self._make_store()
        repo.get_agent_context.return_value = {
            "id": "ctx-abc123",
            "agent_type": "investigation",
            "context_key": "last_root_cause",
            "context_value": {"cause": "OOM"},
            "ttl_hours": None,
            "expires_at": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }

        await store.set(
            "investigation",
            "last_root_cause",
            {"cause": "OOM"},
        )
        result = await store.get("investigation", "last_root_cause")

        repo.upsert_agent_context.assert_awaited_once()
        repo.get_agent_context.assert_awaited_once_with("investigation", "last_root_cause")
        assert result == {"cause": "OOM"}

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        store, repo = self._make_store()
        repo.get_agent_context.return_value = None

        result = await store.get("investigation", "nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_expired_returns_none(self):
        store, repo = self._make_store()
        past = datetime.now(UTC) - timedelta(hours=2)
        repo.get_agent_context.return_value = {
            "id": "ctx-expired",
            "agent_type": "security",
            "context_key": "scan_cache",
            "context_value": {"cached": True},
            "ttl_hours": 1,
            "expires_at": past.isoformat(),
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }

        result = await store.get("security", "scan_cache")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_with_ttl_sets_expires_at(self):
        store, repo = self._make_store()
        repo.upsert_agent_context.return_value = {
            "id": "ctx-ttl",
            "agent_type": "remediation",
            "context_key": "cooldown",
            "context_value": {"active": True},
            "ttl_hours": 24,
            "expires_at": "2026-02-20T00:00:00+00:00",
            "created_at": "2026-02-19T00:00:00+00:00",
            "updated_at": "2026-02-19T00:00:00+00:00",
        }

        before = datetime.now(UTC)
        await store.set(
            "remediation",
            "cooldown",
            {"active": True},
            ttl_hours=24,
        )
        after = datetime.now(UTC)

        call_kwargs = repo.upsert_agent_context.call_args.kwargs
        assert call_kwargs["ttl_hours"] == 24
        assert call_kwargs["expires_at"] is not None
        # expires_at should be ~24h from now
        expected_min = before + timedelta(hours=24)
        expected_max = after + timedelta(hours=24)
        assert expected_min <= call_kwargs["expires_at"] <= expected_max

    @pytest.mark.asyncio
    async def test_set_overwrites_existing(self):
        store, repo = self._make_store()

        await store.set("investigation", "key1", {"version": 1})
        await store.set("investigation", "key1", {"version": 2})

        assert repo.upsert_agent_context.await_count == 2
        second_call = repo.upsert_agent_context.call_args_list[1]
        assert second_call.kwargs["value"] == {"version": 2}

    # ── delete ───────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(self):
        store, repo = self._make_store()
        repo.delete_agent_context.return_value = True

        result = await store.delete("investigation", "old_key")

        assert result is True
        repo.delete_agent_context.assert_awaited_once_with("investigation", "old_key")

    @pytest.mark.asyncio
    async def test_delete_missing_returns_false(self):
        store, repo = self._make_store()
        repo.delete_agent_context.return_value = False

        result = await store.delete("investigation", "ghost")

        assert result is False

    # ── search ───────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_search_by_agent_type(self):
        store, repo = self._make_store()
        future = (datetime.now(UTC) + timedelta(hours=10)).isoformat()
        repo.search_agent_context.return_value = [
            {
                "id": "ctx-1",
                "agent_type": "investigation",
                "context_key": "key_a",
                "context_value": {"a": 1},
                "expires_at": future,
            },
            {
                "id": "ctx-2",
                "agent_type": "investigation",
                "context_key": "key_b",
                "context_value": {"b": 2},
                "expires_at": None,
            },
        ]

        results = await store.search("investigation")

        repo.search_agent_context.assert_awaited_once_with("investigation", None)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_with_key_pattern(self):
        store, repo = self._make_store()
        repo.search_agent_context.return_value = [
            {
                "id": "ctx-3",
                "agent_type": "security",
                "context_key": "cve_cache_2026",
                "context_value": {"cves": []},
                "expires_at": None,
            },
        ]

        results = await store.search("security", key_pattern="cve_cache")

        repo.search_agent_context.assert_awaited_once_with("security", "cve_cache")
        assert len(results) == 1
        assert results[0]["context_key"] == "cve_cache_2026"

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        store, repo = self._make_store()
        repo.search_agent_context.return_value = []

        results = await store.search("learning")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_filters_expired_entries(self):
        """Search should exclude entries whose expires_at is in the past."""
        store, repo = self._make_store()
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        future = (datetime.now(UTC) + timedelta(hours=10)).isoformat()
        repo.search_agent_context.return_value = [
            {
                "id": "ctx-expired",
                "agent_type": "investigation",
                "context_key": "old",
                "context_value": {"stale": True},
                "expires_at": past,
            },
            {
                "id": "ctx-valid",
                "agent_type": "investigation",
                "context_key": "fresh",
                "context_value": {"fresh": True},
                "expires_at": future,
            },
        ]

        results = await store.search("investigation")

        assert len(results) == 1
        assert results[0]["id"] == "ctx-valid"

    # ── cleanup ──────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_cleanup_expired_deletes(self):
        store, repo = self._make_store()
        repo.cleanup_expired_context.return_value = 5

        count = await store.cleanup_expired()

        assert count == 5
        repo.cleanup_expired_context.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_no_expired(self):
        store, repo = self._make_store()
        repo.cleanup_expired_context.return_value = 0

        count = await store.cleanup_expired()

        assert count == 0
