"""Cost analysis API endpoints.

Provides REST endpoints for triggering cost analyses, viewing anomalies,
browsing optimization recommendations, and checking savings.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.agents.cost.runner import CostRunner
from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.models.base import Environment

router = APIRouter()

# Application-level runner instance
_runner: CostRunner | None = None


def get_runner() -> CostRunner:
    """Get or create the cost runner singleton."""
    global _runner
    if _runner is None:
        _runner = CostRunner()
    return _runner


def set_runner(runner: CostRunner) -> None:
    """Override the runner instance (used for testing and dependency injection)."""
    global _runner
    _runner = runner


# --- Request models ---


class TriggerAnalysisRequest(BaseModel):
    """Request body to trigger a cost analysis."""

    environment: str = "production"
    analysis_type: str = "full"  # full, anomaly_only, optimization_only, savings_only
    target_services: list[str] = Field(default_factory=list)
    period: str = "30d"


# --- Endpoints ---


@router.post("/cost/analyses", status_code=202)
async def trigger_analysis(
    request: TriggerAnalysisRequest,
    background_tasks: BackgroundTasks,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict:
    """Trigger a new cost analysis. Runs asynchronously."""
    runner = get_runner()

    try:
        env = Environment(request.environment)
    except ValueError:
        env = Environment.PRODUCTION

    background_tasks.add_task(
        runner.analyze,
        environment=env,
        analysis_type=request.analysis_type,
        target_services=request.target_services or None,
        period=request.period,
    )

    return {
        "status": "accepted",
        "analysis_type": request.analysis_type,
        "environment": request.environment,
        "message": "Cost analysis started. Use GET /cost/analyses to track progress.",
    }


@router.post("/cost/analyses/sync")
async def trigger_analysis_sync(
    request: TriggerAnalysisRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict:
    """Trigger a cost analysis and wait for completion."""
    runner = get_runner()

    try:
        env = Environment(request.environment)
    except ValueError:
        env = Environment.PRODUCTION

    result = await runner.analyze(
        environment=env,
        analysis_type=request.analysis_type,
        target_services=request.target_services or None,
        period=request.period,
    )
    return result.model_dump(mode="json")


@router.get("/cost/analyses")
async def list_analyses(
    analysis_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _user: UserResponse = Depends(get_current_user),
) -> dict:
    """List all cost analyses."""
    runner = get_runner()
    all_analyses = runner.list_analyses()

    if analysis_type:
        all_analyses = [a for a in all_analyses if a["analysis_type"] == analysis_type]

    total = len(all_analyses)
    paginated = all_analyses[offset : offset + limit]

    return {"analyses": paginated, "total": total, "limit": limit, "offset": offset}


@router.get("/cost/analyses/{analysis_id}")
async def get_analysis(
    analysis_id: str, _user: UserResponse = Depends(get_current_user)
) -> dict:
    """Get full cost analysis detail."""
    runner = get_runner()
    result = runner.get_analysis(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result.model_dump(mode="json")


@router.get("/cost/anomalies")
async def list_anomalies(
    severity: str | None = None,
    limit: int = 50,
    _user: UserResponse = Depends(get_current_user),
) -> dict:
    """List cost anomalies from the most recent analysis."""
    runner = get_runner()
    analyses = runner.list_analyses()

    completed = [a for a in analyses if a["status"] == "complete"]
    if not completed:
        return {"anomalies": [], "total": 0}

    state = runner.get_analysis(completed[-1]["analysis_id"])
    if state is None:
        return {"anomalies": [], "total": 0}

    anomalies = state.cost_anomalies
    if severity:
        anomalies = [a for a in anomalies if a.severity == severity]

    total = len(anomalies)
    return {
        "anomalies": [a.model_dump(mode="json") for a in anomalies[:limit]],
        "total": total,
    }


@router.get("/cost/optimizations")
async def list_optimizations(
    category: str | None = None,
    limit: int = 50,
    _user: UserResponse = Depends(get_current_user),
) -> dict:
    """List optimization recommendations from the most recent analysis."""
    runner = get_runner()
    analyses = runner.list_analyses()

    completed = [a for a in analyses if a["status"] == "complete"]
    if not completed:
        return {"optimizations": [], "total": 0, "total_potential_savings": 0}

    state = runner.get_analysis(completed[-1]["analysis_id"])
    if state is None:
        return {"optimizations": [], "total": 0, "total_potential_savings": 0}

    recs = state.optimization_recommendations
    if category:
        recs = [r for r in recs if r.category == category]

    total = len(recs)
    return {
        "optimizations": [r.model_dump(mode="json") for r in recs[:limit]],
        "total": total,
        "total_potential_savings": state.total_potential_savings,
    }


@router.get("/cost/savings")
async def get_savings_summary(_user: UserResponse = Depends(get_current_user)) -> dict:
    """Get cost savings summary from the most recent analysis."""
    runner = get_runner()
    analyses = runner.list_analyses()

    completed = [a for a in analyses if a["status"] == "complete"]
    if not completed:
        return {
            "period": "30d",
            "total_monthly_spend": 0,
            "total_potential_savings": 0,
            "hours_saved_by_automation": 0,
            "automation_savings_usd": 0,
            "message": "No completed analyses. Trigger an analysis first.",
        }

    state = runner.get_analysis(completed[-1]["analysis_id"])
    if state and state.cost_savings:
        return state.cost_savings.model_dump(mode="json")

    return {
        "period": "30d",
        "total_monthly_spend": completed[-1].get("monthly_spend", 0),
        "total_potential_savings": completed[-1].get("potential_savings", 0),
    }
