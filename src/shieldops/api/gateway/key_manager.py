"""API key lifecycle management — create, validate, revoke, list."""

from __future__ import annotations

import hashlib
import secrets
import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from shieldops.api.gateway.models import APIKey, APIKeyScope, APIKeyStatus

logger = structlog.get_logger()

_KEY_PREFIX = "so_live_"


def _hash_key(raw_key: str) -> str:
    """Return the hex SHA-256 digest of *raw_key*."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


class APIKeyManager:
    """In-memory API key store.

    Production deployments should swap the backing dict for a database
    repository; the public interface stays the same.
    """

    def __init__(self) -> None:
        self._mu = threading.Lock()
        # key_id -> APIKey
        self._keys: dict[str, APIKey] = {}
        # hashed_key -> key_id  (lookup index)
        self._hash_index: dict[str, str] = {}

    # ── Create ───────────────────────────────────────────────

    def create_key(
        self,
        org_id: str,
        name: str,
        scopes: list[APIKeyScope],
        expires_in_days: int | None = None,
        rate_limit_per_minute: int = 60,
    ) -> tuple[str, APIKey]:
        """Create a new API key.

        Returns
        -------
        tuple[str, APIKey]
            The raw key (shown once) and the persisted metadata.

        """
        token = secrets.token_urlsafe(32)
        raw_key = f"{_KEY_PREFIX}{token}"
        hashed = _hash_key(raw_key)
        prefix = raw_key[:8]
        key_id = uuid.uuid4().hex

        now = datetime.now(UTC)
        expires_at: datetime | None = None
        if expires_in_days is not None:
            expires_at = now + timedelta(days=expires_in_days)

        api_key = APIKey(
            key_id=key_id,
            org_id=org_id,
            name=name,
            prefix=prefix,
            hashed_key=hashed,
            scopes=scopes,
            status=APIKeyStatus.active,
            rate_limit_per_minute=rate_limit_per_minute,
            created_at=now,
            expires_at=expires_at,
        )

        with self._mu:
            self._keys[key_id] = api_key
            self._hash_index[hashed] = key_id

        logger.info(
            "api_key_created",
            key_id=key_id,
            org_id=org_id,
            name=name,
            scopes=[s.value for s in scopes],
        )

        return raw_key, api_key

    # ── Validate ─────────────────────────────────────────────

    def validate_key(self, raw_key: str) -> APIKey | None:
        """Validate a raw key and return its metadata, or ``None``.

        Checks expiry and revocation status. Updates *last_used_at*
        on success.
        """
        hashed = _hash_key(raw_key)

        with self._mu:
            key_id = self._hash_index.get(hashed)
            if key_id is None:
                return None

            api_key = self._keys.get(key_id)
            if api_key is None:
                return None

            # Revoked?
            if api_key.status == APIKeyStatus.revoked:
                return None

            # Expired?
            now = datetime.now(UTC)
            if api_key.expires_at is not None and now >= api_key.expires_at:
                # Mark as expired for future lookups
                api_key = api_key.model_copy(
                    update={"status": APIKeyStatus.expired},
                )
                self._keys[key_id] = api_key
                return None

            # Touch last_used_at
            api_key = api_key.model_copy(
                update={"last_used_at": now},
            )
            self._keys[key_id] = api_key

        return api_key

    # ── Revoke ───────────────────────────────────────────────

    def revoke_key(self, key_id: str) -> bool:
        """Revoke a key by ID. Returns ``True`` if the key existed."""
        with self._mu:
            api_key = self._keys.get(key_id)
            if api_key is None:
                return False

            self._keys[key_id] = api_key.model_copy(
                update={"status": APIKeyStatus.revoked},
            )

        logger.info("api_key_revoked", key_id=key_id, org_id=api_key.org_id)
        return True

    # ── List ─────────────────────────────────────────────────

    def list_keys(self, org_id: str) -> list[APIKey]:
        """Return all keys for *org_id* with hashed_key redacted."""
        with self._mu:
            keys = [
                k.model_copy(update={"hashed_key": "***"})
                for k in self._keys.values()
                if k.org_id == org_id
            ]
        return keys

    # ── Helpers ──────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Return high-level store statistics."""
        with self._mu:
            total = len(self._keys)
            active = sum(1 for k in self._keys.values() if k.status == APIKeyStatus.active)
        return {
            "total_keys": total,
            "active_keys": active,
            "revoked_keys": total - active,
        }
