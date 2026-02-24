"""Service Maturity Model API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.service_maturity import (
    AssessmentStatus,
    MaturityDimension,
    MaturityLevel,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/service-maturity",
    tags=["Service Maturity Model"],
)

_instance: Any = None


def set_model(model: Any) -> None:
    global _instance
    _instance = model


def _get_model() -> Any:
    if _instance is None:
        raise HTTPException(503, "Service maturity service unavailable")
    return _instance


class CreateAssessmentRequest(BaseModel):
    service_name: str = ""
    dimension: MaturityDimension = MaturityDimension.OBSERVABILITY
    level: MaturityLevel = MaturityLevel.INITIAL
    score: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    assessor: str = ""
    status: AssessmentStatus = AssessmentStatus.DRAFT


@router.post("/assessments")
async def create_assessment(
    body: CreateAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    model = _get_model()
    assessment = model.create_assessment(**body.model_dump())
    return assessment.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    model = _get_model()
    return model.get_stats()


@router.get("/report")
async def get_maturity_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    model = _get_model()
    return model.generate_maturity_report().model_dump()


@router.get("/rankings")
async def get_rankings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    model = _get_model()
    return model.rank_services_by_maturity()


@router.get("/score/{service_name}")
async def get_maturity_score(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    model = _get_model()
    return model.calculate_maturity_score(service_name).model_dump()


@router.get("/gaps/{service_name}")
async def get_maturity_gaps(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    model = _get_model()
    return model.identify_maturity_gaps(service_name)


@router.get("/trend/{service_name}")
async def get_maturity_trend(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    model = _get_model()
    return model.track_maturity_trend(service_name)


@router.get("/plan/{service_name}")
async def get_improvement_plan(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    model = _get_model()
    return model.generate_improvement_plan(service_name)


@router.get("/assessments")
async def list_assessments(
    service_name: str | None = None,
    dimension: MaturityDimension | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    model = _get_model()
    return [
        a.model_dump()
        for a in model.list_assessments(
            service_name=service_name,
            dimension=dimension,
            limit=limit,
        )
    ]


@router.get("/assessments/{assessment_id}")
async def get_assessment(
    assessment_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    model = _get_model()
    assessment = model.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(
            404,
            f"Assessment '{assessment_id}' not found",
        )
    return assessment.model_dump()
