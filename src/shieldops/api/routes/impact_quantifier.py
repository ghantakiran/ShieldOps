"""Impact quantifier API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
iq_route = APIRouter(
    prefix="/impact-quantifier",
    tags=["Impact Quantifier"],
)

_instance: Any = None


def set_engine(engine: Any) -> None:
    global _instance
    _instance = engine


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Impact quantifier service unavailable",
        )
    return _instance


# -- Request models --


class CreateAssessmentRequest(BaseModel):
    incident_id: str
    service_name: str = ""
    duration_minutes: float = 0.0
    affected_customers: int = 0
    total_cost_usd: float = 0.0
    sla_credit_usd: float = 0.0
    primary_dimension: str = "revenue_loss"
    method: str = "estimation"
    severity: str = "medium"


class AddBreakdownRequest(BaseModel):
    assessment_id: str
    category: str = "infrastructure"
    amount_usd: float = 0.0
    description: str = ""
    method: str = "estimation"


class EstimateSlaRequest(BaseModel):
    assessment_id: str
    sla_target_pct: float = 99.9
    monthly_contract_usd: float = 10000.0


class EstimateCustomerRequest(BaseModel):
    assessment_id: str
    total_customers: int = 10000


class CompareRequest(BaseModel):
    assessment_ids: list[str]


# -- Routes --


@iq_route.post("/assessments")
async def create_assessment(
    body: CreateAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    assessment = engine.create_assessment(**body.model_dump())
    return assessment.model_dump()


@iq_route.get("/assessments")
async def list_assessments(
    service_name: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        a.model_dump()
        for a in engine.list_assessments(
            service_name=service_name,
            severity=severity,
            limit=limit,
        )
    ]


@iq_route.get("/assessments/{assessment_id}")
async def get_assessment(
    assessment_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    assessment = engine.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(404, f"Assessment '{assessment_id}' not found")
    return assessment.model_dump()


@iq_route.post("/breakdowns")
async def add_breakdown(
    body: AddBreakdownRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    breakdown = engine.add_cost_breakdown(**body.model_dump())
    if breakdown is None:
        raise HTTPException(
            404,
            f"Assessment '{body.assessment_id}' not found",
        )
    return breakdown.model_dump()


@iq_route.get("/total-impact/{assessment_id}")
async def calculate_total_impact(
    assessment_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_total_impact(assessment_id)


@iq_route.post("/estimate-sla")
async def estimate_sla_credit(
    body: EstimateSlaRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.estimate_sla_credit(**body.model_dump())


@iq_route.post("/estimate-customer")
async def estimate_customer_impact(
    body: EstimateCustomerRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.estimate_customer_impact(**body.model_dump())


@iq_route.post("/compare")
async def compare_incidents(
    body: CompareRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.compare_incidents(body.assessment_ids)


@iq_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_impact_report().model_dump()


@iq_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
