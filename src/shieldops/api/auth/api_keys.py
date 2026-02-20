"""API key generation, validation, and management."""

from __future__ import annotations

import hashlib
import secrets

KEY_PREFIX = "sk-"

VALID_SCOPES = frozenset({"read", "write", "admin"})


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (full_key, key_prefix, key_hash).
        The full_key is shown once at creation time and never stored.
    """
    raw = secrets.token_urlsafe(32)
    full_key = f"{KEY_PREFIX}{raw}"
    key_prefix = full_key[:8]
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, key_prefix, key_hash


def hash_api_key(key: str) -> str:
    """Hash an API key for database lookup."""
    return hashlib.sha256(key.encode()).hexdigest()


def validate_key_format(key: str) -> bool:
    """Check if a string looks like a valid API key."""
    return key.startswith(KEY_PREFIX) and len(key) > 10


def validate_scopes(scopes: list[str]) -> list[str]:
    """Validate and return only recognised scopes.

    Raises:
        ValueError: If any scope is not in VALID_SCOPES.
    """
    invalid = set(scopes) - VALID_SCOPES
    if invalid:
        raise ValueError(f"Invalid scopes: {sorted(invalid)}. Allowed: {sorted(VALID_SCOPES)}")
    return scopes
