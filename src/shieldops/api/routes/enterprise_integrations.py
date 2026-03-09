"""Enterprise Integrations API endpoints.

Provides REST endpoints for managing, monitoring, and diagnosing
enterprise integration connectors (SIEM, ITSM, CI/CD, cloud providers).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    status,
)
from pydantic import BaseModel, Field

from shieldops.agents.enterprise_integration.runner import IntegrationRunner
from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

if TYPE_CHECKING:
    from shieldops.db.repository import Repository

router = APIRouter()

_runner: IntegrationRunner | None = None
_repository: Repository | None = None


def get_runner() -> IntegrationRunner:
    """Get or create the enterprise integrations runner singleton."""
    global _runner
    if _runner is None:
        _runner = IntegrationRunner()
    return _runner


def set_runner(runner: IntegrationRunner) -> None:
    """Override the runner instance (used for testing and dependency injection)."""
    global _runner
    _runner = runner


def set_repository(repo: Repository | None) -> None:
    """Set the persistence repository for read queries."""
    global _repository
    _repository = repo


# --- Request/Response models ---


class IntegrationConfigUpdate(BaseModel):
    """Request body to update an integration's configuration."""

    name: str | None = Field(None, description="Display name for the integration")
    enabled: bool | None = Field(None, description="Whether the integration is active")
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration key-value pairs to merge",
    )
    credentials_ref: str | None = Field(
        None,
        description="Secret manager reference for credentials",
    )
    sync_interval_seconds: int | None = Field(
        None, ge=60, le=86400, description="Sync interval in seconds (60-86400)"
    )


class SyncRequest(BaseModel):
    """Request body to trigger a manual sync."""

    full_sync: bool = Field(
        default=False,
        description="If true, perform a full sync instead of incremental",
    )
    resources: list[str] = Field(
        default_factory=list,
        description="Specific resource types to sync (empty = all)",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntegrationSummary(BaseModel):
    """Brief integration summary for list responses."""

    integration_id: str
    status: str = "unknown"
    last_action: str | None = None
    error: str | None = None


class IntegrationHealthResponse(BaseModel):
    """Health check result for an integration."""

    integration_id: str
    healthy: bool
    status: str
    latency_ms: int = 0
    checked_at: str


# --- Endpoints ---


@router.post("/check/{integration_id}", response_model=IntegrationHealthResponse)
async def run_health_check(
    integration_id: str,
    _user: UserResponse = Depends(
        require_role(UserRole.ADMIN, UserRole.OPERATOR),
    ),
) -> IntegrationHealthResponse:
    """Run a health check on a specific integration."""
    runner = get_runner()
    state = await runner.check_integration(integration_id)
    health = state.health
    return IntegrationHealthResponse(
        integration_id=integration_id,
        healthy=health is not None and health.status == "connected",
        status=health.status if health else "unknown",
        latency_ms=int(health.latency_ms) if health else 0,
        checked_at=datetime.now(UTC).isoformat(),
    )


@router.post("/diagnose/{integration_id}")
async def diagnose_integration(
    integration_id: str,
    _user: UserResponse = Depends(
        require_role(UserRole.ADMIN, UserRole.OPERATOR),
    ),
) -> dict[str, Any]:
    """Run a full diagnostic on an integration."""
    runner = get_runner()
    state = await runner.diagnose_integration(integration_id)
    return {
        "integration_id": integration_id,
        "diagnosis": {
            "diagnostics": [d.model_dump() for d in state.diagnostics],
            "recommendations": state.recommendations,
            "error": state.error,
        },
        "diagnosed_at": datetime.now(UTC).isoformat(),
    }


@router.post(
    "/sync/{integration_id}",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_sync(
    integration_id: str,
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    _user: UserResponse = Depends(
        require_role(UserRole.ADMIN, UserRole.OPERATOR),
    ),
) -> dict[str, Any]:
    """Trigger a manual sync for an integration."""
    runner = get_runner()
    background_tasks.add_task(runner.sync_integration, integration_id)
    return {
        "status": "accepted",
        "integration_id": integration_id,
        "full_sync": request.full_sync,
        "message": f"Sync started for {integration_id}.",
    }


@router.put("/{integration_id}/config")
async def update_config(
    integration_id: str,
    request: IntegrationConfigUpdate,
    _user: UserResponse = Depends(
        require_role(UserRole.ADMIN),
    ),
) -> dict[str, Any]:
    """Update an integration's configuration."""
    runner = get_runner()
    config_updates: dict[str, Any] = {}
    if request.name is not None:
        config_updates["name"] = request.name
    if request.enabled is not None:
        config_updates["enabled"] = request.enabled
    if request.config:
        config_updates.update(request.config)
    if request.credentials_ref is not None:
        config_updates["credentials_ref"] = request.credentials_ref
    if request.sync_interval_seconds is not None:
        config_updates["sync_interval_seconds"] = request.sync_interval_seconds

    state = await runner.configure_integration(
        integration_id=integration_id,
        config=config_updates,
    )
    return {
        "integration_id": integration_id,
        "updated": True,
        "result": state.result,
    }


@router.get("/", response_model=list[IntegrationSummary])
async def list_integrations(
    _user: UserResponse = Depends(get_current_user),
) -> list[IntegrationSummary]:
    """List all integrations with current status."""
    runner = get_runner()
    items = await runner.list_integrations()
    return [IntegrationSummary(**item) for item in items]


@router.get("/{integration_id}/health", response_model=IntegrationHealthResponse)
async def get_health_status(
    integration_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> IntegrationHealthResponse:
    """Get health status for an integration."""
    runner = get_runner()
    health = await runner.get_integration_health(integration_id)
    return IntegrationHealthResponse(
        integration_id=integration_id,
        healthy=health.status == "connected",
        status=health.status,
        latency_ms=int(health.latency_ms),
        checked_at=datetime.now(UTC).isoformat(),
    )


@router.get("/runs")
async def list_runs(
    _user: UserResponse = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List all integration workflow runs."""
    runner = get_runner()
    return runner.list_runs()
