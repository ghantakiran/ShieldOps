"""Pipeline API endpoints.

Provides REST endpoints for triggering, tracking, and approving
investigation-to-remediation pipeline runs.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from shieldops.pipeline.models import PipelineRun, PipelineStatus
from shieldops.pipeline.orchestrator import PipelineOrchestrator

router = APIRouter()

# Application-level orchestrator instance.
_orchestrator: PipelineOrchestrator | None = None


def get_orchestrator() -> PipelineOrchestrator:
    """Get or create the pipeline orchestrator singleton."""
    global _orchestrator  # noqa: PLW0603
    if _orchestrator is None:
        _orchestrator = PipelineOrchestrator()
    return _orchestrator


def set_orchestrator(orch: PipelineOrchestrator) -> None:
    """Override the orchestrator (used in tests / DI)."""
    global _orchestrator  # noqa: PLW0603
    _orchestrator = orch


# ------------------------------------------------------------------
# Request / Response schemas
# ------------------------------------------------------------------


class StartPipelineRequest(BaseModel):
    """Request body to trigger a new pipeline run."""

    alert_name: str
    namespace: str
    service: str


class ApproveRequest(BaseModel):
    """Request body to approve pending recommendations."""

    indices: list[int] | None = Field(
        default=None,
        description=(
            "Indices of recommendations to approve. "
            "If omitted, all pending recommendations are approved."
        ),
    )


class PipelineRunResponse(BaseModel):
    """Serialised pipeline run returned by the API."""

    id: str
    alert_name: str
    namespace: str
    service: str | None = None
    status: PipelineStatus
    investigation_result: dict[str, Any] = Field(
        default_factory=dict,
    )
    remediation_actions: list[dict[str, Any]] = Field(
        default_factory=list,
    )
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str
    completed_at: str | None = None


def _run_to_response(run: PipelineRun) -> PipelineRunResponse:
    """Convert an internal PipelineRun to the API response model."""
    return PipelineRunResponse(
        id=run.id,
        alert_name=run.alert_name,
        namespace=run.namespace,
        service=run.service,
        status=run.status,
        investigation_result=run.investigation_result,
        remediation_actions=[r.model_dump(mode="json") for r in run.remediation_actions],
        timeline=[t.model_dump(mode="json") for t in run.timeline],
        created_at=run.created_at.isoformat(),
        completed_at=(run.completed_at.isoformat() if run.completed_at else None),
    )


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------


@router.post(
    "/api/v1/pipeline/run",
    response_model=PipelineRunResponse,
    status_code=201,
)
async def start_pipeline(
    body: StartPipelineRequest,
) -> PipelineRunResponse:
    """Start a new investigation-to-remediation pipeline run."""
    orch = get_orchestrator()
    run = await orch.run_pipeline(
        alert_name=body.alert_name,
        namespace=body.namespace,
        service=body.service,
    )
    return _run_to_response(run)


@router.get(
    "/api/v1/pipeline/runs/{run_id}",
    response_model=PipelineRunResponse,
)
async def get_pipeline_run(run_id: str) -> PipelineRunResponse:
    """Get the status of a pipeline run by ID."""
    orch = get_orchestrator()
    run = orch.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline run {run_id} not found",
        )
    return _run_to_response(run)


@router.post(
    "/api/v1/pipeline/runs/{run_id}/approve",
    response_model=PipelineRunResponse,
)
async def approve_recommendations(
    run_id: str,
    body: ApproveRequest | None = None,
) -> PipelineRunResponse:
    """Approve pending recommendations for a pipeline run."""
    orch = get_orchestrator()
    try:
        indices = body.indices if body else None
        run = await orch.approve_recommendations(
            run_id=run_id,
            indices=indices,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _run_to_response(run)


@router.get(
    "/api/v1/pipeline/runs",
    response_model=list[PipelineRunResponse],
)
async def list_pipeline_runs(
    limit: int = 50,
) -> list[PipelineRunResponse]:
    """List recent pipeline runs, newest first."""
    orch = get_orchestrator()
    runs = orch.list_runs(limit=limit)
    return [_run_to_response(r) for r in runs]
