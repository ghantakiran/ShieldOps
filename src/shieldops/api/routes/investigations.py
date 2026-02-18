"""Investigation API endpoints.

Provides REST endpoints for triggering, tracking, and managing
investigation agent workflows.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from shieldops.agents.investigation.runner import InvestigationRunner
from shieldops.models.base import AlertContext

router = APIRouter()

# Application-level runner instance (initialized on first use or at startup)
_runner: InvestigationRunner | None = None


def get_runner() -> InvestigationRunner:
    """Get or create the investigation runner singleton."""
    global _runner
    if _runner is None:
        _runner = InvestigationRunner()
    return _runner


def set_runner(runner: InvestigationRunner) -> None:
    """Override the runner instance (used for testing and dependency injection)."""
    global _runner
    _runner = runner


# --- Request/Response models ---


class TriggerInvestigationRequest(BaseModel):
    """Request body to trigger a new investigation."""

    alert_id: str
    alert_name: str
    severity: str = "warning"
    source: str = "api"
    resource_id: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    description: str | None = None


class InvestigationSummary(BaseModel):
    """Brief investigation summary for list responses."""

    investigation_id: str
    alert_id: str
    alert_name: str
    status: str
    confidence: float
    hypotheses_count: int
    duration_ms: int
    error: str | None = None


# --- Endpoints ---


@router.post("/investigations", status_code=202)
async def trigger_investigation(
    request: TriggerInvestigationRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Trigger a new investigation for an alert.

    The investigation runs asynchronously. Returns immediately with a 202
    and the investigation can be tracked via the list/detail endpoints.
    """
    alert = AlertContext(
        alert_id=request.alert_id,
        alert_name=request.alert_name,
        severity=request.severity,
        source=request.source,
        resource_id=request.resource_id,
        labels=request.labels,
        annotations=request.annotations,
        triggered_at=datetime.now(timezone.utc),
        description=request.description,
    )

    runner = get_runner()

    # Run investigation in background so the API responds immediately
    background_tasks.add_task(runner.investigate, alert)

    return {
        "status": "accepted",
        "alert_id": request.alert_id,
        "message": "Investigation started. Use GET /investigations to track progress.",
    }


@router.post("/investigations/sync")
async def trigger_investigation_sync(
    request: TriggerInvestigationRequest,
) -> dict:
    """Trigger an investigation and wait for completion.

    Useful for testing and CLI tools. For production use, prefer the
    async POST /investigations endpoint.
    """
    alert = AlertContext(
        alert_id=request.alert_id,
        alert_name=request.alert_name,
        severity=request.severity,
        source=request.source,
        resource_id=request.resource_id,
        labels=request.labels,
        annotations=request.annotations,
        triggered_at=datetime.now(timezone.utc),
        description=request.description,
    )

    runner = get_runner()
    result = await runner.investigate(alert)
    return result.model_dump(mode="json")


@router.get("/investigations")
async def list_investigations(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List active and recent investigations."""
    runner = get_runner()
    all_investigations = runner.list_investigations()

    # Filter by status if provided
    if status:
        all_investigations = [
            inv for inv in all_investigations if inv["status"] == status
        ]

    total = len(all_investigations)
    paginated = all_investigations[offset : offset + limit]

    return {
        "investigations": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/investigations/{investigation_id}")
async def get_investigation(investigation_id: str) -> dict:
    """Get full investigation detail including reasoning chain and evidence."""
    runner = get_runner()
    result = runner.get_investigation(investigation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return result.model_dump(mode="json")
