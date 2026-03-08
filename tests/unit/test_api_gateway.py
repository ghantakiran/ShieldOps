"""Unit tests for the API gateway — models, key manager, rate limiter."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from shieldops.api.gateway.key_manager import APIKeyManager, _hash_key
from shieldops.api.gateway.models import (
    APIKey,
    APIKeyScope,
    APIKeyStatus,
    APIUsageRecord,
    TenantConfig,
)
from shieldops.api.gateway.rate_limiter import TenantRateLimiter

# ── Model tests ──────────────────────────────────────────────────────


class TestAPIKeyScope:
    """APIKeyScope enum values."""

    def test_scope_values(self) -> None:
        assert APIKeyScope.read == "read"
        assert APIKeyScope.write == "write"
        assert APIKeyScope.admin == "admin"
        assert APIKeyScope.agent_execute == "agent_execute"

    def test_scope_is_str(self) -> None:
        assert isinstance(APIKeyScope.read, str)


class TestAPIKeyModel:
    """APIKey Pydantic model creation and defaults."""

    def test_creation_with_defaults(self) -> None:
        now = datetime.now(UTC)
        key = APIKey(
            key_id="k1",
            org_id="org-1",
            name="test-key",
            prefix="so_live_",
            hashed_key="abc123",
            scopes=[APIKeyScope.read],
            created_at=now,
        )
        assert key.status == APIKeyStatus.active
        assert key.rate_limit_per_minute == 60
        assert key.expires_at is None
        assert key.last_used_at is None

    def test_creation_with_all_fields(self) -> None:
        now = datetime.now(UTC)
        expires = now + timedelta(days=30)
        key = APIKey(
            key_id="k2",
            org_id="org-2",
            name="full-key",
            prefix="so_live_",
            hashed_key="def456",
            scopes=[APIKeyScope.read, APIKeyScope.write],
            status=APIKeyStatus.revoked,
            rate_limit_per_minute=120,
            created_at=now,
            expires_at=expires,
            last_used_at=now,
        )
        assert key.status == APIKeyStatus.revoked
        assert key.rate_limit_per_minute == 120
        assert key.expires_at == expires


class TestTenantConfig:
    """TenantConfig plan values and defaults."""

    def test_default_plan(self) -> None:
        config = TenantConfig(org_id="org-1")
        assert config.plan == "free"
        assert config.rate_limit_per_minute == 60
        assert config.max_concurrent_agents == 1

    @pytest.mark.parametrize("plan", ["free", "starter", "growth", "enterprise"])
    def test_valid_plans(self, plan: str) -> None:
        config = TenantConfig(org_id="org-1", plan=plan)
        assert config.plan == plan

    def test_invalid_plan_rejected(self) -> None:
        with pytest.raises(ValueError, match="String should match pattern"):
            TenantConfig(org_id="org-1", plan="invalid")


class TestAPIUsageRecord:
    """APIUsageRecord model."""

    def test_creation(self) -> None:
        now = datetime.now(UTC)
        record = APIUsageRecord(
            org_id="org-1",
            endpoint="/api/v1/agents",
            method="GET",
            status_code=200,
            latency_ms=42.5,
            timestamp=now,
        )
        assert record.api_key_id is None
        assert record.latency_ms == 42.5


# ── Key manager tests ────────────────────────────────────────────────


class TestAPIKeyManager:
    """APIKeyManager — create, validate, revoke, list."""

    @pytest.fixture()
    def manager(self) -> APIKeyManager:
        return APIKeyManager()

    def test_create_key_returns_raw_key_with_prefix(self, manager: APIKeyManager) -> None:
        raw_key, api_key = manager.create_key(
            org_id="org-1",
            name="my-key",
            scopes=[APIKeyScope.read],
        )
        assert raw_key.startswith("so_live_")

    def test_create_key_stores_hashed_key_not_raw(self, manager: APIKeyManager) -> None:
        raw_key, api_key = manager.create_key(
            org_id="org-1",
            name="my-key",
            scopes=[APIKeyScope.read],
        )
        # The stored hashed_key must be the SHA-256 of the raw key
        assert api_key.hashed_key == _hash_key(raw_key)
        # And it must NOT be the raw key itself
        assert api_key.hashed_key != raw_key

    def test_validate_key_succeeds_with_correct_raw_key(self, manager: APIKeyManager) -> None:
        raw_key, _ = manager.create_key(
            org_id="org-1",
            name="my-key",
            scopes=[APIKeyScope.read],
        )
        result = manager.validate_key(raw_key)
        assert result is not None
        assert result.org_id == "org-1"
        assert result.last_used_at is not None

    def test_validate_key_returns_none_for_invalid_key(self, manager: APIKeyManager) -> None:
        result = manager.validate_key("so_live_bogus_key_value")
        assert result is None

    def test_validate_key_returns_none_for_revoked_key(self, manager: APIKeyManager) -> None:
        raw_key, api_key = manager.create_key(
            org_id="org-1",
            name="my-key",
            scopes=[APIKeyScope.read],
        )
        manager.revoke_key(api_key.key_id)
        result = manager.validate_key(raw_key)
        assert result is None

    def test_validate_key_returns_none_for_expired_key(self, manager: APIKeyManager) -> None:
        raw_key, api_key = manager.create_key(
            org_id="org-1",
            name="my-key",
            scopes=[APIKeyScope.read],
            expires_in_days=1,
        )
        # Simulate time passing beyond expiry
        future = datetime.now(UTC) + timedelta(days=2)
        with patch("shieldops.api.gateway.key_manager.datetime") as mock_dt:
            mock_dt.now.return_value = future
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = manager.validate_key(raw_key)
        assert result is None

    def test_revoke_key_changes_status(self, manager: APIKeyManager) -> None:
        raw_key, api_key = manager.create_key(
            org_id="org-1",
            name="my-key",
            scopes=[APIKeyScope.read],
        )
        success = manager.revoke_key(api_key.key_id)
        assert success is True
        # Internally the key should now be revoked
        assert manager._keys[api_key.key_id].status == APIKeyStatus.revoked

    def test_revoke_key_nonexistent_returns_false(self, manager: APIKeyManager) -> None:
        assert manager.revoke_key("nonexistent-id") is False

    def test_list_keys_redacts_hashed_key(self, manager: APIKeyManager) -> None:
        manager.create_key(org_id="org-1", name="k1", scopes=[APIKeyScope.read])
        keys = manager.list_keys("org-1")
        assert len(keys) == 1
        assert keys[0].hashed_key == "***"

    def test_list_keys_filters_by_org_id(self, manager: APIKeyManager) -> None:
        manager.create_key(org_id="org-1", name="k1", scopes=[APIKeyScope.read])
        manager.create_key(org_id="org-2", name="k2", scopes=[APIKeyScope.write])
        manager.create_key(org_id="org-1", name="k3", scopes=[APIKeyScope.admin])

        org1_keys = manager.list_keys("org-1")
        org2_keys = manager.list_keys("org-2")

        assert len(org1_keys) == 2
        assert len(org2_keys) == 1
        assert all(k.org_id == "org-1" for k in org1_keys)
        assert org2_keys[0].org_id == "org-2"


# ── Rate limiter tests ───────────────────────────────────────────────


class TestTenantRateLimiter:
    """TenantRateLimiter — sliding-window rate limiting."""

    @pytest.fixture()
    def limiter(self) -> TenantRateLimiter:
        return TenantRateLimiter(window_seconds=60)

    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self, limiter: TenantRateLimiter) -> None:
        allowed, remaining = await limiter.check_rate_limit("org-1", limit_override=5)
        assert allowed is True
        assert remaining == 4

    @pytest.mark.asyncio
    async def test_blocks_requests_over_limit(self, limiter: TenantRateLimiter) -> None:
        # Exhaust the limit
        for _ in range(3):
            await limiter.check_rate_limit("org-1", limit_override=3)

        allowed, remaining = await limiter.check_rate_limit("org-1", limit_override=3)
        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_returns_correct_remaining_count(self, limiter: TenantRateLimiter) -> None:
        limit = 5
        await limiter.check_rate_limit("org-1", limit_override=limit)  # remaining=4
        _, remaining = await limiter.check_rate_limit("org-1", limit_override=limit)  # remaining=3
        assert remaining == 3

    @pytest.mark.asyncio
    async def test_get_usage_stats_returns_request_count(self, limiter: TenantRateLimiter) -> None:
        await limiter.check_rate_limit("org-1", limit_override=10)
        await limiter.check_rate_limit("org-1", limit_override=10)

        stats = limiter.get_usage_stats("org-1")
        assert stats["requests_in_window"] == 2
        assert stats["org_id"] == "org-1"
        assert stats["window_seconds"] == 60

    @pytest.mark.asyncio
    async def test_rate_limit_resets_after_window_expires(self) -> None:
        # Use a tiny window so we can test expiry without sleeping
        limiter = TenantRateLimiter(window_seconds=1)

        # Exhaust the limit
        for _ in range(2):
            await limiter.check_rate_limit("org-1", limit_override=2)

        allowed, _ = await limiter.check_rate_limit("org-1", limit_override=2)
        assert allowed is False

        # Manipulate internal timestamps to simulate window expiry
        with limiter._mu:
            limiter._requests["org-1"] = [time.monotonic() - 2.0]

        allowed, remaining = await limiter.check_rate_limit("org-1", limit_override=2)
        assert allowed is True
        assert remaining == 1

    @pytest.mark.asyncio
    async def test_different_orgs_independent(self, limiter: TenantRateLimiter) -> None:
        # Exhaust org-1
        for _ in range(2):
            await limiter.check_rate_limit("org-1", limit_override=2)

        allowed_org1, _ = await limiter.check_rate_limit("org-1", limit_override=2)
        allowed_org2, _ = await limiter.check_rate_limit("org-2", limit_override=2)

        assert allowed_org1 is False
        assert allowed_org2 is True
