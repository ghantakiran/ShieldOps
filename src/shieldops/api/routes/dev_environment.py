"""Developer environment health monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.dev_environment import (
    EnvironmentType,
    HealthIssueType,
    IssueImpact,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/dev-environment",
    tags=["Dev Environment"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Dev environment service unavailable")
    return _engine


class RecordIssueRequest(BaseModel):
    developer: str
    env_type: EnvironmentType = EnvironmentType.LOCAL
    issue_type: HealthIssueType = HealthIssueType.DEPENDENCY_CONFLICT
    impact: IssueImpact = IssueImpact.MINOR
    tool_name: str = ""
    expected_version: str = ""
    actual_version: str = ""
    details: str = ""


class SetBaselineRequest(BaseModel):
    env_type: EnvironmentType = EnvironmentType.LOCAL
    tool_name: str = ""
    required_version: str = ""
    max_drift_days: int = 14
    details: str = ""


@router.post("/issues")
async def record_issue(
    body: RecordIssueRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_issue(**body.model_dump())
    return result.model_dump()


@router.get("/issues")
async def list_issues(
    developer: str | None = None,
    issue_type: HealthIssueType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_issues(developer=developer, issue_type=issue_type, limit=limit)
    ]


@router.get("/issues/{record_id}")
async def get_issue(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_issue(record_id)
    if result is None:
        raise HTTPException(404, f"Issue record '{record_id}' not found")
    return result.model_dump()


@router.post("/baselines")
async def set_baseline(
    body: SetBaselineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.set_baseline(**body.model_dump())
    return result.model_dump()


@router.get("/version-drift")
async def detect_version_drift(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_version_drift()


@router.get("/blocking-issues")
async def identify_blocking_issues(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_blocking_issues()


@router.get("/affected-developers")
async def rank_most_affected_developers(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_most_affected_developers()


@router.get("/baseline-comparison")
async def compare_to_baseline(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.compare_to_baseline()


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    return engine.clear_data()


deh_route = router
