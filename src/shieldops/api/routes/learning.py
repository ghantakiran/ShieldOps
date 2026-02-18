"""Learning agent API endpoints.

Provides REST endpoints for triggering learning cycles, viewing patterns,
browsing playbook updates, and checking threshold recommendations.
"""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from shieldops.agents.learning.runner import LearningRunner
from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

router = APIRouter()

# Application-level runner instance
_runner: LearningRunner | None = None


def get_runner() -> LearningRunner:
    """Get or create the learning runner singleton."""
    global _runner
    if _runner is None:
        _runner = LearningRunner()
    return _runner


def set_runner(runner: LearningRunner) -> None:
    """Override the runner instance (used for testing and dependency injection)."""
    global _runner
    _runner = runner


# --- Request models ---


class TriggerLearningRequest(BaseModel):
    """Request body to trigger a learning cycle."""

    learning_type: str = "full"  # full, pattern_only, playbook_only, threshold_only
    period: str = "30d"


# --- Endpoints ---


@router.post("/learning/cycles", status_code=202)
async def trigger_learning_cycle(
    request: TriggerLearningRequest,
    background_tasks: BackgroundTasks,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Trigger a new learning cycle. Runs asynchronously."""
    runner = get_runner()

    background_tasks.add_task(
        runner.learn,
        learning_type=request.learning_type,
        period=request.period,
    )

    return {
        "status": "accepted",
        "learning_type": request.learning_type,
        "period": request.period,
        "message": "Learning cycle started. Use GET /learning/cycles to track progress.",
    }


@router.post("/learning/cycles/sync")
async def trigger_learning_cycle_sync(
    request: TriggerLearningRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Trigger a learning cycle and wait for completion."""
    runner = get_runner()

    result = await runner.learn(
        learning_type=request.learning_type,
        period=request.period,
    )
    return result.model_dump(mode="json")


@router.get("/learning/cycles")
async def list_cycles(
    learning_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all learning cycles."""
    runner = get_runner()
    all_cycles = runner.list_cycles()

    if learning_type:
        all_cycles = [c for c in all_cycles if c["learning_type"] == learning_type]

    total = len(all_cycles)
    paginated = all_cycles[offset : offset + limit]

    return {"cycles": paginated, "total": total, "limit": limit, "offset": offset}


@router.get("/learning/cycles/{learning_id}")
async def get_cycle(
    learning_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get full learning cycle detail."""
    runner = get_runner()
    result = runner.get_cycle(learning_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Learning cycle not found")
    return result.model_dump(mode="json")


@router.get("/learning/patterns")
async def list_patterns(
    alert_type: str | None = None,
    limit: int = 50,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List pattern insights from the most recent learning cycle."""
    runner = get_runner()
    cycles = runner.list_cycles()

    completed = [c for c in cycles if c["status"] == "complete"]
    if not completed:
        return {"patterns": [], "total": 0}

    state = runner.get_cycle(completed[-1]["learning_id"])
    if state is None:
        return {"patterns": [], "total": 0}

    patterns = state.pattern_insights
    if alert_type:
        patterns = [p for p in patterns if p.alert_type == alert_type]

    total = len(patterns)
    return {
        "patterns": [p.model_dump(mode="json") for p in patterns[:limit]],
        "total": total,
    }


@router.get("/learning/playbook-updates")
async def list_playbook_updates(
    update_type: str | None = None,
    limit: int = 50,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List playbook update recommendations from the most recent learning cycle."""
    runner = get_runner()
    cycles = runner.list_cycles()

    completed = [c for c in cycles if c["status"] == "complete"]
    if not completed:
        return {"playbook_updates": [], "total": 0}

    state = runner.get_cycle(completed[-1]["learning_id"])
    if state is None:
        return {"playbook_updates": [], "total": 0}

    updates = state.playbook_updates
    if update_type:
        updates = [u for u in updates if u.update_type == update_type]

    total = len(updates)
    return {
        "playbook_updates": [u.model_dump(mode="json") for u in updates[:limit]],
        "total": total,
    }


@router.get("/learning/threshold-adjustments")
async def list_threshold_adjustments(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List threshold adjustment recommendations from the most recent learning cycle."""
    runner = get_runner()
    cycles = runner.list_cycles()

    completed = [c for c in cycles if c["status"] == "complete"]
    if not completed:
        return {"threshold_adjustments": [], "total": 0, "estimated_fp_reduction": 0}

    state = runner.get_cycle(completed[-1]["learning_id"])
    if state is None:
        return {"threshold_adjustments": [], "total": 0, "estimated_fp_reduction": 0}

    return {
        "threshold_adjustments": [a.model_dump(mode="json") for a in state.threshold_adjustments],
        "total": len(state.threshold_adjustments),
        "estimated_fp_reduction": state.estimated_false_positive_reduction,
    }
