"""Tests for extended ActionRateLimiter methods and PolicyEngine enrichment."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from shieldops.models.base import Environment, RemediationAction, RiskLevel
from shieldops.policy.opa.client import PolicyEngine
from shieldops.policy.opa.rate_limiter import ActionRateLimiter

# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────


def _make_action(
    *,
    env: Environment = Environment.PRODUCTION,
    team: str | None = None,
) -> RemediationAction:
    params: dict = {}
    if team:
        params["team"] = team
    return RemediationAction(
        id="act-test",
        action_type="restart_pod",
        target_resource="pod/api",
        environment=env,
        risk_level=RiskLevel.LOW,
        parameters=params,
        description="Restart API pod",
    )


def _mock_redis_client() -> AsyncMock:
    """Return a mock Redis client with get/incr/expire stubs."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.incr = AsyncMock(return_value=1)
    client.expire = AsyncMock()
    return client


# ────────────────────────────────────────────────────────────────────
# TestMinuteKeyGeneration
# ────────────────────────────────────────────────────────────────────


class TestMinuteKeyGeneration:
    def test_minute_key_format(self):
        limiter = ActionRateLimiter()
        key = limiter._minute_key("production")
        minute = datetime.now(UTC).strftime("%Y%m%d%H%M")
        assert key == f"shieldops:rate:min:production:{minute}"

    def test_minute_key_differs_from_hour_key(self):
        limiter = ActionRateLimiter()
        minute_key = limiter._minute_key("staging")
        hour_key = limiter._key("staging")
        assert minute_key != hour_key
        assert ":min:" in minute_key
        assert ":min:" not in hour_key


# ────────────────────────────────────────────────────────────────────
# TestTeamKeyGeneration
# ────────────────────────────────────────────────────────────────────


class TestTeamKeyGeneration:
    def test_team_key_format(self):
        limiter = ActionRateLimiter()
        key = limiter._team_key("platform", "production")
        hour = datetime.now(UTC).strftime("%Y%m%d%H")
        assert key == f"shieldops:rate:platform:production:{hour}"

    def test_team_key_differs_per_team(self):
        limiter = ActionRateLimiter()
        key_a = limiter._team_key("alpha", "production")
        key_b = limiter._team_key("beta", "production")
        assert key_a != key_b

    def test_team_key_differs_per_environment(self):
        limiter = ActionRateLimiter()
        key_prod = limiter._team_key("platform", "production")
        key_dev = limiter._team_key("platform", "development")
        assert key_prod != key_dev


# ────────────────────────────────────────────────────────────────────
# TestCountRecentActionsMinute
# ────────────────────────────────────────────────────────────────────


class TestCountRecentActionsMinute:
    @pytest.mark.asyncio
    async def test_returns_count_when_value_exists(self):
        limiter = ActionRateLimiter()
        mock_client = _mock_redis_client()
        mock_client.get = AsyncMock(return_value="7")
        limiter._client = mock_client

        count = await limiter.count_recent_actions_minute("production")
        assert count == 7

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_value(self):
        limiter = ActionRateLimiter()
        mock_client = _mock_redis_client()
        mock_client.get = AsyncMock(return_value=None)
        limiter._client = mock_client

        count = await limiter.count_recent_actions_minute("production")
        assert count == 0

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self):
        limiter = ActionRateLimiter()
        mock_client = _mock_redis_client()
        mock_client.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        limiter._client = mock_client

        count = await limiter.count_recent_actions_minute("production")
        assert count == 0


# ────────────────────────────────────────────────────────────────────
# TestCountTeamActions
# ────────────────────────────────────────────────────────────────────


class TestCountTeamActions:
    @pytest.mark.asyncio
    async def test_returns_count_when_value_exists(self):
        limiter = ActionRateLimiter()
        mock_client = _mock_redis_client()
        mock_client.get = AsyncMock(return_value="12")
        limiter._client = mock_client

        count = await limiter.count_team_actions("platform", "staging")
        assert count == 12

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_value(self):
        limiter = ActionRateLimiter()
        mock_client = _mock_redis_client()
        mock_client.get = AsyncMock(return_value=None)
        limiter._client = mock_client

        count = await limiter.count_team_actions("platform", "staging")
        assert count == 0

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self):
        limiter = ActionRateLimiter()
        mock_client = _mock_redis_client()
        mock_client.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        limiter._client = mock_client

        count = await limiter.count_team_actions("platform", "staging")
        assert count == 0


# ────────────────────────────────────────────────────────────────────
# TestIncrementTeam
# ────────────────────────────────────────────────────────────────────


class TestIncrementTeam:
    @pytest.mark.asyncio
    async def test_increments_and_returns_count(self):
        limiter = ActionRateLimiter()
        mock_client = _mock_redis_client()
        mock_client.incr = AsyncMock(return_value=5)
        limiter._client = mock_client

        result = await limiter.increment_team("platform", "production")
        assert result == 5
        mock_client.incr.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sets_3600_ttl(self):
        limiter = ActionRateLimiter()
        mock_client = _mock_redis_client()
        mock_client.incr = AsyncMock(return_value=1)
        limiter._client = mock_client

        await limiter.increment_team("platform", "production")
        mock_client.expire.assert_awaited_once()
        args = mock_client.expire.call_args[0]
        assert args[1] == 3600

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self):
        limiter = ActionRateLimiter()
        mock_client = _mock_redis_client()
        mock_client.incr = AsyncMock(side_effect=ConnectionError("Redis down"))
        limiter._client = mock_client

        result = await limiter.increment_team("platform", "production")
        assert result == 0


# ────────────────────────────────────────────────────────────────────
# TestIncrementMinute
# ────────────────────────────────────────────────────────────────────


class TestIncrementMinute:
    @pytest.mark.asyncio
    async def test_increments_and_returns_count(self):
        limiter = ActionRateLimiter()
        mock_client = _mock_redis_client()
        mock_client.incr = AsyncMock(return_value=3)
        limiter._client = mock_client

        result = await limiter.increment_minute("production")
        assert result == 3
        mock_client.incr.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sets_120_ttl(self):
        limiter = ActionRateLimiter()
        mock_client = _mock_redis_client()
        mock_client.incr = AsyncMock(return_value=1)
        limiter._client = mock_client

        await limiter.increment_minute("production")
        mock_client.expire.assert_awaited_once()
        args = mock_client.expire.call_args[0]
        assert args[1] == 120

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self):
        limiter = ActionRateLimiter()
        mock_client = _mock_redis_client()
        mock_client.incr = AsyncMock(side_effect=ConnectionError("Redis down"))
        limiter._client = mock_client

        result = await limiter.increment_minute("production")
        assert result == 0


# ────────────────────────────────────────────────────────────────────
# TestContextEnrichment
# ────────────────────────────────────────────────────────────────────


class TestContextEnrichment:
    @pytest.mark.asyncio
    async def test_minute_count_added_to_context(self):
        rate_limiter = MagicMock()
        rate_limiter.count_recent_actions = AsyncMock(return_value=5)
        rate_limiter.count_recent_actions_minute = AsyncMock(return_value=2)
        rate_limiter.count_team_actions = AsyncMock(return_value=0)
        rate_limiter.increment = AsyncMock()
        rate_limiter.increment_minute = AsyncMock()
        rate_limiter.increment_team = AsyncMock()

        engine = PolicyEngine(opa_url="http://localhost:8181", rate_limiter=rate_limiter)

        captured_input: dict = {}

        async def _capture_post(url, *, json, **kwargs):
            captured_input.update(json["input"])
            resp = MagicMock()
            resp.json.return_value = {"result": True, "reasons": []}
            resp.raise_for_status = MagicMock()
            return resp

        engine._client.post = AsyncMock(side_effect=_capture_post)

        action = _make_action()
        await engine.evaluate(action, agent_id="agent-1")

        assert captured_input["context"]["actions_this_minute"] == 2

    @pytest.mark.asyncio
    async def test_team_actions_added_to_context(self):
        rate_limiter = MagicMock()
        rate_limiter.count_recent_actions = AsyncMock(return_value=5)
        rate_limiter.count_recent_actions_minute = AsyncMock(return_value=1)
        rate_limiter.count_team_actions = AsyncMock(return_value=8)
        rate_limiter.increment = AsyncMock()
        rate_limiter.increment_minute = AsyncMock()
        rate_limiter.increment_team = AsyncMock()

        engine = PolicyEngine(opa_url="http://localhost:8181", rate_limiter=rate_limiter)

        captured_input: dict = {}

        async def _capture_post(url, *, json, **kwargs):
            captured_input.update(json["input"])
            resp = MagicMock()
            resp.json.return_value = {"result": True, "reasons": []}
            resp.raise_for_status = MagicMock()
            return resp

        engine._client.post = AsyncMock(side_effect=_capture_post)

        action = _make_action(team="platform")
        await engine.evaluate(action, agent_id="agent-1")

        assert captured_input["context"]["team_actions_this_hour"] == 8

    @pytest.mark.asyncio
    async def test_no_team_skips_team_enrichment(self):
        rate_limiter = MagicMock()
        rate_limiter.count_recent_actions = AsyncMock(return_value=0)
        rate_limiter.count_recent_actions_minute = AsyncMock(return_value=0)
        rate_limiter.count_team_actions = AsyncMock(return_value=0)
        rate_limiter.increment = AsyncMock()
        rate_limiter.increment_minute = AsyncMock()
        rate_limiter.increment_team = AsyncMock()

        engine = PolicyEngine(opa_url="http://localhost:8181", rate_limiter=rate_limiter)

        captured_input: dict = {}

        async def _capture_post(url, *, json, **kwargs):
            captured_input.update(json["input"])
            resp = MagicMock()
            resp.json.return_value = {"result": True, "reasons": []}
            resp.raise_for_status = MagicMock()
            return resp

        engine._client.post = AsyncMock(side_effect=_capture_post)

        action = _make_action(team=None)
        await engine.evaluate(action, agent_id="agent-1")

        assert "team_actions_this_hour" not in captured_input["context"]
        rate_limiter.count_team_actions.assert_not_awaited()


# ────────────────────────────────────────────────────────────────────
# TestBackwardCompatibility
# ────────────────────────────────────────────────────────────────────


class TestBackwardCompatibility:
    @pytest.mark.asyncio
    async def test_existing_count_recent_actions_still_works(self):
        limiter = ActionRateLimiter()
        mock_client = _mock_redis_client()
        mock_client.get = AsyncMock(return_value="10")
        limiter._client = mock_client

        count = await limiter.count_recent_actions("production")
        assert count == 10

    @pytest.mark.asyncio
    async def test_existing_increment_still_works(self):
        limiter = ActionRateLimiter()
        mock_client = _mock_redis_client()
        mock_client.incr = AsyncMock(return_value=11)
        limiter._client = mock_client

        result = await limiter.increment("production")
        assert result == 11
        mock_client.expire.assert_awaited_once()
        args = mock_client.expire.call_args[0]
        assert args[1] == 3600

    @pytest.mark.asyncio
    async def test_hour_key_unchanged(self):
        limiter = ActionRateLimiter()
        key = limiter._key("production")
        hour = datetime.now(UTC).strftime("%Y%m%d%H")
        assert key == f"shieldops:rate:production:{hour}"


# ────────────────────────────────────────────────────────────────────
# TestExtendedIncrement
# ────────────────────────────────────────────────────────────────────


class TestExtendedIncrement:
    @pytest.mark.asyncio
    async def test_minute_and_team_incremented_on_allow(self):
        rate_limiter = MagicMock()
        rate_limiter.count_recent_actions = AsyncMock(return_value=0)
        rate_limiter.count_recent_actions_minute = AsyncMock(return_value=0)
        rate_limiter.count_team_actions = AsyncMock(return_value=0)
        rate_limiter.increment = AsyncMock()
        rate_limiter.increment_minute = AsyncMock()
        rate_limiter.increment_team = AsyncMock()

        engine = PolicyEngine(opa_url="http://localhost:8181", rate_limiter=rate_limiter)

        async def _allow_post(url, *, json, **kwargs):
            resp = MagicMock()
            resp.json.return_value = {"result": True, "reasons": []}
            resp.raise_for_status = MagicMock()
            return resp

        engine._client.post = AsyncMock(side_effect=_allow_post)

        action = _make_action(team="platform")
        await engine.evaluate(action, agent_id="agent-1")

        rate_limiter.increment.assert_awaited_once()
        rate_limiter.increment_minute.assert_awaited_once_with("production")
        rate_limiter.increment_team.assert_awaited_once_with("platform", "production")

    @pytest.mark.asyncio
    async def test_no_team_skips_team_increment(self):
        rate_limiter = MagicMock()
        rate_limiter.count_recent_actions = AsyncMock(return_value=0)
        rate_limiter.count_recent_actions_minute = AsyncMock(return_value=0)
        rate_limiter.count_team_actions = AsyncMock(return_value=0)
        rate_limiter.increment = AsyncMock()
        rate_limiter.increment_minute = AsyncMock()
        rate_limiter.increment_team = AsyncMock()

        engine = PolicyEngine(opa_url="http://localhost:8181", rate_limiter=rate_limiter)

        async def _allow_post(url, *, json, **kwargs):
            resp = MagicMock()
            resp.json.return_value = {"result": True, "reasons": []}
            resp.raise_for_status = MagicMock()
            return resp

        engine._client.post = AsyncMock(side_effect=_allow_post)

        action = _make_action(team=None)
        await engine.evaluate(action, agent_id="agent-1")

        rate_limiter.increment_minute.assert_awaited_once()
        rate_limiter.increment_team.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_increment_on_deny(self):
        rate_limiter = MagicMock()
        rate_limiter.count_recent_actions = AsyncMock(return_value=0)
        rate_limiter.count_recent_actions_minute = AsyncMock(return_value=0)
        rate_limiter.count_team_actions = AsyncMock(return_value=0)
        rate_limiter.increment = AsyncMock()
        rate_limiter.increment_minute = AsyncMock()
        rate_limiter.increment_team = AsyncMock()

        engine = PolicyEngine(opa_url="http://localhost:8181", rate_limiter=rate_limiter)

        async def _deny_post(url, *, json, **kwargs):
            resp = MagicMock()
            resp.json.return_value = {"result": False, "reasons": ["denied"]}
            resp.raise_for_status = MagicMock()
            return resp

        engine._client.post = AsyncMock(side_effect=_deny_post)

        action = _make_action(team="platform")
        await engine.evaluate(action, agent_id="agent-1")

        rate_limiter.increment.assert_not_awaited()
        rate_limiter.increment_minute.assert_not_awaited()
        rate_limiter.increment_team.assert_not_awaited()
