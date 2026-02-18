"""Unit tests for OPA policy rules and the rate limiter."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.models.base import Environment, RemediationAction, RiskLevel
from shieldops.policy.opa.client import PolicyDecision, PolicyEngine
from shieldops.policy.opa.rate_limiter import ActionRateLimiter


class TestPolicyDecision:
    def test_allowed(self):
        d = PolicyDecision(allowed=True)
        assert d.allowed is True
        assert d.denied is False

    def test_denied(self):
        d = PolicyDecision(allowed=False, reasons=["blocked"])
        assert d.allowed is False
        assert d.denied is True
        assert d.reasons == ["blocked"]


class TestPolicyEngineWithRateLimiter:
    """Test that the PolicyEngine enriches context with rate limiter data."""

    @pytest.mark.asyncio
    async def test_evaluate_enriches_context(self):
        """Verify that actions_this_hour is added to the OPA input context."""
        mock_limiter = AsyncMock()
        mock_limiter.count_recent_actions.return_value = 5

        engine = PolicyEngine(opa_url="http://opa:8181", rate_limiter=mock_limiter)
        engine._client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {"result": True}
        mock_response.raise_for_status = MagicMock()
        engine._client.post = AsyncMock(return_value=mock_response)

        action = RemediationAction(
            id="act-001",
            action_type="restart_pod",
            target_resource="default/nginx",
            environment=Environment.PRODUCTION,
            risk_level=RiskLevel.LOW,
            description="test",
        )

        result = await engine.evaluate(action, agent_id="test-agent")
        assert result.allowed is True

        # Verify the POST was called with enriched context
        call_args = engine._client.post.call_args
        input_data = call_args.kwargs.get("json", call_args.args[1] if len(call_args.args) > 1 else {})
        assert input_data["input"]["context"]["actions_this_hour"] == 5

        # Verify rate limiter was incremented
        mock_limiter.increment.assert_called_once_with("production")

    @pytest.mark.asyncio
    async def test_evaluate_without_rate_limiter(self):
        """Verify engine works without rate limiter."""
        engine = PolicyEngine(opa_url="http://opa:8181", rate_limiter=None)
        engine._client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {"result": True}
        mock_response.raise_for_status = MagicMock()
        engine._client.post = AsyncMock(return_value=mock_response)

        action = RemediationAction(
            id="act-002",
            action_type="restart_pod",
            target_resource="default/nginx",
            environment=Environment.DEVELOPMENT,
            risk_level=RiskLevel.LOW,
            description="test",
        )

        result = await engine.evaluate(action, agent_id="test-agent")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_evaluate_http_error_fails_closed(self):
        """Verify that HTTP errors result in deny (fail closed)."""
        import httpx

        engine = PolicyEngine(opa_url="http://opa:8181")
        engine._client = AsyncMock()
        engine._client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

        action = RemediationAction(
            id="act-003",
            action_type="restart_pod",
            target_resource="default/nginx",
            environment=Environment.DEVELOPMENT,
            risk_level=RiskLevel.LOW,
            description="test",
        )

        result = await engine.evaluate(action, agent_id="test-agent")
        assert result.allowed is False
        assert "Defaulting to deny" in result.reasons[0]


class TestPolicyEngineRiskClassification:
    """Test risk classification rules."""

    def test_destructive_action_is_critical(self):
        engine = PolicyEngine()
        assert engine.classify_risk("drain_node", Environment.DEVELOPMENT) == RiskLevel.CRITICAL

    def test_production_high_impact(self):
        engine = PolicyEngine()
        assert engine.classify_risk("rollback_deployment", Environment.PRODUCTION) == RiskLevel.HIGH

    def test_production_default_is_medium(self):
        engine = PolicyEngine()
        assert engine.classify_risk("restart_pod", Environment.PRODUCTION) == RiskLevel.MEDIUM

    def test_staging_is_low(self):
        engine = PolicyEngine()
        assert engine.classify_risk("restart_pod", Environment.STAGING) == RiskLevel.LOW

    def test_development_is_low(self):
        engine = PolicyEngine()
        assert engine.classify_risk("restart_pod", Environment.DEVELOPMENT) == RiskLevel.LOW


class TestActionRateLimiter:
    """Test the Redis-based rate limiter (with mocked Redis)."""

    @pytest.mark.asyncio
    async def test_count_recent_actions_empty(self):
        limiter = ActionRateLimiter()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        limiter._client = mock_redis

        count = await limiter.count_recent_actions("production")
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_recent_actions_with_value(self):
        limiter = ActionRateLimiter()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="7")
        limiter._client = mock_redis

        count = await limiter.count_recent_actions("production")
        assert count == 7

    @pytest.mark.asyncio
    async def test_increment(self):
        limiter = ActionRateLimiter()
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=3)
        mock_redis.expire = AsyncMock()
        limiter._client = mock_redis

        count = await limiter.increment("staging")
        assert count == 3
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_handles_error(self):
        limiter = ActionRateLimiter()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("connection lost"))
        limiter._client = mock_redis

        count = await limiter.count_recent_actions("production")
        assert count == 0  # Graceful degradation
