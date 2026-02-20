"""User management API routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from shieldops.api.auth.dependencies import require_role
from shieldops.api.auth.models import UserRole

router = APIRouter()


@router.get("/users")
async def list_users(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _user: Any = Depends(require_role(UserRole.ADMIN)),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """List all users (admin only)."""
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    users = await repository.list_users(limit=limit, offset=offset)
    return {
        "items": users,
        "total": len(users),
        "limit": limit,
        "offset": offset,
    }


@router.get("/users/{user_id}")
async def get_user(
    request: Request,
    user_id: str,
    _user: Any = Depends(require_role(UserRole.ADMIN)),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Get a specific user by ID."""
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    user: dict[str, Any] | None = await repository.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}/role")
async def update_user_role(
    request: Request,
    user_id: str,
    body: dict[str, str],
    _user: Any = Depends(require_role(UserRole.ADMIN)),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Update a user's role."""
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    role = body.get("role", "")
    if role not in ("admin", "operator", "viewer"):
        raise HTTPException(
            status_code=400,
            detail="Invalid role. Must be: admin, operator, viewer",
        )
    updated: dict[str, Any] | None = await repository.update_user_role(user_id, role)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return updated


@router.put("/users/{user_id}/active")
async def toggle_user_active(
    request: Request,
    user_id: str,
    body: dict[str, bool],
    _user: Any = Depends(require_role(UserRole.ADMIN)),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Activate or deactivate a user."""
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    is_active = body.get("is_active", True)
    updated: dict[str, Any] | None = await repository.update_user_active(user_id, is_active)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return updated
