"""FastAPI dependencies for auth — current user extraction and role enforcement."""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.api.auth.service import decode_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserResponse:
    """Extract and validate the current user from the JWT bearer token."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Optionally validate against DB via app.state.repository
    repository = getattr(request.app.state, "repository", None)
    if repository:
        user = await repository.get_user_by_id(payload["sub"])
        if user is None or not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )
        return UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=UserRole(user["role"]),
            is_active=user["is_active"],
        )

    # Fallback: trust the token payload when DB is unavailable
    return UserResponse(
        id=payload["sub"],
        email=payload.get("email", ""),
        name=payload.get("name", ""),
        role=UserRole(payload.get("role", "viewer")),
        is_active=True,
    )


def require_role(*roles: UserRole):
    """Factory that returns a dependency enforcing one or more roles."""
    async def _check(user: UserResponse = Depends(get_current_user)) -> UserResponse:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.value}' not authorized. Required: {[r.value for r in roles]}",
            )
        return user
    return _check
