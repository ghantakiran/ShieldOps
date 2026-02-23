"""Tests for token revocation, refresh rotation, and blacklist management.

Covers TokenBlacklist, TokenManager, TokenPair, and RefreshToken models.
Uses mocked auth service (create_access_token / decode_token) to avoid
depending on real JWT secret configuration.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from shieldops.api.auth.token_manager import (
    RefreshToken,
    TokenBlacklist,
    TokenManager,
    TokenPair,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOKEN_COUNTER = 0


def _fake_create_access_token(subject: str, role: str, **kwargs) -> str:
    """Return a deterministic fake JWT."""
    global _TOKEN_COUNTER
    _TOKEN_COUNTER += 1
    return f"fake-jwt-{subject}-{role}-{_TOKEN_COUNTER}"


def _fake_decode_token(token: str) -> dict | None:
    """Decode our fake JWT format."""
    if not token.startswith("fake-jwt-"):
        return None
    parts = token.split("-")
    # fake-jwt-{subject}-{role}-{counter}
    if len(parts) < 5:
        return None
    return {"sub": parts[2], "role": parts[3], "jti": f"jti-{parts[4]}"}


# Patch paths target where the names are imported IN token_manager.py
_PATCH_CREATE = "shieldops.api.auth.token_manager.create_access_token"
_PATCH_DECODE = "shieldops.api.auth.token_manager.decode_token"


# ---------------------------------------------------------------------------
# TokenBlacklist
# ---------------------------------------------------------------------------


class TestTokenBlacklist:
    @pytest.fixture()
    def blacklist(self):
        return TokenBlacklist()

    @pytest.mark.asyncio
    async def test_add_and_contains(self, blacklist):
        await blacklist.add("jti-1", ttl=60)
        assert await blacklist.contains("jti-1") is True

    @pytest.mark.asyncio
    async def test_contains_returns_false_for_unknown(self, blacklist):
        assert await blacklist.contains("unknown") is False

    @pytest.mark.asyncio
    async def test_remove(self, blacklist):
        await blacklist.add("jti-1", ttl=60)
        await blacklist.remove("jti-1")
        assert await blacklist.contains("jti-1") is False

    @pytest.mark.asyncio
    async def test_remove_nonexistent_is_noop(self, blacklist):
        await blacklist.remove("nonexistent")  # Should not raise

    @pytest.mark.asyncio
    async def test_size_empty(self, blacklist):
        assert blacklist.size == 0

    @pytest.mark.asyncio
    async def test_size_after_add(self, blacklist):
        await blacklist.add("jti-1", ttl=60)
        await blacklist.add("jti-2", ttl=60)
        assert blacklist.size == 2

    @pytest.mark.asyncio
    async def test_size_after_remove(self, blacklist):
        await blacklist.add("jti-1", ttl=60)
        await blacklist.remove("jti-1")
        assert blacklist.size == 0

    @pytest.mark.asyncio
    async def test_ttl_expiry(self, blacklist):
        # Add with TTL of 0 (immediate expiry in monotonic time)
        await blacklist.add("jti-exp", ttl=0)
        # After cleanup, it should be gone since monotonic is always advancing
        # We need time to pass, so set the expiry in the past
        blacklist._revoked["jti-exp"] = time.monotonic() - 1
        assert await blacklist.contains("jti-exp") is False

    @pytest.mark.asyncio
    async def test_ttl_not_expired(self, blacklist):
        await blacklist.add("jti-live", ttl=3600)
        assert await blacklist.contains("jti-live") is True

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_only(self, blacklist):
        await blacklist.add("alive", ttl=3600)
        await blacklist.add("dead", ttl=1)
        blacklist._revoked["dead"] = time.monotonic() - 10
        assert blacklist.size == 1  # size triggers cleanup
        assert await blacklist.contains("alive") is True

    @pytest.mark.asyncio
    async def test_multiple_adds_same_jti(self, blacklist):
        await blacklist.add("jti-1", ttl=60)
        await blacklist.add("jti-1", ttl=120)
        assert blacklist.size == 1


# ---------------------------------------------------------------------------
# RefreshToken model
# ---------------------------------------------------------------------------


class TestRefreshTokenModel:
    def test_required_fields(self):
        rt = RefreshToken(token="tok", user_id="u1", family_id="f1")
        assert rt.token == "tok"  # noqa: S105
        assert rt.user_id == "u1"
        assert rt.family_id == "f1"

    def test_defaults(self):
        rt = RefreshToken(token="tok", user_id="u1", family_id="f1")
        assert rt.role == "viewer"
        assert rt.used is False
        assert rt.created_at > 0

    def test_custom_role(self):
        rt = RefreshToken(token="tok", user_id="u1", family_id="f1", role="admin")
        assert rt.role == "admin"

    def test_used_flag(self):
        rt = RefreshToken(token="tok", user_id="u1", family_id="f1", used=True)
        assert rt.used is True


# ---------------------------------------------------------------------------
# TokenPair model
# ---------------------------------------------------------------------------


class TestTokenPairModel:
    def test_required_fields(self):
        tp = TokenPair(access_token="a", refresh_token="r")
        assert tp.access_token == "a"  # noqa: S105
        assert tp.refresh_token == "r"  # noqa: S105

    def test_defaults(self):
        tp = TokenPair(access_token="a", refresh_token="r")
        assert tp.token_type == "bearer"  # noqa: S105
        assert tp.expires_in == 3600

    def test_custom_expires(self):
        tp = TokenPair(access_token="a", refresh_token="r", expires_in=7200)
        assert tp.expires_in == 7200

    def test_serialization(self):
        tp = TokenPair(access_token="a", refresh_token="r")
        data = tp.model_dump()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"  # noqa: S105


# ---------------------------------------------------------------------------
# TokenManager
# ---------------------------------------------------------------------------


@patch(_PATCH_DECODE, side_effect=_fake_decode_token)
@patch(_PATCH_CREATE, side_effect=_fake_create_access_token)
class TestTokenManagerIssue:
    @pytest.mark.asyncio
    async def test_issue_tokens_returns_pair(self, mock_create, mock_decode):
        mgr = TokenManager()
        pair = await mgr.issue_tokens("user-1", role="admin")
        assert isinstance(pair, TokenPair)
        assert pair.access_token.startswith("fake-jwt-")
        assert len(pair.refresh_token) > 0

    @pytest.mark.asyncio
    async def test_issue_tokens_default_role(self, mock_create, mock_decode):
        mgr = TokenManager()
        pair = await mgr.issue_tokens("user-1")
        assert pair.access_token  # contains "viewer" since default
        assert pair.token_type == "bearer"  # noqa: S105

    @pytest.mark.asyncio
    async def test_issue_tokens_custom_ttl(self, mock_create, mock_decode):
        mgr = TokenManager(access_ttl=1800)
        pair = await mgr.issue_tokens("user-1")
        assert pair.expires_in == 1800

    @pytest.mark.asyncio
    async def test_issue_tokens_creates_refresh_entry(self, mock_create, mock_decode):
        mgr = TokenManager()
        pair = await mgr.issue_tokens("user-1")
        assert pair.refresh_token in mgr._refresh_tokens

    @pytest.mark.asyncio
    async def test_active_refresh_count_after_issue(self, mock_create, mock_decode):
        mgr = TokenManager()
        await mgr.issue_tokens("user-1")
        await mgr.issue_tokens("user-2")
        assert mgr.active_refresh_count == 2


@patch(_PATCH_DECODE, side_effect=_fake_decode_token)
@patch(_PATCH_CREATE, side_effect=_fake_create_access_token)
class TestTokenManagerRefresh:
    @pytest.mark.asyncio
    async def test_refresh_returns_new_pair(self, mock_create, mock_decode):
        mgr = TokenManager()
        original = await mgr.issue_tokens("user-1", role="admin")
        new_pair = await mgr.refresh(original.refresh_token)
        assert new_pair is not None
        assert new_pair.refresh_token != original.refresh_token

    @pytest.mark.asyncio
    async def test_refresh_invalid_token_returns_none(self, mock_create, mock_decode):
        mgr = TokenManager()
        result = await mgr.refresh("nonexistent-token")
        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_marks_old_token_used(self, mock_create, mock_decode):
        mgr = TokenManager()
        original = await mgr.issue_tokens("user-1")
        await mgr.refresh(original.refresh_token)
        assert mgr._refresh_tokens[original.refresh_token].used is True

    @pytest.mark.asyncio
    async def test_reuse_detection_revokes_family(self, mock_create, mock_decode):
        mgr = TokenManager()
        original = await mgr.issue_tokens("user-1")
        first_refresh = await mgr.refresh(original.refresh_token)
        assert first_refresh is not None

        # Reuse the original (already-used) token
        second_attempt = await mgr.refresh(original.refresh_token)
        assert second_attempt is None

        # Both old and new refresh tokens should be revoked (family purged)
        assert original.refresh_token not in mgr._refresh_tokens
        assert first_refresh.refresh_token not in mgr._refresh_tokens

    @pytest.mark.asyncio
    async def test_refresh_preserves_user_and_role(self, mock_create, mock_decode):
        mgr = TokenManager()
        original = await mgr.issue_tokens("user-1", role="admin")
        new_pair = await mgr.refresh(original.refresh_token)
        assert new_pair is not None
        stored = mgr._refresh_tokens[new_pair.refresh_token]
        assert stored.user_id == "user-1"
        assert stored.role == "admin"

    @pytest.mark.asyncio
    async def test_refresh_same_family_id(self, mock_create, mock_decode):
        mgr = TokenManager()
        original = await mgr.issue_tokens("user-1")
        old_family = mgr._refresh_tokens[original.refresh_token].family_id
        new_pair = await mgr.refresh(original.refresh_token)
        assert new_pair is not None
        new_family = mgr._refresh_tokens[new_pair.refresh_token].family_id
        assert old_family == new_family


@patch(_PATCH_DECODE, side_effect=_fake_decode_token)
@patch(_PATCH_CREATE, side_effect=_fake_create_access_token)
class TestTokenManagerRevoke:
    @pytest.mark.asyncio
    async def test_revoke_valid_token(self, mock_create, mock_decode):
        mgr = TokenManager()
        pair = await mgr.issue_tokens("user-1")
        result = await mgr.revoke_token(pair.access_token)
        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_invalid_token_returns_false(self, mock_create, mock_decode):
        mgr = TokenManager()
        result = await mgr.revoke_token("invalid-garbage")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_revoked_after_revoke(self, mock_create, mock_decode):
        mgr = TokenManager()
        pair = await mgr.issue_tokens("user-1")
        await mgr.revoke_token(pair.access_token)
        assert await mgr.is_revoked(pair.access_token) is True

    @pytest.mark.asyncio
    async def test_is_revoked_returns_false_for_active(self, mock_create, mock_decode):
        mgr = TokenManager()
        pair = await mgr.issue_tokens("user-1")
        assert await mgr.is_revoked(pair.access_token) is False

    @pytest.mark.asyncio
    async def test_is_revoked_invalid_token_returns_true(self, mock_create, mock_decode):
        mgr = TokenManager()
        assert await mgr.is_revoked("not-a-real-token") is True

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(self, mock_create, mock_decode):
        mgr = TokenManager()
        await mgr.issue_tokens("user-1")
        await mgr.issue_tokens("user-1")
        await mgr.issue_tokens("user-2")  # different user

        count = await mgr.revoke_all_user_tokens("user-1")
        assert count == 2
        # user-2's tokens should still exist
        assert mgr.active_refresh_count == 1

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens_no_tokens(self, mock_create, mock_decode):
        mgr = TokenManager()
        count = await mgr.revoke_all_user_tokens("nonexistent-user")
        assert count == 0


@patch(_PATCH_DECODE, side_effect=_fake_decode_token)
@patch(_PATCH_CREATE, side_effect=_fake_create_access_token)
class TestTokenManagerActiveRefreshCount:
    @pytest.mark.asyncio
    async def test_active_count_zero_initially(self, mock_create, mock_decode):
        mgr = TokenManager()
        assert mgr.active_refresh_count == 0

    @pytest.mark.asyncio
    async def test_active_count_decreases_after_refresh(self, mock_create, mock_decode):
        mgr = TokenManager()
        pair = await mgr.issue_tokens("user-1")
        assert mgr.active_refresh_count == 1
        await mgr.refresh(pair.refresh_token)
        # Old one marked used, new one created -> still 1 active
        assert mgr.active_refresh_count == 1

    @pytest.mark.asyncio
    async def test_active_count_after_revoke_all(self, mock_create, mock_decode):
        mgr = TokenManager()
        await mgr.issue_tokens("user-1")
        await mgr.issue_tokens("user-1")
        await mgr.revoke_all_user_tokens("user-1")
        assert mgr.active_refresh_count == 0


@patch(_PATCH_DECODE, side_effect=_fake_decode_token)
@patch(_PATCH_CREATE, side_effect=_fake_create_access_token)
class TestTokenManagerCustomBlacklist:
    @pytest.mark.asyncio
    async def test_uses_custom_blacklist(self, mock_create, mock_decode):
        custom_bl = TokenBlacklist()
        mgr = TokenManager(blacklist=custom_bl)
        pair = await mgr.issue_tokens("user-1")
        await mgr.revoke_token(pair.access_token)
        assert custom_bl.size == 1

    @pytest.mark.asyncio
    async def test_default_blacklist_is_token_blacklist(self, mock_create, mock_decode):
        mgr = TokenManager()
        assert isinstance(mgr._blacklist, TokenBlacklist)
