"""Token revocation and refresh rotation.

Provides JWT token management with blacklisting, refresh rotation,
and token family tracking to detect reuse attacks.
"""

from __future__ import annotations

import secrets
import time
from typing import Protocol, runtime_checkable

import structlog
from pydantic import BaseModel, Field

from shieldops.api.auth.service import create_access_token, decode_token

logger = structlog.get_logger()


@runtime_checkable
class RevokedTokenStore(Protocol):
    """Protocol for pluggable revocation backends (e.g. Redis/DB)."""

    async def add(self, jti: str, ttl: int) -> None: ...
    async def contains(self, jti: str) -> bool: ...
    async def remove(self, jti: str) -> None: ...


class TokenBlacklist:
    """In-memory token blacklist with TTL-based expiry."""

    def __init__(self) -> None:
        self._revoked: dict[str, float] = {}  # jti -> expires_at (monotonic)

    async def add(self, jti: str, ttl: int = 3600) -> None:
        self._revoked[jti] = time.monotonic() + ttl

    async def contains(self, jti: str) -> bool:
        self._cleanup()
        return jti in self._revoked

    async def remove(self, jti: str) -> None:
        self._revoked.pop(jti, None)

    def _cleanup(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._revoked.items() if now > v]
        for k in expired:
            del self._revoked[k]

    @property
    def size(self) -> int:
        self._cleanup()
        return len(self._revoked)


class RefreshToken(BaseModel):
    """A refresh token record."""

    token: str
    user_id: str
    family_id: str  # Tracks the refresh chain
    role: str = "viewer"
    created_at: float = Field(default_factory=time.monotonic)
    used: bool = False


class TokenPair(BaseModel):
    """An access + refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int = 3600


class TokenManager:
    """Manages token issuance, refresh rotation, and revocation.

    Features:
    - Refresh token rotation: new refresh token on each use
    - Token family tracking: revokes all tokens in a chain on reuse detection
    - JTI-based blacklist for access token revocation
    """

    def __init__(
        self,
        blacklist: RevokedTokenStore | None = None,
        access_ttl: int = 3600,
        refresh_ttl: int = 86400 * 7,
    ) -> None:
        self._blacklist: RevokedTokenStore = blacklist or TokenBlacklist()
        self._refresh_tokens: dict[str, RefreshToken] = {}
        self._user_families: dict[str, set[str]] = {}  # user_id -> family_ids
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl

    async def issue_tokens(self, user_id: str, role: str = "viewer") -> TokenPair:
        """Issue a new access + refresh token pair."""
        access_token = create_access_token(subject=user_id, role=role)
        refresh = self._create_refresh_token(user_id, role)
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh.token,
            expires_in=self._access_ttl,
        )

    async def refresh(self, refresh_token: str) -> TokenPair | None:
        """Rotate tokens using a refresh token.

        Returns new token pair or None if the refresh token is invalid.
        Detects reuse attacks via token family tracking.
        """
        stored = self._refresh_tokens.get(refresh_token)
        if stored is None:
            return None

        # Reuse detection: if already used, revoke entire family
        if stored.used:
            logger.warning(
                "refresh_token_reuse_detected",
                user_id=stored.user_id,
                family_id=stored.family_id,
            )
            await self._revoke_family(stored.family_id)
            return None

        # Mark current refresh token as used
        stored.used = True

        # Issue new pair in the same family
        access_token = create_access_token(subject=stored.user_id, role=stored.role)
        new_refresh = self._create_refresh_token(
            stored.user_id,
            stored.role,
            family_id=stored.family_id,
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=new_refresh.token,
            expires_in=self._access_ttl,
        )

    async def revoke_token(self, token: str) -> bool:
        """Revoke a single access token by its JTI."""
        payload = decode_token(token)
        if payload is None:
            return False
        jti = payload.get("jti", "")
        if not jti:
            return False
        await self._blacklist.add(jti, ttl=self._access_ttl)
        logger.info("token_revoked", jti=jti)
        return True

    async def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all tokens for a user (all families)."""
        families = self._user_families.get(user_id, set())
        count = 0
        for fid in list(families):
            count += await self._revoke_family(fid)
        return count

    async def is_revoked(self, token: str) -> bool:
        """Check if an access token has been revoked."""
        payload = decode_token(token)
        if payload is None:
            return True
        jti = payload.get("jti", "")
        if not jti:
            return False
        return await self._blacklist.contains(jti)

    def _create_refresh_token(
        self,
        user_id: str,
        role: str,
        family_id: str | None = None,
    ) -> RefreshToken:
        token_str = secrets.token_urlsafe(32)
        fid = family_id or secrets.token_urlsafe(16)
        refresh = RefreshToken(
            token=token_str,
            user_id=user_id,
            family_id=fid,
            role=role,
        )
        self._refresh_tokens[token_str] = refresh
        self._user_families.setdefault(user_id, set()).add(fid)
        return refresh

    async def _revoke_family(self, family_id: str) -> int:
        """Revoke all tokens in a refresh chain."""
        to_remove = [k for k, v in self._refresh_tokens.items() if v.family_id == family_id]
        for k in to_remove:
            del self._refresh_tokens[k]
        return len(to_remove)

    @property
    def active_refresh_count(self) -> int:
        return sum(1 for v in self._refresh_tokens.values() if not v.used)
