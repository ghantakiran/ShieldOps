"""FastAPI dependencies for auth — JWT + API key authentication."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shieldops.api.auth.api_keys import hash_api_key, validate_key_format
from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.api.auth.service import decode_token

logger = structlog.get_logger()

_bearer = HTTPBearer(auto_error=False)


async def _authenticate_via_api_key(
    token: str,
    repository: Any,
) -> UserResponse | None:
    """Attempt to authenticate using an API key.

    Returns a UserResponse if the key is valid, None otherwise.
    """
    if not validate_key_format(token):
        return None

    key_hash = hash_api_key(token)
    key_record = await repository.get_api_key_by_hash(key_hash)

    if key_record is None:
        return None

    # Check active status
    if not key_record.get("is_active", False):
        return None

    # Check expiry
    expires_at = key_record.get("expires_at")
    if expires_at is not None:
        if isinstance(expires_at, str):
            from datetime import datetime as _dt

            expires_at = _dt.fromisoformat(expires_at)
        if expires_at <= datetime.now(UTC):
            return None

    # Look up the owning user
    user = await repository.get_user_by_id(key_record["user_id"])
    if user is None or not user.get("is_active", True):
        return None

    # Update last_used_at in background (fire-and-forget)
    try:
        await repository.update_api_key_last_used(key_record["id"])
    except Exception:
        logger.debug(
            "api_key_last_used_update_failed",
            key_id=key_record["id"],
        )

    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=UserRole(user["role"]),
        is_active=user["is_active"],
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserResponse:
    """Extract and validate the current user.

    Authentication order:
    1. JWT bearer token (standard flow)
    2. API key (``sk-...`` prefixed bearer token)
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = credentials.credentials
    repository = getattr(request.app.state, "repository", None)

    # ── Try API key authentication first if token looks like one
    if validate_key_format(raw_token) and repository:
        user = await _authenticate_via_api_key(raw_token, repository)
        if user is not None:
            return user
        # If it looked like an API key but failed, reject it
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Standard JWT authentication ──────────────────────────
    payload = decode_token(raw_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Optionally validate against DB
    if repository:
        user_data = await repository.get_user_by_id(payload["sub"])
        if user_data is None or not user_data.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )
        return UserResponse(
            id=user_data["id"],
            email=user_data["email"],
            name=user_data["name"],
            role=UserRole(user_data["role"]),
            is_active=user_data["is_active"],
        )

    # Fallback: trust the token payload when DB is unavailable
    return UserResponse(
        id=payload["sub"],
        email=payload.get("email", ""),
        name=payload.get("name", ""),
        role=UserRole(payload.get("role", "viewer")),
        is_active=True,
    )


def require_role(
    *roles: UserRole,
) -> Callable[..., Coroutine[Any, Any, UserResponse]]:
    """Factory that returns a dependency enforcing one or more roles."""

    async def _check(
        user: UserResponse = Depends(get_current_user),
    ) -> UserResponse:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{user.role.value}' not authorized. Required: {[r.value for r in roles]}"
                ),
            )
        return user

    return _check
