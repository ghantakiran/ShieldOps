"""Auth API routes — login, register, me."""

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
    hash_password,
    verify_password,
)
from shieldops.config import settings

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
async def get_me(user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user."""
    return user
