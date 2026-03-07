"""API Gateway management routes — key CRUD, usage, tenant config."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from shieldops.api.gateway.key_manager import APIKeyManager
from shieldops.api.gateway.models import (
    APIKeyScope,
    APIKeyStatus,
    TenantConfig,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/gateway", tags=["API Gateway"])

# Module-level singletons; wired at app startup.
_key_manager: APIKeyManager | None = None
_tenant_configs: dict[str, TenantConfig] = {}


def configure(
    key_manager: APIKeyManager,
    tenant_configs: dict[str, TenantConfig] | None = None,
) -> None:
    """Wire dependencies at application startup."""
    global _key_manager, _tenant_configs  # noqa: PLW0603
    _key_manager = key_manager
    if tenant_configs is not None:
        _tenant_configs = tenant_configs


def _get_key_manager() -> APIKeyManager:
    if _key_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API gateway not initialised",
        )
    return _key_manager


# ── Request / Response schemas ───────────────────────────────


class CreateKeyRequest(BaseModel):
    """Body for POST /gateway/keys."""

    name: str = Field(..., min_length=1, max_length=255)
    scopes: list[APIKeyScope] = Field(
        default_factory=lambda: [APIKeyScope.read],
    )
    expires_in_days: int | None = Field(
        default=90,
        ge=1,
        le=365,
        description="Days until the key expires (None = never)",
    )
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10_000)


class CreateKeyResponse(BaseModel):
    """Returned once at creation — contains the raw key."""

    raw_key: str
    key_id: str
    org_id: str
    name: str
    prefix: str
    scopes: list[APIKeyScope]
    status: APIKeyStatus
    rate_limit_per_minute: int
    expires_at: str | None = None
    created_at: str


class KeySummary(BaseModel):
    """Safe key summary — never exposes the hash."""

    key_id: str
    org_id: str
    name: str
    prefix: str
    scopes: list[APIKeyScope]
    status: APIKeyStatus
    rate_limit_per_minute: int
    created_at: str
    expires_at: str | None = None
    last_used_at: str | None = None


# ── Endpoints ────────────────────────────────────────────────


@router.post("/keys", status_code=status.HTTP_201_CREATED)
async def create_key(
    body: CreateKeyRequest,
    request: Request,
) -> CreateKeyResponse:
    """Create a new API key. The raw key is returned **once**."""
    org_id = _require_org_id(request)
    manager = _get_key_manager()

    raw_key, api_key = manager.create_key(
        org_id=org_id,
        name=body.name,
        scopes=body.scopes,
        expires_in_days=body.expires_in_days,
        rate_limit_per_minute=body.rate_limit_per_minute,
    )

    logger.info(
        "gateway_key_created",
        key_id=api_key.key_id,
        org_id=org_id,
    )

    return CreateKeyResponse(
        raw_key=raw_key,
        key_id=api_key.key_id,
        org_id=api_key.org_id,
        name=api_key.name,
        prefix=api_key.prefix,
        scopes=api_key.scopes,
        status=api_key.status,
        rate_limit_per_minute=api_key.rate_limit_per_minute,
        expires_at=(api_key.expires_at.isoformat() if api_key.expires_at else None),
        created_at=api_key.created_at.isoformat(),
    )


@router.get("/keys")
async def list_keys(request: Request) -> dict[str, Any]:
    """List all API keys for the current organisation."""
    org_id = _require_org_id(request)
    manager = _get_key_manager()

    keys = manager.list_keys(org_id)
    items = [
        KeySummary(
            key_id=k.key_id,
            org_id=k.org_id,
            name=k.name,
            prefix=k.prefix,
            scopes=k.scopes,
            status=k.status,
            rate_limit_per_minute=k.rate_limit_per_minute,
            created_at=k.created_at.isoformat(),
            expires_at=(k.expires_at.isoformat() if k.expires_at else None),
            last_used_at=(k.last_used_at.isoformat() if k.last_used_at else None),
        ).model_dump()
        for k in keys
    ]

    return {"items": items, "total": len(items)}


@router.delete(
    "/keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def revoke_key(key_id: str, request: Request) -> None:
    """Revoke an API key by ID."""
    _require_org_id(request)
    manager = _get_key_manager()

    revoked = manager.revoke_key(key_id)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    logger.info("gateway_key_revoked", key_id=key_id)


@router.get("/usage")
async def get_usage(request: Request) -> dict[str, Any]:
    """Return usage statistics for the current organisation."""
    org_id = _require_org_id(request)

    # Pull usage from the middleware if attached to the app
    middleware = _find_gateway_middleware(request)
    if middleware is None:
        return {
            "org_id": org_id,
            "records": [],
            "total": 0,
        }

    records = middleware.get_usage_records(org_id=org_id)
    return {
        "org_id": org_id,
        "records": records,
        "total": len(records),
    }


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    """Return the tenant configuration for the current organisation."""
    org_id = _require_org_id(request)

    config = _tenant_configs.get(org_id)
    if config is None:
        # Return sensible defaults when no explicit config exists
        config = TenantConfig(org_id=org_id)

    return config.model_dump()


# ── Helpers ──────────────────────────────────────────────────


def _require_org_id(request: Request) -> str:
    """Extract org_id from request state or raise 401."""
    org_id: str | None = getattr(request.state, "org_id", None)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Organisation context required",
        )
    return org_id


def _find_gateway_middleware(
    request: Request,
) -> Any | None:
    """Walk the app middleware stack to find APIGatewayMiddleware."""
    from shieldops.api.gateway.middleware import APIGatewayMiddleware

    app: Any = request.app
    # Starlette wraps middleware; walk the .app chain
    while app is not None:
        if isinstance(app, APIGatewayMiddleware):
            return app
        app = getattr(app, "app", None)
    return None
