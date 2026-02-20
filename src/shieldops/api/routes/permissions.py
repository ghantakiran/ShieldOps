"""Permissions API routes — inspect RBAC permission matrix."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.api.auth.permissions import DEFAULT_PERMISSIONS

router = APIRouter()


@router.get("/permissions")
async def list_my_permissions(
    user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Return all permissions for the current user's role."""
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    perms = DEFAULT_PERMISSIONS.get(role, {})
    return {
        "role": role,
        "permissions": perms,
    }


@router.get("/permissions/matrix")
async def get_permission_matrix(
    _user: UserResponse = Depends(
        require_role(UserRole.ADMIN),  # type: ignore[arg-type]
    ),
) -> dict[str, Any]:
    """Return the full permission matrix (admin only)."""
    return {
        "matrix": DEFAULT_PERMISSIONS,
    }
