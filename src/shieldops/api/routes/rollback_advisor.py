"""Deployment Rollback Advisor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.rollback_advisor import (
    RollbackDecision,
    RollbackStrategy,
)

logger = structlog.get_logger()
ra_route = APIRouter(
    prefix="/rollback-advisor",
    tags=["Rollback Advisor"],
)

_advisor: Any = None


def set_advisor(advisor: Any) -> None:
    global _advisor
    _advisor = advisor


def _get_advisor() -> Any:
    if _advisor is None:
        raise HTTPException(503, "Rollback advisor unavailable")
    return _advisor


class CreateAssessmentRequest(BaseModel):
    deployment_id: str
    service_name: str
    signals: list[str] = Field(default_factory=list)
    blast_radius_pct: float = 0.0


class ExecuteRollbackRequest(BaseModel):
    strategy: RollbackStrategy
    executed_by: str


@ra_route.post("/assessments")
async def create_assessment(
    body: CreateAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    assessment = advisor.create_assessment(**body.model_dump())
    return assessment.model_dump()  # type: ignore[no-any-return]


@ra_route.get("/assessments")
async def list_assessments(
    service_name: str | None = None,
    decision: RollbackDecision | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    advisor = _get_advisor()
    return [  # type: ignore[no-any-return]
        a.model_dump()
        for a in advisor.list_assessments(
            service_name=service_name,
            decision=decision,
            limit=limit,
        )
    ]


@ra_route.get("/assessments/{assessment_id}")
async def get_assessment(
    assessment_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    assessment = advisor.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(
            404,
            f"Assessment '{assessment_id}' not found",
        )
    return assessment.model_dump()  # type: ignore[no-any-return]


@ra_route.post("/assessments/{assessment_id}/evaluate")
async def evaluate_rollback(
    assessment_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    assessment = advisor.evaluate_rollback_need(
        assessment_id,
    )
    if assessment is None:
        raise HTTPException(
            404,
            f"Assessment '{assessment_id}' not found",
        )
    return assessment.model_dump()  # type: ignore[no-any-return]


@ra_route.post("/assessments/{assessment_id}/execute")
async def execute_rollback(
    assessment_id: str,
    body: ExecuteRollbackRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    action = advisor.execute_rollback(
        assessment_id,
        body.strategy,
        body.executed_by,
    )
    if action is None:
        raise HTTPException(
            404,
            f"Assessment '{assessment_id}' not found",
        )
    return action.model_dump()  # type: ignore[no-any-return]


@ra_route.get("/success-rate")
async def get_success_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    return {  # type: ignore[no-any-return]
        "success_rate_pct": (advisor.calculate_rollback_success_rate()),
    }


@ra_route.get("/patterns")
async def get_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    advisor = _get_advisor()
    return advisor.identify_rollback_patterns()  # type: ignore[no-any-return]


@ra_route.get("/estimate/{service_name}")
async def estimate_time(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    return advisor.estimate_rollback_time(service_name)  # type: ignore[no-any-return]


@ra_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    return advisor.generate_rollback_report().model_dump()  # type: ignore[no-any-return]


@ra_route.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    advisor = _get_advisor()
    advisor.clear_data()
    return {"status": "cleared"}


@ra_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    return advisor.get_stats()  # type: ignore[no-any-return]
