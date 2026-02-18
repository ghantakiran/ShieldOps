"""Supervisor agent API endpoints.

Provides REST endpoints for submitting events to the supervisor,
viewing orchestration sessions, and checking delegation history.
"""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.agents.supervisor.runner import SupervisorRunner
from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

router = APIRouter()

# Application-level runner instance
_runner: SupervisorRunner | None = None


def get_runner() -> SupervisorRunner:
    """Get or create the supervisor runner singleton."""
    global _runner
    if _runner is None:
        _runner = SupervisorRunner()
    return _runner


def set_runner(runner: SupervisorRunner) -> None:
    """Override the runner instance (used for testing and dependency injection)."""
    global _runner
    _runner = runner


# --- Request models ---


class SubmitEventRequest(BaseModel):
    """Request body to submit an event to the supervisor."""

    type: str  # alert, incident, cve_alert, remediation_request, etc.
    severity: str = "medium"
    source: str = "manual"
    resource_id: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Endpoints ---


@router.post("/supervisor/events", status_code=202)
async def submit_event(
    request: SubmitEventRequest,
    background_tasks: BackgroundTasks,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict:
    """Submit an event for supervisor orchestration. Runs asynchronously."""
    runner = get_runner()

    event = request.model_dump()
    background_tasks.add_task(runner.handle_event, event=event)

    return {
        "status": "accepted",
        "event_type": request.type,
        "severity": request.severity,
        "message": "Event submitted. Use GET /supervisor/sessions to track progress.",
    }


@router.post("/supervisor/events/sync")
async def submit_event_sync(
    request: SubmitEventRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict:
    """Submit an event and wait for supervisor orchestration to complete."""
    runner = get_runner()

    event = request.model_dump()
    result = await runner.handle_event(event=event)
    return result.model_dump(mode="json")


@router.get("/supervisor/sessions")
async def list_sessions(
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _user: UserResponse = Depends(get_current_user),
) -> dict:
    """List all supervisor sessions."""
    runner = get_runner()
    all_sessions = runner.list_sessions()

    if event_type:
        all_sessions = [s for s in all_sessions if s["event_type"] == event_type]

    total = len(all_sessions)
    paginated = all_sessions[offset : offset + limit]

    return {"sessions": paginated, "total": total, "limit": limit, "offset": offset}


@router.get("/supervisor/sessions/{session_id}")
async def get_session(session_id: str, _user: UserResponse = Depends(get_current_user)) -> dict:
    """Get full supervisor session detail."""
    runner = get_runner()
    result = runner.get_session(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return result.model_dump(mode="json")


@router.get("/supervisor/sessions/{session_id}/tasks")
async def get_session_tasks(
    session_id: str, _user: UserResponse = Depends(get_current_user)
) -> dict:
    """Get all delegated tasks for a session."""
    runner = get_runner()
    result = runner.get_session(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "tasks": [t.model_dump(mode="json") for t in result.delegated_tasks],
        "total": len(result.delegated_tasks),
    }


@router.get("/supervisor/sessions/{session_id}/escalations")
async def get_session_escalations(
    session_id: str, _user: UserResponse = Depends(get_current_user)
) -> dict:
    """Get all escalations for a session."""
    runner = get_runner()
    result = runner.get_session(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "escalations": [e.model_dump(mode="json") for e in result.escalations],
        "total": len(result.escalations),
    }
