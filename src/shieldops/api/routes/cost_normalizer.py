"""Multi-cloud cost normalization API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/cost-normalizer", tags=["Cost Normalizer"])

_normalizer: Any = None


def set_normalizer(normalizer: Any) -> None:
    global _normalizer
    _normalizer = normalizer


def _get_normalizer() -> Any:
    if _normalizer is None:
        raise HTTPException(503, "Cost normalizer service unavailable")
    return _normalizer


class AddPricingRequest(BaseModel):
    provider: str
    category: str
    resource_type: str
    price_per_unit: float
    unit: str = "hour"
    region: str = "us-east-1"
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompareRequest(BaseModel):
    resource_type: str
    category: str


class AnalyzeWorkloadRequest(BaseModel):
    workload_name: str
    resources: list[dict[str, Any]]


class UpdatePricingRequest(BaseModel):
    price_per_unit: float


@router.post("/pricing")
async def add_pricing(
    body: AddPricingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    normalizer = _get_normalizer()
    entry = normalizer.add_pricing(**body.model_dump())
    return entry.model_dump()


@router.get("/pricing")
async def get_pricing(
    provider: str | None = None,
    category: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    normalizer = _get_normalizer()
    return [e.model_dump() for e in normalizer.get_pricing(provider=provider, category=category)]


@router.put("/pricing/{pricing_id}")
async def update_pricing(
    pricing_id: str,
    body: UpdatePricingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    normalizer = _get_normalizer()
    entry = normalizer.update_pricing(pricing_id, body.price_per_unit)
    if entry is None:
        raise HTTPException(404, f"Pricing '{pricing_id}' not found")
    return entry.model_dump()


@router.delete("/pricing/{pricing_id}")
async def delete_pricing(
    pricing_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    normalizer = _get_normalizer()
    if not normalizer.delete_pricing(pricing_id):
        raise HTTPException(404, f"Pricing '{pricing_id}' not found")
    return {"status": "deleted"}


@router.post("/compare")
async def compare_resource(
    body: CompareRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    normalizer = _get_normalizer()
    result = normalizer.compare_resource(**body.model_dump())
    return result.model_dump()


@router.post("/analyze")
async def analyze_workload(
    body: AnalyzeWorkloadRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    normalizer = _get_normalizer()
    result = normalizer.analyze_workload(**body.model_dump())
    return result.model_dump()


@router.get("/cheapest/{category}")
async def get_cheapest_provider(
    category: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    normalizer = _get_normalizer()
    return normalizer.get_cheapest_provider(category)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    normalizer = _get_normalizer()
    return normalizer.get_stats()
