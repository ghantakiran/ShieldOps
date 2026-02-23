"""Token management API routes — refresh, revoke, revoke-all."""

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from shieldops.api.auth.token_manager import TokenManager

logger = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["Token Management"])

_manager: TokenManager | None = None


def set_manager(manager: TokenManager) -> None:
    global _manager
    _manager = manager


def _get_manager() -> TokenManager:
    if _manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token manager not initialized",
        )
    return _manager


class RefreshRequest(BaseModel):
    refresh_token: str


class RevokeRequest(BaseModel):
    token: str


class RevokeAllRequest(BaseModel):
    user_id: str


@router.post("/refresh")
async def refresh_tokens(request: RefreshRequest) -> dict[str, Any]:
    """Rotate access + refresh tokens."""
    manager = _get_manager()
    pair = await manager.refresh(request.refresh_token)
    if pair is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    return pair.model_dump()


@router.post("/revoke")
async def revoke_token(request: RevokeRequest) -> dict[str, Any]:
    """Revoke a single access token."""
    manager = _get_manager()
    success = await manager.revoke_token(request.token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token",
        )
    return {"status": "revoked"}


@router.post("/revoke-all")
async def revoke_all_tokens(request: RevokeAllRequest) -> dict[str, Any]:
    """Revoke all tokens for a user."""
    manager = _get_manager()
    count = await manager.revoke_all_user_tokens(request.user_id)
    return {"status": "revoked", "tokens_revoked": count}
