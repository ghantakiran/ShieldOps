"""SLO advisor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/slo-advisor", tags=["SLO Advisor"])

_advisor: Any = None


def set_advisor(advisor: Any) -> None:
    global _advisor
    _advisor = advisor


def _get_advisor() -> Any:
    if _advisor is None:
        raise HTTPException(503, "SLO advisor service unavailable")
    return _advisor


class RecordSampleRequest(BaseModel):
    service: str
    metric_type: str = "AVAILABILITY"
    value: float = 0.0
    unit: str = ""


class CompareRequest(BaseModel):
    proposed_targets: dict[str, float]


@router.post("/samples")
async def record_sample(
    body: RecordSampleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    sample = advisor.record_sample(**body.model_dump())
    return sample.model_dump()


@router.get("/samples")
async def list_samples(
    service: str | None = None,
    metric_type: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    advisor = _get_advisor()
    return [
        s.model_dump()
        for s in advisor.list_samples(service=service, metric_type=metric_type, limit=limit)
    ]


@router.get("/samples/{sample_id}")
async def get_sample(
    sample_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    sample = advisor.get_sample(sample_id)
    if sample is None:
        raise HTTPException(404, f"Sample '{sample_id}' not found")
    return sample.model_dump()


@router.get("/recommend/{service}/{metric_type}")
async def recommend_target(
    service: str,
    metric_type: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    recommendation = advisor.recommend_target(service=service, metric_type=metric_type)
    if recommendation is None:
        raise HTTPException(404, f"No recommendation for '{service}/{metric_type}'")
    return recommendation.model_dump()


@router.get("/recommend/{service}")
async def recommend_all_targets(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    advisor = _get_advisor()
    return [r.model_dump() for r in advisor.recommend_all_targets(service=service)]


@router.get("/budget-policy/{service}")
async def suggest_budget_policy(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    return advisor.suggest_budget_policy(service=service)


@router.get("/historical/{service}")
async def analyze_historical_performance(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    return advisor.analyze_historical_performance(service=service)


@router.post("/compare/{service}")
async def compare_targets(
    service: str,
    body: CompareRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    return advisor.compare_targets(service=service, proposed_targets=body.proposed_targets)


@router.get("/advisor-report")
async def generate_advisor_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    return advisor.generate_advisor_report()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    return advisor.get_stats()
