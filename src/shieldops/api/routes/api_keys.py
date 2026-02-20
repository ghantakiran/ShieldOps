"""API key management routes — create, list, revoke."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from pydantic import BaseModel, Field

from shieldops.api.auth.api_keys import (
    generate_api_key,
    validate_scopes,
)
from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/api-keys", tags=["API Keys"])

_repository: Any | None = None


def set_repository(repo: Any) -> None:
    """Set the repository instance for API key routes."""
    global _repository  # noqa: PLW0603
    _repository = repo


def _get_repo(request: Request) -> Any:
    repo = _repository or getattr(request.app.state, "repository", None)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    return repo


# ── Request / Response bodies ────────────────────────────────


class CreateAPIKeyBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class APIKeyCreatedResponse(BaseModel):
    """Returned only at creation time — contains the full key."""

    id: str
    key: str  # full key, shown only once
    key_prefix: str
    name: str
    scopes: list[str]
    expires_at: str | None = None
    created_at: str | None = None


class APIKeySummary(BaseModel):
    """Safe summary — never includes the full key or hash."""

    id: str
    key_prefix: str
    name: str
    scopes: list[str]
    expires_at: str | None = None
    last_used_at: str | None = None
    is_active: bool
    created_at: str | None = None


# ── Endpoints ────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_api_key_endpoint(
    request: Request,
    body: CreateAPIKeyBody,
    user: UserResponse = Depends(get_current_user),
) -> APIKeyCreatedResponse:
    """Create a new API key. The full key is returned ONCE."""
    repo = _get_repo(request)

    # Validate scopes
    try:
        validate_scopes(body.scopes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Reject already-expired keys
    if body.expires_at is not None and body.expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="expires_at must be in the future",
        )

    full_key, key_prefix, key_hash = generate_api_key()

    record = await repo.create_api_key(
        user_id=user.id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name=body.name,
        scopes=body.scopes,
        expires_at=body.expires_at,
    )

    logger.info(
        "api_key_issued",
        key_id=record["id"],
        user_id=user.id,
        scopes=body.scopes,
    )

    return APIKeyCreatedResponse(
        id=record["id"],
        key=full_key,
        key_prefix=key_prefix,
        name=record["name"],
        scopes=record["scopes"],
        expires_at=record["expires_at"],
        created_at=record["created_at"],
    )


@router.get("")
async def list_api_keys(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List the caller's API keys (prefix, name, scopes only)."""
    repo = _get_repo(request)

    keys = await repo.list_api_keys_for_user(user_id=user.id, limit=limit, offset=offset)

    # Strip key_hash from response — never expose it
    items = [
        APIKeySummary(
            id=k["id"],
            key_prefix=k["key_prefix"],
            name=k["name"],
            scopes=k["scopes"],
            expires_at=k["expires_at"],
            last_used_at=k["last_used_at"],
            is_active=k["is_active"],
            created_at=k["created_at"],
        ).model_dump()
        for k in keys
    ]

    return {
        "items": items,
        "total": len(items),
        "limit": limit,
        "offset": offset,
    }


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def revoke_api_key_endpoint(
    request: Request,
    key_id: str,
    user: UserResponse = Depends(get_current_user),
) -> None:
    """Revoke an API key. Only the key's owner can revoke it."""
    repo = _get_repo(request)

    revoked = await repo.revoke_api_key(key_id=key_id, user_id=user.id)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    logger.info(
        "api_key_revoked_by_user",
        key_id=key_id,
        user_id=user.id,
    )
