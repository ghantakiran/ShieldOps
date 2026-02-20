"""Fine-grained permission checking for API routes."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import structlog
from fastapi import Depends, HTTPException, Request, status

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

logger = structlog.get_logger()

# Default permission matrix: role -> resource -> actions
DEFAULT_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "admin": {
        "*": ["*"],  # admin can do everything
    },
    "operator": {
        "investigations": ["read", "create", "update"],
        "remediations": ["read", "create", "update"],
        "security_scans": ["read", "create"],
        "vulnerabilities": ["read", "update"],
        "playbooks": ["read", "trigger"],
        "agents": ["read", "start", "stop"],
        "audit_log": ["read"],
        "analytics": ["read"],
        "cost": ["read"],
    },
    "viewer": {
        "investigations": ["read"],
        "remediations": ["read"],
        "security_scans": ["read"],
        "vulnerabilities": ["read"],
        "playbooks": ["read"],
        "agents": ["read"],
        "audit_log": ["read"],
        "analytics": ["read"],
        "cost": ["read"],
    },
}


def check_permission(role: str, resource: str, action: str) -> bool:
    """Check if a role has permission for a resource+action.

    Returns True when the role's permission entry grants access,
    including wildcard matches (``"*"`` resource or ``"*"`` action).
    """
    role_perms = DEFAULT_PERMISSIONS.get(role, {})
    # Check wildcard resource with wildcard action (admin)
    if "*" in role_perms and "*" in role_perms["*"]:
        return True
    resource_actions = role_perms.get(resource, [])
    return action in resource_actions or "*" in resource_actions


def require_permission(
    resource: str,
    action: str,
) -> Callable[..., Coroutine[Any, Any, UserResponse]]:
    """FastAPI dependency factory that enforces resource+action permission.

    Usage::

        @router.get("/investigations")
        async def list_investigations(
            user=Depends(require_permission("investigations", "read")),
        ):
            ...
    """

    async def _check(
        request: Request,
        user: UserResponse = Depends(get_current_user),
    ) -> UserResponse:
        role = user.role.value if hasattr(user.role, "value") else str(user.role)
        if not check_permission(role, resource, action):
            logger.warning(
                "permission_denied",
                user_id=user.id,
                role=role,
                resource=resource,
                action=action,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(f"Permission denied: {resource}:{action} requires higher role"),
            )
        return user

    return _check
