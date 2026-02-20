"""Auth API routes — login, register, me, refresh, revoke."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    UserRole,
)
from shieldops.api.auth.service import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from shieldops.config import settings

logger = structlog.get_logger()

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
async def login(request: Request, body: LoginRequest) -> TokenResponse:
    """Authenticate a user and return a JWT token."""
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )

    user = await repository.get_user_by_email(body.email)
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )

    token = create_access_token(subject=user["id"], role=user["role"])
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: Request,
    body: RegisterRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> UserResponse:
    """Register a new user (admin only)."""
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )

    existing = await repository.get_user_by_email(body.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = await repository.create_user(
        email=body.email,
        name=body.name,
        password_hash=hash_password(body.password),
        role=body.role.value,
    )
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=UserRole(user["role"]),
        is_active=user["is_active"],
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_me(
    user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Return the currently authenticated user."""
    return user


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    user: UserResponse = Depends(get_current_user),
) -> TokenResponse:
    """Issue a new access token for an authenticated user."""
    token = create_access_token(subject=user.id, role=user.role.value)
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/auth/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    request: Request,
    user: UserResponse = Depends(get_current_user),
) -> None:
    """Revoke the current token by adding its JTI to Redis."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return
    raw_token = auth_header[7:]
    payload = decode_token(raw_token)
    if payload is None:
        return
    jti = payload.get("jti", "")
    if not jti:
        return
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url)
        ttl = settings.jwt_expire_minutes * 60
        await r.setex(f"revoked:{jti}", ttl, "1")
        await r.aclose()
    except Exception as e:
        logger.warning("token_revocation_redis_failed", error=str(e))
