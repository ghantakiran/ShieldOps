"""OIDC authentication routes."""

import secrets as _secrets
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from shieldops.api.auth.service import create_access_token, hash_password
from shieldops.config import settings

logger = structlog.get_logger()

router = APIRouter()
_oidc_client: Any | None = None
_pending_states: dict[str, bool] = {}


def set_oidc_client(client: Any) -> None:
    """Inject the OIDCClient instance at startup."""
    global _oidc_client  # noqa: PLW0603
    _oidc_client = client


@router.get("/auth/oidc/login")
async def oidc_login() -> RedirectResponse:
    """Redirect to OIDC identity provider."""
    if _oidc_client is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC not configured",
        )
    url, state = await _oidc_client.get_authorization_url()
    _pending_states[state] = True
    return RedirectResponse(url=url)


@router.get("/auth/oidc/callback")
async def oidc_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
) -> dict[str, Any]:
    """Handle OIDC callback: exchange code, provision user, return JWT."""
    if _oidc_client is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC not configured",
        )

    # Verify state to prevent CSRF
    if state not in _pending_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter",
        )
    del _pending_states[state]

    # Exchange authorization code for tokens
    try:
        tokens = await _oidc_client.exchange_code(code)
    except Exception as exc:
        logger.error("oidc_code_exchange_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to exchange authorization code",
        ) from exc

    # Fetch user info from IdP
    access_token = tokens.get("access_token", "")
    try:
        userinfo = await _oidc_client.get_userinfo(access_token)
    except Exception as exc:
        logger.error("oidc_userinfo_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to fetch user info",
        ) from exc

    email = userinfo.get("email", "")
    name = userinfo.get("name", email)

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not provided by identity provider",
        )

    # Auto-provision or find existing user
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )

    user = await repository.get_user_by_email(email)
    if user is None:
        # Auto-provision with viewer role
        user = await repository.create_user(
            email=email,
            name=name,
            password_hash=hash_password(_secrets.token_urlsafe(32)),
            role="viewer",
        )
        logger.info("oidc_user_provisioned", email=email)

    # Generate JWT
    jwt_token = create_access_token(subject=user["id"], role=user["role"])

    return {
        "access_token": jwt_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expire_minutes * 60,
        "user": {
            "id": user["id"],
            "email": email,
            "name": name,
            "role": user["role"],
        },
    }
