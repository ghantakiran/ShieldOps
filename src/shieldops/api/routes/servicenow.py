"""API routes for ServiceNow ITSM integration.

Provides endpoints to connect, check status, receive webhooks, and
proxy incident / change-request creation into ServiceNow.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

logger = structlog.get_logger()
router = APIRouter(prefix="/integrations/servicenow")

# ── Module-level singleton ────────────────────────────────────────────

_client: Any | None = None


def set_client(client: Any) -> None:
    """Inject the :class:`ServiceNowClient` at app startup."""
    global _client
    _client = client


def _get_client() -> Any:
    if _client is None:
        raise HTTPException(
            status_code=503,
            detail="ServiceNow integration not configured",
        )
    return _client


# ── Request / response schemas ────────────────────────────────────────


class ConnectRequest(BaseModel):
    instance_url: str
    username: str
    password: str


class ConnectResponse(BaseModel):
    connected: bool
    instance_url: str = ""
    error: str = ""
    timestamp: str = ""


class CreateIncidentRequest(BaseModel):
    """Payload to create a ServiceNow incident from ShieldOps data."""

    title: str
    description: str = ""
    severity: str = "medium"
    environment: str = ""
    service: str = ""
    incident_id: str = ""
    category: str | None = None
    assignment_group: str | None = None


class CreateChangeRequest(BaseModel):
    """Payload to create a ServiceNow change request from a remediation."""

    name: str
    description: str = ""
    risk_level: str = "medium"
    environment: str = ""
    target: str = ""
    remediation_id: str = ""
    playbook: str = ""
    change_type: str = "normal"
    assignment_group: str | None = None


class WebhookPayload(BaseModel):
    sys_id: str = ""
    number: str = ""
    state: str | None = None
    table: str = "incident"
    action: str = "update"
    extra: dict[str, Any] = Field(default_factory=dict)


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post("/connect", response_model=ConnectResponse)
async def connect(
    request: ConnectRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> ConnectResponse:
    """Test connection to a ServiceNow instance and save the client.

    Only admins may configure integrations.
    """
    from shieldops.integrations.itsm.servicenow import ServiceNowClient

    client = ServiceNowClient(
        instance_url=request.instance_url,
        username=request.username,
        password=request.password,
    )
    result = await client.test_connection()

    if result.get("connected"):
        # Persist the client for subsequent requests
        global _client
        _client = client
        logger.info(
            "servicenow_connected",
            instance_url=request.instance_url,
        )

    return ConnectResponse(
        connected=result.get("connected", False),
        instance_url=result.get("instance_url", ""),
        error=result.get("error", ""),
        timestamp=result.get("timestamp", ""),
    )


@router.get("/status")
async def status(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Return current ServiceNow connection status."""
    if _client is None:
        return {"connected": False, "instance_url": None}

    result = await _client.test_connection()
    return {
        "connected": result.get("connected", False),
        "instance_url": result.get("instance_url"),
        "timestamp": result.get("timestamp"),
    }


@router.post("/webhook")
async def receive_webhook(
    request: Request,
) -> dict[str, Any]:
    """Handle incoming ServiceNow webhook notifications.

    ServiceNow Business Rules push state changes here.  This endpoint
    does NOT require JWT authentication -- it is secured via the
    ``X-ServiceNow-Token`` header validated below.
    """
    client = _get_client()

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    result = await client.handle_webhook(payload)
    return {"status": "processed", "event": result}


@router.post("/incidents")
async def create_incident(
    body: CreateIncidentRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Create a ServiceNow incident from ShieldOps data."""
    client = _get_client()
    result = await client.create_from_shieldops_incident(body.model_dump())
    return {"status": "created", "record": result}


@router.post("/change-requests")
async def create_change_request(
    body: CreateChangeRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Create a ServiceNow change request from a remediation plan."""
    client = _get_client()
    result = await client.create_change_from_remediation(body.model_dump())
    return {"status": "created", "record": result}
