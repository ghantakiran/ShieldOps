"""API routes for Jira bidirectional sync integration.

Provides endpoints to connect, query status, create issues,
and receive incoming Jira webhooks.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from shieldops.integrations.itsm.jira import (
    JiraAuthError,
    JiraClient,
    JiraConfig,
    JiraError,
    JiraNotFoundError,
)

logger = structlog.get_logger()
router = APIRouter()

# ── Module-level dependency injection ────────────────────────────────

_client: JiraClient | None = None
_config: JiraConfig | None = None


def set_client(client: JiraClient) -> None:
    """Inject the JiraClient singleton at application startup."""
    global _client
    _client = client


def set_config(config: JiraConfig) -> None:
    """Store the active Jira configuration."""
    global _config
    _config = config


def _get_client() -> JiraClient:
    """Return the configured client or raise 503."""
    if _client is None:
        raise HTTPException(
            status_code=503,
            detail="Jira integration is not configured",
        )
    return _client


# ── Request / Response Models ────────────────────────────────────────


class ConnectRequest(BaseModel):
    """Payload for POST /integrations/jira/connect."""

    base_url: str
    email: str
    api_token: str
    project_key: str = "OPS"
    issue_type_mapping: dict[str, str] = Field(default_factory=dict)
    priority_mapping: dict[str, str] = Field(default_factory=dict)
    status_to_jira: dict[str, str] = Field(default_factory=dict)
    status_from_jira: dict[str, str] = Field(default_factory=dict)
    field_mapping: dict[str, str] = Field(default_factory=dict)


class ConnectResponse(BaseModel):
    status: str
    message: str
    account: dict[str, Any] = Field(default_factory=dict)


class StatusResponse(BaseModel):
    connected: bool
    base_url: str | None = None
    project_key: str | None = None
    email: str | None = None
    status_mapping: dict[str, str] = Field(default_factory=dict)
    priority_mapping: dict[str, str] = Field(default_factory=dict)


class CreateIssueRequest(BaseModel):
    """Payload for POST /integrations/jira/issues."""

    incident_id: str = ""
    title: str = ""
    alert_name: str = ""
    description: str = ""
    severity: str = "medium"
    service: str = ""
    environment: str = "production"
    type: str = "incident"
    extra_fields: dict[str, Any] = Field(default_factory=dict)


# ── Routes ───────────────────────────────────────────────────────────


@router.post("/connect", response_model=ConnectResponse)
async def connect_jira(body: ConnectRequest) -> ConnectResponse:
    """Test connection to Jira Cloud and save configuration.

    Creates a new JiraClient with the provided credentials, verifies
    connectivity by calling ``/rest/api/3/myself``, and stores the
    client + config for subsequent requests.
    """
    client = JiraClient(
        base_url=body.base_url,
        email=body.email,
        api_token=body.api_token,
        project_key=body.project_key,
        status_to_jira=body.status_to_jira or None,
        status_from_jira=body.status_from_jira or None,
        priority_mapping=body.priority_mapping or None,
        issue_type_mapping=body.issue_type_mapping or None,
        field_mapping=body.field_mapping or None,
    )

    try:
        account = await client.test_connection()
    except JiraAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except JiraError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("jira_connect_failed", error=str(exc))
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to Jira: {exc}",
        ) from exc

    # Persist client + config
    config = JiraConfig(
        base_url=body.base_url,
        email=body.email,
        api_token=body.api_token,
        project_key=body.project_key,
        issue_type_mapping=body.issue_type_mapping or dict(client.issue_type_mapping),
        priority_mapping=body.priority_mapping or dict(client.priority_mapping),
        status_to_jira=body.status_to_jira or dict(client.status_to_jira),
        status_from_jira=body.status_from_jira or dict(client.status_from_jira),
        field_mapping=body.field_mapping or dict(client.field_mapping),
    )
    set_client(client)
    set_config(config)

    logger.info(
        "jira_connected",
        account_id=account.get("account_id"),
        project_key=body.project_key,
    )
    return ConnectResponse(
        status="connected",
        message=f"Connected as {account.get('display_name', 'unknown')}",
        account=account,
    )


@router.get("/status", response_model=StatusResponse)
async def jira_status() -> StatusResponse:
    """Return current Jira connection status and configuration summary."""
    if _client is None or _config is None:
        return StatusResponse(connected=False)

    return StatusResponse(
        connected=True,
        base_url=_config.base_url,
        project_key=_config.project_key,
        email=_config.email,
        status_mapping=_config.status_to_jira,
        priority_mapping=_config.priority_mapping,
    )


@router.post("/webhook")
async def receive_webhook(request: Request) -> dict[str, Any]:
    """Handle incoming Jira webhooks (status changes, comments, etc.).

    Jira sends POST requests here when issues are updated.
    The client maps Jira statuses back to ShieldOps statuses.
    """
    client = _get_client()

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    try:
        result = await client.handle_webhook(payload)
    except Exception as exc:
        logger.error("jira_webhook_error", error=str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Webhook processing failed: {exc}",
        ) from exc

    return result


@router.post("/issues")
async def create_issue(body: CreateIssueRequest) -> dict[str, Any]:
    """Create a Jira issue from a ShieldOps incident."""
    client = _get_client()

    incident = body.model_dump()
    # Merge extra_fields into the top-level dict
    extra = incident.pop("extra_fields", {})
    incident.update(extra)

    try:
        result = await client.create_from_incident(incident)
    except JiraAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except JiraError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    return result


@router.get("/issues/{issue_key}")
async def get_issue(issue_key: str) -> dict[str, Any]:
    """Retrieve a Jira issue by key (e.g., OPS-123)."""
    client = _get_client()

    try:
        raw = await client.get_issue(issue_key)
    except JiraNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except JiraAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except JiraError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    parsed = client.parse_issue(raw)
    return parsed.model_dump()
